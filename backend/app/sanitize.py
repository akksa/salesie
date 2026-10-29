"""Postgres TEXT and JSONB reject NUL characters and unpaired UTF-16 surrogates, and JSONB rejects NaN and
Infinity. Instagram comments, form input and model output can contain any of these, so values are cleaned
before anything is stored."""

import math
import re
from collections.abc import Iterable
from typing import Any


def clean_text(value: str) -> str:
    return value.replace("\x00", "").encode("utf-8", "replace").decode("utf-8")


def clean_json(value: Any) -> Any:
    match value:
        case str():
            return clean_text(value)
        case list():
            return [clean_json(item) for item in value]
        case dict():
            return {clean_text(str(key)): clean_json(item) for key, item in value.items()}
        case float() if not math.isfinite(value):
            return str(value)  # JSONB has no NaN/Infinity
        case _:
            return value


# Credential shapes that upstream error messages sometimes echo back (OpenAI-style keys, Meta tokens).
_CREDENTIALS = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{8,}|EAA[A-Za-z0-9]{10,}|IG[A-Za-z0-9]{20,})|(?i:bearer)\s+\S+"
)


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Remove our own secrets and credential-looking strings from text we store or show."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[redacted]")
    return _CREDENTIALS.sub("[redacted]", text)
