"""Public HTTP client utility for controller communication with ISO 27001 compliant logging.

This module provides the public HTTP client interface that wraps InternalHttpClient
and adds automatic audit and debug logging for all HTTP requests. All sensitive
data is automatically masked using DataMasker before logging to comply with ISO 27001.
"""

import asyncio
import time
from typing import Any, Dict, Literal, Optional, Set, Union

import httpx

from ..models.config import AuthStrategy, MisoClientConfig
from ..services.logger import LoggerService
from ..utils.jwt_tools import JwtTokenCache
from .http_client_auth_helpers import handle_401_refresh, prepare_authenticated_request
from .http_client_query_helpers import (
    add_pagination_params,
    merge_filter_params,
    parse_filter_query_string,
    parse_paginated_response,
    prepare_json_filter_body,
)
from .http_client_runtime_helpers import (
    cancel_pending_logging_tasks,
    create_logging_task,
    ensure_correlation_headers,
    wait_pending_logging_tasks,
)
from .internal_http_client import InternalHttpClient
from .user_token_refresh import UserTokenRefreshManager


class HttpClient:
    """Public HTTP client for Miso Controller communication with ISO 27001 compliant logging.

    This class wraps InternalHttpClient and adds:
    - Automatic audit logging for all requests
    - Debug logging when log_level is 'debug'
    - Automatic data masking for all sensitive information

    All sensitive data (headers, bodies, query params) is masked using DataMasker
    before logging to ensure ISO 27001 compliance.
    """

    def __init__(
        self,
        config: MisoClientConfig,
        logger: LoggerService,
        internal_client: Optional[InternalHttpClient] = None,
    ):
        """Initialize public HTTP client with configuration and logger.

        Args:
            config: MisoClient configuration
            logger: LoggerService instance for audit and debug logging
            internal_client: Optional shared InternalHttpClient (e.g. same as logger).
                When provided, all requests use this client and the same client token.

        """
        self.config = config
        self.logger = logger
        self._internal_client = (
            internal_client if internal_client is not None else InternalHttpClient(config)
        )
        self._jwt_cache = JwtTokenCache(max_size=1000)
        self._user_token_refresh = UserTokenRefreshManager()
        self._logging_tasks: Set[asyncio.Task[Any]] = set()

    async def close(self):
        """Close the HTTP client."""
        # Wait for all logging tasks to complete before closing
        # This prevents "Event loop is closed" errors during teardown
        try:
            await self._wait_for_logging_tasks(timeout=1.0)
        except (RuntimeError, asyncio.CancelledError):
            # Event loop closed or cancelled - cancel remaining tasks
            cancel_pending_logging_tasks(self._logging_tasks)
        await self._internal_client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def get_environment_token(self) -> str:
        """Get environment token using client credentials.

        This is called automatically by HttpClient but can be called manually.

        Returns:
            Client token string

        """
        return await self._internal_client.get_environment_token()

    async def _wait_for_logging_tasks(self, timeout: float = 0.5) -> None:
        """Wait for all pending logging tasks to complete.

        Useful for tests to ensure logging has finished before assertions.

        Args:
            timeout: Maximum time to wait in seconds

        """
        await wait_pending_logging_tasks(self._logging_tasks, timeout)

    def _create_logging_task(
        self,
        method: str,
        url: str,
        response: Any,
        error: Optional[Exception],
        start_time: float,
        request_data: Optional[Dict[str, Any]],
        request_headers: Dict[str, Any],
    ) -> None:
        """Create non-blocking logging task."""
        create_logging_task(
            self._logging_tasks,
            self.logger,
            self.config,
            self._jwt_cache,
            method,
            url,
            response,
            error,
            start_time,
            request_data,
            request_headers,
        )

    async def _execute_with_logging(
        self,
        method: str,
        url: str,
        request_func,
        request_data: Optional[Dict[str, Any]] = None,
        request_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """Execute HTTP request with automatic audit and debug logging."""
        start_time = time.perf_counter()
        effective_request_kwargs = request_kwargs if request_kwargs is not None else kwargs
        request_headers = ensure_correlation_headers(effective_request_kwargs)
        try:
            response = await request_func()
            self._create_logging_task(
                method, url, response, None, start_time, request_data, request_headers
            )
            return response
        except Exception as e:
            self._create_logging_task(
                method, url, None, e, start_time, request_data, request_headers
            )
            raise

    async def get(self, url: str, **kwargs) -> Any:
        """Make GET request with automatic audit and debug logging.

        Args:
            url: Request URL
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails

        """

        request_kwargs = dict(kwargs)

        async def _get():
            return await self._internal_client.get(url, **request_kwargs)

        return await self._execute_with_logging(
            "GET", url, _get, request_kwargs=request_kwargs, **kwargs
        )

    async def post(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Make POST request with automatic audit and debug logging.

        Args:
            url: Request URL
            data: Request data (will be JSON encoded). Callers may also pass
                json= in kwargs; body params are forwarded without duplication.
            **kwargs: Additional httpx request parameters (e.g. json=, timeout=,
                headers=). Body params are passed to httpx at most once.

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails

        """

        request_kwargs = dict(kwargs)

        async def _post():
            return await self._internal_client.post(url, data, **request_kwargs)

        return await self._execute_with_logging(
            "POST",
            url,
            _post,
            data,
            request_kwargs=request_kwargs,
            **kwargs,
        )

    async def put(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """Make PUT request with automatic audit and debug logging.

        Args:
            url: Request URL
            data: Request data (will be JSON encoded). Callers may also pass
                json= in kwargs; body params are forwarded without duplication.
            **kwargs: Additional httpx request parameters (e.g. json=, timeout=,
                headers=). Body params are passed to httpx at most once.

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails

        """

        request_kwargs = dict(kwargs)

        async def _put():
            return await self._internal_client.put(url, data, **request_kwargs)

        return await self._execute_with_logging(
            "PUT",
            url,
            _put,
            data,
            request_kwargs=request_kwargs,
            **kwargs,
        )

    async def delete(self, url: str, **kwargs) -> Any:
        """Make DELETE request with automatic audit and debug logging.

        Args:
            url: Request URL
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails

        """

        request_kwargs = dict(kwargs)

        async def _delete():
            return await self._internal_client.delete(url, **request_kwargs)

        return await self._execute_with_logging(
            "DELETE", url, _delete, request_kwargs=request_kwargs, **kwargs
        )

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """Generic request method with automatic audit and debug logging.

        Args:
            method: HTTP method
            url: Request URL
            data: Request data (for POST/PUT)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails

        """
        method_upper = method.upper()
        if method_upper == "GET":
            return await self.get(url, **kwargs)
        elif method_upper == "POST":
            return await self.post(url, data, **kwargs)
        elif method_upper == "PUT":
            return await self.put(url, data, **kwargs)
        elif method_upper == "DELETE":
            return await self.delete(url, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    def register_user_token_refresh_callback(self, user_id: str, callback: Any) -> None:
        """Register refresh callback for a user.

        Args:
            user_id: User ID
            callback: Async function that takes old token and returns new token

        """
        self._user_token_refresh.register_refresh_callback(user_id, callback)

    def register_user_refresh_token(self, user_id: str, refresh_token: str) -> None:
        """Register refresh token for a user.

        Args:
            user_id: User ID
            refresh_token: Refresh token string

        """
        self._user_token_refresh.register_refresh_token(user_id, refresh_token)

    def set_auth_service_for_refresh(self, auth_service: Any) -> None:
        """Set AuthService instance for refresh endpoint calls.

        Args:
            auth_service: AuthService instance

        """
        self._user_token_refresh.set_auth_service(auth_service)

    async def _prepare_authenticated_request(self, token: str, auto_refresh: bool, **kwargs) -> str:
        """Prepare authenticated request by getting valid token and setting headers.

        Args:
            token: User authentication token
            auto_refresh: Whether to refresh token if expired
            **kwargs: Request kwargs (headers will be modified)

        Returns:
            Valid token to use for request

        """
        return await prepare_authenticated_request(
            self._user_token_refresh, token, auto_refresh, **kwargs
        )

    async def _handle_401_refresh(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        token: str,
        data: Optional[Dict[str, Any]],
        auth_strategy: Optional[AuthStrategy],
        error: httpx.HTTPStatusError,
        auto_refresh: bool,
        **kwargs,
    ) -> Any:
        """Handle 401 error by refreshing token and retrying request."""
        return await handle_401_refresh(
            self._internal_client,
            self._user_token_refresh,
            method,
            url,
            token,
            data,
            auth_strategy,
            error,
            auto_refresh,
            **kwargs,
        )

    async def authenticated_request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        token: str,
        data: Optional[Dict[str, Any]] = None,
        auth_strategy: Optional[AuthStrategy] = None,
        auto_refresh: bool = True,
        **kwargs,
    ) -> Any:
        """Make authenticated request with Bearer token and automatic refresh.

        Client token sent as x-client-token (via InternalHttpClient), user token as Bearer.

        Args:
            method: HTTP method
            url: Request URL
            token: User authentication token (sent as Bearer)
            data: Request data (for POST/PUT)
            auth_strategy: Optional authentication strategy
            auto_refresh: Whether to refresh token on 401 (default: True)

        """
        request_kwargs = dict(kwargs)
        valid_token = await self._prepare_authenticated_request(token, auto_refresh, **kwargs)

        async def _authenticated_request():
            try:
                return await self._internal_client.authenticated_request(
                    method, url, valid_token, data, auth_strategy, **request_kwargs
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    return await self._handle_401_refresh(
                        method,
                        url,
                        valid_token,
                        data,
                        auth_strategy,
                        e,
                        auto_refresh,
                        **request_kwargs,
                    )
                raise

        return await self._execute_with_logging(
            method,
            url,
            _authenticated_request,
            data,
            request_kwargs=request_kwargs,
            **kwargs,
        )

    async def request_with_auth_strategy(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """Make request with auth strategy, trying methods in priority order on 401."""
        request_kwargs = dict(kwargs)

        async def _request():
            return await self._internal_client.request_with_auth_strategy(
                method, url, auth_strategy, data, **request_kwargs
            )

        return await self._execute_with_logging(
            method,
            url,
            _request,
            data,
            request_kwargs=request_kwargs,
            **kwargs,
        )

    async def get_with_filters(
        self, url: str, filter_builder: Optional[Any] = None, **kwargs
    ) -> Any:
        """Make GET request with filter builder support."""
        if filter_builder:
            from ..models.filter import FilterQuery
            from ..utils.filter import build_query_string

            query_string = build_query_string(FilterQuery(filters=filter_builder.build()))
            if query_string:
                merge_filter_params(kwargs, parse_filter_query_string(query_string))

        return await self.get(url, **kwargs)

    async def get_paginated(
        self, url: str, page: Optional[int] = None, page_size: Optional[int] = None, **kwargs
    ) -> Any:
        """Make GET request with pagination support (returns PaginatedListResponse)."""
        add_pagination_params(kwargs, page, page_size)
        return parse_paginated_response(await self.get(url, **kwargs))

    def clear_user_token(self, token: str) -> None:
        """Clear a user's JWT token from cache.

        Args:
            token: JWT token string to remove from cache

        """
        self._jwt_cache.clear_token(token)

    async def post_with_filters(
        self,
        url: str,
        json_filter: Optional[Union[Any, Dict[str, Any]]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """Make POST request with JSON filter support (filters merged into body)."""
        request_body = prepare_json_filter_body(json_filter, json_body)
        return await self.post(url, data=request_body if request_body else None, **kwargs)
