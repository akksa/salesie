"""Public test-mode checkout pages for HostedTestCheckout links (no login: the unguessable token is the key).
No real money moves; the page says so. Paying wins the deal and sends the shopper a receipt by DM."""

import html
import logging
from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.agent.runner import AgentServices, notify_shopper
from app.api.deps import SessionDep
from app.models import Business, PaymentLink, PaymentStatus, Product
from app.payments.checkout import format_money, mark_paid

logger = logging.getLogger(__name__)
router = APIRouter(tags=["checkout"])
Token = Annotated[str, Path(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
EXPIRED = "This link has expired. Ask the shop for a new one."


@router.get("/pay/{token}", response_class=HTMLResponse, include_in_schema=False)
async def checkout_page(token: Token, session: SessionDep) -> HTMLResponse:
    view = await _view(session, token)
    if view is None:
        return _page("Link not found", "<p>This checkout link doesn't exist.</p>", status_code=404)
    link, product, business = view
    summary = _summary(link, product, business)
    if link.status == PaymentStatus.PAID:
        return _page("Paid", f"{summary}<p class=ok>Paid. Thank you!</p>")
    if link.status == PaymentStatus.EXPIRED:
        return _page("Link expired", f"{summary}<p>{EXPIRED}</p>", status_code=410)
    total = html.escape(format_money(link.amount_minor, link.currency))
    form = f"<form method=post><button type=submit>Pay {total}</button></form>"
    return _page(f"Checkout: {business.name}", summary + form)


@router.post("/pay/{token}", response_class=HTMLResponse, include_in_schema=False)
async def pay(token: Token, request: Request) -> HTMLResponse:
    sessionmaker = request.app.state.sessionmaker
    async with sessionmaker() as session, session.begin():  # the payment is committed on its own
        outcome = await mark_paid(session, token)
        if outcome is None:
            return _page("Link not found", "<p>This checkout link doesn't exist.</p>", status_code=404)
        if outcome.refused:
            view = await _view(session, token)
            summary = _summary(*view) if view else ""
            return _page("Link expired", f"{summary}<p>{html.escape(outcome.refused)}</p>", status_code=410)
        contact_id, newly_paid = outcome.deal.contact_id, outcome.newly_paid
        product = await session.get(Product, outcome.link.product_id)
        product_name = product.name if product else "order"
    if newly_paid:
        await _send_receipt(request, contact_id, product_name)
    async with sessionmaker() as session:
        view = await _view(session, token)
    if view is None:
        return _page("Link not found", "<p>This checkout link doesn't exist.</p>", status_code=404)
    return _page("Paid", f"{_summary(*view)}<p class=ok>Payment received. Thank you!</p>")


async def _send_receipt(request: Request, contact_id: int, product_name: str) -> None:
    agent: AgentServices = request.app.state.agent
    text = (
        f"Payment received, thank you! 🎉 Your {product_name} is confirmed. We'll be in touch about delivery."
    )
    if agent.payments.name == "test_checkout":
        text += " (Test checkout: no money was taken.)"
    try:
        async with request.app.state.sessionmaker() as session, session.begin():
            await notify_shopper(session, agent, contact_id, text)
    except Exception:  # the payment already stands; a missed receipt is logged, not fatal
        logger.exception("could not send payment receipt to contact %s", contact_id)


async def _view(session: SessionDep, token: str) -> tuple[PaymentLink, Product, Business] | None:
    row = (
        await session.execute(
            select(PaymentLink, Product, Business)
            .join(Product, Product.id == PaymentLink.product_id)
            .join(Business, Business.id == PaymentLink.business_id)
            .where(PaymentLink.token == token)
        )
    ).first()
    return None if row is None else (row[0], row[1], row[2])


def _summary(link: PaymentLink, product: Product, business: Business) -> str:
    quantity = f" x {link.quantity}" if link.quantity > 1 else ""
    return (
        f"<p class=shop>{html.escape(business.name)}</p>"
        f"<h1>{html.escape(product.name)}{quantity}</h1>"
        f"<p class=total>{html.escape(format_money(link.amount_minor, link.currency))}</p>"
    )


def _page(title: str, body: str, *, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f6f1ec;color:#1f1a17;display:grid;place-items:center;
min-height:100vh;margin:0;padding:16px}}
main{{background:#fff;border-radius:16px;padding:28px;max-width:380px;width:100%;
box-shadow:0 8px 30px #0001}}
.test{{background:#fff4d6;color:#7a5a00;border-radius:8px;padding:8px 12px;font-size:13px}}
.shop{{color:#8a7f78;margin:16px 0 0}} h1{{margin:4px 0}}
.total{{font-size:28px;font-weight:700;margin:8px 0 20px}}
button{{width:100%;padding:14px;border:0;border-radius:10px;background:#c2410c;color:#fff;font-size:16px;
font-weight:600;cursor:pointer}} .ok{{color:#15803d;font-weight:600}}
@media (prefers-color-scheme:dark){{body{{background:#1a1614;color:#f3ede8}}main{{background:#26201d}}}}
</style></head><body><main>
<p class=test>Test mode: no real payment is taken.</p>{body}
</main></body></html>""",
        status_code=status_code,
    )
