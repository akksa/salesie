import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent.factory import build_agent_services
from app.api import agent, catalog, crm, dashboard, pay, simulator, webhooks
from app.api.ratelimit import FailedLoginLimiter
from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker
from app.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = create_engine(settings.database_url)

    agent_services = build_agent_services(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        for client in (agent_services.llm, agent_services.live_sender, agent_services.messenger_sender):
            if (close := getattr(client, "aclose", None)) is not None:
                await close()
        await engine.dispose()

    docs = settings.api_docs_enabled  # off in public deployments: no free map of the attack surface
    app = FastAPI(
        title="Salesie",
        lifespan=lifespan,
        openapi_url="/openapi.json" if docs else None,
        docs_url="/docs" if docs else None,
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.login_limiter = FailedLoginLimiter()
    app.state.agent = agent_services
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(webhooks.router)
    app.include_router(catalog.router)
    app.include_router(crm.router)
    app.include_router(simulator.router)
    app.include_router(agent.router)
    app.include_router(dashboard.router)
    app.include_router(pay.router)

    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built dashboard (frontend/dist) from the same origin, with SPA fallback to index.html."""
    if not (FRONTEND_DIST / "index.html").is_file():
        return
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith(("api/", "webhooks/")):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
        candidate = (FRONTEND_DIST / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(FRONTEND_DIST):
            return FileResponse(candidate)
        # Always revalidated: a cached index.html names old hashed scripts after a rebuild (blank dashboard)
        return FileResponse(FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache"})


class _HidePaymentTokens(logging.Filter):
    """Payment link tokens and Meta's webhook verify token are secrets: keep them out of access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_hide_secrets(a) if isinstance(a, str) else a for a in record.args)
        return True


def _hide_secrets(text: str) -> str:
    return _VERIFY_TOKEN.sub(r"\1[token]", _PAY_TOKEN.sub("/pay/[token]", text))


_PAY_TOKEN = re.compile(r"/pay/[A-Za-z0-9_-]+")
_VERIFY_TOKEN = re.compile(r"(hub[._]verify_token=)[^&\s]+")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("uvicorn.access").addFilter(_HidePaymentTokens())
