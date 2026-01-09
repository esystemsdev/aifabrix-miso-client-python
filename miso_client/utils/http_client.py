"""
Public HTTP client utility for controller communication with ISO 27001 compliant logging.

This module provides the public HTTP client interface that wraps InternalHttpClient
and adds automatic audit and debug logging for all HTTP requests. All sensitive
data is automatically masked using DataMasker before logging to comply with ISO 27001.
"""

import asyncio
import time
from typing import Any, Dict, Literal, Optional, Union

import httpx

from ..models.config import AuthStrategy, MisoClientConfig
from ..services.logger import LoggerService
from ..utils.jwt_tools import JwtTokenCache, extract_user_id
from .http_client_logging_helpers import (
    handle_logging_task_error,
    log_http_request,
    wait_for_logging_tasks,
)
from .http_client_query_helpers import (
    add_pagination_params,
    merge_filter_params,
    parse_filter_query_string,
    parse_paginated_response,
    prepare_json_filter_body,
)
from .internal_http_client import InternalHttpClient
from .user_token_refresh import UserTokenRefreshManager


class HttpClient:
    """
    Public HTTP client for Miso Controller communication with ISO 27001 compliant logging.

    This class wraps InternalHttpClient and adds:
    - Automatic audit logging for all requests
    - Debug logging when log_level is 'debug'
    - Automatic data masking for all sensitive information

    All sensitive data (headers, bodies, query params) is masked using DataMasker
    before logging to ensure ISO 27001 compliance.
    """

    def __init__(self, config: MisoClientConfig, logger: LoggerService):
        """
        Initialize public HTTP client with configuration and logger.

        Args:
            config: MisoClient configuration
            logger: LoggerService instance for audit and debug logging
        """
        self.config = config
        self.logger = logger
        self._internal_client = InternalHttpClient(config)
        self._jwt_cache = JwtTokenCache(max_size=1000)
        self._user_token_refresh = UserTokenRefreshManager()

    async def close(self):
        """Close the HTTP client."""
        await self._internal_client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def get_environment_token(self) -> str:
        """
        Get environment token using client credentials.

        This is called automatically by HttpClient but can be called manually.

        Returns:
            Client token string
        """
        return await self._internal_client.get_environment_token()

    def _handle_logging_task_error(self, task: asyncio.Task) -> None:
        """
        Handle errors in background logging tasks.

        Silently swallows all exceptions to prevent logging errors from breaking requests.

        Args:
            task: The completed logging task
        """
        handle_logging_task_error(task)

    async def _wait_for_logging_tasks(self, timeout: float = 0.5) -> None:
        """
        Wait for all pending logging tasks to complete.

        Useful for tests to ensure logging has finished before assertions.

        Args:
            timeout: Maximum time to wait in seconds
        """
        if hasattr(self, "_logging_tasks") and self._logging_tasks:
            await wait_for_logging_tasks(self._logging_tasks, timeout)

    async def _execute_with_logging(
        self,
        method: str,
        url: str,
        request_func,
        request_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Execute HTTP request with automatic audit and debug logging.

        Args:
            method: HTTP method name
            url: Request URL
            request_func: Async function to execute the request
            request_data: Request body data (optional)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            Exception: If request fails
        """
        start_time = time.perf_counter()
        request_headers = kwargs.get("headers", {})
        try:
            response = await request_func()
            # Create logging task but don't await it (non-blocking)
            # Store task reference to allow tests to await if needed
            logging_task = asyncio.create_task(
                log_http_request(
                    self.logger,
                    self.config,
                    self._jwt_cache,
                    method,
                    url,
                    response,
                    None,
                    start_time,
                    request_data,
                    request_headers,
                )
            )
            logging_task.add_done_callback(self._handle_logging_task_error)
            # Store task for potential cleanup (optional)
            if not hasattr(self, "_logging_tasks"):
                self._logging_tasks = set()
            self._logging_tasks.add(logging_task)
            logging_task.add_done_callback(lambda t: self._logging_tasks.discard(t))
            return response
        except Exception as e:
            # Create logging task for error case
            logging_task = asyncio.create_task(
                log_http_request(
                    self.logger,
                    self.config,
                    self._jwt_cache,
                    method,
                    url,
                    None,
                    e,
                    start_time,
                    request_data,
                    request_headers,
                )
            )
            logging_task.add_done_callback(self._handle_logging_task_error)
            if not hasattr(self, "_logging_tasks"):
                self._logging_tasks = set()
            self._logging_tasks.add(logging_task)
            logging_task.add_done_callback(lambda t: self._logging_tasks.discard(t))
            raise

    async def get(self, url: str, **kwargs) -> Any:
        """
        Make GET request with automatic audit and debug logging.

        Args:
            url: Request URL
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """

        async def _get():
            return await self._internal_client.get(url, **kwargs)

        return await self._execute_with_logging("GET", url, _get, **kwargs)

    async def post(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """
        Make POST request with automatic audit and debug logging.

        Args:
            url: Request URL
            data: Request data (will be JSON encoded)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """

        async def _post():
            return await self._internal_client.post(url, data, **kwargs)

        return await self._execute_with_logging("POST", url, _post, data, **kwargs)

    async def put(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """
        Make PUT request with automatic audit and debug logging.

        Args:
            url: Request URL
            data: Request data (will be JSON encoded)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """

        async def _put():
            return await self._internal_client.put(url, data, **kwargs)

        return await self._execute_with_logging("PUT", url, _put, data, **kwargs)

    async def delete(self, url: str, **kwargs) -> Any:
        """
        Make DELETE request with automatic audit and debug logging.

        Args:
            url: Request URL
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """

        async def _delete():
            return await self._internal_client.delete(url, **kwargs)

        return await self._execute_with_logging("DELETE", url, _delete, **kwargs)

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Generic request method with automatic audit and debug logging.

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
        """
        Register refresh callback for a user.

        Args:
            user_id: User ID
            callback: Async function that takes old token and returns new token
        """
        self._user_token_refresh.register_refresh_callback(user_id, callback)

    def register_user_refresh_token(self, user_id: str, refresh_token: str) -> None:
        """
        Register refresh token for a user.

        Args:
            user_id: User ID
            refresh_token: Refresh token string
        """
        self._user_token_refresh.register_refresh_token(user_id, refresh_token)

    def set_auth_service_for_refresh(self, auth_service: Any) -> None:
        """
        Set AuthService instance for refresh endpoint calls.

        Args:
            auth_service: AuthService instance
        """
        self._user_token_refresh.set_auth_service(auth_service)

    async def _prepare_authenticated_request(self, token: str, auto_refresh: bool, **kwargs) -> str:
        """
        Prepare authenticated request by getting valid token and setting headers.

        Args:
            token: User authentication token
            auto_refresh: Whether to refresh token if expired
            **kwargs: Request kwargs (headers will be modified)

        Returns:
            Valid token to use for request
        """
        # Get valid token (refresh if expired)
        valid_token = await self._user_token_refresh.get_valid_token(
            token, refresh_if_needed=auto_refresh
        )
        if not valid_token:
            valid_token = token  # Fallback to original token

        # Add Bearer token to headers for logging context
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {valid_token}"
        kwargs["headers"] = headers

        return valid_token

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
        """
        Handle 401 error by refreshing token and retrying request.

        Args:
            method: HTTP method
            url: Request URL
            token: Current token
            data: Request data
            auth_strategy: Authentication strategy
            error: HTTPStatusError with 401 status
            auto_refresh: Whether to refresh token
            **kwargs: Request kwargs

        Returns:
            Response data from retried request

        Raises:
            httpx.HTTPStatusError: If refresh fails or retry fails
        """
        if not auto_refresh:
            raise error

        user_id = extract_user_id(token)
        refreshed_token = await self._user_token_refresh._refresh_token(token, user_id)

        if not refreshed_token:
            raise error

        # Retry request with refreshed token
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {refreshed_token}"
        kwargs["headers"] = headers

        try:
            return await self._internal_client.authenticated_request(
                method, url, refreshed_token, data, auth_strategy, **kwargs
            )
        except httpx.HTTPStatusError:
            # Retry failed, raise original error
            raise error

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
        """
        Make authenticated request with Bearer token and automatic refresh.

        IMPORTANT: Client token is sent as x-client-token header (via InternalHttpClient)
        User token is sent as Authorization: Bearer header (this method parameter)
        These are two separate tokens for different purposes.

        Args:
            method: HTTP method
            url: Request URL
            token: User authentication token (sent as Bearer token)
            data: Request data (for POST/PUT)
            auth_strategy: Optional authentication strategy (defaults to bearer + client-token)
            auto_refresh: Whether to automatically refresh token on 401 (default: True)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """
        # Prepare token and headers
        valid_token = await self._prepare_authenticated_request(token, auto_refresh, **kwargs)

        # Execute request with 401 handling
        async def _authenticated_request():
            try:
                return await self._internal_client.authenticated_request(
                    method, url, valid_token, data, auth_strategy, **kwargs
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    return await self._handle_401_refresh(
                        method, url, valid_token, data, auth_strategy, e, auto_refresh, **kwargs
                    )
                raise

        return await self._execute_with_logging(method, url, _authenticated_request, data, **kwargs)

    async def request_with_auth_strategy(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Make request with authentication strategy and automatic audit/debug logging.

        Tries authentication methods in priority order until one succeeds.
        If a method returns 401, automatically tries the next method in the strategy.

        Args:
            method: HTTP method
            url: Request URL
            auth_strategy: Authentication strategy configuration
            data: Request data (for POST/PUT)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If all authentication methods fail
        """

        async def _request_with_auth_strategy():
            return await self._internal_client.request_with_auth_strategy(
                method, url, auth_strategy, data, **kwargs
            )

        return await self._execute_with_logging(
            method, url, _request_with_auth_strategy, data, **kwargs
        )

    async def get_with_filters(
        self,
        url: str,
        filter_builder: Optional[Any] = None,
        **kwargs,
    ) -> Any:
        """
        Make GET request with filter builder support.

        Args:
            url: Request URL
            filter_builder: Optional FilterBuilder instance with filters
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails

        Examples:
            >>> from miso_client.models.filter import FilterBuilder
            >>> filter_builder = FilterBuilder().add('status', 'eq', 'active')
            >>> response = await client.http_client.get_with_filters('/api/items', filter_builder)
        """
        if filter_builder:
            from ..models.filter import FilterQuery
            from ..utils.filter import build_query_string

            filter_query = FilterQuery(filters=filter_builder.build())
            query_string = build_query_string(filter_query)

            if query_string:
                filter_params = parse_filter_query_string(query_string)
                merge_filter_params(kwargs, filter_params)

        return await self.get(url, **kwargs)

    async def get_paginated(
        self,
        url: str,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        **kwargs,
    ) -> Any:
        """
        Make GET request with pagination support.

        Args:
            url: Request URL
            page: Optional page number (1-based)
            page_size: Optional number of items per page
            **kwargs: Additional httpx request parameters

        Returns:
            PaginatedListResponse with meta and data (or raw response if format doesn't match)

        Raises:
            MisoClientError: If request fails

        Examples:
            >>> response = await client.http_client.get_paginated(
            ...     '/api/items', page=1, page_size=25
            ... )
            >>> response.meta.totalItems
            120
            >>> len(response.data)
            25
        """
        add_pagination_params(kwargs, page, page_size)
        response_data = await self.get(url, **kwargs)
        return parse_paginated_response(response_data)

    def clear_user_token(self, token: str) -> None:
        """
        Clear a user's JWT token from cache.

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
        """
        Make POST request with JSON filter support.

        Args:
            url: Request URL
            json_filter: Optional JsonFilter or FilterQuery instance
            json_body: Optional JSON body (filters will be merged into this)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails

        Examples:
            >>> from miso_client.models.filter import JsonFilter, FilterOption
            >>> json_filter = JsonFilter(
            ...     filters=[FilterOption(field='status', op='eq', value='active')]
            ... )
            >>> response = await client.http_client.post_with_filters(
            ...     '/api/items/search',
            ...     json_filter=json_filter
            ... )
        """
        # Prepare JSON body with filter data
        request_body = prepare_json_filter_body(json_filter, json_body)

        # Use post method with merged body
        return await self.post(url, data=request_body if request_body else None, **kwargs)
