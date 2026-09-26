"""Isolated, bounded broker transport without SDK auth/logging interceptors."""

from __future__ import annotations

import asyncio
import random
import ssl
import time
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx
from pydantic import SecretStr

from ..models.bootstrap import BootstrapError
from .bootstrap_credentials import parse_minted_token, validate_credentials, validate_http_client
from .bootstrap_snapshot import MAX_BODY, SnapshotClock

RETRY_STATUS = {429, 502, 503, 504}


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
        client_id: str,
        client_secret: str,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        validate_credentials(client_id, client_secret)
        if http_client is not None:
            validate_http_client(http_client)
        self.endpoint = endpoint
        self._mint_endpoint = endpoint.removesuffix("bootstrap") + "token"
        self._credentials: Optional[tuple[SecretStr, SecretStr]] = (
            SecretStr(client_id),
            SecretStr(client_secret),
        )
        self._token: Optional[SecretStr] = None
        self._mint_deadline = 0.0
        self._snapshot_clock: Optional[SnapshotClock] = None
        self._closed = False
        self._owned = http_client is None
        self.client = http_client or httpx.AsyncClient(
            timeout=5, follow_redirects=False, trust_env=False
        )

    def install_token(self, token: SecretStr, clock: SnapshotClock) -> None:
        """Accept only a runtime-validated token; discard startup credentials."""
        if self._closed:
            raise BootstrapError("closed")
        self._token = token
        self._snapshot_clock = clock
        self._credentials = None

    def invalidate(self) -> None:
        """Erase retained credentials synchronously and prevent further exchanges."""
        self._closed = True
        self._token = None
        self._snapshot_clock = None
        self._credentials = None

    async def fetch(self) -> bytes:
        """Fetch within a total budget, sanitizing every transport error."""
        failure: Optional[BootstrapError] = None
        try:
            return await asyncio.wait_for(self._fetch(), timeout=30)
        except BootstrapError as error:
            failure = BootstrapError(error.code, error.status_code)
        except Exception:
            failure = BootstrapError("temporarily-unavailable")
        raise failure

    async def _fetch(self) -> bytes:
        if self._closed:
            raise BootstrapError("closed")
        if self._token is None:
            minted = parse_minted_token(await self._exchange(True))
            if self._closed:
                raise BootstrapError("closed")
            self._token, self._mint_deadline = minted
        return await self._exchange(False)

    async def _exchange(self, mint: bool) -> bytes:
        for attempt in range(3):
            body, delay = await self._attempt(mint, attempt)
            if body is not None:
                return body
            if attempt < 2:
                await asyncio.sleep(delay)
        raise BootstrapError("temporarily-unavailable")

    async def _attempt(self, mint: bool, attempt: int) -> tuple[Optional[bytes], float]:
        retry = False
        try:
            return await asyncio.wait_for(self._request(mint, attempt), timeout=5)
        except httpx.NetworkError as error:
            retry = not _tls_failure(error)
        except (httpx.TimeoutException, asyncio.TimeoutError):
            retry = True
        if not retry:
            raise BootstrapError("transport-error")
        return None, retry_delay(None, attempt)

    def _build_request(self, mint: bool) -> httpx.Request:
        if self._closed:
            raise BootstrapError("closed")
        headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
        if mint:
            if self._credentials is None:
                raise BootstrapError("token-unavailable")
            headers["x-client-id"], headers["x-client-secret"] = (
                value.get_secret_value() for value in self._credentials
            )
        else:
            headers["x-client-token"] = self._request_token()
        return httpx.Request(
            "POST",
            self._mint_endpoint if mint else self.endpoint,
            headers=headers,
            json=None if mint else {"protocolVersion": 1},
            extensions={"timeout": {key: 5.0 for key in ("connect", "read", "write", "pool")}},
        )

    def _request_token(self) -> str:
        """Check the appropriate deadline immediately before each snapshot attempt."""
        if self._token is None:
            raise BootstrapError("token-unavailable")
        if self._credentials is not None and time.monotonic() >= self._mint_deadline:
            raise BootstrapError("token-expired")
        clock = self._snapshot_clock
        if clock is not None and clock.now(time.time(), time.monotonic()) >= clock.secrets:
            self.invalidate()
            raise BootstrapError("snapshot-expired")
        return self._token.get_secret_value()

    async def _request(self, mint: bool, attempt: int) -> tuple[Optional[bytes], float]:
        validate_http_client(self.client)
        # A standalone Request skips injected defaults, cookies, params and base_url.
        response = await self.client.send(
            self._build_request(mint), stream=True, auth=None, follow_redirects=False
        )
        try:
            return await self._read_response(response, 201 if mint else 200, attempt)
        finally:
            await response.aclose()

    async def _read_response(
        self, response: httpx.Response, expected: int, attempt: int
    ) -> tuple[Optional[bytes], float]:
        if response.status_code in (401, 403):
            raise BootstrapError("authorization-denied", response.status_code)
        if response.status_code in RETRY_STATUS:
            return None, retry_delay(response.headers.get("Retry-After"), attempt)
        if response.status_code != expected:
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
        """Clear credentials and close the owned HTTP transport only."""
        self.invalidate()
        if self._owned:
            await self.client.aclose()
