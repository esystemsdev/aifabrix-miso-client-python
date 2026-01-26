"""
Authentication service for token validation and user management.

This module handles authentication operations including client token management,
token validation, user information retrieval, and logout functionality.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from ..models.config import AuthResult, AuthStrategy, UserInfo
from ..services.auth_token_cache import (
    cache_validation_result,
    check_cache_for_token,
)
from ..services.auth_user_cache import (
    cache_user_info,
    check_user_info_cache,
    clear_user_cache,
    get_user_cache_key,
)
from ..services.cache import CacheService
from ..services.redis import RedisService
from ..utils.auth_cache_helpers import get_cache_ttl_from_token, get_token_cache_key
from ..utils.error_utils import extract_correlation_id_from_error
from ..utils.http_client import HttpClient

if TYPE_CHECKING:
    from ..api import ApiClient

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for token validation and user management."""

    def __init__(
        self,
        http_client: HttpClient,
        redis: RedisService,
        cache: Optional[CacheService] = None,
        api_client: Optional["ApiClient"] = None,
    ):
        """
        Initialize authentication service.

        Args:
            http_client: HTTP client instance (for backward compatibility)
            redis: Redis service instance
            cache: Optional cache service instance (for token validation caching)
            api_client: Optional API client instance (for typed API calls)
        """
        self.config = http_client.config
        self.http_client = http_client
        self.redis = redis
        self.cache = cache
        self.api_client = api_client
        self.validation_ttl = self.config.validation_ttl
        self.user_ttl = self.config.user_ttl

    def _get_token_cache_key(self, token: str) -> str:
        """
        Generate cache key for token validation using SHA-256 hash.

        Uses token hash instead of full token for security.

        Args:
            token: JWT token string

        Returns:
            Cache key string in format: token_validation:{sha256_hash}
        """
        return get_token_cache_key(token)

    def _get_cache_ttl_from_token(self, token: str) -> int:
        """
        Calculate smart TTL based on token expiration.

        If token has expiration claim, cache until token_exp - 30s buffer.
        Minimum: 60 seconds, Maximum: validation_ttl.

        Args:
            token: JWT token string

        Returns:
            TTL in seconds
        """
        return get_cache_ttl_from_token(token, self.validation_ttl)

    def _get_user_cache_key(self, user_id: str) -> str:
        """
        Generate cache key for user info.

        Args:
            user_id: User ID string

        Returns:
            Cache key string in format: user:{userId}
        """
        return get_user_cache_key(user_id)

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

    async def _check_cache_for_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Check cache for token validation result.

        Args:
            token: JWT token to check

        Returns:
            Cached validation result if found, None otherwise
        """
        cache_key = self._get_token_cache_key(token)
        return await check_cache_for_token(self.cache, cache_key)

    async def _fetch_validation_from_api_client(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Dict[str, Any]:
        """
        Fetch token validation using ApiClient.

        Args:
            token: JWT token to validate
            auth_strategy: Optional authentication strategy

        Returns:
            Validation result dictionary
        """
        if not self.api_client:
            raise ValueError("ApiClient is required for this method")
        response = await self.api_client.auth.validate_token(token, auth_strategy=auth_strategy)
        # Extract data from typed response (matches OpenAPI spec format)
        return {
            "data": {
                "authenticated": response.data.authenticated,
                "user": response.data.user.model_dump() if response.data.user else None,
                "expiresAt": response.data.expiresAt,
            },
        }

    async def _fetch_validation_from_http_client(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Dict[str, Any]:
        """
        Fetch token validation using HttpClient (backward compatibility).

        Args:
            token: JWT token to validate
            auth_strategy: Optional authentication strategy

        Returns:
            Validation result dictionary
        """
        if auth_strategy is not None:
            result = await self.http_client.authenticated_request(
                "POST",
                "/api/v1/auth/validate",
                token,
                {"token": token},
                auth_strategy=auth_strategy,
            )
            return result  # type: ignore[no-any-return]

        result = await self.http_client.authenticated_request(
            "POST", "/api/v1/auth/validate", token, {"token": token}
        )
        return result  # type: ignore[no-any-return]

    async def _fetch_validation_from_api(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Dict[str, Any]:
        """
        Fetch token validation from API (ApiClient or HttpClient).

        Args:
            token: JWT token to validate
            auth_strategy: Optional authentication strategy

        Returns:
            Validation result dictionary
        """
        if self.api_client:
            return await self._fetch_validation_from_api_client(token, auth_strategy)
        else:
            return await self._fetch_validation_from_http_client(token, auth_strategy)

    async def _cache_validation_result(self, token: str, result: Dict[str, Any]) -> None:
        """
        Cache successful validation results.

        Args:
            token: JWT token that was validated
            result: Validation result dictionary
        """
        cache_key = self._get_token_cache_key(token)
        ttl = self._get_cache_ttl_from_token(token)
        await cache_validation_result(self.cache, cache_key, result, ttl)

    async def _validate_token_request(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Dict[str, Any]:
        """
        Helper method to call /api/v1/auth/validate endpoint with proper request body.

        Checks cache before making HTTP request and caches successful validation results.

        Args:
            token: JWT token to validate
            auth_strategy: Optional authentication strategy

        Returns:
            Validation result dictionary
        """
        # Check cache first
        cached_result = await self._check_cache_for_token(token)
        if cached_result:
            return cached_result

        # Cache miss - fetch from API
        result = await self._fetch_validation_from_api(token, auth_strategy)

        # Cache successful validation results
        await self._cache_validation_result(token, result)

        return result

    def _log_error(self, message: str, error: Exception) -> None:
        """Log error with correlation ID if available."""
        correlation_id = extract_correlation_id_from_error(error)
        extra = {"correlationId": correlation_id} if correlation_id else None
        logger.error(message, exc_info=error, extra=extra)

    async def login(self, redirect: str, state: Optional[str] = None) -> Dict[str, Any]:
        """
        Initiate login flow by calling GET /api/v1/auth/login.

        Args:
            redirect: Callback URL for Keycloak redirect
            state: Optional CSRF protection token

        Returns:
            Dictionary with loginUrl and state, or empty dict on error
        """
        try:
            if self.api_client:
                response = await self.api_client.auth.login(redirect, state)
                return {"data": {"loginUrl": response.data.loginUrl, "state": state}}

            params = {"redirect": redirect}
            if state:
                params["state"] = state
            return await self.http_client.get("/api/v1/auth/login", params=params)  # type: ignore
        except Exception as error:
            self._log_error("Login failed", error)
            return {}

    def _is_api_key_auth(self, token: str) -> bool:
        """Check if token matches configured API_KEY."""
        return bool(self.config.api_key and token == self.config.api_key)

    async def validate_token(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Validate token with controller. API_KEY bypasses OAuth2 validation.

        Args:
            token: JWT token to validate (or API_KEY for testing)
            auth_strategy: Optional authentication strategy

        Returns:
            True if token is valid, False otherwise
        """
        if self._is_api_key_auth(token):
            return True

        try:
            result = await self._validate_token_request(token, auth_strategy)
            auth_data = result.get("data", result)
            return AuthResult(**auth_data).authenticated
        except Exception as error:
            self._log_error("Token validation failed", error)
            return False

    async def get_user(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Optional[UserInfo]:
        """
        Get user information from token validation.

        Args:
            token: JWT token (or API_KEY for testing)
            auth_strategy: Optional authentication strategy

        Returns:
            UserInfo if token is valid, None otherwise (including API_KEY auth)
        """
        if self._is_api_key_auth(token):
            return None

        try:
            result = await self._validate_token_request(token, auth_strategy)
            data = result.get("data", {})
            if data.get("authenticated") and data.get("user"):
                return UserInfo(**data["user"])
            return None
        except Exception as error:
            self._log_error("Failed to get user info", error)
            return None

    async def _check_user_info_cache(self, token: str) -> Optional[UserInfo]:
        """
        Check cache for user info.

        Args:
            token: JWT token to extract userId from

        Returns:
            Cached UserInfo if found, None otherwise
        """
        return await check_user_info_cache(self.cache, token)

    async def _cache_user_info(self, token: str, user_info: UserInfo) -> None:
        """
        Cache user info result.

        Args:
            token: JWT token to extract userId from
            user_info: UserInfo to cache
        """
        await cache_user_info(self.cache, token, user_info, self.user_ttl)

    async def get_user_info(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Optional[UserInfo]:
        """
        Get user information from GET /api/v1/auth/user endpoint.

        Results are cached using userId from token with configurable TTL (default 5 min).

        Args:
            token: JWT token (or API_KEY for testing)
            auth_strategy: Optional authentication strategy

        Returns:
            UserInfo if token is valid, None otherwise (including API_KEY auth)
        """
        if self._is_api_key_auth(token):
            return None

        try:
            # Check cache first
            cached_user = await self._check_user_info_cache(token)
            if cached_user:
                return cached_user

            # Cache miss - fetch from controller
            if self.api_client:
                response = await self.api_client.auth.get_user(token, auth_strategy=auth_strategy)
                user_info = response.data.user
            else:
                user_data = await self.http_client.authenticated_request(
                    "GET", "/api/v1/auth/user", token, auth_strategy=auth_strategy
                )
                user_info = UserInfo(**user_data)

            # Cache the result
            if user_info:
                await self._cache_user_info(token, user_info)

            return user_info
        except Exception as error:
            self._log_error("Failed to get user info", error)
            return None

    async def clear_user_cache(self, token: str) -> None:
        """
        Clear cached user info for a user.

        Args:
            token: JWT token to extract userId from
        """
        await clear_user_cache(self.cache, token)

    async def _clear_logout_caches(self, token: str) -> None:
        """Clear token and user caches after logout."""
        try:
            self.http_client.clear_user_token(token)
        except Exception:
            pass  # Silently continue if cache clearing fails

        if self.cache:
            # Clear token validation cache
            try:
                await self.cache.delete(self._get_token_cache_key(token))
                logger.debug("Token validation cache cleared on logout")
            except Exception as error:
                logger.warning("Failed to clear validation cache on logout", exc_info=error)

            # Clear user info cache
            await self.clear_user_cache(token)

    async def logout(self, token: str) -> Dict[str, Any]:
        """
        Logout user by invalidating the access token via POST /api/v1/auth/logout.

        Args:
            token: Access token to invalidate

        Returns:
            Response dict with data field, or empty dict on error
        """
        try:
            if self.api_client:
                await self.api_client.auth.logout(token)
                result: Dict[str, Any] = {"data": None}
            else:
                result = await self.http_client.authenticated_request(
                    "POST", "/api/v1/auth/logout", token, {"token": token}
                )

            await self._clear_logout_caches(token)
            return result
        except Exception as error:
            self._log_error("Logout failed", error)
            return {}

    async def refresh_user_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh user access token using refresh token.

        Args:
            refresh_token: Refresh token string

        Returns:
            Dict with token, refreshToken, expiresIn, or None if refresh fails
        """
        try:
            if self.api_client:
                response = await self.api_client.auth.refresh_token(refresh_token)
                return {
                    "data": {
                        "token": response.data.accessToken,
                        "accessToken": response.data.accessToken,
                        "refreshToken": response.data.refreshToken,
                        "expiresIn": response.data.expiresIn,
                    },
                }

            return cast(
                Optional[Dict[str, Any]],
                await self.http_client.request(
                    "POST", "/api/v1/auth/refresh", {"refreshToken": refresh_token}
                ),
            )
        except Exception as error:
            self._log_error("Failed to refresh user token", error)
            return None

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
