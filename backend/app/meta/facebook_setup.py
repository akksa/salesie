"""Connect a Facebook Page: `uv run python -m app.meta.facebook_setup`.

Uses FACEBOOK_PAGE_ACCESS_TOKEN from backend/.env to (1) check the token and read the Page's id and name,
(2) subscribe this app to the Page's comments and Messenger messages, (3) save the Page id on the
business, so webhooks for that Page are routed to it, and (4) import the Page's recent posts, linking each
to the catalog product named in its caption. Safe to run again (e.g. after publishing new posts).
"""

import asyncio
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.models import Business, Channel, Post, Product
from app.sanitize import redact

SUBSCRIBED_FIELDS = "feed,messages,message_echoes"


@dataclass(frozen=True)
class PageConnection:
    page_id: str
    page_name: str
    subscribed: bool


class SetupError(Exception):
    pass


async def connect_page(
    access_token: str, graph_url: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> PageConnection:
    async with httpx.AsyncClient(
        base_url=graph_url.rstrip("/"),
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15.0,
        transport=transport,
    ) as http:
        me = await _call(http, "GET", "/me", {"fields": "id,name"}, access_token)
        page_id, page_name = str(me.get("id", "")), str(me.get("name", ""))
        if not page_id:
            raise SetupError("the token didn't return a Page id: is it a Page access token?")
        result = await _call(
            http,
            "POST",
            f"/{page_id}/subscribed_apps",
            {"subscribed_fields": SUBSCRIBED_FIELDS},
            access_token,
        )
        return PageConnection(page_id, page_name, subscribed=result.get("success") is True)


async def fetch_page_posts(
    access_token: str, graph_url: str, page_id: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> list[dict]:
    async with httpx.AsyncClient(
        base_url=graph_url.rstrip("/"),
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15.0,
        transport=transport,
    ) as http:
        params = {"fields": "id,message,full_picture,permalink_url", "limit": "25"}
        data = await _call(http, "GET", f"/{page_id}/posts", params, access_token)
    return [p for p in data.get("data", []) if isinstance(p, dict) and p.get("id")]


async def sync_posts(session: AsyncSession, business: Business, posts: list[dict]) -> list[str]:
    """Upsert Facebook posts and link unlinked ones to the product named in the caption. A caption leads
    with its subject, so the product mentioned first wins ("The Weekend Bundle: tote + earrings").
    A linked product without a photo takes the post's photo."""
    products = (await session.scalars(select(Product).where(Product.business_id == business.id))).all()
    report = []
    for raw in posts:
        post = await session.scalar(
            select(Post).where(
                Post.business_id == business.id,
                Post.channel == Channel.FACEBOOK,
                Post.external_id == str(raw["id"]),
            )
        )
        if post is None:
            post = Post(business_id=business.id, channel=Channel.FACEBOOK, external_id=str(raw["id"]))
            session.add(post)
        caption = raw.get("message") if isinstance(raw.get("message"), str) else None
        post.caption = caption or post.caption
        for field, key in (("image_url", "full_picture"), ("permalink", "permalink_url")):
            value = raw.get(key)
            if isinstance(value, str) and value.startswith("https://") and len(value) <= 2000:
                setattr(post, field, value)
        text = (post.caption or "").lower()
        if post.product_id is None and text:
            named = [p for p in products if p.name.lower() in text]
            if named:
                post.product_id = min(named, key=lambda p: (text.index(p.name.lower()), -len(p.name))).id
        product = next((p for p in products if p.id == post.product_id), None)
        if product is not None and product.image_url is None and post.image_url:
            product.image_url = post.image_url  # the catalog shows the post's photo until the owner sets one
        name = product.name if product is not None else "no product"
        report.append(f"{(post.caption or '(no caption)')[:50]!r} -> {name}")
    await session.flush()
    return report


async def _call(http: httpx.AsyncClient, method: str, path: str, params: dict[str, str], token: str) -> dict:
    try:
        response = await http.request(method, path, params=params)
    except httpx.HTTPError as exc:
        raise SetupError(f"couldn't reach Meta: {type(exc).__name__}") from exc
    data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if response.status_code >= 400:
        message = str((data.get("error") or {}).get("message", response.text[:200]))
        raise SetupError(redact(f"{method} {path} failed ({response.status_code}): {message}", [token]))
    return data if isinstance(data, dict) else {}


async def main() -> str:
    settings = get_settings()
    if settings.facebook_page_access_token is None:
        raise SetupError("set FACEBOOK_PAGE_ACCESS_TOKEN in backend/.env first")
    connection = await connect_page(
        settings.facebook_page_access_token.get_secret_value(), settings.facebook_graph_url
    )
    engine = create_engine(settings.database_url)
    try:
        async with create_sessionmaker(engine)() as session:
            business = await session.scalar(select(Business).order_by(Business.id).limit(1))
            if business is None:
                raise SetupError("no business yet: run `uv run python -m app.seed` first")
            business.fb_page_id = connection.page_id
            posts = await fetch_page_posts(
                settings.facebook_page_access_token.get_secret_value(),
                settings.facebook_graph_url,
                connection.page_id,
            )
            linked = await sync_posts(session, business, posts)
            await session.commit()
    finally:
        await engine.dispose()
    subscribed = (
        "subscribed to comments and messages"
        if connection.subscribed
        else "NOT subscribed (check permissions)"
    )
    lines = "\n".join(f"  - {line}" for line in linked) or "  (no posts yet)"
    return f"Connected Page {connection.page_name!r} ({connection.page_id}); {subscribed}.\nPosts:\n{lines}"


if __name__ == "__main__":
    try:
        print(asyncio.run(main()))
    except SetupError as error:
        raise SystemExit(f"Facebook setup failed: {error}") from None
