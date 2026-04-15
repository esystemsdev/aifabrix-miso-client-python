"""Client token manager for InternalHttpClient.

This module provides client token management functionality including token fetching,
caching, and correlation ID extraction.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

from ..errors import AuthenticationError, ConnectionError
from ..models.config import ClientTokenResponse, MisoClientConfig
from .controller_url_resolver import resolve_controller_url
from .jwt_tools import decode_token

CORRELATION_HEADERS = [
    "x-correlation-id",
    "x-request-id",
    "correlation-id",
    "correlationId",
    "x-correlationid",
    "request-id",
]


class ClientTokenManager:
    """Manages client token lifecycle including fetching, caching, and expiration.

    This class handles all client token operations for InternalHttpClient.
    """

    def __init__(self, config: MisoClientConfig):
        """Initialize client token manager.

        Args:
            config: MisoClient configuration

        """
        self.config = config
        self.client_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.token_refresh_lock = asyncio.Lock()

    def extract_correlation_id(self, response: Optional[httpx.Response] = None) -> Optional[str]:
        """Extract correlation ID from response headers."""
        if not response:
            return None

        for header_name in CORRELATION_HEADERS:
            correlation_id = response.headers.get(header_name) or response.headers.get(
                header_name.lower()
            )
            if correlation_id:
                return str(correlation_id)

        return None

    def _is_token_valid(self, now: Optional[datetime] = None) -> bool:
        """Return True when cached client token is still valid."""
        current_time = now or datetime.now()
        return bool(
            self.client_token and self.token_expires_at and self.token_expires_at > current_time
        )

    def _build_auth_error_message(
        self, base: str, client_id: str, correlation_id: Optional[str]
    ) -> str:
        """Build consistent auth error message with optional context."""
        error_msg = base
        if client_id:
            error_msg += f" (clientId: {client_id})"
        if correlation_id:
            error_msg += f" (correlationId: {correlation_id})"
        return error_msg

    def _create_temp_client(self, client_id: str) -> httpx.AsyncClient:
        """Create temporary client for token endpoint without interceptor recursion."""
        resolved_url = resolve_controller_url(self.config)
        return httpx.AsyncClient(
            base_url=resolved_url,
            timeout=30.0,
            headers={
                "Content-Type": "application/json",
                "x-client-id": client_id,
                "x-client-secret": self.config.client_secret,
            },
        )

    async def _request_token_response(self, client_id: str) -> httpx.Response:
        """Request raw token response from controller."""
        token_uri = self.config.clientTokenUri or "/api/v1/auth/token"
        temp_client = self._create_temp_client(client_id)
        try:
            return await temp_client.post(token_uri)
        finally:
            await temp_client.aclose()

    def _normalize_token_response_data(self, payload: object) -> dict:
        """Normalize token response payload with nested-data support."""
        if not isinstance(payload, dict):
            return {}
        data = dict(payload)
        if "data" in data and isinstance(data["data"], dict):
            nested_data = dict(data["data"])
            if "success" in data:
                nested_data["success"] = data["success"]
            return nested_data
        return data

    def _ensure_token_defaults(self, data: dict) -> dict:
        """Ensure response has success and expiresIn defaults when token is present."""
        result = dict(data)
        if "token" not in result:
            return result
        if "success" not in result:
            result["success"] = True
        if "expiresIn" not in result and "expiresAt" in result:
            result["expiresIn"] = self._expires_in_from_expires_at(result.get("expiresAt"))
        return result

    @staticmethod
    def _expires_in_from_expires_at(expires_at_raw: object) -> int:
        """Convert expiresAt ISO string to expiresIn seconds."""
        try:
            if not isinstance(expires_at_raw, str):
                return 1800
            expires_at = datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
            now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
            return max(0, int((expires_at - now).total_seconds()))
        except Exception:
            return 1800

    def _expires_in_from_token_claims(self, token: str) -> int:
        """Calculate expiresIn from JWT exp claim, or default."""
        try:
            decoded = decode_token(token)
            if decoded and "exp" in decoded and isinstance(decoded["exp"], (int, float)):
                token_exp = datetime.fromtimestamp(decoded["exp"])
                now = datetime.now()
                return max(0, int((token_exp - now).total_seconds()))
        except Exception:
            pass
        return 1800

    def _resolve_expires_in(self, token_response: ClientTokenResponse) -> int:
        """Resolve token lifetime in seconds."""
        expires_in = token_response.expiresIn
        if expires_in and expires_in > 0:
            return expires_in
        return self._expires_in_from_token_claims(token_response.token)

    def _store_token_with_expiration(self, token_response: ClientTokenResponse) -> None:
        """Store token and computed expiration with safety buffer."""
        self.client_token = token_response.token
        expires_in = max(0, self._resolve_expires_in(token_response) - 30)
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

    def _validate_http_status(
        self, response: httpx.Response, client_id: str, correlation_id: Optional[str]
    ) -> None:
        """Validate token endpoint HTTP status."""
        if response.status_code in [200, 201]:
            return
        error_msg = self._build_auth_error_message(
            f"Failed to get client token: HTTP {response.status_code}",
            client_id,
            correlation_id,
        )
        raise AuthenticationError(
            error_msg,
            status_code=response.status_code,
            auth_method="client-credentials",
        )

    def _validate_token_response(
        self, token_response: ClientTokenResponse, client_id: str, correlation_id: Optional[str]
    ) -> None:
        """Validate semantic token response contents."""
        if token_response.success and token_response.token:
            return
        error_msg = self._build_auth_error_message(
            "Failed to get client token: Invalid response", client_id, correlation_id
        )
        raise AuthenticationError(error_msg, auth_method="client-credentials")

    async def get_client_token(self) -> str:
        """Get client token, fetching if needed.

        Returns cached token while it is not expired so that the same token
        is reused for all client-credential requests (e.g. logger and application
        status). Refetches only when token is actually expired (or missing).

        Returns:
            Client token string

        Raises:
            AuthenticationError: If token fetch fails

        """
        now = datetime.now()
        if self._is_token_valid(now):
            assert self.client_token is not None
            return self.client_token

        async with self.token_refresh_lock:
            if self._is_token_valid(now):
                assert self.client_token is not None
                return self.client_token

            await self.fetch_client_token()
            assert self.client_token is not None
            return self.client_token

    async def fetch_client_token(self) -> None:
        """Fetch and cache client token from controller."""
        client_id = self.config.client_id
        response: Optional[httpx.Response] = None
        correlation_id: Optional[str] = None

        try:
            response = await self._request_token_response(client_id)
            correlation_id = self.extract_correlation_id(response)
            self._validate_http_status(response, client_id, correlation_id)
            data = self._normalize_token_response_data(response.json())
            token_response = ClientTokenResponse(**self._ensure_token_defaults(data))
            self._validate_token_response(token_response, client_id, correlation_id)
            self._store_token_with_expiration(token_response)
        except httpx.HTTPError as error:
            error_msg = self._build_auth_error_message(
                f"Failed to get client token: {str(error)}", client_id, correlation_id
            )
            raise ConnectionError(error_msg)
        except Exception as error:
            if isinstance(error, (AuthenticationError, ConnectionError)):
                raise
            error_msg = self._build_auth_error_message(
                f"Failed to get client token: {str(error)}", client_id, correlation_id
            )
            raise AuthenticationError(error_msg, auth_method="client-credentials")

    def clear_token(self) -> None:
        """Clear cached client token.

        Forces token refresh on next request.
        """
        self.client_token = None
        self.token_expires_at = None
