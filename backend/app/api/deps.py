import secrets
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Path, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ratelimit import FailedLoginLimiter
from app.config import Settings
from app.db import get_session
from app.models import Business
from app.schemas import INT32_MAX

_basic = HTTPBasic(auto_error=False)
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _cross_site(request: Request) -> bool:
    """Browsers send cached Basic credentials with cross-site requests, so changes must come from our own
    pages. Sec-Fetch-Site and Origin are set by browsers and can't be forged by another site's page."""
    site = request.headers.get("sec-fetch-site")
    if site is not None and site not in ("same-origin", "none"):
        return True
    origin = request.headers.get("origin")
    return origin is not None and urlsplit(origin).netloc != request.headers.get("host", "")


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
IdPath = Annotated[int, Path(ge=1, le=INT32_MAX)]


def require_owner(
    request: Request,
    settings: SettingsDep,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> str:
    if request.method in _UNSAFE_METHODS and _cross_site(request):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-site request refused")
    limiter: FailedLoginLimiter = request.app.state.login_limiter
    client = request.client.host if request.client else "unknown"
    if (wait := limiter.retry_after(client)) is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed logins, try again later",
            headers={"Retry-After": str(wait)},
        )
    if credentials is not None:
        user_ok = secrets.compare_digest(credentials.username.encode(), settings.owner_username.encode())
        password_ok = secrets.compare_digest(
            credentials.password.encode(), settings.owner_password.get_secret_value().encode()
        )
        if user_ok and password_ok:
            return credentials.username
        limiter.record_failure(client)  # only wrong guesses count, not the browser's first challenge
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Invalid credentials", headers={"WWW-Authenticate": "Basic"}
    )


async def current_business(session: SessionDep) -> Business:
    """Phase 1 runs one business per deployment; multi-tenant routing comes with real onboarding."""
    business = await session.scalar(select(Business).order_by(Business.id).limit(1))
    if business is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "No business is set up yet. Run: uv run python -m app.seed"
        )
    return business


BusinessDep = Annotated[Business, Depends(current_business)]
