"""Internal HTTP client utility for controller communication.

This module provides the internal HTTP client implementation with automatic client
token management. This class is not meant to be used directly - use the public
HttpClient class instead which adds ISO 27001 compliant audit and debug logging.
"""

import asyncio
import json
from types import TracebackType
from typing import Any, Awaitable, Callable, Dict, Literal, Optional, Tuple, Type, cast

import httpx

from ..errors import ConnectionError, MisoClientError
from ..models.config import AuthMethod, MisoClientConfig
from .bootstrap_auth import handle_bootstrap_auth_response
from .bootstrap_request_policy import ManagedRequestPolicy
from .client_token_manager import ClientTokenManager
from .controller_url_resolver import resolve_controller_url
from .http_error_handler import detect_auth_method_from_headers, parse_error_response
from .http_error_sanitizer import safe_error_body, safe_error_text
from .internal_http_auth_strategy import AuthStrategyRequestsMixin
from .request_target import RequestTarget, build_external_client


def _parse_optional_json_response(response: httpx.Response) -> Any:
    """Return JSON object or ``{}`` when the body is empty or not JSON (e.g. DELETE 204)."""
    raw = response.content or b""
    if not raw.strip():
        return {}
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError):
        return {}


class InternalHttpClient(AuthStrategyRequestsMixin):
    """Internal HTTP client for Miso Controller communication.

    Provides automatic client token management. This class contains the core HTTP
    functionality without logging. Wrapped by HttpClient which adds audit logging.

    Requests are routed by target origin (:class:`RequestTarget`): controller
    targets carry the client token (and the managed origin pin); external
    targets travel on a plain transport that carries no SDK credential.
    """

    def __init__(self, config: MisoClientConfig):
        """Initialize internal HTTP client with configuration.

        Args:
            config: MisoClient configuration

        """
        self.config = config
        self._managed_policy = (
            ManagedRequestPolicy(config.controller_url)
            if config.application_token_provider is not None
            else None
        )
        self.client: Optional[httpx.AsyncClient] = None
        self._external: Optional[httpx.AsyncClient] = None
        self._target = RequestTarget(config)
        self.token_manager = ClientTokenManager(config)

    async def _initialize_client(self) -> None:
        """Initialize HTTP client if not already initialized."""
        if self.config.runtime_guard is not None:
            self.config.runtime_guard()
        if self.client is None:
            # Use resolved URL (controllerPrivateUrl or controller_url)
            resolved_url = resolve_controller_url(self.config)
            self.client = httpx.AsyncClient(
                base_url=resolved_url,
                timeout=30.0,
                trust_env=self._managed_policy is None,
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

    async def _prepare_request(
        self, url: str, kwargs: Dict[str, Any]
    ) -> Tuple[httpx.AsyncClient, bool]:
        """Pick the transport for ``url`` and attach credentials only for the controller.

        Returns ``(client, is_controller)``. External targets never see the client
        token: no lookup, no header, no origin pin, no bootstrap response handling.
        """
        await self._initialize_client()
        assert self.client is not None
        if not self._target.is_controller(url):
            self._target.strip_sdk_credentials(kwargs)
            return self._external_client(), False
        if self._managed_policy is not None:
            self._managed_policy.prepare(self.client.base_url, url, kwargs)
        await self._ensure_client_token()
        return self.client, True

    def _external_client(self) -> httpx.AsyncClient:
        if self._external is None:
            timeout = self.client.timeout if self.client is not None else 30.0
            self._external = build_external_client(timeout)
        return self._external

    async def close(self) -> None:
        """Close both transports."""
        await self.token_manager.close()
        clients = [c for c in (self.client, self._external) if c is not None]
        self.client, self._external = None, None
        for client in clients:
            try:
                await client.aclose()
            except (RuntimeError, asyncio.CancelledError):
                # Event loop closed or cancelled - that's okay during teardown
                return
            except Exception:
                # Ignore any other errors during cleanup
                return

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
        controller: bool = True,
    ) -> MisoClientError:
        """Create MisoClientError from HTTP status error with auth metadata.

        Managed errors expose only sanitized controller diagnostics; external
        provider explanations also mask sensitive fields and known credentials.
        """
        managed = controller and self.config.application_token_provider is not None
        error_body = safe_error_body(
            error.response,
            (self.config.client_secret or "", self.config.encryption_key or ""),
            managed,
        )
        error_response = parse_error_response(error.response, url, error_body)
        if error_response is not None:
            error_response.statusCode = error.response.status_code
        auth_method = self._detect_auth_method(error, error_response, request_headers)
        message = (
            "Managed runtime request failed" if managed else f"HTTP {error.response.status_code}"
        )
        if error_body:
            message += ": " + json.dumps(error_body)
        elif not managed:
            message += ": " + safe_error_text(
                error.response, (self.config.client_secret or "", self.config.encryption_key or "")
            )
        return MisoClientError(
            message,
            status_code=error.response.status_code,
            error_body=error_body,
            error_response=error_response,
            auth_method=auth_method,
        )

    def _connection_error(
        self, error: httpx.RequestError, controller: bool = True
    ) -> MisoClientError:
        """Omit raw bootstrap runtime request objects and messages from diagnostics."""
        if controller and self.config.application_token_provider is not None:
            return ConnectionError("Managed runtime request failed")
        return ConnectionError(f"Request failed: {str(error)}")

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
        self,
        kwargs: Dict[str, Any],
        fallback_headers: Optional[Dict[str, str]] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Dict[str, str]:
        """Build merged request headers for downstream error metadata."""
        source = client if client is not None else self.client
        request_headers = dict(source.headers) if source else {}
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
        method: Literal["post", "put", "patch"],
        url: str,
        json_body: Optional[Any],
        content: Optional[Any],
        data_from_kwargs: Optional[Any],
        files: Optional[Any],
        kwargs: Dict[str, Any],
        client: httpx.AsyncClient,
    ) -> httpx.Response:
        """Dispatch POST/PUT/PATCH request with one selected body style."""
        caller = cast(Callable[..., Awaitable[httpx.Response]], getattr(client, method))
        if json_body is not None:
            return await caller(url, json=json_body, **kwargs)
        if content is not None:
            return await caller(url, content=content, **kwargs)
        if data_from_kwargs is not None:
            return await caller(url, data=data_from_kwargs, **kwargs)
        if files is not None:
            return await caller(url, files=files, **kwargs)
        return await caller(url, **kwargs)

    async def _handle_token_response(self, response: httpx.Response) -> None:
        """Separate application identity failures from ordinary user/RBAC errors."""
        provider = self.config.application_token_provider
        if provider is not None:
            await handle_bootstrap_auth_response(response, provider)
        elif response.status_code == 401:
            self.token_manager.clear_token()

    async def get(self, url: str, **kwargs: Any) -> Any:
        """Make GET request."""
        return await self._execute_no_body_request("get", url, kwargs)

    async def post(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        """Make POST request."""
        return await self._execute_body_request("post", url, data, kwargs)

    async def _execute_body_request(
        self,
        method: Literal["post", "put", "patch"],
        url: str,
        data: Optional[Dict[str, Any]],
        kwargs: Dict[str, Any],
    ) -> Any:
        """Execute request with optional body payload and shared error handling."""
        client, controller = await self._prepare_request(url, kwargs)
        json_body, content, data_from_kwargs, files = self._extract_body_kwargs(data, kwargs)
        try:
            response = await self._dispatch_with_body(
                method, url, json_body, content, data_from_kwargs, files, kwargs, client
            )
            if controller:
                await self._handle_token_response(response)
            response.raise_for_status()
            return _parse_optional_json_response(response)
        except httpx.HTTPStatusError as e:
            failure = self._create_error_from_http_status(
                e, url, self._request_headers_for_error(kwargs, client=client), controller
            )
        except httpx.RequestError as e:
            failure = self._connection_error(e, controller)
        raise failure

    async def put(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        """Make PUT request."""
        return await self._execute_body_request("put", url, data, kwargs)

    async def patch(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Any:
        """Make PATCH request (e.g. HubSpot CRM partial updates)."""
        return await self._execute_body_request("patch", url, data, kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        """Make DELETE request."""
        return await self._execute_no_body_request("delete", url, kwargs)

    async def _execute_no_body_request(
        self, method: Literal["get", "delete"], url: str, kwargs: Dict[str, Any]
    ) -> Any:
        """Execute GET/DELETE request using shared error-handling flow."""
        client, controller = await self._prepare_request(url, kwargs)
        try:
            caller = getattr(client, method)
            response = await caller(url, **kwargs)
            if controller:
                await self._handle_token_response(response)
            response.raise_for_status()
            if method == "delete":
                return _parse_optional_json_response(response)
            return response.json()
        except httpx.HTTPStatusError as e:
            failure = self._create_error_from_http_status(
                e, url, self._request_headers_for_error(kwargs, client=client), controller
            )
        except httpx.RequestError as e:
            failure = self._connection_error(e, controller)
        raise failure

    async def get_raw(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make GET request and return the raw ``httpx.Response`` (no ``.json()`` parsing).

        Use for binary bodies (file downloads, Graph ``/content`` after redirects) where
        :meth:`get` would raise ``UnicodeDecodeError`` or ``json.JSONDecodeError``.
        """
        client, controller = await self._prepare_request(url, kwargs)
        try:
            response = await client.get(url, **kwargs)
            if controller:
                await self._handle_token_response(response)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            failure = self._create_error_from_http_status(
                e, url, self._request_headers_for_error(kwargs, client=client), controller
            )
        except httpx.RequestError as e:
            failure = self._connection_error(e, controller)
        raise failure

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
        url: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Generic request method."""
        raw_method = getattr(method, "value", method)
        method_upper = str(raw_method).strip().upper()
        handler_map = {
            "GET": lambda: self.get(url, **kwargs),
            "POST": lambda: self.post(url, data, **kwargs),
            "PUT": lambda: self.put(url, data, **kwargs),
            "PATCH": lambda: self.patch(url, data, **kwargs),
            "DELETE": lambda: self.delete(url, **kwargs),
        }
        handler = handler_map.get(method_upper)
        if handler is None:
            raise ValueError(f"Unsupported HTTP method: {raw_method!r}")
        return await handler()

    async def get_environment_token(self) -> str:
        """Get environment token using client credentials.

        This is called automatically by HttpClient but can be called manually.

        Returns:
            Client token string

        """
        return await self.token_manager.get_client_token()
