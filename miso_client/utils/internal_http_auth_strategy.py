"""Auth-strategy request flow for :class:`InternalHttpClient` (split for file size)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Literal, NoReturn, Optional, Tuple

import httpx

from ..errors import AuthenticationError, ConnectionError, MisoClientError
from ..models.config import AuthMethod, AuthStrategy
from .auth_strategy import AuthStrategyHandler
from .bootstrap_auth import BOOTSTRAP_AUTH_ERRORS

if TYPE_CHECKING:
    from ..models.config import MisoClientConfig
    from .client_token_manager import ClientTokenManager


class AuthStrategyRequestsMixin:
    """Bearer/client-token strategy requests; every attempt goes through ``self.request``
    and therefore through the same origin routing as plain requests."""

    config: "MisoClientConfig"
    token_manager: "ClientTokenManager"

    async def request(
        self, method: Any, url: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Any:  # pragma: no cover - provided by InternalHttpClient
        raise NotImplementedError

    async def _initialize_client(self) -> None:  # pragma: no cover - provided by InternalHttpClient
        raise NotImplementedError

    async def authenticated_request(
        self,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        url: str,
        token: str,
        data: Optional[Dict[str, Any]] = None,
        auth_strategy: Optional[AuthStrategy] = None,
        **kwargs: Any,
    ) -> Any:
        """Make authenticated request with Bearer token."""
        auth_strategy = self._resolve_auth_strategy(token, auth_strategy)
        return await self.request_with_auth_strategy(method, url, auth_strategy, data, **kwargs)

    def _resolve_auth_strategy(
        self, token: str, auth_strategy: Optional[AuthStrategy]
    ) -> AuthStrategy:
        """Resolve or create auth strategy and inject bearer token."""
        resolved = auth_strategy or AuthStrategyHandler.get_default_strategy()
        resolved.bearerToken = token
        return resolved

    async def request_with_auth_strategy(
        self,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Make request using auth strategy fallback order."""
        if self.config.runtime_guard is not None:
            self.config.runtime_guard()
        await self._initialize_client()
        client_token = await self._resolve_client_token_for_auth_strategy(auth_strategy)
        succeeded, result, last_error = await self._try_auth_methods(
            method, url, auth_strategy, client_token, data, kwargs
        )
        if succeeded:
            return result
        self._raise_all_auth_methods_failed(last_error)

    async def _try_auth_methods(
        self,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        client_token: Optional[str],
        data: Optional[Dict[str, Any]],
        request_kwargs: Dict[str, Any],
    ) -> Tuple[bool, Any, Optional[Exception]]:
        """Try strategy methods in priority order and capture last auth-related error."""
        last_error: Optional[Exception] = None
        for auth_method in auth_strategy.methods:
            try:
                result = await self._request_with_single_auth_method(
                    method, url, auth_strategy, auth_method, client_token, data, request_kwargs
                )
                return True, result, None
            except (MisoClientError, httpx.HTTPStatusError) as error:
                should_continue = self._handle_auth_method_http_error(error, auth_method)
                if should_continue:
                    last_error = error
                    continue
                raise
            except httpx.RequestError as error:
                raise ConnectionError(f"Request failed: {str(error)}")
            except ValueError as error:
                last_error = error
                continue
        return False, None, last_error

    def _handle_auth_method_http_error(
        self, error: MisoClientError | httpx.HTTPStatusError, auth_method: AuthMethod
    ) -> bool:
        """Handle strategy HTTP errors and return whether fallback should continue."""
        status = (
            error.status_code if isinstance(error, MisoClientError) else error.response.status_code
        )
        if (
            isinstance(error, MisoClientError)
            and (error.error_body or {}).get("code") in BOOTSTRAP_AUTH_ERRORS
        ):
            return False
        if status != 401:
            return False
        self._clear_client_token_on_401(auth_method)
        return True

    async def _resolve_client_token_for_auth_strategy(
        self, auth_strategy: AuthStrategy
    ) -> Optional[str]:
        """Resolve client token once when strategy requires client credentials."""
        if "client-token" in auth_strategy.methods or "client-credentials" in auth_strategy.methods:
            return await self.token_manager.get_client_token()
        return None

    def _merge_auth_headers(
        self, kwargs: Dict[str, Any], auth_headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Merge strategy auth headers with existing request headers."""
        request_headers = kwargs.get("headers", {}).copy()
        request_headers.update(auth_headers)
        return {**kwargs, "headers": request_headers}

    async def _request_with_single_auth_method(
        self,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        auth_method: AuthMethod,
        client_token: Optional[str],
        data: Optional[Dict[str, Any]],
        request_kwargs: Dict[str, Any],
    ) -> Any:
        """Attempt a request using one authentication method."""
        if auth_method in ("client-token", "client-credentials"):
            client_token = await self.token_manager.get_client_token()
        auth_headers = AuthStrategyHandler.build_auth_headers(
            auth_method, auth_strategy, client_token
        )
        kwargs_with_auth = self._merge_auth_headers(request_kwargs, auth_headers)
        return await self.request(method, url, data, **kwargs_with_auth)

    def _clear_client_token_on_401(self, auth_method: AuthMethod) -> None:
        """Clear cached client token when client auth methods receive 401."""
        if auth_method in ["client-token", "client-credentials"]:
            self.token_manager.clear_token()

    def _raise_all_auth_methods_failed(self, last_error: Optional[Exception]) -> NoReturn:
        """Raise final strategy failure when all methods are exhausted."""
        if last_error is None:
            raise AuthenticationError("No authentication methods available")

        status_code = getattr(last_error, "status_code", 401)
        error_response = getattr(last_error, "error_response", None)
        raise MisoClientError(
            f"All authentication methods failed. Last error: {str(last_error)}",
            status_code=status_code,
            error_response=error_response,
            error_body=getattr(last_error, "error_body", None),
            auth_method=getattr(last_error, "auth_method", None),
        )
