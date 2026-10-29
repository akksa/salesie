import re

import httpx
import pytest

from tests.conftest import create_post, create_product


async def test_api_requires_owner_credentials(anon_client: httpx.AsyncClient) -> None:
    response = await anon_client.get("/api/contacts")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


async def test_api_rejects_wrong_password(app) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", auth=("owner", "nope")) as c:
        assert (await c.get("/api/contacts")).status_code == 401


async def test_api_without_a_business_explains_how_to_fix(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/products")
    assert response.status_code == 409
    assert "seed" in response.json()["detail"]


async def test_business_settings_round_trip(client: httpx.AsyncClient, business_id: int) -> None:
    response = await client.patch("/api/business", json={"ig_account_id": "178414999", "currency": "EUR"})
    assert response.status_code == 200, response.text
    business = (await client.get("/api/business")).json()
    assert business["ig_account_id"] == "178414999"
    assert business["currency"] == "EUR"


async def test_product_create_list_update(client: httpx.AsyncClient, business_id: int) -> None:
    created = await create_product(client, name="Silver leaf earrings", price_minor=2500)
    response = await client.patch(
        f"/api/products/{created['id']}", json={"price_minor": 2200, "status": "draft"}
    )
    assert response.status_code == 200, response.text

    [product] = (await client.get("/api/products")).json()
    assert product["name"] == "Silver leaf earrings"
    assert product["price_minor"] == 2200
    assert product["status"] == "draft"
    assert product["attributes"] == {"color": "sage"}


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "price_minor": 100},
        {"name": "Dress", "price_minor": -1},
        {"name": "Dress", "image_url": "javascript:alert(1)"},
        {"name": "Dress", "status": "archived"},
    ],
)
async def test_product_validation(client: httpx.AsyncClient, business_id: int, body: dict) -> None:
    response = await client.post("/api/products", json=body)
    assert response.status_code == 422


async def test_unknown_product_id_returns_404(client: httpx.AsyncClient, business_id: int) -> None:
    assert (await client.patch("/api/products/999", json={"name": "x"})).status_code == 404
    response = await client.post("/api/posts", json={"external_id": "1", "product_id": 999})
    assert response.status_code == 404


async def test_post_can_be_relinked_to_another_product(client: httpx.AsyncClient, business_id: int) -> None:
    dress = await create_product(client, name="Dress")
    tote = await create_product(client, name="Tote")
    post = await create_post(client, product_id=dress["id"])

    response = await client.patch(f"/api/posts/{post['id']}", json={"product_id": tote["id"]})
    assert response.status_code == 200, response.text
    [listed] = (await client.get("/api/posts")).json()
    assert listed["product_name"] == "Tote"
    assert listed["engagement_count"] == 0


async def test_duplicate_post_external_id_is_a_conflict(client: httpx.AsyncClient, business_id: int) -> None:
    await create_post(client, external_id="18000000000000077")
    response = await client.post("/api/posts", json={"external_id": "18000000000000077"})
    assert response.status_code == 409


async def test_unknown_contact_and_conversation_return_404(
    client: httpx.AsyncClient, business_id: int
) -> None:
    assert (await client.get("/api/contacts/1")).status_code == 404
    assert (await client.get("/api/conversations/1")).status_code == 404


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/products/{id}", {"name": None}),
        ("/api/products/{id}", {"status": None}),
        ("/api/products/{id}", {"attributes": None}),
        ("/api/business", {"name": None}),
        ("/api/business", {"currency": None}),
    ],
)
async def test_patch_rejects_null_for_required_fields(
    client: httpx.AsyncClient, business_id: int, path: str, body: dict
) -> None:
    product = await create_product(client)
    response = await client.patch(path.format(id=product["id"]), json=body)
    assert response.status_code == 422, response.text


async def test_patch_null_clears_optional_fields(client: httpx.AsyncClient, business_id: int) -> None:
    product = await create_product(client, image_url="https://example.com/a.jpg")
    post = await create_post(client, product_id=product["id"])
    assert (
        await client.patch(f"/api/products/{product['id']}", json={"price_minor": None, "image_url": None})
    ).status_code == 200
    assert (await client.patch(f"/api/posts/{post['id']}", json={"product_id": None})).status_code == 200

    [listed_product] = (await client.get("/api/products")).json()
    assert listed_product["price_minor"] is None
    assert listed_product["image_url"] is None
    [listed_post] = (await client.get("/api/posts")).json()
    assert listed_post["product_id"] is None


def _api_routes() -> list[tuple[str, str]]:
    """Every /api operation, taken from the generated OpenAPI schema (FastAPI nests included routers,
    so app.routes alone would miss them)."""
    from app.main import create_app
    from tests.conftest import make_settings

    schema = create_app(make_settings()).openapi()
    return sorted(
        (method.upper(), re.sub(r"\{[a-z_]+\}", "1", path))
        for path, operations in schema["paths"].items()
        if path.startswith("/api")
        for method in operations
    )


API_ROUTES = _api_routes()


def test_route_inventory_is_complete() -> None:
    assert len(API_ROUTES) >= 17
    assert ("POST", "/api/simulator/instagram/dm") in API_ROUTES
    assert ("POST", "/api/webhook-events/1/replay") in API_ROUTES


@pytest.mark.parametrize(("method", "path"), API_ROUTES)
@pytest.mark.parametrize("auth", [None, ("owner", "nope"), ("intruder", "test-owner-password")])
async def test_every_api_route_requires_the_owner(
    app, business_id: int, method: str, path: str, auth: tuple[str, str] | None
) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", auth=auth) as c:
        response = await c.request(method, path, json={})
    assert response.status_code == 401, (method, path, response.text)
