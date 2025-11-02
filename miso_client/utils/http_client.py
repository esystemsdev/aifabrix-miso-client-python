"""
Public HTTP client utility for controller communication with ISO 27001 compliant logging.

This module provides the public HTTP client interface that wraps InternalHttpClient
and adds automatic audit and debug logging for all HTTP requests. All sensitive
data is automatically masked using DataMasker before logging to comply with ISO 27001.
"""

import time
from typing import Any, Dict, Literal, Optional
from urllib.parse import parse_qs, urlparse

from ..models.config import MisoClientConfig
from ..services.logger import LoggerService
from ..utils.data_masker import DataMasker
from ..utils.jwt_tools import decode_token
from .internal_http_client import InternalHttpClient


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

    def _should_skip_logging(self, url: str) -> bool:
        """
        Check if logging should be skipped for this URL.

        Skips logging for /api/logs and /api/auth/token to prevent infinite loops.

        Args:
            url: Request URL

        Returns:
            True if logging should be skipped, False otherwise
        """
        # Skip logging for log endpoint (prevent infinite audit loops)
        if url == "/api/logs" or url.startswith("/api/logs"):
            return True

        # Skip logging for token endpoint (client token fetch, prevent loops)
        if url == "/api/auth/token" or url.startswith("/api/auth/token"):
            return True

        return False

    def _extract_user_id_from_headers(self, headers: Dict[str, Any]) -> Optional[str]:
        """
        Extract user ID from JWT token in Authorization header.

        Args:
            headers: Request headers dictionary

        Returns:
            User ID if found, None otherwise
        """
        auth_header = headers.get("authorization") or headers.get("Authorization")
        if not auth_header or not isinstance(auth_header, str):
            return None

        # Extract token (Bearer <token> format)
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header

        try:
            decoded = decode_token(token)
            if decoded:
                return decoded.get("sub") or decoded.get("userId") or decoded.get("user_id")
        except Exception:
            pass

        return None

    async def _log_http_request_audit(
        self,
        method: str,
        url: str,
        response: Optional[Any] = None,
        error: Optional[Exception] = None,
        start_time: float = 0.0,
        request_data: Optional[Dict[str, Any]] = None,
        request_headers: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """
        Log HTTP request audit event with ISO 27001 compliant data masking.

        Args:
            method: HTTP method
            url: Request URL
            response: Response data (if successful)
            error: Exception (if request failed)
            start_time: Request start time
            request_data: Request body data
            request_headers: Request headers
            **kwargs: Additional request parameters
        """
        try:
            # Skip logging for certain endpoints
            if self._should_skip_logging(url):
                return

            # Calculate duration
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract status code
            status_code: Optional[int] = None
            response_size: Optional[int] = None
            if response is not None:
                # Response is already parsed JSON from InternalHttpClient
                # We don't have direct access to status code from parsed response
                # But we can infer success (no error means success)
                status_code = 200  # Default assumption if response exists
                # Estimate response size
                try:
                    response_str = str(response)
                    response_size = len(response_str.encode("utf-8"))
                except Exception:
                    pass

            if error is not None:
                # Extract status code from error if available
                if hasattr(error, "status_code"):
                    status_code = error.status_code
                else:
                    status_code = 500  # Default for errors

            # Extract user ID from headers
            user_id: Optional[str] = None
            if request_headers:
                user_id = self._extract_user_id_from_headers(request_headers)

            # Calculate request size
            request_size: Optional[int] = None
            if request_data is not None:
                try:
                    request_str = str(request_data)
                    request_size = len(request_str.encode("utf-8"))
                except Exception:
                    pass

            # Mask sensitive data in error message
            error_message: Optional[str] = None
            if error is not None:
                error_message = str(error)
                # Mask error message if it contains sensitive data
                try:
                    # Try to mask if error message looks like it contains structured data
                    if isinstance(error_message, str) and any(
                        keyword in error_message.lower()
                        for keyword in ["password", "token", "secret", "key"]
                    ):
                        error_message = DataMasker.MASKED_VALUE
                except Exception:
                    pass

            # Build audit context (all sensitive data must be masked)
            audit_context: Dict[str, Any] = {
                "method": method,
                "url": url,
                "statusCode": status_code,
                "duration": duration_ms,
            }

            if user_id:
                audit_context["userId"] = user_id
            if request_size is not None:
                audit_context["requestSize"] = request_size
            if response_size is not None:
                audit_context["responseSize"] = response_size
            if error_message:
                audit_context["error"] = error_message

            # Log audit event
            action = f"http.request.{method.upper()}"
            await self.logger.audit(action, url, audit_context)

            # Log debug details if log level is debug
            if self.config.log_level == "debug":
                await self._log_http_request_debug(
                    method,
                    url,
                    response,
                    error,
                    duration_ms,
                    status_code,
                    user_id,
                    request_data,
                    request_headers,
                    **kwargs,
                )

        except Exception:
            # Silently swallow all logging errors - never break HTTP requests
            pass

    async def _log_http_request_debug(
        self,
        method: str,
        url: str,
        response: Optional[Any],
        error: Optional[Exception],
        duration_ms: int,
        status_code: Optional[int],
        user_id: Optional[str],
        request_data: Optional[Dict[str, Any]],
        request_headers: Optional[Dict[str, Any]],
        **kwargs,
    ) -> None:
        """
        Log detailed debug information for HTTP request.

        All sensitive data is masked before logging.

        Args:
            method: HTTP method
            url: Request URL
            response: Response data
            error: Exception if request failed
            duration_ms: Request duration in milliseconds
            status_code: HTTP status code
            user_id: User ID if available
            request_data: Request body data
            request_headers: Request headers
            **kwargs: Additional request parameters
        """
        try:
            # Mask request headers
            masked_request_headers: Optional[Dict[str, Any]] = None
            if request_headers:
                masked_request_headers = DataMasker.mask_sensitive_data(request_headers)

            # Mask request body
            masked_request_body: Optional[Any] = None
            if request_data is not None:
                masked_request_body = DataMasker.mask_sensitive_data(request_data)

            # Mask response body (limit to first 1000 characters)
            # Note: Response headers not available from InternalHttpClient (returns parsed JSON)
            masked_response_body: Optional[str] = None
            if response is not None:
                try:
                    response_str = str(response)
                    # Limit to first 1000 characters
                    if len(response_str) > 1000:
                        response_str = response_str[:1000] + "..."
                    # Mask sensitive data
                    try:
                        # Try to mask if response is a dict
                        if isinstance(response, dict):
                            masked_dict = DataMasker.mask_sensitive_data(response)
                            masked_response_body = str(masked_dict)
                        else:
                            masked_response_body = response_str
                    except Exception:
                        masked_response_body = response_str
                except Exception:
                    pass

            # Extract query parameters from URL and mask
            query_params: Optional[Dict[str, Any]] = None
            try:
                parsed_url = urlparse(url)
                if parsed_url.query:
                    query_dict = parse_qs(parsed_url.query)
                    # Convert lists to single values for simplicity
                    query_simple: Dict[str, Any] = {
                        k: v[0] if len(v) == 1 else v for k, v in query_dict.items()
                    }
                    query_params = DataMasker.mask_sensitive_data(query_simple)
            except Exception:
                pass

            # Build debug context (all sensitive data must be masked)
            debug_context: Dict[str, Any] = {
                "method": method,
                "url": url,
                "statusCode": status_code,
                "duration": duration_ms,
                "baseURL": self.config.controller_url,
                "timeout": 30.0,  # Default timeout
            }

            if user_id:
                debug_context["userId"] = user_id
            if masked_request_headers:
                debug_context["requestHeaders"] = masked_request_headers
            if masked_request_body is not None:
                debug_context["requestBody"] = masked_request_body
            if masked_response_body:
                debug_context["responseBody"] = masked_response_body
            if query_params:
                debug_context["queryParams"] = query_params

            # Log debug message
            message = f"HTTP {method} {url} - Status: {status_code}, Duration: {duration_ms}ms"
            await self.logger.debug(message, debug_context)

        except Exception:
            # Silently swallow all logging errors - never break HTTP requests
            pass

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
        start_time = time.perf_counter()
        request_headers = kwargs.get("headers", {})
        try:
            response = await self._internal_client.get(url, **kwargs)
            await self._log_http_request_audit(
                "GET",
                url,
                response=response,
                error=None,
                start_time=start_time,
                request_data=None,
                request_headers=request_headers,
                **kwargs,
            )
            return response
        except Exception as e:
            await self._log_http_request_audit(
                "GET",
                url,
                response=None,
                error=e,
                start_time=start_time,
                request_data=None,
                request_headers=request_headers,
                **kwargs,
            )
            raise

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
        start_time = time.perf_counter()
        request_headers = kwargs.get("headers", {})
        try:
            response = await self._internal_client.post(url, data, **kwargs)
            await self._log_http_request_audit(
                "POST",
                url,
                response=response,
                error=None,
                start_time=start_time,
                request_data=data,
                request_headers=request_headers,
                **kwargs,
            )
            return response
        except Exception as e:
            await self._log_http_request_audit(
                "POST",
                url,
                response=None,
                error=e,
                start_time=start_time,
                request_data=data,
                request_headers=request_headers,
                **kwargs,
            )
            raise

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
        start_time = time.perf_counter()
        request_headers = kwargs.get("headers", {})
        try:
            response = await self._internal_client.put(url, data, **kwargs)
            await self._log_http_request_audit(
                "PUT",
                url,
                response=response,
                error=None,
                start_time=start_time,
                request_data=data,
                request_headers=request_headers,
                **kwargs,
            )
            return response
        except Exception as e:
            await self._log_http_request_audit(
                "PUT",
                url,
                response=None,
                error=e,
                start_time=start_time,
                request_data=data,
                request_headers=request_headers,
                **kwargs,
            )
            raise

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
        start_time = time.perf_counter()
        request_headers = kwargs.get("headers", {})
        try:
            response = await self._internal_client.delete(url, **kwargs)
            await self._log_http_request_audit(
                "DELETE",
                url,
                response=response,
                error=None,
                start_time=start_time,
                request_data=None,
                request_headers=request_headers,
                **kwargs,
            )
            return response
        except Exception as e:
            await self._log_http_request_audit(
                "DELETE",
                url,
                response=None,
                error=e,
                start_time=start_time,
                request_data=None,
                request_headers=request_headers,
                **kwargs,
            )
            raise

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

    async def authenticated_request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        token: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Make authenticated request with Bearer token and automatic audit/debug logging.

        IMPORTANT: Client token is sent as x-client-token header (via InternalHttpClient)
        User token is sent as Authorization: Bearer header (this method parameter)
        These are two separate tokens for different purposes.

        Args:
            method: HTTP method
            url: Request URL
            token: User authentication token (sent as Bearer token)
            data: Request data (for POST/PUT)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """
        # Add Bearer token to headers for logging context
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        kwargs["headers"] = headers

        return await self.request(method, url, data, **kwargs)

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
        from ..models.filter import FilterQuery
        from ..utils.filter import build_query_string

        # Build query string from filter builder
        if filter_builder:
            # Create FilterQuery from FilterBuilder
            filter_query = FilterQuery(filters=filter_builder.build())
            query_string = build_query_string(filter_query)

            # Parse query string into params
            if query_string:
                from urllib.parse import parse_qs

                # Parse query string into dict
                query_params = parse_qs(query_string)
                # Convert single-item lists to values
                params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}

                # Merge with existing params
                existing_params = kwargs.get("params", {})
                if existing_params:
                    # Merge params (filter builder takes precedence)
                    merged_params = {**existing_params, **params}
                else:
                    merged_params = params

                kwargs["params"] = merged_params

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
            >>> response = await client.http_client.get_paginated('/api/items', page=1, page_size=25)
            >>> response.meta.total_items
            120
            >>> len(response.data)
            25
        """
        from ..models.pagination import PaginatedListResponse

        # Add pagination params
        params = kwargs.get("params", {})
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size

        if params:
            kwargs["params"] = params

        # Make request
        response_data = await self.get(url, **kwargs)

        # Try to parse as PaginatedListResponse
        try:
            return PaginatedListResponse(**response_data)
        except Exception:
            # If response doesn't match PaginatedListResponse format, return as-is
            # This allows flexibility for different response formats
            return response_data
