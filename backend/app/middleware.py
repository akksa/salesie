"""Pure-ASGI middleware that must run before routing (and therefore before auth)."""

from fastapi import HTTPException, status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (
        b"content-security-policy",
        b"default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline'; "
        b"connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    ),
]


class BodySizeLimitMiddleware:
    """Reject request bodies over `max_bytes` while they stream in. Without this, FastAPI buffers a body
    in full before dependencies such as auth run, so an anonymous multi-GB upload could exhaust memory."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await _send_too_large(send)
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # Re-raised by FastAPI's body parsing and turned into a 413 by its exception handler.
                    raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "body too large")
            return message

        await self.app(scope, limited_receive, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        private = scope["path"].startswith(("/api/", "/pay/"))  # owner data and payment pages: never cached

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                extra = [*_SECURITY_HEADERS, *([(b"cache-control", b"no-store")] if private else [])]
                message = {**message, "headers": [*message.get("headers", []), *extra]}
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _send_too_large(send: Send) -> None:
    body = b'{"detail":"body too large"}'
    await send(
        {
            "type": "http.response.start",
            "status": status.HTTP_413_CONTENT_TOO_LARGE,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})
