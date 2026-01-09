"""
Authentication service for token validation and user management.

This module handles authentication operations including client token management,
token validation, user information retrieval, and logout functionality.
"""

import hashlib
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from ..models.config import AuthResult, AuthStrategy, UserInfo
from ..services.cache import CacheService
from ..services.redis import RedisService
from ..utils.error_utils import extract_correlation_id_from_error
from ..utils.http_client import HttpClient
from ..utils.jwt_tools import decode_token

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

    def _get_token_cache_key(self, token: str) -> str:
        """
        Generate cache key for token validation using SHA-256 hash.

        Uses token hash instead of full token for security.

        Args:
            token: JWT token string

        Returns:
            Cache key string in format: token_validation:{sha256_hash}
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return f"token_validation:{token_hash}"

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
        try:
            decoded = decode_token(token)
            if decoded and "exp" in decoded:
                token_exp = decoded["exp"]
                if isinstance(token_exp, (int, float)):
                    now = time.time()
                    # Calculate TTL as token_exp - now - 30s buffer
                    ttl = int(token_exp - now - 30)
                    # Clamp between min (60s) and max (validation_ttl)
                    return max(60, min(ttl, self.validation_ttl))
        except Exception:
            # If token expiration cannot be determined, use default TTL
            pass

        return self.validation_ttl

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
        if not self.cache:
            return None

        cache_key = self._get_token_cache_key(token)
        cached_result = await self.cache.get(cache_key)
        if cached_result and isinstance(cached_result, dict):
            logger.debug("Token validation cache hit")
            return cast(Dict[str, Any], cached_result)

        return None

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
        # Extract data from typed response
        return {
            "success": response.success,
            "data": {
                "authenticated": response.data.authenticated,
                "user": response.data.user.model_dump() if response.data.user else None,
                "expiresAt": response.data.expiresAt,
            },
            "timestamp": response.timestamp,
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
        if not self.cache:
            return

        result_dict: Dict[str, Any] = result
        if result_dict.get("data", {}).get("authenticated") is not True:
            return

        cache_key = self._get_token_cache_key(token)
        ttl = self._get_cache_ttl_from_token(token)
        try:
            await self.cache.set(cache_key, result_dict, ttl)
            logger.debug(f"Token validation cached with TTL: {ttl}s")
        except Exception as error:
            logger.warning("Failed to cache validation result", exc_info=error)

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

    async def login(self, redirect: str, state: Optional[str] = None) -> Dict[str, Any]:
        """
        Initiate login flow by calling the controller login endpoint.

        This method calls GET /api/v1/auth/login with redirect and optional state parameters.
        The controller returns a login URL that should be used to redirect the user to Keycloak.

        Args:
            redirect: Callback URL where Keycloak redirects after authentication (required)
            state: Optional CSRF protection token (auto-generated by backend if omitted)

        Returns:
            Dictionary containing:
                - success: True if successful
                - data: Dictionary with loginUrl and state
                - timestamp: Response timestamp

        Example:
            >>> response = await auth_service.login(
            ...     redirect="http://localhost:3000/auth/callback",
            ...     state="abc123"
            ... )
            >>> login_url = response["data"]["loginUrl"]
            >>> state = response["data"]["state"]
        """
        try:
            if self.api_client:
                # Use ApiClient for typed API calls
                response = await self.api_client.auth.login(redirect, state)
                # Extract data from typed response
                return {
                    "success": response.success,
                    "data": {
                        "loginUrl": response.data.loginUrl,
                        "state": state,  # State is returned in response if provided
                    },
                    "timestamp": response.timestamp,
                }
            else:
                # Fallback to HttpClient for backward compatibility
                params = {"redirect": redirect}
                if state:
                    params["state"] = state

                response = await self.http_client.get("/api/v1/auth/login", params=params)
                return response  # type: ignore[no-any-return]
        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Login failed",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
            # Return empty dict on error per service method pattern
            return {}

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
            result = await self._validate_token_request(token, auth_strategy)
            auth_result = AuthResult(**result)
            return auth_result.authenticated

        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Token validation failed",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
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
            result = await self._validate_token_request(token, auth_strategy)
            # _validate_token_request returns dict with "data" key
            authenticated = result.get("data", {}).get("authenticated", False)
            user_data = result.get("data", {}).get("user")

            if authenticated and user_data:
                return UserInfo(**user_data)

            return None

        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Failed to get user info",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
            return None

    async def get_user_info(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Optional[UserInfo]:
        """
        Get user information from GET /api/v1/auth/user endpoint.

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
            if self.api_client:
                # Use ApiClient for typed API calls
                response = await self.api_client.auth.get_user(token, auth_strategy=auth_strategy)
                # Extract user from typed response
                return response.data.user
            else:
                # Fallback to HttpClient for backward compatibility
                if auth_strategy is not None:
                    user_data = await self.http_client.authenticated_request(
                        "GET", "/api/v1/auth/user", token, auth_strategy=auth_strategy
                    )
                else:
                    user_data = await self.http_client.authenticated_request(
                        "GET", "/api/v1/auth/user", token
                    )

                return UserInfo(**user_data)

        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Failed to get user info",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
            return None

    async def logout(self, token: str) -> Dict[str, Any]:
        """
        Logout user by invalidating the access token.

        This method calls POST /api/v1/auth/logout with the user's access token in the request body.
        The token will be invalidated on the server side, and JWT token cache will be cleared automatically.

        Args:
            token: Access token to invalidate (required)

        Returns:
            Dictionary containing:
                - success: True if successful
                - message: Success message
                - timestamp: Response timestamp

        Example:
            >>> response = await auth_service.logout(token="jwt-token-here")
            >>> if response.get("success"):
            ...     print("Logout successful")
        """
        try:
            if self.api_client:
                # Use ApiClient for typed API calls
                response = await self.api_client.auth.logout(token)
                # Extract data from typed response
                result = {
                    "success": response.success,
                    "message": response.message,
                    "timestamp": response.timestamp,
                }
            else:
                # Fallback to HttpClient for backward compatibility
                result = await self.http_client.authenticated_request(
                    "POST", "/api/v1/auth/logout", token, {"token": token}
                )
                result = result  # type: ignore[assignment]

            # Clear JWT token cache after successful logout
            try:
                self.http_client.clear_user_token(token)
            except Exception:
                # Silently continue if cache clearing fails
                pass

            # Clear validation cache entry after successful logout
            if self.cache:
                try:
                    cache_key = self._get_token_cache_key(token)
                    await self.cache.delete(cache_key)
                    logger.debug("Token validation cache cleared on logout")
                except Exception as error:
                    logger.warning("Failed to clear validation cache on logout", exc_info=error)

            return result  # type: ignore[no-any-return]
        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Logout failed",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
            # Return empty dict on error per service method pattern
            return {}

    async def refresh_user_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh user access token using refresh token.

        The refresh endpoint uses the refresh token in the request body for authentication.
        Client token is automatically sent via x-client-token header.

        Args:
            refresh_token: Refresh token string

        Returns:
            Dictionary containing:
                - token: New access token
                - refreshToken: New refresh token (if provided)
                - expiresIn: Token expiration in seconds
            None if refresh fails
        """
        try:
            if self.api_client:
                # Use ApiClient for typed API calls
                response = await self.api_client.auth.refresh_token(refresh_token)
                # Extract data from typed response
                # Map accessToken to token for backward compatibility
                return {
                    "success": response.success,
                    "data": {
                        "token": response.data.accessToken,  # Map accessToken to token
                        "accessToken": response.data.accessToken,
                        "refreshToken": response.data.refreshToken,
                        "expiresIn": response.data.expiresIn,
                    },
                    "message": response.message,
                    "timestamp": response.timestamp,
                }
            else:
                # Fallback to HttpClient for backward compatibility
                # Uses request() (not authenticated_request()) since refresh token is the auth
                response = await self.http_client.request(
                    "POST",
                    "/api/v1/auth/refresh",
                    {"refreshToken": refresh_token},
                )

                return response  # type: ignore[no-any-return]
        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Failed to refresh user token",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
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
