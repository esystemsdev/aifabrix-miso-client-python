"""Internal HTTP client utility for controller communication.

This module provides the internal HTTP client implementation with automatic client
token management. This class is not meant to be used directly - use the public
HttpClient class instead which adds ISO 27001 compliant audit and debug logging.
"""

import asyncio
from types import TracebackType
from typing import Any, Awaitable, Callable, Dict, Literal, Optional, Tuple, Type, cast

import httpx

from ..errors import AuthenticationError, ConnectionError, MisoClientError
from ..models.config import AuthMethod, AuthStrategy, MisoClientConfig
from .auth_strategy import AuthStrategyHandler
from .client_token_manager import ClientTokenManager
from .controller_url_resolver import resolve_controller_url
from .http_error_handler import detect_auth_method_from_headers, parse_error_response


class InternalHttpClient:
    """Internal HTTP client for Miso Controller communication.

    Provides automatic client token management. This class contains the core HTTP
    functionality without logging. Wrapped by HttpClient which adds audit logging.
    """

    def __init__(self, config: MisoClientConfig):
        """Initialize internal HTTP client with configuration.

        Args:
            config: MisoClient configuration

        """
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None
        self.token_manager = ClientTokenManager(config)

    async def _initialize_client(self) -> None:
        """Initialize HTTP client if not already initialized."""
        if self.client is None:
            # Use resolved URL (controllerPrivateUrl or controller_url)
            resolved_url = resolve_controller_url(self.config)
            self.client = httpx.AsyncClient(
                base_url=resolved_url,
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                },
            )

    async def _ensure_client_token(self) -> None:
        """Ensure client token is set in headers."""
        await self._initialize_client()
        token = await self.token_manager.get_client_token()
        if self.client:
            self.client.headers["x-client-token"] = token

    async def close(self) -> None:
        """Close the HTTP client."""
        if self.client:
            try:
                await self.client.aclose()
            except (RuntimeError, asyncio.CancelledError):
                # Event loop closed or cancelled - that's okay during teardown
                pass
            except Exception:
                # Ignore any other errors during cleanup
                pass
            finally:
                self.client = None

    async def __aenter__(self) -> "InternalHttpClient":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Async context manager exit."""
        await self.close()

    def _create_error_from_http_status(
        self,
        error: httpx.HTTPStatusError,
        url: str,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> MisoClientError:
        """Create MisoClientError from HTTP status error with auth metadata."""
        error_response = parse_error_response(error.response, url)
        error_body = self._extract_error_body(error, error_response)
        auth_method = self._detect_auth_method(error, error_response, request_headers)
        return MisoClientError(
            f"HTTP {error.response.status_code}: {error.response.text}",
            status_code=error.response.status_code,
            error_body=error_body,
            error_response=error_response,
            auth_method=auth_method,
        )

    def _extract_error_body(
        self, error: httpx.HTTPStatusError, error_response: Any
    ) -> Dict[str, Any]:
        """Extract JSON body when structured parser returned no response."""
        if error_response:
            return {}
        content_type = error.response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return {}
        try:
            parsed = error.response.json()
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _detect_auth_method(
        self,
        error: httpx.HTTPStatusError,
        error_response: Any,
        request_headers: Optional[Dict[str, str]],
    ) -> Optional[AuthMethod]:
        """Detect auth method for 401 responses from payload or request headers."""
        if error.response.status_code != 401:
            return None
        if error_response and error_response.authMethod in [
            "bearer",
            "client-token",
            "client-credentials",
            "api-key",
        ]:
            return cast(AuthMethod, error_response.authMethod)
        return detect_auth_method_from_headers(request_headers)

    def _request_headers_for_error(
        self, kwargs: Dict[str, Any], fallback_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Build merged request headers for downstream error metadata."""
        request_headers = dict(self.client.headers) if self.client else {}
        if fallback_headers:
            request_headers.update(fallback_headers)
        request_headers.update(kwargs.get("headers", {}))
        return request_headers

    def _extract_body_kwargs(
        self, data: Optional[Dict[str, Any]], kwargs: Dict[str, Any]
    ) -> Tuple[Optional[Any], Optional[Any], Optional[Any], Optional[Any]]:
        """Pop and normalize body-related kwargs to avoid duplicate payload args."""
        json_from_kwargs = kwargs.pop("json", None)
        content = kwargs.pop("content", None)
        data_from_kwargs = kwargs.pop("data", None)
        files = kwargs.pop("files", None)
        json_body = data if data is not None else json_from_kwargs
        return json_body, content, data_from_kwargs, files

    async def _dispatch_with_body(
        self,
        method: Literal["post", "put"],
        url: str,
        json_body: Optional[Any],
        content: Optional[Any],
        data_from_kwargs: Optional[Any],
        files: Optional[Any],
        kwargs: Dict[str, Any],
    ) -> httpx.Response:
        """Dispatch POST/PUT request with one selected body style."""
        assert self.client is not None
        caller = cast(Callable[..., Awaitable[httpx.Response]], getattr(self.client, method))
        if json_body is not None:
            return await caller(url, json=json_body, **kwargs)
        if content is not None:
            return await caller(url, content=content, **kwargs)
        if data_from_kwargs is not None:
            return await caller(url, data=data_from_kwargs, **kwargs)
        if files is not None:
            return await caller(url, files=files, **kwargs)
        return await caller(url, **kwargs)

    def _clear_token_if_unauthorized(self, response: httpx.Response) -> None:
        """Clear cached client token when response indicates unauthorized access."""
        if response.status_code == 401:
            self.token_manager.clear_token()

    async def get(self, url: str, **kwargs: Any) -> Any:
        """Make GET request."""
        return await self._execute_no_body_request("get", url, kwargs)

    async def post(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        """Make POST request."""
        return await self._execute_body_request("post", url, data, kwargs)

    async def _execute_body_request(
        self,
        method: Literal["post", "put"],
        url: str,
        data: Optional[Dict[str, Any]],
        kwargs: Dict[str, Any],
    ) -> Any:
        """Execute request with optional body payload and shared error handling."""
        await self._initialize_client()
        await self._ensure_client_token()
        json_body, content, data_from_kwargs, files = self._extract_body_kwargs(data, kwargs)
        try:
            response = await self._dispatch_with_body(
                method, url, json_body, content, data_from_kwargs, files, kwargs
            )
            self._clear_token_if_unauthorized(response)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise self._create_error_from_http_status(
                e, url, self._request_headers_for_error(kwargs)
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def put(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        """Make PUT request."""
        return await self._execute_body_request("put", url, data, kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        """Make DELETE request."""
        return await self._execute_no_body_request("delete", url, kwargs)

    async def _execute_no_body_request(
        self, method: Literal["get", "delete"], url: str, kwargs: Dict[str, Any]
    ) -> Any:
        """Execute GET/DELETE request using shared error-handling flow."""
        await self._initialize_client()
        await self._ensure_client_token()
        try:
            assert self.client is not None
            caller = getattr(self.client, method)
            response = await caller(url, **kwargs)
            self._clear_token_if_unauthorized(response)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise self._create_error_from_http_status(
                e, url, self._request_headers_for_error(kwargs)
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Generic request method."""
        method_upper = method.upper()
        handler_map = {
            "GET": lambda: self.get(url, **kwargs),
            "POST": lambda: self.post(url, data, **kwargs),
            "PUT": lambda: self.put(url, data, **kwargs),
            "DELETE": lambda: self.delete(url, **kwargs),
        }
        handler = handler_map.get(method_upper)
        if handler is None:
            raise ValueError(f"Unsupported HTTP method: {method}")
        return await handler()

    async def authenticated_request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
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
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Make request using auth strategy fallback order."""
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
        method: Literal["GET", "POST", "PUT", "DELETE"],
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
            except httpx.HTTPStatusError as error:
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
        self, error: httpx.HTTPStatusError, auth_method: AuthMethod
    ) -> bool:
        """Handle strategy HTTP errors and return whether fallback should continue."""
        if error.response.status_code != 401:
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
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        auth_method: AuthMethod,
        client_token: Optional[str],
        data: Optional[Dict[str, Any]],
        request_kwargs: Dict[str, Any],
    ) -> Any:
        """Attempt a request using one authentication method."""
        auth_headers = AuthStrategyHandler.build_auth_headers(
            auth_method, auth_strategy, client_token
        )
        kwargs_with_auth = self._merge_auth_headers(request_kwargs, auth_headers)
        return await self.request(method, url, data, **kwargs_with_auth)

    def _clear_client_token_on_401(self, auth_method: AuthMethod) -> None:
        """Clear cached client token when client auth methods receive 401."""
        if auth_method in ["client-token", "client-credentials"]:
            self.token_manager.clear_token()

    def _raise_all_auth_methods_failed(self, last_error: Optional[Exception]) -> None:
        """Raise final strategy failure when all methods are exhausted."""
        if last_error is None:
            raise AuthenticationError("No authentication methods available")

        status_code = getattr(last_error, "status_code", 401)
        error_response = getattr(last_error, "error_response", None)
        raise MisoClientError(
            f"All authentication methods failed. Last error: {str(last_error)}",
            status_code=status_code,
            error_response=error_response,
        )

    async def get_environment_token(self) -> str:
        """Get environment token using client credentials.

        This is called automatically by HttpClient but can be called manually.

        Returns:
            Client token string

        """
        return await self.token_manager.get_client_token()
