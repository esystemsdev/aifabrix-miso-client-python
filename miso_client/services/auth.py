"""
Authentication service for token validation and user management.

This module handles authentication operations including client token management,
token validation, user information retrieval, and logout functionality.
"""

import logging
from typing import Optional

from ..models.config import AuthResult, AuthStrategy, UserInfo
from ..services.redis import RedisService
from ..utils.http_client import HttpClient

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for token validation and user management."""

    def __init__(self, http_client: HttpClient, redis: RedisService):
        """
        Initialize authentication service.

        Args:
            http_client: HTTP client instance
            redis: Redis service instance
        """
        self.config = http_client.config
        self.http_client = http_client
        self.redis = redis

    async def get_environment_token(self) -> str:
        """
        Get environment token using client credentials.

        This is called automatically by HttpClient, but can be called manually if needed.

        Returns:
            Client token string

        Raises:
            AuthenticationError: If token fetch fails
        """
        return await self.http_client.get_environment_token()

    def login(self, redirect_uri: str) -> str:
        """
        Initiate login flow by redirecting to controller.

        Returns the login URL for browser redirect or manual navigation.
        Backend will extract environment and application from client token.

        Args:
            redirect_uri: URI to redirect to after successful login

        Returns:
            Login URL string
        """
        return f"{self.config.controller_url}/api/auth/login?redirect={redirect_uri}"

    async def validate_token(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Validate token with controller.

        If API_KEY is configured and token matches it, bypasses OAuth2 validation.

        Args:
            token: JWT token to validate (or API_KEY for testing)
            auth_strategy: Optional authentication strategy

        Returns:
            True if token is valid, False otherwise
        """
        # Check API_KEY first (for testing)
        if self.config.api_key and token == self.config.api_key:
            return True

        # Fall back to OAuth2 validation
        try:
            if auth_strategy is not None:
                result = await self.http_client.authenticated_request(
                    "POST", "/api/auth/validate", token, auth_strategy=auth_strategy
                )
            else:
                result = await self.http_client.authenticated_request(
                    "POST", "/api/auth/validate", token
                )

            auth_result = AuthResult(**result)
            return auth_result.authenticated

        except Exception as error:
            logger.error("Token validation failed", exc_info=error)
            return False

    async def get_user(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Optional[UserInfo]:
        """
        Get user information from token.

        If API_KEY is configured and token matches it, returns None (no user info for API key auth).

        Args:
            token: JWT token (or API_KEY for testing)
            auth_strategy: Optional authentication strategy

        Returns:
            UserInfo if token is valid, None otherwise
        """
        # Check API_KEY first (for testing)
        if self.config.api_key and token == self.config.api_key:
            # API key authentication doesn't provide user info
            return None

        # Fall back to OAuth2 validation
        try:
            if auth_strategy is not None:
                result = await self.http_client.authenticated_request(
                    "POST", "/api/auth/validate", token, auth_strategy=auth_strategy
                )
            else:
                result = await self.http_client.authenticated_request(
                    "POST", "/api/auth/validate", token
                )

            auth_result = AuthResult(**result)

            if auth_result.authenticated and auth_result.user:
                return auth_result.user

            return None

        except Exception as error:
            logger.error("Failed to get user info", exc_info=error)
            return None

    async def get_user_info(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Optional[UserInfo]:
        """
        Get user information from GET /api/auth/user endpoint.

        If API_KEY is configured and token matches it, returns None (no user info for API key auth).

        Args:
            token: JWT token (or API_KEY for testing)
            auth_strategy: Optional authentication strategy

        Returns:
            UserInfo if token is valid, None otherwise
        """
        # Check API_KEY first (for testing)
        if self.config.api_key and token == self.config.api_key:
            # API key authentication doesn't provide user info
            return None

        # Fall back to OAuth2 validation
        try:
            if auth_strategy is not None:
                user_data = await self.http_client.authenticated_request(
                    "GET", "/api/auth/user", token, auth_strategy=auth_strategy
                )
            else:
                user_data = await self.http_client.authenticated_request(
                    "GET", "/api/auth/user", token
                )

            return UserInfo(**user_data)

        except Exception as error:
            logger.error("Failed to get user info", exc_info=error)
            return None

    async def logout(self) -> None:
        """
        Logout user.

        Backend extracts app/env from client token (no body needed).
        """
        try:
            # Backend extracts app/env from client token
            await self.http_client.request("POST", "/api/auth/logout")
        except Exception as error:
            logger.error("Logout failed", exc_info=error)
            # Silently fail per service method pattern

    async def is_authenticated(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Check if user is authenticated (has valid token).

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            True if user is authenticated, False otherwise
        """
        if auth_strategy is not None:
            return await self.validate_token(token, auth_strategy=auth_strategy)
        else:
            return await self.validate_token(token)
