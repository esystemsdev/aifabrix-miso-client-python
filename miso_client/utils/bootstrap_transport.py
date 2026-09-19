"""Isolated, bounded broker transport without SDK auth/logging interceptors."""

from __future__ import annotations

import asyncio
import random
import ssl
import time
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlsplit

import httpx

from ..models.bootstrap import BootstrapError, IdentityTokenProvider
from .bootstrap_snapshot import MAX_BODY

RETRY_STATUS = {429, 502, 503, 504}


def validate_settings(url: str, audience: str) -> str:
    """Validate trusted deployment settings before identity or network access."""
    valid = False
    try:
        parts = urlsplit(url)
        valid = bool(
            parts.scheme == "https"
            and parts.hostname
            and not parts.username
            and not parts.password
            and not parts.query
            and not parts.fragment
            and parts.path in ("", "/")
            and parts.port != 0
        )
    except ValueError:
        valid = False  # Reject malformed deployment URLs without raw diagnostics.
    if not valid or not audience or audience.strip() != audience:
        raise BootstrapError("invalid-azure-settings")
    if audience.endswith("/.default"):
        raise BootstrapError("invalid-azure-audience")
    return url.rstrip("/") + "/api/v1/auth/bootstrap"


def _tls_failure(error: BaseException) -> bool:
    """Identify certificate/TLS failures without copying error diagnostics."""
    seen: set[int] = set()
    current: Optional[BaseException] = error
    while current is not None and id(current) not in seen:
        if isinstance(current, ssl.SSLError):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def retry_delay(value: Optional[str], attempt: int) -> float:
    """Honor bounded Retry-After or use jitter for missing/invalid values."""
    seconds: Optional[float] = None
    if value:
        try:
            seconds = (
                float(value)
                if value.isdigit()
                else (parsedate_to_datetime(value).timestamp() - time.time())
            )
        except (ValueError, TypeError, OverflowError):
            seconds = None  # Malformed Retry-After falls back to bounded jitter.
    if seconds is not None and seconds >= 0:
        if seconds > 10:
            raise BootstrapError("temporarily-unavailable")
        return seconds
    return random.uniform(0, 2**attempt)


class BrokerTransport:
    """Owns only a newly-created httpx client; injected clients remain caller-owned."""

    def __init__(
        self,
        endpoint: str,
        audience: str,
        provider: IdentityTokenProvider,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.endpoint = endpoint
        self.scope = audience + "/.default"
        self.provider = provider
        self._owned = http_client is None
        self.client = http_client or httpx.AsyncClient(
            timeout=5, follow_redirects=False, trust_env=False
        )

    async def fetch(self) -> bytes:
        """Fetch within a total budget, sanitizing every transport/identity error."""
        failure: Optional[BootstrapError] = None
        try:
            return await asyncio.wait_for(self._fetch(), timeout=30)
        except BootstrapError as error:
            failure = BootstrapError(error.code, error.status_code)
        except Exception:
            failure = BootstrapError("temporarily-unavailable")
        raise failure

    async def _fetch(self) -> bytes:
        token = await asyncio.wait_for(self.provider.get_token(self.scope), timeout=5)
        if not token.token.get_secret_value() or token.expires_at <= time.time():
            raise BootstrapError("invalid-identity-token")
        for attempt in range(3):
            body, delay = await self._attempt(token.token.get_secret_value(), attempt)
            if body is not None:
                return body
            if attempt < 2:
                await asyncio.sleep(delay)
        raise BootstrapError("temporarily-unavailable")

    async def _attempt(self, token: str, attempt: int) -> tuple[Optional[bytes], float]:
        retry = False
        try:
            return await asyncio.wait_for(self._request(token, attempt), timeout=5)
        except httpx.NetworkError as error:
            retry = not _tls_failure(error)
        except (httpx.TimeoutException, asyncio.TimeoutError):
            retry = True
        if not retry:
            raise BootstrapError("transport-error")
        return None, retry_delay(None, attempt)

    async def _request(self, token: str, attempt: int) -> tuple[Optional[bytes], float]:
        async with self.client.stream(
            "POST",
            self.endpoint,
            json={"protocolVersion": 1},
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            follow_redirects=False,
        ) as response:
            if response.status_code in (401, 403):
                raise BootstrapError("authorization-denied", response.status_code)
            if response.status_code in RETRY_STATUS:
                return None, retry_delay(response.headers.get("Retry-After"), attempt)
            if response.status_code != 200:
                raise BootstrapError("protocol-error", response.status_code)
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise BootstrapError("protocol-error")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > MAX_BODY:
                    raise BootstrapError("protocol-error")
                body.extend(chunk)
            return bytes(body), 0

    async def close(self) -> None:
        """Close the owned HTTP transport only."""
        if self._owned:
            await self.client.aclose()
