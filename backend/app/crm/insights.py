"""Attribution for the owner: which posts and channels turned into sales, and how the agent is doing.

Deals are measured as a cohort: everything opened in the last N days, followed to its current stage.
A lead is a contact first seen in the period; per-post leads use the same definition. All aggregation
happens in SQL, so the numbers hold at any volume.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Actor,
    AgentRun,
    AgentRunStatus,
    Business,
    Contact,
    Deal,
    DealStage,
    DealStageChange,
    Engagement,
    Post,
    Product,
)
from app.schemas import ChannelPerformance, FunnelStep, InsightsOut, PostBrief, PostPerformance

_FUNNEL = (DealStage.NEW, DealStage.ENGAGED, DealStage.QUALIFIED, DealStage.PAYMENT_SENT, DealStage.WON)
TOP_POSTS = 20


def _rank(column: Any) -> Any:
    """Funnel position of a stage; lost (and anything else) is -1."""
    return case({stage.value: rank for rank, stage in enumerate(_FUNNEL)}, value=column, else_=-1)


async def insights(session: AsyncSession, business: Business, days: int) -> InsightsOut:
    since = datetime.now(UTC) - timedelta(days=days)
    cohort = select(Deal.id).where(Deal.business_id == business.id, Deal.created_at >= since)
    is_won = Deal.stage == DealStage.WON
    deals, won, revenue = (
        await session.execute(
            select(
                func.count(Deal.id),
                func.count(Deal.id).filter(is_won),
                func.coalesce(func.sum(Deal.amount_minor).filter(is_won), 0),
            ).where(Deal.id.in_(cohort))
        )
    ).one()
    leads = await session.scalar(
        select(func.count(Contact.id)).where(Contact.business_id == business.id, Contact.created_at >= since)
    )
    replies, handoffs, median = await _agent_stats(session, business, since)
    return InsightsOut(
        currency=business.currency,
        days=days,
        leads=leads or 0,
        deals=deals,
        won=won,
        revenue_minor=revenue or 0,
        conversion_rate=won / deals if deals else None,
        agent_replies=replies,
        median_agent_reply_seconds=round(median, 2) if median is not None else None,
        handoffs=handoffs,
        funnel=await _funnel(session, cohort),
        by_post=await _by_post(session, business, cohort, since),
        by_channel=await _by_channel(session, cohort),
    )


async def _agent_stats(
    session: AsyncSession, business: Business, since: datetime
) -> tuple[int, int, float | None]:
    replied = AgentRun.reply_text.is_not(None)
    handed_off = or_(  # handed over by the model, or after a model error (holding message + pause)
        AgentRun.status == AgentRunStatus.HANDED_OFF, and_(AgentRun.status == AgentRunStatus.FAILED, replied)
    )
    seconds = func.extract("epoch", AgentRun.finished_at - AgentRun.started_at)
    replies, handoffs, median = (
        await session.execute(
            select(
                func.count(AgentRun.id).filter(replied),
                func.count(AgentRun.id).filter(handed_off),
                func.percentile_cont(0.5).within_group(seconds).filter(replied),
            ).where(AgentRun.business_id == business.id, AgentRun.started_at >= since)
        )
    ).one()
    return replies, handoffs, float(median) if median is not None else None


async def _funnel(session: AsyncSession, cohort: Select[Any]) -> list[FunnelStep]:
    """How far each deal got. The stage-change log counts, except the owner's manual moves (which may be
    corrections); a deal's current stage always counts, so a deal the owner marked won is won."""
    history = (
        select(DealStageChange.deal_id, func.max(_rank(DealStageChange.to_stage)).label("rank"))
        .where(DealStageChange.deal_id.in_(cohort), DealStageChange.actor != Actor.OWNER)
        .group_by(DealStageChange.deal_id)
        .subquery()
    )
    furthest = func.greatest(_rank(Deal.stage), func.coalesce(history.c.rank, -1))
    reached = {
        rank: count
        for rank, count in await session.execute(
            select(furthest, func.count(Deal.id))
            .outerjoin(history, history.c.deal_id == Deal.id)
            .where(Deal.id.in_(cohort))
            .group_by(furthest)
        )
    }
    return [
        FunnelStep(stage=stage, reached=sum(n for r, n in reached.items() if r >= rank))
        for rank, stage in enumerate(_FUNNEL)
    ]


async def _by_post(
    session: AsyncSession, business: Business, cohort: Select[Any], since: datetime
) -> list[PostPerformance]:
    is_won = Deal.stage == DealStage.WON
    deal_stats = (
        select(
            Deal.source_post_id.label("post_id"),
            func.count(Deal.id).label("deals"),
            func.count(Deal.id).filter(is_won).label("won"),
            func.coalesce(func.sum(Deal.amount_minor).filter(is_won), 0).label("revenue"),
        )
        .where(Deal.id.in_(cohort), Deal.source_post_id.is_not(None))
        .group_by(Deal.source_post_id)
        .subquery()
    )
    lead_stats = (  # new contacts in the period who engaged with the post: the headline "leads" definition
        select(
            Engagement.post_id.label("post_id"),
            func.count(func.distinct(Engagement.contact_id)).label("leads"),
        )
        .join(Contact, Contact.id == Engagement.contact_id)
        .where(
            Engagement.business_id == business.id,
            Contact.created_at >= since,
            Engagement.post_id.is_not(None),
        )
        .group_by(Engagement.post_id)
        .subquery()
    )
    leads, deals_n = func.coalesce(lead_stats.c.leads, 0), func.coalesce(deal_stats.c.deals, 0)
    won_n, revenue = func.coalesce(deal_stats.c.won, 0), func.coalesce(deal_stats.c.revenue, 0)
    rows = await session.execute(
        select(Post, Product.name, leads, deals_n, won_n, revenue)
        .outerjoin(Product, Product.id == Post.product_id)
        .outerjoin(deal_stats, deal_stats.c.post_id == Post.id)
        .outerjoin(lead_stats, lead_stats.c.post_id == Post.id)
        .where(
            Post.business_id == business.id,
            or_(deal_stats.c.post_id.is_not(None), lead_stats.c.post_id.is_not(None)),
        )
        .order_by(revenue.desc(), won_n.desc(), leads.desc(), Post.id.desc())
        .limit(TOP_POSTS)
    )
    return [
        PostPerformance(
            post=PostBrief.model_validate(post),
            product_name=name,
            leads=lead,
            deals=d,
            won=w,
            revenue_minor=r,
        )
        for post, name, lead, d, w, r in rows
    ]


async def _by_channel(session: AsyncSession, cohort: Select[Any]) -> list[ChannelPerformance]:
    is_won = Deal.stage == DealStage.WON
    rows = await session.execute(
        select(
            Deal.channel,
            func.count(Deal.id),
            func.count(Deal.id).filter(is_won),
            func.coalesce(func.sum(Deal.amount_minor).filter(is_won), 0),
        )
        .where(Deal.id.in_(cohort))
        .group_by(Deal.channel)
        .order_by(func.count(Deal.id).desc())
    )
    return [ChannelPerformance(channel=c, deals=d, won=w, revenue_minor=r or 0) for c, d, w, r in rows]
