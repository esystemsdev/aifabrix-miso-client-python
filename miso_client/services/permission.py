"""
Permission service for user authorization with caching.

This module handles permission-based access control with caching support.
Permissions are cached with Redis and in-memory fallback using CacheService.
Optimized to extract userId from JWT token before API calls for cache optimization.
"""

import logging
import time
from typing import TYPE_CHECKING, List, Optional, cast

from ..models.config import AuthStrategy, PermissionResult
from ..services.cache import CacheService
from ..utils.auth_utils import validate_token_request
from ..utils.error_utils import extract_correlation_id_from_error
from ..utils.http_client import HttpClient
from ..utils.jwt_tools import extract_user_id

if TYPE_CHECKING:
    from ..api import ApiClient

logger = logging.getLogger(__name__)


class PermissionService:
    """Permission service for user authorization with caching."""

    def __init__(
        self, http_client: HttpClient, cache: CacheService, api_client: Optional["ApiClient"] = None
    ):
        """
        Initialize permission service.

        Args:
            http_client: HTTP client instance (for backward compatibility)
            cache: Cache service instance (handles Redis + in-memory fallback)
            api_client: Optional API client instance (for typed API calls)
        """
        self.config = http_client.config
        self.http_client = http_client
        self.cache = cache
        self.api_client = api_client
        self.permission_ttl = self.config.permission_ttl

    async def get_permissions(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> List[str]:
        """
        Get user permissions with Redis caching.

        Optimized to extract userId from token first to check cache before API call.

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            List of user permissions
        """
        try:
            # Extract userId from token to check cache first (avoids API call on cache hit)
            user_id = extract_user_id(token)
            cache_key = f"permissions:{user_id}" if user_id else None

            # Check cache first if we have userId
            if cache_key:
                cached_data = await self.cache.get(cache_key)
                if cached_data and isinstance(cached_data, dict):
                    return cast(List[str], cached_data.get("permissions", []))

            # Cache miss or no userId in token - fetch from controller
            # If we don't have userId, get it from validate endpoint
            if not user_id:
                user_info = await validate_token_request(
                    token, self.http_client, self.api_client, auth_strategy
                )
                user_id = user_info.get("user", {}).get("id") if user_info else None
                if not user_id:
                    return []
                cache_key = f"permissions:{user_id}"

            # Cache miss - fetch from controller
            if self.api_client:
                # Use ApiClient for typed API calls
                response = await self.api_client.permissions.get_permissions(
                    token, auth_strategy=auth_strategy
                )
                permissions = response.data.permissions or []
            else:
                # Fallback to HttpClient for backward compatibility
                if auth_strategy is not None:
                    permission_result = await self.http_client.authenticated_request(
                        "GET", "/api/v1/auth/permissions", token, auth_strategy=auth_strategy
                    )
                else:
                    permission_result = await self.http_client.authenticated_request(
                        "GET", "/api/v1/auth/permissions", token
                    )

                permission_data = PermissionResult(**permission_result)
                permissions = permission_data.permissions or []

            # Cache the result (CacheService handles Redis + in-memory automatically)
            assert cache_key is not None
            await self.cache.set(
                cache_key,
                {"permissions": permissions, "timestamp": int(time.time() * 1000)},
                self.permission_ttl,
            )

            return permissions

        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Failed to get permissions",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
            return []

    async def has_permission(
        self, token: str, permission: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Check if user has specific permission.

        Args:
            token: JWT token
            permission: Permission to check
            auth_strategy: Optional authentication strategy

        Returns:
            True if user has the permission, False otherwise
        """
        permissions = await self.get_permissions(token, auth_strategy=auth_strategy)
        return permission in permissions

    async def has_any_permission(
        self, token: str, permissions: List[str], auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Check if user has any of the specified permissions.

        Args:
            token: JWT token
            permissions: List of permissions to check
            auth_strategy: Optional authentication strategy

        Returns:
            True if user has any of the permissions, False otherwise
        """
        user_permissions = await self.get_permissions(token, auth_strategy=auth_strategy)
        return any(permission in user_permissions for permission in permissions)

    async def has_all_permissions(
        self, token: str, permissions: List[str], auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Check if user has all of the specified permissions.

        Args:
            token: JWT token
            permissions: List of permissions to check
            auth_strategy: Optional authentication strategy

        Returns:
            True if user has all permissions, False otherwise
        """
        user_permissions = await self.get_permissions(token, auth_strategy=auth_strategy)
        return all(permission in user_permissions for permission in permissions)

    async def refresh_permissions(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> List[str]:
        """
        Force refresh permissions from controller (bypass cache).

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            Fresh list of user permissions
        """
        try:
            # Get user info to extract userId
            user_info = await validate_token_request(
                token, self.http_client, self.api_client, auth_strategy
            )
            user_id = user_info.get("user", {}).get("id") if user_info else None
            if not user_id:
                return []

            cache_key = f"permissions:{user_id}"

            # Fetch fresh permissions from controller using refresh endpoint
            if self.api_client:
                # Use ApiClient for typed API calls
                response = await self.api_client.permissions.refresh_permissions(
                    token, auth_strategy=auth_strategy
                )
                permissions = response.data.permissions or []
            else:
                # Fallback to HttpClient for backward compatibility
                if auth_strategy is not None:
                    permission_result = await self.http_client.authenticated_request(
                        "GET",
                        "/api/v1/auth/permissions/refresh",
                        token,
                        auth_strategy=auth_strategy,
                    )
                else:
                    permission_result = await self.http_client.authenticated_request(
                        "GET", "/api/v1/auth/permissions/refresh", token
                    )

                permission_data = PermissionResult(**permission_result)
                permissions = permission_data.permissions or []

            # Update cache with fresh data (CacheService handles Redis + in-memory automatically)
            await self.cache.set(
                cache_key,
                {"permissions": permissions, "timestamp": int(time.time() * 1000)},
                self.permission_ttl,
            )

            return permissions

        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Failed to refresh permissions",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
            return []

    async def clear_permissions_cache(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> None:
        """
        Clear cached permissions for a user.

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy
        """
        try:
            # Get user info to extract userId
            user_info = await validate_token_request(
                token, self.http_client, self.api_client, auth_strategy
            )
            user_id = user_info.get("user", {}).get("id") if user_info else None
            if not user_id:
                return

            cache_key = f"permissions:{user_id}"

            # Clear from cache (CacheService handles Redis + in-memory automatically)
            await self.cache.delete(cache_key)

        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Failed to clear permissions cache",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
            # Silently continue per service method pattern
