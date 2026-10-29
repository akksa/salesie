"""Payment links. HostedTestCheckout is Salesie's own test-mode checkout page, so the whole flow
(comment → DM → link → paid → deal won) works without a payment provider account. A real provider
(e.g. Stripe Payment Links) implements PaymentProvider and confirms payment via its own webhook."""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crm import deals
from app.crm.store import lock_contact
from app.models import (
    OPEN_STAGES,
    Actor,
    Business,
    Deal,
    DealStage,
    PaymentLink,
    PaymentStatus,
    Product,
    ProductStatus,
)

ZERO_DECIMAL_CURRENCIES = frozenset({"JPY", "KRW", "VND", "CLP", "ISK", "UGX", "XAF", "XOF"})
_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥", "AUD": "A$", "CAD": "C$"}


def format_money(amount_minor: int, currency: str) -> str:
    decimals = 0 if currency in ZERO_DECIMAL_CURRENCIES else 2
    amount = amount_minor / (10**decimals)
    number = f"{amount:,.{decimals}f}"
    symbol = _SYMBOLS.get(currency)
    return f"{symbol}{number}" if symbol else f"{number} {currency}"


class PaymentProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def create_link(
        self, session: AsyncSession, *, business: Business, deal: Deal, product: Product, quantity: int
    ) -> PaymentLink: ...


class HostedTestCheckout:
    name = "test_checkout"

    def __init__(self, public_base_url: str) -> None:
        self._base = public_base_url.rstrip("/")

    async def create_link(
        self, session: AsyncSession, *, business: Business, deal: Deal, product: Product, quantity: int
    ) -> PaymentLink:
        if product.price_minor is None:
            raise ValueError(f"product {product.id} has no price")
        await expire_open_links(session, deal.id)  # only the newest link for a deal can be paid
        token = secrets.token_urlsafe(24)
        link = PaymentLink(
            business_id=business.id,
            deal_id=deal.id,
            product_id=product.id,
            quantity=quantity,
            amount_minor=product.price_minor * quantity,
            currency=business.currency,
            token=token,
            provider=self.name,
            url=f"{self._base}/pay/{token}",
        )
        session.add(link)
        await session.flush()
        return link


async def expire_open_links(session: AsyncSession, deal_id: int) -> None:
    await session.execute(
        update(PaymentLink)
        .where(PaymentLink.deal_id == deal_id, PaymentLink.status == PaymentStatus.OPEN)
        .values(status=PaymentStatus.EXPIRED)
    )


@dataclass(frozen=True)
class PaymentOutcome:
    link: PaymentLink
    deal: Deal
    newly_paid: bool
    refused: str | None = None  # why this link can't be paid any more


async def mark_paid(session: AsyncSession, token: str) -> PaymentOutcome | None:
    """Record a payment and win the deal. Idempotent: paying an already-paid link changes nothing.
    Expired links, and links whose deal is no longer open, are refused."""
    deal_id = await session.scalar(select(PaymentLink.deal_id).where(PaymentLink.token == token))
    if deal_id is None:
        return None
    contact_id = await session.scalar(select(Deal.contact_id).where(Deal.id == deal_id))
    if contact_id is not None:
        await lock_contact(session, contact_id)  # before reading state, so the audit trail is accurate
    link = await session.scalar(select(PaymentLink).where(PaymentLink.token == token).with_for_update())
    deal = await session.get(Deal, deal_id, populate_existing=True)
    if link is None or deal is None:
        return None
    if link.status == PaymentStatus.PAID:
        return PaymentOutcome(link, deal, newly_paid=False)
    product = await session.get(Product, link.product_id)
    priced_now = product.price_minor * link.quantity if product and product.price_minor is not None else None
    unchanged = (
        product is not None and product.status == ProductStatus.ACTIVE and priced_now == link.amount_minor
    )
    if link.status == PaymentStatus.EXPIRED or deal.stage not in OPEN_STAGES or not unchanged:
        refused = "This link has expired. Ask the shop for a new one."
        return PaymentOutcome(link, deal, newly_paid=False, refused=refused)
    link.status = PaymentStatus.PAID
    link.paid_at = datetime.now(UTC)
    deal.amount_minor = link.amount_minor
    await deals.change_stage(
        session,
        deal,
        DealStage.WON,
        actor=Actor.SYSTEM,
        reason=f"paid {format_money(link.amount_minor, link.currency)} via {link.provider}",
    )
    return PaymentOutcome(link, deal, newly_paid=True)
