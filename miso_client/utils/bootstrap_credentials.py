"""Deployment settings and confidential token-exchange validation."""

from __future__ import annotations

import json
import math
import re
import time
from typing import Dict, Optional, cast
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..models.bootstrap import BootstrapError
from .bootstrap_snapshot import timestamp, unique_object


class MintedToken(BaseModel):
    """Confidential controller token response, never included in diagnostics."""

    model_config = ConfigDict(strict=True, hide_input_in_errors=True)
    token: SecretStr = Field(min_length=1, max_length=65536, repr=False, exclude=True)
    expiresIn: float = Field(gt=0, allow_inf_nan=False)
    expiresAt: str


def parse_minted_token(body: bytes) -> tuple[SecretStr, float]:
    """Validate the token endpoint's data envelope and conservative lifetime."""
    result: Optional[tuple[SecretStr, float]] = None
    try:
        raw = cast(object, json.loads(body, object_pairs_hook=unique_object))
        if not isinstance(raw, dict):
            raise ValueError("envelope")
        envelope = cast(Dict[str, object], raw)
        if envelope.get("success", True) is not True:
            raise ValueError("envelope")
        token = MintedToken.model_validate(envelope.get("data"))
        lifetime = min(token.expiresIn, timestamp(token.expiresAt) - time.time())
        if (
            not math.isfinite(lifetime)
            or lifetime <= 0
            or not token.token.get_secret_value().strip()
        ):
            raise ValueError("expired token")
        result = token.token, time.monotonic() + lifetime
    except (ValueError, TypeError, RecursionError):
        result = None  # Normalize outside the handler to avoid retaining secret-bearing errors.
    if result is None:
        raise BootstrapError("protocol-error")
    return result


def validate_settings(url: str) -> str:
    """Return a pinned HTTPS bootstrap URL, preserving a safe deployment prefix."""
    valid = False
    try:
        parts = urlsplit(url)
        segments = parts.path.rstrip("/").split("/")[1:]
        valid = bool(
            url
            and url == url.strip()
            and parts.scheme == "https"
            and parts.hostname
            and not parts.username
            and not parts.password
            and not parts.query
            and not parts.fragment
            and "?" not in url
            and "#" not in url
            and "//" not in parts.path
            and parts.port != 0
            and not re.search(r"[\x00-\x20\x7f\\%]", url)
            and all(re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part) for part in segments)
        )
    except ValueError:
        valid = False  # Malformed URLs use the same safe settings error as invalid URLs.
    if not valid:
        raise BootstrapError("invalid-bootstrap-settings")
    return url.rstrip("/") + "/api/v1/auth/bootstrap"


def validate_credentials(client_id: str, client_secret: str) -> None:
    """Reject absent or unsafe header values before opening a connection."""
    if any(
        not value.strip() or not value.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in value)
        for value in (client_id, client_secret)
    ):
        raise BootstrapError("invalid-bootstrap-settings")


def validate_http_client(client: httpx.AsyncClient) -> None:
    """Require isolated injected clients; hooks would observe unmasked credentials."""
    if client.trust_env or any(client.event_hooks.values()):
        raise BootstrapError("invalid-bootstrap-http-client")
