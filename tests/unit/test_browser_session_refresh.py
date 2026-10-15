"""Browser-session cookie refresh: single refresh, rotation memo, no token leaks."""

import asyncio
import logging
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, cast
from unittest.mock import AsyncMock, Mock

import httpx
import jwt
import pytest

from miso_client import MisoClient, SessionCookieValidation, apply_session_cookie
from miso_client.models.config import UserInfo
from miso_client.services.browser_session_refresh import (
    REFRESH_ENDPOINT,
    SESSION_COOKIE_NAME,
    BrowserSessionRefreshService,
    get_session_cookie_token,
    is_token_expired,
    token_key,
)
from miso_client.utils.data_masker import DataMasker


def make_token(exp_offset: Optional[int], jti: str) -> str:
    claims: Dict[str, Any] = {"sub": "user-1", "jti": jti}
    if exp_offset is not None:
        claims["exp"] = int(time.time()) + exp_offset
    return jwt.encode(claims, "unit-test-signing-key-0123456789abcdef", algorithm="HS256")


EXPIRED = make_token(-60, "expired-jti")
RENEWED = make_token(300, "renewed-jti")
LIVE = make_token(300, "live-jti")
SET_COOKIE = f"{SESSION_COOKIE_NAME}={RENEWED}; Path=/; HttpOnly; SameSite=Lax"
USER = UserInfo(id="user-1", username="alice")


class RefreshTransport:
    """Record refresh requests and answer with a configurable Miso response."""

    def __init__(self, status: int = 200, gate: Optional[asyncio.Event] = None) -> None:
        self.requests: List[httpx.Request] = []
        self.status = status
        self.gate = gate
        self.set_cookie: Optional[str] = SET_COOKIE
        self.body: Dict[str, Any] = {"data": {"authenticated": True, "expiresIn": 300}}

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.gate is not None:
            await self.gate.wait()
        if self.status != 200:
            return httpx.Response(
                self.status,
                json={"type": "/Errors/Unauthorized", "detail": "No active browser session"},
            )
        headers = [("set-cookie", "other=1; Path=/")]
        if self.set_cookie:
            headers.append(("set-cookie", self.set_cookie))
        return httpx.Response(200, headers=headers, json=self.body)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


def make_service(config: Any, miso: RefreshTransport) -> BrowserSessionRefreshService:
    http_client = Mock()
    http_client.config = config
    http_client.get_environment_token = AsyncMock(return_value="client-token")
    auth = Mock()
    auth.get_user = AsyncMock(side_effect=lambda token: USER if token in (LIVE, RENEWED) else None)
    return BrowserSessionRefreshService(http_client, auth, transport=miso.transport())


@pytest.mark.asyncio
async def test_expired_cookie_refreshes_once_and_returns_set_cookie(config: Any) -> None:
    miso = RefreshTransport()
    service = make_service(config, miso)
    get_user = cast(AsyncMock, service.auth.get_user)

    result = await service.validate_or_refresh(EXPIRED)

    assert result.valid and result.refreshed
    assert result.token == RENEWED
    assert result.user == USER
    assert result.set_cookie == SET_COOKIE
    assert len(miso.requests) == 1
    request = miso.requests[0]
    assert request.method == "POST" and request.url.path == REFRESH_ENDPOINT
    assert request.headers["cookie"] == f"{SESSION_COOKIE_NAME}={EXPIRED}"
    assert request.headers["x-client-token"] == "client-token"
    assert "authorization" not in request.headers
    assert request.content == b""
    get_user.assert_awaited_once_with(RENEWED)


@pytest.mark.asyncio
async def test_concurrent_requests_share_one_refresh(config: Any) -> None:
    gate = asyncio.Event()
    miso = RefreshTransport(gate=gate)
    service = make_service(config, miso)

    pending = [asyncio.ensure_future(service.validate_or_refresh(EXPIRED)) for _ in range(10)]
    await asyncio.sleep(0)
    while not miso.requests:
        await asyncio.sleep(0)
    gate.set()
    results = await asyncio.gather(*pending)

    assert len(miso.requests) == 1
    assert all(r.valid and r.token == RENEWED for r in results)
    assert service._inflight == {}


@pytest.mark.asyncio
async def test_old_cookie_after_rotation_hits_memo(config: Any) -> None:
    miso = RefreshTransport()
    service = make_service(config, miso)
    await service.validate_or_refresh(EXPIRED)

    again = await service.validate_or_refresh(EXPIRED)

    assert len(miso.requests) == 1
    assert again.valid and again.token == RENEWED and again.set_cookie == SET_COOKIE


@pytest.mark.asyncio
async def test_memo_expires_with_renewed_token(config: Any) -> None:
    miso = RefreshTransport()
    service = make_service(config, miso)
    await service.refresh_browser_session(EXPIRED)
    key = token_key(EXPIRED)
    service._memo[key] = (service._memo[key][0], time.time() - 1)

    await service.refresh_browser_session(EXPIRED)

    assert len(miso.requests) == 2


@pytest.mark.asyncio
async def test_live_token_validates_without_refresh(config: Any) -> None:
    miso = RefreshTransport()
    service = make_service(config, miso)

    result = await service.validate_or_refresh(LIVE)

    assert result.valid and not result.refreshed
    assert result.token == LIVE and result.set_cookie is None
    assert miso.requests == []


@pytest.mark.asyncio
async def test_invalid_unexpired_token_is_not_refreshed(config: Any) -> None:
    miso = RefreshTransport()
    service = make_service(config, miso)
    bad = make_token(300, "revoked-jti")

    result = await service.validate_or_refresh(bad)

    assert result == SessionCookieValidation(valid=False)
    assert miso.requests == []


@pytest.mark.asyncio
async def test_token_without_exp_is_not_refreshed(config: Any) -> None:
    miso = RefreshTransport()
    service = make_service(config, miso)

    result = await service.validate_or_refresh(make_token(None, "no-exp"))

    assert not result.valid
    assert miso.requests == []


@pytest.mark.asyncio
async def test_no_active_browser_session_is_401_without_retry(config: Any) -> None:
    miso = RefreshTransport(status=401)
    service = make_service(config, miso)

    first = await service.validate_or_refresh(EXPIRED)

    assert first == SessionCookieValidation(valid=False)
    assert len(miso.requests) == 1
    assert service._memo == {}
    await service.validate_or_refresh(EXPIRED)
    assert len(miso.requests) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "set_cookie,body",
    [
        (None, {"data": {"authenticated": True, "expiresIn": 300}}),
        (SET_COOKIE, {"authenticated": True, "expiresIn": 300}),
        (SET_COOKIE, {"data": {"authenticated": False}}),
    ],
)
async def test_non_canonical_refresh_response_is_rejected(
    config: Any, set_cookie: Optional[str], body: Dict[str, Any]
) -> None:
    miso = RefreshTransport()
    miso.set_cookie = set_cookie
    miso.body = body
    service = make_service(config, miso)

    assert await service.refresh_browser_session(EXPIRED) is None
    assert service._memo == {}


@pytest.mark.asyncio
async def test_renewed_token_failing_validation_is_invalid(config: Any) -> None:
    miso = RefreshTransport()
    service = make_service(config, miso)
    service.auth.get_user = AsyncMock(return_value=None)

    result = await service.validate_or_refresh(EXPIRED)

    assert result == SessionCookieValidation(valid=False)


@pytest.mark.asyncio
async def test_transport_failure_returns_invalid(config: Any) -> None:
    async def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic failure", request=request)

    service = make_service(config, RefreshTransport())
    service._transport = httpx.MockTransport(fail)

    assert (await service.validate_or_refresh(EXPIRED)).valid is False


@pytest.mark.asyncio
async def test_tokens_never_appear_in_logs(config: Any, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    service = make_service(config, RefreshTransport())
    await service.validate_or_refresh(EXPIRED)
    rejected = make_service(config, RefreshTransport(status=401))
    await rejected.validate_or_refresh(make_token(-60, "other-expired"))

    text = caplog.text + "".join(repr(r.__dict__) for r in caplog.records)
    for secret in (EXPIRED, RENEWED, "client-token"):
        assert secret not in text
    assert RENEWED not in repr(await service.validate_or_refresh(EXPIRED))


def test_bearer_header_is_never_read_as_session_cookie() -> None:
    bearer_only = SimpleNamespace(headers={"authorization": f"Bearer {EXPIRED}"}, cookies={})
    with_cookie = SimpleNamespace(cookies={SESSION_COOKIE_NAME: f" {EXPIRED} "})

    assert get_session_cookie_token(bearer_only) is None
    assert get_session_cookie_token(SimpleNamespace()) is None
    assert get_session_cookie_token(with_cookie) == EXPIRED


@pytest.mark.asyncio
async def test_missing_token_never_refreshes(config: Any) -> None:
    miso = RefreshTransport()
    service = make_service(config, miso)

    assert (await service.validate_or_refresh(None)).valid is False
    assert miso.requests == []


def test_is_token_expired_uses_leeway() -> None:
    assert is_token_expired(make_token(10, "near")) is True
    assert is_token_expired(make_token(10, "near"), leeway_seconds=0) is False
    assert is_token_expired("not-a-jwt") is False


def test_session_cookie_headers_are_masked() -> None:
    assert DataMasker.is_sensitive_field("cookie")
    assert DataMasker.is_sensitive_field("set-cookie")


def test_apply_session_cookie_appends_header() -> None:
    added: List[tuple] = []
    response = SimpleNamespace(headers=SimpleNamespace(append=lambda k, v: added.append((k, v))))
    result = SessionCookieValidation(valid=True, token=RENEWED, set_cookie=SET_COOKIE)

    assert apply_session_cookie(response, result) is True
    assert apply_session_cookie(response, SessionCookieValidation(valid=True)) is False
    assert apply_session_cookie(response, None) is False
    assert added == [("set-cookie", SET_COOKIE)]


@pytest.mark.asyncio
async def test_misoclient_delegates_and_keeps_shared_cookie_jar_clean(config: Any) -> None:
    client = MisoClient(config)
    miso = RefreshTransport()
    service = BrowserSessionRefreshService(client.http_client, client.auth, miso.transport())
    client._browser_session = service
    client.http_client.get_environment_token = AsyncMock(return_value="client-token")
    client.auth.get_user = AsyncMock(return_value=USER)

    result = await client.validate_or_refresh_session_cookie(EXPIRED)

    assert result.valid and result.set_cookie == SET_COOKIE
    shared = client.http_client.get_internal_client().client
    assert shared is None or not shared.cookies
    request = SimpleNamespace(cookies={SESSION_COOKIE_NAME: EXPIRED})
    assert client.get_session_cookie_token(request) == EXPIRED
    await client.disconnect()


@pytest.mark.asyncio
async def test_misoclient_refresh_session_cookie_skips_validation(config: Any) -> None:
    client = MisoClient(config)
    miso = RefreshTransport()
    client._browser_session = BrowserSessionRefreshService(
        client.http_client, client.auth, miso.transport()
    )
    client.http_client.get_environment_token = AsyncMock(return_value="client-token")
    get_user = AsyncMock(return_value=USER)
    client.auth.get_user = get_user

    refreshed = await client.refresh_session_cookie(EXPIRED)

    assert refreshed is not None
    assert refreshed.access_token == RENEWED and refreshed.set_cookie == SET_COOKIE
    assert refreshed.expires_in == 300
    get_user.assert_not_awaited()
    await client.disconnect()
