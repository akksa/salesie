"""Protections added after red-team review: limits that apply before auth, headers, login throttling."""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from tests.conftest import OWNER_AUTH, _build_app, make_settings


async def _big_chunks() -> AsyncIterator[bytes]:
    for _ in range(11):
        yield b"x" * 100_000


@pytest.mark.parametrize("path", ["/api/products", "/api/simulator/instagram/dm", "/webhooks/meta"])
async def test_oversized_bodies_are_cut_off_before_auth(anon_client: httpx.AsyncClient, path: str) -> None:
    streamed = await anon_client.post(path, content=_big_chunks())
    assert streamed.status_code == 413
    declared = await anon_client.post(path, content=b"x" * 1_000_001)
    assert declared.status_code == 413


async def test_security_headers_are_set(client: httpx.AsyncClient, business_id: int) -> None:
    response = await client.get("/api/contacts")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert "cache-control" not in (await client.get("/healthz")).headers


async def test_api_docs_are_off_by_default(anon_client: httpx.AsyncClient) -> None:
    for path in ("/openapi.json", "/docs"):
        response = await anon_client.get(path)  # 404, or the dashboard's index.html when it's built
        assert "openapi" not in response.text.lower()
        assert "swagger" not in response.text.lower()


async def test_repeated_wrong_passwords_are_throttled_per_client(app: FastAPI, business_id: int) -> None:
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://test", auth=("owner", "wrong")) as attacker,
        httpx.AsyncClient(transport=transport, base_url="http://test") as browser,
    ):
        statuses = [(await attacker.get("/api/app-config")).status_code for _ in range(21)]
        assert statuses[:20] == [401] * 20
        assert statuses[20] == 429
        blocked = await attacker.get("/api/app-config", auth=OWNER_AUTH)
        assert blocked.status_code == 429  # same client stays blocked even with the right password
        assert int(blocked.headers["retry-after"]) > 0
        # A browser's initial unauthenticated challenge doesn't count as a failed guess.
        app.state.login_limiter._failures.clear()
        for _ in range(25):
            assert (await browser.get("/api/app-config")).status_code == 401


def test_short_owner_password_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least 16"):
        make_settings(owner_password="short-password")


@pytest.fixture
async def docs_app() -> AsyncIterator[FastAPI]:
    async for built in _build_app(make_settings(api_docs_enabled=True)):
        yield built


async def test_api_docs_can_be_enabled_for_development(docs_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=docs_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        assert (await c.get("/openapi.json")).status_code == 200


def test_empty_optional_secrets_mean_unset() -> None:
    settings = make_settings(instagram_access_token="", model_api_key="  ")
    assert settings.instagram_access_token is None
    assert settings.model_api_key is None
    with pytest.raises(ValidationError, match="MODEL_API_KEY"):
        make_settings(llm_provider="muse", model_api_key="")
