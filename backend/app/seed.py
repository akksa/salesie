"""Create the demo shop: `uv run python -m app.seed`. Does nothing if a business already exists.
`--reset` first deletes ALL data in the configured database (use it to get a clean demo).

The Instagram account id is a placeholder; set the real one in the dashboard (or PATCH /api/business)
once the Meta app is connected. The simulator works with either.
"""

import asyncio
import sys

from sqlalchemy import select, text

from app.config import get_settings
from app.db import create_engine, create_sessionmaker
from app.models import Base, Business, Channel, Post, Product

PLACEHOLDER_IG_ACCOUNT_ID = "17841400000000000"
SHOP_NOTES = (
    "Free shipping nationwide, 3-5 business days.\n"
    "Returns within 14 days if unworn with tags.\n"
    "Payment by card through a secure checkout link."
)

PRODUCTS = [
    {
        "name": "Linen wrap dress",
        "description": "Breathable linen wrap dress with tie waist.",
        "attributes": {"color": "sage", "sizes": "XS-XL", "material": "linen"},
        "price_minor": 6800,
        "post": ("18000000000000101", "Linen wrap dress is back in sage 🌿 Sizes XS-XL. Comment 'price'!"),
    },
    {
        "name": "Hand-painted canvas tote",
        "description": "One-of-a-kind tote, painted by hand.",
        "attributes": {"color": "natural", "size": "38 x 42 cm"},
        "price_minor": 3200,
        "post": ("18000000000000102", "Every tote is painted by hand, so no two are the same 🎨"),
    },
    {
        "name": "Silver leaf earrings",
        "description": "Lightweight sterling silver leaf drops.",
        "attributes": {"material": "sterling silver"},
        "price_minor": 2400,
        "post": ("18000000000000103", "Weekend drop: silver leaf earrings ✨ Only 12 pairs."),
    },
]


async def seed(*, reset: bool = False) -> str:
    engine = create_engine(get_settings().database_url)
    try:
        if reset:
            tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
            async with engine.begin() as conn:
                await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        async with create_sessionmaker(engine)() as session:
            if await session.scalar(select(Business.id).limit(1)) is not None:
                return "A business already exists; nothing to do."
            business = Business(
                name="Bloom & Thread",
                currency="USD",
                ig_account_id=PLACEHOLDER_IG_ACCOUNT_ID,
                sales_notes=SHOP_NOTES,
            )
            session.add(business)
            await session.flush()
            for spec in PRODUCTS:
                fields = {k: v for k, v in spec.items() if k != "post"}
                product = Product(business_id=business.id, **fields)
                session.add(product)
                await session.flush()
                media_id, caption = spec["post"]
                session.add(
                    Post(
                        business_id=business.id,
                        channel=Channel.INSTAGRAM,
                        external_id=media_id,
                        caption=caption,
                        product_id=product.id,
                    )
                )
            await session.commit()
            return f"Created {business.name} with {len(PRODUCTS)} products and posts."
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print(asyncio.run(seed(reset="--reset" in sys.argv[1:])))
