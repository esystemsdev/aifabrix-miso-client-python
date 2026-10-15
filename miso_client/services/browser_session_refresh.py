"""Server-side refresh of the Miso browser session cookie.

A browser that opens a consumer API link directly sends only the
``miso_access_token`` cookie. Its access token lives a few minutes; Miso keeps
the refresh token server-side and renews the cookie on bodyless
``POST /api/v1/auth/refresh``. This module lets a server-side consumer make that
call with the forwarded cookie, once per expired token, and hand the renewed
``Set-Cookie`` back to the browser.

Bearer-header tokens are never refreshed here: callers pass only the cookie
token (see :func:`get_session_cookie_token`).
"""

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, cast

import httpx

from ..models.session_cookie import BrowserSessionRefresh, SessionCookieValidation
from ..utils.controller_url_resolver import resolve_controller_url
from ..utils.jwt_tools import decode_token
from ..utils.shared_task import await_shared

if TYPE_CHECKING:
    from ..services.auth import AuthService
    from ..utils.http_client import HttpClient

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "miso_access_token"
REFRESH_ENDPOINT = "/api/v1/auth/refresh"
# Refresh slightly before ``exp`` so clock skew never lets Miso see an expired token
# and a cached validation (kept until ``exp - 30s``) never answers for it.
EXPIRY_LEEWAY_SECONDS = 30
# Old -> new memo lifetime when the renewed token carries no ``exp``.
DEFAULT_MEMO_SECONDS = 60
MEMO_MAX_SIZE = 1000


def token_key(token: str) -> str:
    """Return the SHA-256 hex digest used to key a token without storing it."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_exp(token: str) -> Optional[float]:
    """Return the ``exp`` claim as a number, or None when absent or undecodable."""
    decoded = decode_token(token)
    exp = decoded.get("exp") if decoded else None
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        return None
    return float(exp)


def is_token_expired(token: str, leeway_seconds: int = EXPIRY_LEEWAY_SECONDS) -> bool:
    """Return True when the token's ``exp`` is within ``leeway_seconds`` of now.

    Tokens without a readable ``exp`` are treated as not expired, so they take
    the normal validation path and are never refreshed.
    """
    exp = _token_exp(token)
    return exp is not None and exp <= time.time() + leeway_seconds


def get_session_cookie_token(request: Any) -> Optional[str]:
    """Read the ``miso_access_token`` cookie from a FastAPI/Starlette/Flask request.

    Args:
        request: Framework request object exposing a ``cookies`` mapping

    Returns:
        Cookie token, or None when the cookie is missing or empty

    """
    cookies = getattr(request, "cookies", None)
    value = cookies.get(SESSION_COOKIE_NAME) if cookies is not None else None
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _find_session_cookie(response: httpx.Response) -> Optional[Tuple[str, str]]:
    """Return ``(token, raw Set-Cookie header)`` for the session cookie, if present."""
    for header in response.headers.get_list("set-cookie"):
        name, _, rest = header.partition("=")
        if name.strip() != SESSION_COOKIE_NAME:
            continue
        value = rest.split(";", 1)[0].strip()
        if value:
            return value, header
    return None


def _parse_refresh_response(response: httpx.Response) -> Optional[BrowserSessionRefresh]:
    """Parse the canonical refresh response: ``data.authenticated`` plus session cookie."""
    body: object = response.json()
    raw_data = cast(Dict[str, Any], body).get("data") if isinstance(body, dict) else None
    data = cast(Dict[str, Any], raw_data) if isinstance(raw_data, dict) else None
    if data is None or data.get("authenticated") is not True:
        logger.warning("Browser session refresh returned an unexpected response shape")
        return None
    cookie = _find_session_cookie(response)
    if cookie is None:
        logger.warning("Browser session refresh returned no session cookie")
        return None
    expires_in = data.get("expiresIn")
    return BrowserSessionRefresh(
        access_token=cookie[0],
        expires_in=expires_in if isinstance(expires_in, int) else None,
        set_cookie=cookie[1],
    )


class BrowserSessionRefreshService:
    """Validate cookie tokens and renew expired ones through Miso's session refresh.

    Concurrent requests carrying the same expired cookie share one refresh. Miso
    deletes the previous session on rotation, so the renewed session is kept in
    an in-process memo (keyed by SHA-256 of the old token) until the new token
    expires; later requests that still carry the old cookie reuse it.
    """

    def __init__(
        self,
        http_client: "HttpClient",
        auth: "AuthService",
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        """Initialize the service.

        Args:
            http_client: HTTP client (supplies config and the client token)
            auth: Auth service used to validate tokens
            transport: Optional httpx transport (tests)

        """
        self.config = http_client.config
        self.http_client = http_client
        self.auth = auth
        self._transport = transport
        self._inflight: Dict[str, "asyncio.Task[Optional[BrowserSessionRefresh]]"] = {}
        self._memo: "OrderedDict[str, Tuple[BrowserSessionRefresh, float]]" = OrderedDict()

    async def validate_or_refresh(self, token: Optional[str]) -> SessionCookieValidation:
        """Validate a cookie token, renewing the browser session when it has expired.

        Only expiry triggers a refresh; any other validation failure is returned
        as invalid without calling Miso's refresh.

        Args:
            token: Access token from the ``miso_access_token`` cookie

        Returns:
            SessionCookieValidation; ``set_cookie`` is set only when renewed

        """
        if not token:
            return SessionCookieValidation(valid=False)
        if not is_token_expired(token):
            user = await self.auth.get_user(token)
            if user is None:
                return SessionCookieValidation(valid=False)
            return SessionCookieValidation(valid=True, token=token, user=user)
        return await self._validate_refreshed(token)

    async def _validate_refreshed(self, expired_token: str) -> SessionCookieValidation:
        """Refresh the session and validate the renewed token."""
        refreshed = await self.refresh_browser_session(expired_token)
        if refreshed is None:
            return SessionCookieValidation(valid=False)
        user = await self.auth.get_user(refreshed.access_token)
        if user is None:
            logger.warning("Renewed browser session token failed validation")
            return SessionCookieValidation(valid=False)
        return SessionCookieValidation(
            valid=True,
            token=refreshed.access_token,
            user=user,
            set_cookie=refreshed.set_cookie,
            refreshed=True,
        )

    async def refresh_browser_session(
        self, expired_access_token: str
    ) -> Optional[BrowserSessionRefresh]:
        """Renew the browser session for an expired cookie token, once per token.

        Args:
            expired_access_token: Access token from the ``miso_access_token`` cookie

        Returns:
            BrowserSessionRefresh, or None when Miso has no active session or the
            refresh fails

        """
        key = token_key(expired_access_token)
        remembered = self._memo_get(key)
        if remembered is not None:
            return remembered
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.ensure_future(self._refresh_and_remember(key, expired_access_token))
            self._inflight[key] = task
            task.add_done_callback(lambda done: self._forget_inflight(key, done))
        return await await_shared(task)

    def _forget_inflight(self, key: str, task: "asyncio.Task[Any]") -> None:
        if self._inflight.get(key) is task:
            del self._inflight[key]

    async def _refresh_and_remember(
        self, key: str, expired_token: str
    ) -> Optional[BrowserSessionRefresh]:
        """Run one refresh; remember a success, swallow and log any failure."""
        try:
            response = await self._post_refresh(expired_token)
            if response.status_code != 200:
                logger.warning(
                    "Browser session refresh rejected",
                    extra={
                        "statusCode": response.status_code,
                        "correlationId": response.headers.get("x-correlation-id"),
                    },
                )
                return None
            result = _parse_refresh_response(response)
        except Exception as error:
            logger.error("Browser session refresh failed", exc_info=error)
            return None
        if result is not None:
            self._remember(key, result)
        return result

    async def _post_refresh(self, expired_token: str) -> httpx.Response:
        """POST the forwarded cookie to Miso on a short-lived client.

        The shared SDK client keeps a cookie jar; a renewed session cookie stored
        there would ride along on later controller calls, so it is never used here.
        """
        if self.config.runtime_guard is not None:
            self.config.runtime_guard()
        client_token = await self.http_client.get_environment_token()
        headers = {
            "x-client-token": client_token,
            "cookie": f"{SESSION_COOKIE_NAME}={expired_token}",
        }
        async with httpx.AsyncClient(
            base_url=resolve_controller_url(self.config),
            timeout=30.0,
            trust_env=self.config.application_token_provider is None,
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            return await client.post(REFRESH_ENDPOINT, headers=headers)

    def _memo_get(self, key: str) -> Optional[BrowserSessionRefresh]:
        entry = self._memo.get(key)
        if entry is None:
            return None
        if entry[1] <= time.time():
            del self._memo[key]
            return None
        return entry[0]

    def _remember(self, key: str, result: BrowserSessionRefresh) -> None:
        """Keep old -> new until the renewed token is about to expire."""
        exp = _token_exp(result.access_token)
        if exp is not None:
            until = exp - EXPIRY_LEEWAY_SECONDS
        else:
            until = time.time() + (result.expires_in or DEFAULT_MEMO_SECONDS)
        self._memo[key] = (result, until)
        self._memo.move_to_end(key)
        now = time.time()
        for stale in [k for k, (_, expiry) in self._memo.items() if expiry <= now]:
            del self._memo[stale]
        while len(self._memo) > MEMO_MAX_SIZE:
            self._memo.popitem(last=False)


class SessionCookieMixin:
    """MisoClient methods for browser-session cookie validation and refresh."""

    http_client: "HttpClient"
    auth: "AuthService"
    _browser_session: Optional[BrowserSessionRefreshService] = None

    def _browser_session_service(self) -> BrowserSessionRefreshService:
        if self._browser_session is None:
            self._browser_session = BrowserSessionRefreshService(self.http_client, self.auth)
        return self._browser_session

    def get_session_cookie_token(self, request: Any) -> Optional[str]:
        """Read the ``miso_access_token`` cookie token from a request."""
        return get_session_cookie_token(request)

    async def refresh_session_cookie(self, token: str) -> Optional[BrowserSessionRefresh]:
        """Renew the browser session for a cookie token without validating the result.

        For consumers that validate tokens themselves. Calls Miso even when the
        token has not expired; check :func:`is_token_expired` first. Concurrent
        calls with the same token share one refresh.

        Args:
            token: Access token from the ``miso_access_token`` cookie

        Returns:
            BrowserSessionRefresh, or None when Miso has no active session or the
            refresh fails

        """
        return await self._browser_session_service().refresh_browser_session(token)

    async def validate_or_refresh_session_cookie(
        self, token: Optional[str]
    ) -> SessionCookieValidation:
        """Validate a ``miso_access_token`` cookie token, renewing it when expired.

        Pass only the cookie token, never a Bearer-header token. When the result
        carries ``set_cookie``, add it to the response so the browser keeps the
        renewed cookie.

        Args:
            token: Access token from the ``miso_access_token`` cookie

        Returns:
            SessionCookieValidation with ``valid``, ``token``, ``user`` and
            ``set_cookie``

        Example:
            >>> token = client.get_session_cookie_token(request)
            >>> result = await client.validate_or_refresh_session_cookie(token)
            >>> if not result.valid:
            ...     raise HTTPException(status_code=401)
            >>> apply_session_cookie(response, result)

        """
        return await self._browser_session_service().validate_or_refresh(token)
