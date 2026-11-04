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
    "Free shipping across India on every order; delivery in 3-6 working days.\n"
    "Launch price on the Linen Co-ord Set: ₹2,999 for the first 20 orders, while stock lasts.\n"
    "Returns within 7 days if unworn with tags.\n"
    "Pay securely through the checkout link we send you."
)

# Product photos made with Muse Image (docs/brand), served from the public repo so the links never expire.
IMAGES = "https://raw.githubusercontent.com/akksa/salesie/main/docs/brand"

# Prices are in paise (₹1 = 100). The "offers" are products and shop notes: the agent never invents discounts.
PRODUCTS = [
    {
        "name": "Linen Wrap Dress",
        "image_url": f"{IMAGES}/03-linen-wrap-dress.jpg",
        "description": "Breathable washed-linen wrap dress with a tie waist and flutter sleeves.",
        "attributes": {"colours": "sage, sand, navy", "sizes": "XS-XL", "material": "100% linen"},
        "price_minor": 249900,
        "post": (
            "18000000000000101",
            "Our Linen Wrap Dress is back in sage, sand and navy 🌿 Comment 'price'!",
        ),
    },
    {
        "name": "Block-Print Cotton Top",
        "image_url": f"{IMAGES}/04-block-print-top.jpg",
        "description": "Hand block-printed cotton top with a relaxed fit.",
        "attributes": {"colours": "indigo, rust", "sizes": "S-XL", "material": "cotton"},
        "price_minor": 129900,
        "post": (
            "18000000000000102",
            "Hand block-printed, one stamp at a time: the Block-Print Cotton Top 💙",
        ),
    },
    {
        "name": "Linen Co-ord Set",
        "image_url": f"{IMAGES}/05-linen-coord-set.jpg",
        "description": "Matching linen shirt and drawstring trousers. Launch price for the first 20 orders.",
        "attributes": {"colours": "white, olive", "sizes": "S-XL", "material": "100% linen"},
        "price_minor": 299900,
        "post": (
            "18000000000000103",
            "New: the Linen Co-ord Set at a launch price of ₹2,999 for the first 20 orders ✨",
        ),
    },
    {
        "name": "Hand-Painted Canvas Tote",
        "image_url": f"{IMAGES}/06-canvas-tote.jpg",
        "description": "Sturdy canvas tote, painted by hand, so no two are the same.",
        "attributes": {"colour": "natural", "size": "38 x 42 cm"},
        "price_minor": 89900,
        "post": ("18000000000000104", "Every Hand-Painted Canvas Tote is one of a kind 🎨"),
    },
    {
        "name": "Silver Leaf Earrings",
        "image_url": f"{IMAGES}/07-silver-leaf-earrings.jpg",
        "description": "Lightweight sterling silver leaf drops.",
        "attributes": {"material": "sterling silver"},
        "price_minor": 74900,
        "post": ("18000000000000105", "Silver Leaf Earrings: light enough to forget you're wearing them ✨"),
    },
    {
        "name": "Weekend Bundle",
        "image_url": f"{IMAGES}/08-weekend-bundle.jpg",
        "description": "A Hand-Painted Canvas Tote and Silver Leaf Earrings together; you save ₹199.",
        "attributes": {"includes": "canvas tote + silver leaf earrings", "you save": "₹199"},
        "price_minor": 144900,
        "post": ("18000000000000106", "The Weekend Bundle: tote + earrings for ₹1,449 (save ₹199) 🛍️"),
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
                currency="INR",
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
