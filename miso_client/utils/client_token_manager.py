"""
Client token manager for InternalHttpClient.

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


class ClientTokenManager:
    """
    Manages client token lifecycle including fetching, caching, and expiration.

    This class handles all client token operations for InternalHttpClient.
    """

    def __init__(self, config: MisoClientConfig):
        """
        Initialize client token manager.

        Args:
            config: MisoClient configuration
        """
        self.config = config
        self.client_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.token_refresh_lock = asyncio.Lock()

    def extract_correlation_id(self, response: Optional[httpx.Response] = None) -> Optional[str]:
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

    async def get_client_token(self) -> str:
        """
        Get client token, fetching if needed.

        Proactively refreshes if token will expire within 60 seconds.

        Returns:
            Client token string

        Raises:
            AuthenticationError: If token fetch fails
        """
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
            await self.fetch_client_token()
            assert self.client_token is not None
            return self.client_token

    async def fetch_client_token(self) -> None:
        """
        Fetch client token from controller.

        Raises:
            AuthenticationError: If token fetch fails
        """
        client_id = self.config.client_id
        response: Optional[httpx.Response] = None
        correlation_id: Optional[str] = None

        try:
            # Use resolved URL for temporary client
            resolved_url = resolve_controller_url(self.config)
            # Use a temporary client to avoid interceptor recursion
            temp_client = httpx.AsyncClient(
                base_url=resolved_url,
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                    "x-client-id": client_id,
                    "x-client-secret": self.config.client_secret,
                },
            )

            # Use configurable client token URI or default
            token_uri = self.config.clientTokenUri or "/api/v1/auth/token"
            response = await temp_client.post(token_uri)
            await temp_client.aclose()

            # Extract correlation ID from response
            correlation_id = self.extract_correlation_id(response)

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

            # Calculate expiration: use expiresIn if available, otherwise decode JWT to get exp claim
            expires_in = token_response.expiresIn
            if not expires_in or expires_in <= 0:
                # Try to extract expiration from JWT token
                try:
                    decoded = decode_token(token_response.token)
                    if decoded and "exp" in decoded and isinstance(decoded["exp"], (int, float)):
                        # Calculate expires_in from JWT exp claim
                        token_exp = datetime.fromtimestamp(decoded["exp"])
                        now = datetime.now()
                        expires_in = max(0, int((token_exp - now).total_seconds()))
                    else:
                        # No expiration found, use default (30 minutes)
                        expires_in = 1800
                except Exception:
                    # JWT decode failed, use default (30 minutes)
                    expires_in = 1800

            # Set expiration with 30 second buffer before actual expiration
            expires_in = max(0, expires_in - 30)
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

    def clear_token(self) -> None:
        """
        Clear cached client token.

        Forces token refresh on next request.
        """
        self.client_token = None
        self.token_expires_at = None
