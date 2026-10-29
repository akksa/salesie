"""Meta signs every webhook POST with X-Hub-Signature-256: sha256=<hex HMAC-SHA256 of the raw body>,
keyed by the app secret."""

import hashlib
import hmac

SIGNATURE_HEADER = "X-Hub-Signature-256"
_PREFIX = "sha256="


def sign(body: bytes, secret: str) -> str:
    return _PREFIX + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def is_valid_signature(body: bytes, header: str | None, secret: str) -> bool:
    if not secret or not header or not header.isascii() or not header.startswith(_PREFIX):
        return False
    return hmac.compare_digest(sign(body, secret), header.lower())
