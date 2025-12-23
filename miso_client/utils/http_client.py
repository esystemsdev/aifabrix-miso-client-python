"""
Public HTTP client utility for controller communication with ISO 27001 compliant logging.

This module provides the public HTTP client interface that wraps InternalHttpClient
and adds automatic audit and debug logging for all HTTP requests. All sensitive
data is automatically masked using DataMasker before logging to comply with ISO 27001.
"""

import asyncio
import time
from typing import Any, Dict, Literal, Optional
from urllib.parse import parse_qs

import httpx

from ..models.config import AuthStrategy, MisoClientConfig
from ..services.logger import LoggerService
from ..utils.jwt_tools import JwtTokenCache, extract_user_id
from .http_client_logging import log_http_request_audit, log_http_request_debug
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
        try:
            exception = task.exception()
            if exception:
                # Silently swallow logging errors - never break HTTP requests
                pass
        except Exception:
            # Task might not be done yet or other error - ignore
            pass

    async def _wait_for_logging_tasks(self, timeout: float = 0.5) -> None:
        """
        Wait for all pending logging tasks to complete.

        Useful for tests to ensure logging has finished before assertions.

        Args:
            timeout: Maximum time to wait in seconds
        """
        if hasattr(self, "_logging_tasks") and self._logging_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._logging_tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # Some tasks might still be running, that's okay
                pass

    def _calculate_status_code(
        self, response: Optional[Any], error: Optional[Exception]
    ) -> Optional[int]:
        """
        Calculate HTTP status code from response or error.

        Args:
            response: Response data (if successful)
            error: Exception (if request failed)

        Returns:
            HTTP status code, or None if cannot determine
        """
        if response is not None:
            return 200
        if error is not None:
            if hasattr(error, "status_code"):
                status_code = getattr(error, "status_code", None)
                if isinstance(status_code, int):
                    return status_code
            return 500
        return None

    def _extract_user_id_from_headers(
        self, request_headers: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Extract user ID from request headers.

        Args:
            request_headers: Request headers dictionary

        Returns:
            User ID if found, None otherwise
        """
        if request_headers:
            return self._jwt_cache.extract_user_id_from_headers(request_headers)
        return None

    async def _log_debug_if_enabled(
        self,
        method: str,
        url: str,
        response: Optional[Any],
        error: Optional[Exception],
        start_time: float,
        user_id: Optional[str],
        request_data: Optional[Dict[str, Any]],
        request_headers: Optional[Dict[str, Any]],
    ) -> None:
        """
        Log debug details if debug logging is enabled.

        Args:
            method: HTTP method
            url: Request URL
            response: Response data (if successful)
            error: Exception (if request failed)
            start_time: Request start time
            user_id: User ID if available
            request_data: Request body data
            request_headers: Request headers
        """
        if self.config.log_level != "debug":
            return

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        status_code = self._calculate_status_code(response, error)
        await log_http_request_debug(
            logger=self.logger,
            method=method,
            url=url,
            response=response,
            duration_ms=duration_ms,
            status_code=status_code,
            user_id=user_id,
            request_data=request_data,
            request_headers=request_headers,
            base_url=self.config.controller_url,
            config=self.config,
        )

    async def _log_http_request(
        self,
        method: str,
        url: str,
        response: Optional[Any],
        error: Optional[Exception],
        start_time: float,
        request_data: Optional[Dict[str, Any]],
        request_headers: Optional[Dict[str, Any]],
    ) -> None:
        """
        Log HTTP request with audit and optional debug logging.

        Args:
            method: HTTP method
            url: Request URL
            response: Response data (if successful)
            error: Exception (if request failed)
            start_time: Request start time
            request_data: Request body data
            request_headers: Request headers
        """
        user_id = self._extract_user_id_from_headers(request_headers)

        await log_http_request_audit(
            logger=self.logger,
            method=method,
            url=url,
            response=response,
            error=error,
            start_time=start_time,
            request_data=request_data,
            user_id=user_id,
            log_level=self.config.log_level,
            config=self.config,
        )

        await self._log_debug_if_enabled(
            method, url, response, error, start_time, user_id, request_data, request_headers
        )

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
                self._log_http_request(
                    method, url, response, None, start_time, request_data, request_headers
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
                self._log_http_request(
                    method, url, None, e, start_time, request_data, request_headers
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

        # Use internal client's authenticated_request which handles auth strategy
        async def _authenticated_request():
            try:
                return await self._internal_client.authenticated_request(
                    method, url, valid_token, data, auth_strategy, **kwargs
                )
            except httpx.HTTPStatusError as e:
                # Handle 401 with automatic refresh
                if e.response.status_code == 401 and auto_refresh:
                    user_id = extract_user_id(valid_token)
                    refreshed_token = await self._user_token_refresh._refresh_token(
                        valid_token, user_id
                    )

                    if refreshed_token:
                        # Retry request with refreshed token
                        try:
                            headers["Authorization"] = f"Bearer {refreshed_token}"
                            kwargs["headers"] = headers
                            return await self._internal_client.authenticated_request(
                                method, url, refreshed_token, data, auth_strategy, **kwargs
                            )
                        except httpx.HTTPStatusError:
                            # Retry failed, raise original error
                            raise e

                # Re-raise if not 401 or refresh failed
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

    def _parse_filter_query_string(self, query_string: str) -> Dict[str, Any]:
        """
        Parse filter query string into params dictionary.

        Args:
            query_string: Query string from FilterQuery

        Returns:
            Params dictionary with filters
        """
        query_params = parse_qs(query_string)
        return {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}

    def _merge_filter_params(self, kwargs: Dict[str, Any], filter_params: Dict[str, Any]) -> None:
        """
        Merge filter params with existing params.

        Args:
            kwargs: Request kwargs dictionary
            filter_params: Filter params from FilterBuilder
        """
        existing_params = kwargs.get("params", {})
        if existing_params:
            merged_params = {**existing_params, **filter_params}
        else:
            merged_params = filter_params
        kwargs["params"] = merged_params

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
                filter_params = self._parse_filter_query_string(query_string)
                self._merge_filter_params(kwargs, filter_params)

        return await self.get(url, **kwargs)

    def _add_pagination_params(
        self, kwargs: Dict[str, Any], page: Optional[int], page_size: Optional[int]
    ) -> None:
        """
        Add pagination params to kwargs.

        Args:
            kwargs: Request kwargs dictionary
            page: Optional page number (1-based)
            page_size: Optional number of items per page
        """
        params = kwargs.get("params", {})
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size

        if params:
            kwargs["params"] = params

    def _parse_paginated_response(self, response_data: Any) -> Any:
        """
        Parse response as PaginatedListResponse if possible.

        Args:
            response_data: Response data from API

        Returns:
            PaginatedListResponse if format matches, otherwise raw response
        """
        from ..models.pagination import PaginatedListResponse

        try:
            return PaginatedListResponse(**response_data)
        except Exception:
            # If response doesn't match PaginatedListResponse format, return as-is
            # This allows flexibility for different response formats
            return response_data

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
        self._add_pagination_params(kwargs, page, page_size)
        response_data = await self.get(url, **kwargs)
        return self._parse_paginated_response(response_data)

    def clear_user_token(self, token: str) -> None:
        """
        Clear a user's JWT token from cache.

        Args:
            token: JWT token string to remove from cache
        """
        self._jwt_cache.clear_token(token)
