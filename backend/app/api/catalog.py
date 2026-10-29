from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import BusinessDep, IdPath, SessionDep, require_owner
from app.models import Business, Engagement, Post, Product
from app.schemas import (
    BusinessOut,
    BusinessUpdate,
    PostIn,
    PostOut,
    PostUpdate,
    ProductIn,
    ProductOut,
    ProductUpdate,
)

router = APIRouter(prefix="/api", tags=["catalog"], dependencies=[Depends(require_owner)])


@router.get("/business")
async def get_business(business: BusinessDep) -> BusinessOut:
    return BusinessOut.model_validate(business)


@router.patch("/business")
async def update_business(body: BusinessUpdate, business: BusinessDep, session: SessionDep) -> BusinessOut:
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(business, field, value)
    await _commit_or_conflict(session, "another business already uses that account id")
    return BusinessOut.model_validate(business)


@router.get("/products")
async def list_products(business: BusinessDep, session: SessionDep) -> list[ProductOut]:
    products = await session.scalars(
        select(Product).where(Product.business_id == business.id).order_by(Product.created_at.desc())
    )
    return [ProductOut.model_validate(p) for p in products]


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(body: ProductIn, business: BusinessDep, session: SessionDep) -> ProductOut:
    product = Product(business_id=business.id, **body.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return ProductOut.model_validate(product)


@router.patch("/products/{product_id}")
async def update_product(
    product_id: IdPath, body: ProductUpdate, business: BusinessDep, session: SessionDep
) -> ProductOut:
    product = await _owned_product(session, business, product_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await session.commit()
    await session.refresh(product)
    return ProductOut.model_validate(product)


def _posts_query(business_id: int) -> Select[Post, str, int]:  # product name is NULL when unlinked
    engagement_count = (
        select(func.count(Engagement.id)).where(Engagement.post_id == Post.id).scalar_subquery()
    )
    return (
        select(Post, Product.name, engagement_count)
        .outerjoin(Product, Product.id == Post.product_id)
        .where(Post.business_id == business_id)
    )


@router.get("/posts")
async def list_posts(business: BusinessDep, session: SessionDep) -> list[PostOut]:
    rows = await session.execute(_posts_query(business.id).order_by(Post.created_at.desc(), Post.id.desc()))
    return [_post_out(post, product_name, count) for post, product_name, count in rows]


@router.post("/posts", status_code=status.HTTP_201_CREATED)
async def create_post(body: PostIn, business: BusinessDep, session: SessionDep) -> PostOut:
    product = (
        await _owned_product(session, business, body.product_id) if body.product_id is not None else None
    )
    post = Post(business_id=business.id, **body.model_dump())
    session.add(post)
    await _commit_or_conflict(session, "a post with that external id already exists")
    await session.refresh(post)
    return _post_out(post, product.name if product else None, 0)


@router.patch("/posts/{post_id}")
async def update_post(
    post_id: IdPath, body: PostUpdate, business: BusinessDep, session: SessionDep
) -> PostOut:
    post = await session.get(Post, post_id)
    if post is None or post.business_id != business.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "post not found")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("product_id") is not None:
        await _owned_product(session, business, changes["product_id"])
    for field, value in changes.items():
        setattr(post, field, value)
    await session.commit()
    updated, product_name, count = (
        await session.execute(_posts_query(business.id).where(Post.id == post_id))
    ).one()
    return _post_out(updated, product_name, count)


async def _owned_product(session: SessionDep, business: Business, product_id: int) -> Product:
    product = await session.get(Product, product_id)
    if product is None or product.business_id != business.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product not found")
    return product


async def _commit_or_conflict(session: SessionDep, message: str) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message) from exc


def _post_out(post: Post, product_name: str | None, engagement_count: int) -> PostOut:
    return PostOut(
        id=post.id,
        channel=post.channel,
        external_id=post.external_id,
        caption=post.caption,
        image_url=post.image_url,
        permalink=post.permalink,
        product_id=post.product_id,
        product_name=product_name,
        engagement_count=engagement_count,
        created_at=post.created_at,
    )
