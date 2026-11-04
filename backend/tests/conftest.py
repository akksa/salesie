import hashlib
import hmac
import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from fastapi import FastAPI
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from sqlalchemy import text

from app.config import ENV_FILE, Settings
from app.main import create_app
from app.models import Base, Business

BACKEND_DIR = ENV_FILE.parent
OWNER_AUTH = ("owner", "test-owner-password")
APP_SECRET = "test-app-secret"
VERIFY_TOKEN = "test-verify-token"
IG_ACCOUNT_ID = "17841400000000001"


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or dotenv_values(ENV_FILE).get("TEST_DATABASE_URL")
    if not url:
        pytest.exit("TEST_DATABASE_URL is not set; run scripts/devdb.sh init", returncode=2)
    return url


class _IsolatedSettings(Settings):
    """Only what a test passes in: never backend/.env or the shell's environment, which hold real keys."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": _test_database_url(),
        "meta_app_secret": APP_SECRET,
        "meta_verify_token": VERIFY_TOKEN,
        "owner_username": OWNER_AUTH[0],
        "owner_password": OWNER_AUTH[1],
        "simulator_enabled": True,
        "agent_enabled": False,  # ingestion tests run without the sales agent; agent tests opt in
        "llm_provider": "mock",
        "instagram_access_token": None,  # tests never talk to the real Meta APIs, whatever .env holds
        "facebook_page_access_token": None,
        "allow_test_checkout_with_live_instagram": False,
        "public_base_url": "http://testserver",
    }
    return _IsolatedSettings(**(values | overrides))


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Run the real migrations down and up once, so every test runs on the migrated schema."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["database_url"] = _test_database_url()
    command.downgrade(config, "base")
    command.upgrade(config, "head")


async def _build_app(settings: Settings) -> AsyncIterator[FastAPI]:
    app = create_app(settings)
    tables = [table.name for table in Base.metadata.sorted_tables]
    async with app.state.engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        # Give every table its own id range, so a product id can never coincide with a post or contact
        # id and a test can't pass when code mixes them up.
        for offset, table in enumerate(tables, start=1):
            await conn.execute(
                text("SELECT setval(pg_get_serial_sequence(:table, 'id'), :start, false)"),
                {"table": table, "start": offset * 1000},
            )
    yield app
    await app.state.engine.dispose()


@pytest.fixture
async def app() -> AsyncIterator[FastAPI]:
    async for built in _build_app(make_settings()):
        yield built


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", auth=OWNER_AUTH) as c:
        yield c


@pytest.fixture
async def anon_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def business_id(app: FastAPI) -> int:
    async with app.state.sessionmaker() as session:
        business = Business(name="Bloom & Thread", currency="USD", ig_account_id=IG_ACCOUNT_ID)
        session.add(business)
        await session.commit()
        return business.id


def meta_signature(body: bytes, secret: str = APP_SECRET) -> str:
    """Computed here, not with app.meta.signature, so the tests pin Meta's real scheme
    (sha256= + hex HMAC-SHA256 of the raw body) instead of whatever the app happens to do."""
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def deliver(
    client: httpx.AsyncClient, payload: dict[str, Any] | list[Any], *, secret: str = APP_SECRET
) -> httpx.Response:
    """POST a webhook body exactly as Meta would: raw JSON bytes plus an HMAC signature header."""
    body = json.dumps(payload).encode()
    headers = {"X-Hub-Signature-256": meta_signature(body, secret), "Content-Type": "application/json"}
    return await client.post("/webhooks/meta", content=body, headers=headers)


async def create_product(client: httpx.AsyncClient, **fields: Any) -> dict[str, Any]:
    body = {"name": "Linen summer dress", "price_minor": 4900, "attributes": {"color": "sage"}} | fields
    response = await client.post("/api/products", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def create_post(client: httpx.AsyncClient, **fields: Any) -> dict[str, Any]:
    body = {"external_id": "18000000000000001", "caption": "New drop!"} | fields
    response = await client.post("/api/posts", json=body)
    assert response.status_code == 201, response.text
    return response.json()
