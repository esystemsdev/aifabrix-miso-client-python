"""
Internal HTTP client utility for controller communication.

This module provides the internal HTTP client implementation with automatic client
token management. This class is not meant to be used directly - use the public
HttpClient class instead which adds ISO 27001 compliant audit and debug logging.
"""

from typing import Any, Dict, Literal, Optional

import httpx

from ..errors import AuthenticationError, ConnectionError, MisoClientError
from ..models.config import AuthStrategy, MisoClientConfig
from .auth_strategy import AuthStrategyHandler
from .client_token_manager import ClientTokenManager
from .controller_url_resolver import resolve_controller_url
from .http_error_handler import parse_error_response


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
        self.token_manager = ClientTokenManager(config)

    async def _initialize_client(self):
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

    async def _ensure_client_token(self):
        """Ensure client token is set in headers."""
        await self._initialize_client()
        token = await self.token_manager.get_client_token()
        if self.client:
            self.client.headers["x-client-token"] = token

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
                self.token_manager.clear_token()

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Try to parse structured error response
            error_response = parse_error_response(e.response, url)
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
                self.token_manager.clear_token()

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Try to parse structured error response
            error_response = parse_error_response(e.response, url)
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
                self.token_manager.clear_token()

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Try to parse structured error response
            error_response = parse_error_response(e.response, url)
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
                self.token_manager.clear_token()

            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Try to parse structured error response
            error_response = parse_error_response(e.response, url)
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
            client_token = await self.token_manager.get_client_token()

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
                            self.token_manager.clear_token()
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
        return await self.token_manager.get_client_token()
