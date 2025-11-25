"""
Internal HTTP client utility for controller communication.

This module provides the internal HTTP client implementation with automatic client
token management. This class is not meant to be used directly - use the public
HttpClient class instead which adds ISO 27001 compliant audit and debug logging.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Optional

import httpx

from ..errors import AuthenticationError, ConnectionError, MisoClientError
from ..models.config import AuthStrategy, ClientTokenResponse, MisoClientConfig
from ..models.error_response import ErrorResponse
from .auth_strategy import AuthStrategyHandler


class InternalHttpClient:
    """
    Internal HTTP client for Miso Controller communication with automatic client token management.

    This class contains the core HTTP functionality without logging.
    It is wrapped by the public HttpClient class which adds audit and debug logging.
    """

    def __init__(self, config: MisoClientConfig):
        """
        Initialize internal HTTP client with configuration.

        Args:
            config: MisoClient configuration
        """
        self.config = config
        self.client: Optional[httpx.AsyncClient] = None
        self.client_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.token_refresh_lock = asyncio.Lock()

    async def _initialize_client(self):
        """Initialize HTTP client if not already initialized."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=self.config.controller_url,
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                },
            )

    async def _get_client_token(self) -> str:
        """
        Get client token, fetching if needed.

        Proactively refreshes if token will expire within 60 seconds.

        Returns:
            Client token string

        Raises:
            AuthenticationError: If token fetch fails
        """
        await self._initialize_client()

        now = datetime.now()

        # If token exists and not expired (with 60s buffer for proactive refresh), return it
        if (
            self.client_token
            and self.token_expires_at
            and self.token_expires_at > now + timedelta(seconds=60)
        ):
            assert self.client_token is not None
            return self.client_token

        # Acquire lock to prevent concurrent token fetches
        async with self.token_refresh_lock:
            # Double-check after acquiring lock
            if (
                self.client_token
                and self.token_expires_at
                and self.token_expires_at > now + timedelta(seconds=60)
            ):
                assert self.client_token is not None
                return self.client_token

            # Fetch new token
            await self._fetch_client_token()
            assert self.client_token is not None
            return self.client_token

    def _extract_correlation_id(self, response: Optional[httpx.Response] = None) -> Optional[str]:
        """
        Extract correlation ID from response headers.

        Checks common correlation ID header names.

        Args:
            response: HTTP response object (optional)

        Returns:
            Correlation ID string if found, None otherwise
        """
        if not response:
            return None

        # Check common correlation ID header names (case-insensitive)
        correlation_headers = [
            "x-correlation-id",
            "x-request-id",
            "correlation-id",
            "correlationId",
            "x-correlationid",
            "request-id",
        ]

        for header_name in correlation_headers:
            correlation_id = response.headers.get(header_name) or response.headers.get(
                header_name.lower()
            )
            if correlation_id:
                return str(correlation_id)

        return None

    async def _fetch_client_token(self) -> None:
        """
        Fetch client token from controller.

        Raises:
            AuthenticationError: If token fetch fails
        """
        await self._initialize_client()

        client_id = self.config.client_id
        response: Optional[httpx.Response] = None
        correlation_id: Optional[str] = None

        try:
            # Use a temporary client to avoid interceptor recursion
            temp_client = httpx.AsyncClient(
                base_url=self.config.controller_url,
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                    "x-client-id": client_id,
                    "x-client-secret": self.config.client_secret,
                },
            )

            response = await temp_client.post("/api/v1/auth/token")
            await temp_client.aclose()

            # Extract correlation ID from response
            correlation_id = self._extract_correlation_id(response)

            if response.status_code != 200:
                error_msg = f"Failed to get client token: HTTP {response.status_code}"
                if client_id:
                    error_msg += f" (clientId: {client_id})"
                if correlation_id:
                    error_msg += f" (correlationId: {correlation_id})"
                raise AuthenticationError(error_msg, status_code=response.status_code)

            data = response.json()

            # Handle nested response structure (data field)
            # If response has {'success': True, 'data': {...}}, extract data and preserve success
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
                nested_data = data["data"]
                # Merge success from top level if present
                if "success" in data:
                    nested_data["success"] = data["success"]
                data = nested_data

            token_response = ClientTokenResponse(**data)

            if not token_response.success or not token_response.token:
                error_msg = "Failed to get client token: Invalid response"
                if client_id:
                    error_msg += f" (clientId: {client_id})"
                if correlation_id:
                    error_msg += f" (correlationId: {correlation_id})"
                raise AuthenticationError(error_msg)

            self.client_token = token_response.token
            # Set expiration with 30 second buffer before actual expiration
            expires_in = max(0, token_response.expiresIn - 30)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

        except httpx.HTTPError as e:
            error_msg = f"Failed to get client token: {str(e)}"
            if client_id:
                error_msg += f" (clientId: {client_id})"
            if correlation_id:
                error_msg += f" (correlationId: {correlation_id})"
            raise ConnectionError(error_msg)
        except Exception as e:
            if isinstance(e, (AuthenticationError, ConnectionError)):
                raise
            error_msg = f"Failed to get client token: {str(e)}"
            if client_id:
                error_msg += f" (clientId: {client_id})"
            if correlation_id:
                error_msg += f" (correlationId: {correlation_id})"
            raise AuthenticationError(error_msg)

    async def _ensure_client_token(self):
        """Ensure client token is set in headers."""
        token = await self._get_client_token()
        if self.client:
            self.client.headers["x-client-token"] = token

    def _parse_error_response(self, response: httpx.Response, url: str) -> Optional[ErrorResponse]:
        """
        Parse structured error response from HTTP response.

        Args:
            response: HTTP response object
            url: Request URL (used for instance URI if not in response)

        Returns:
            ErrorResponse if response matches structure, None otherwise
        """
        if not response.headers.get("content-type", "").startswith("application/json"):
            return None

        try:
            response_data = response.json()
            # Check if response matches ErrorResponse structure
            if (
                isinstance(response_data, dict)
                and "errors" in response_data
                and "type" in response_data
                and "title" in response_data
                and "statusCode" in response_data
            ):
                # Set instance from URL if not provided
                if "instance" not in response_data or not response_data["instance"]:
                    response_data["instance"] = url
                return ErrorResponse(**response_data)
        except (ValueError, TypeError, KeyError):
            # JSON parsing failed or structure doesn't match
            pass

        return None

    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def get(self, url: str, **kwargs) -> Any:
        """
        Make GET request.

        Args:
            url: Request URL
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """
        await self._initialize_client()
        await self._ensure_client_token()
        try:
            assert self.client is not None
            response = await self.client.get(url, **kwargs)

            # Handle 401 - clear token to force refresh
            if response.status_code == 401:
                self.client_token = None
                self.token_expires_at = None

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Try to parse structured error response
            error_response = self._parse_error_response(e.response, url)
            error_body = {}
            if (
                e.response.headers.get("content-type", "").startswith("application/json")
                and not error_response
            ):
                try:
                    error_body = e.response.json()
                except (ValueError, TypeError):
                    pass

            raise MisoClientError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                error_body=error_body,
                error_response=error_response,
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def post(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """
        Make POST request.

        Args:
            url: Request URL
            data: Request data (will be JSON encoded)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """
        await self._initialize_client()
        await self._ensure_client_token()
        try:
            assert self.client is not None
            response = await self.client.post(url, json=data, **kwargs)

            if response.status_code == 401:
                self.client_token = None
                self.token_expires_at = None

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Try to parse structured error response
            error_response = self._parse_error_response(e.response, url)
            error_body = {}
            if (
                e.response.headers.get("content-type", "").startswith("application/json")
                and not error_response
            ):
                try:
                    error_body = e.response.json()
                except (ValueError, TypeError):
                    pass

            raise MisoClientError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                error_body=error_body,
                error_response=error_response,
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def put(self, url: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """
        Make PUT request.

        Args:
            url: Request URL
            data: Request data (will be JSON encoded)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """
        await self._initialize_client()
        await self._ensure_client_token()
        try:
            assert self.client is not None
            response = await self.client.put(url, json=data, **kwargs)

            if response.status_code == 401:
                self.client_token = None
                self.token_expires_at = None

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Try to parse structured error response
            error_response = self._parse_error_response(e.response, url)
            error_body = {}
            if (
                e.response.headers.get("content-type", "").startswith("application/json")
                and not error_response
            ):
                try:
                    error_body = e.response.json()
                except (ValueError, TypeError):
                    pass

            raise MisoClientError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                error_body=error_body,
                error_response=error_response,
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def delete(self, url: str, **kwargs) -> Any:
        """
        Make DELETE request.

        Args:
            url: Request URL
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """
        await self._initialize_client()
        await self._ensure_client_token()
        try:
            assert self.client is not None
            response = await self.client.delete(url, **kwargs)

            if response.status_code == 401:
                self.client_token = None
                self.token_expires_at = None

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Try to parse structured error response
            error_response = self._parse_error_response(e.response, url)
            error_body = {}
            if (
                e.response.headers.get("content-type", "").startswith("application/json")
                and not error_response
            ):
                try:
                    error_body = e.response.json()
                except (ValueError, TypeError):
                    pass

            raise MisoClientError(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code,
                error_body=error_body,
                error_response=error_response,
            )
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Generic request method.

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
        auth_strategy: Optional[AuthStrategy] = None,
        **kwargs,
    ) -> Any:
        """
        Make authenticated request with Bearer token.

        IMPORTANT: Client token is sent as x-client-token header (via _ensure_client_token)
        User token is sent as Authorization: Bearer header (this method parameter)
        These are two separate tokens for different purposes.

        Args:
            method: HTTP method
            url: Request URL
            token: User authentication token (sent as Bearer token)
            data: Request data (for POST/PUT)
            auth_strategy: Optional authentication strategy (defaults to bearer + client-token)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If request fails
        """
        # If no strategy provided, use default (backward compatibility)
        if auth_strategy is None:
            auth_strategy = AuthStrategyHandler.get_default_strategy()
            # Set bearer token from parameter
            auth_strategy.bearerToken = token

        # Use request_with_auth_strategy for consistency
        return await self.request_with_auth_strategy(method, url, auth_strategy, data, **kwargs)

    async def request_with_auth_strategy(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Make request with authentication strategy (priority-based fallback).

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
        await self._initialize_client()

        # Get client token once (used by client-token and client-credentials methods)
        # Client token is always sent (identifies the application)
        client_token: Optional[str] = None
        if "client-token" in auth_strategy.methods or "client-credentials" in auth_strategy.methods:
            client_token = await self._get_client_token()

        # Try each method in priority order
        last_error: Optional[Exception] = None
        for auth_method in auth_strategy.methods:
            try:
                # Build headers for this auth method
                auth_headers = AuthStrategyHandler.build_auth_headers(
                    auth_method, auth_strategy, client_token
                )

                # Merge with existing headers
                request_headers = kwargs.get("headers", {}).copy()
                request_headers.update(auth_headers)
                request_kwargs = {**kwargs, "headers": request_headers}

                # Make the request using existing request method
                # Note: request() will call _ensure_client_token() which always sends client token
                try:
                    return await self.request(method, url, data, **request_kwargs)
                except httpx.HTTPStatusError as e:
                    # If 401, try next method
                    if e.response.status_code == 401:
                        # Clear client token to force refresh on next attempt
                        if auth_method in ["client-token", "client-credentials"]:
                            self.client_token = None
                            self.token_expires_at = None
                        last_error = e
                        continue
                    # For other HTTP errors, re-raise (don't try next method)
                    raise
                except httpx.RequestError as e:
                    # Connection errors - don't retry with different auth
                    raise ConnectionError(f"Request failed: {str(e)}")

            except ValueError as e:
                # Missing credentials for this method - try next
                last_error = e
                continue
            except (ConnectionError, MisoClientError):
                # Don't retry connection errors or non-401 client errors
                raise

        # All methods failed
        if last_error:
            status_code = getattr(last_error, "status_code", 401)
            error_response = None
            if hasattr(last_error, "error_response"):
                error_response = last_error.error_response
            raise MisoClientError(
                f"All authentication methods failed. Last error: {str(last_error)}",
                status_code=status_code,
                error_response=error_response,
            )
        raise AuthenticationError("No authentication methods available")

    async def get_environment_token(self) -> str:
        """
        Get environment token using client credentials.

        This is called automatically by HttpClient but can be called manually.

        Returns:
            Client token string
        """
        return await self._get_client_token()
