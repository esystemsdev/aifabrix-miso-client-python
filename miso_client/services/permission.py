"""Permission service for user authorization with caching.

This module handles permission-based access control with caching support.
Permissions are cached with Redis and in-memory fallback using CacheService.
Optimized to extract userId from JWT token before API calls for cache optimization.
"""

import logging
import time
from typing import TYPE_CHECKING, List, Optional, cast

from ..models.config import AuthStrategy, PermissionResult
from ..services.application_context import ApplicationContextService
from ..services.authorization_mixin import ApplicationContextMixin
from ..services.cache import CacheService
from ..utils.auth_utils import validate_token_request
from ..utils.error_utils import extract_correlation_id_from_error
from ..utils.http_client import HttpClient
from ..utils.jwt_tools import extract_user_id

if TYPE_CHECKING:
    from ..api import ApiClient

logger = logging.getLogger(__name__)


class PermissionService(ApplicationContextMixin):
    """Permission service for user authorization with caching."""

    def __init__(
        self, http_client: HttpClient, cache: CacheService, api_client: Optional["ApiClient"] = None
    ):
        """Initialize permission service.

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
        # Initialize application context service for automatic environment detection
        self._app_context_service: Optional[ApplicationContextService] = None

    def _build_cache_key(self, user_id: Optional[str]) -> Optional[str]:
        if not user_id:
            return None
        return f"permissions:{user_id}"

    async def _get_cached_permissions(self, cache_key: Optional[str]) -> Optional[List[str]]:
        if not cache_key:
            return None
        cached_data = await self.cache.get(cache_key)
        if cached_data and isinstance(cached_data, dict):
            return cast(List[str], cached_data.get("permissions", []))
        return None

    async def _resolve_user_id(
        self, token: str, user_id: Optional[str], auth_strategy: Optional[AuthStrategy]
    ) -> Optional[str]:
        if user_id:
            return user_id

        user_info = await validate_token_request(
            token, self.http_client, self.api_client, auth_strategy
        )
        return user_info.get("data", {}).get("user", {}).get("id") if user_info else None

    def _get_request_context(self) -> tuple[Optional[str], Optional[str]]:
        context = self._get_app_context_service().get_application_context_sync()
        environment = (
            context.environment
            if context.environment and context.environment != "unknown"
            else None
        )
        application = (
            context.application
            if context.application and context.application != "unknown"
            else None
        )
        return environment, application

    async def _fetch_permissions(
        self,
        token: str,
        environment: Optional[str],
        application: Optional[str],
        auth_strategy: Optional[AuthStrategy],
    ) -> List[str]:
        if self.api_client:
            return await self._fetch_permissions_with_api_client(
                token, environment, application, auth_strategy
            )
        return await self._fetch_permissions_with_http_client(
            token, environment, application, auth_strategy
        )

    async def _fetch_permissions_with_api_client(
        self,
        token: str,
        environment: Optional[str],
        application: Optional[str],
        auth_strategy: Optional[AuthStrategy],
    ) -> List[str]:
        api_client = self.api_client
        assert api_client is not None
        response = await api_client.permissions.get_permissions(
            token,
            environment=environment,
            application=application,
            auth_strategy=auth_strategy,
        )
        return response.data.permissions or []

    async def _fetch_permissions_with_http_client(
        self,
        token: str,
        environment: Optional[str],
        application: Optional[str],
        auth_strategy: Optional[AuthStrategy],
    ) -> List[str]:
        params: dict[str, str] = {}
        if environment:
            params["environment"] = environment
        if application:
            params["application"] = application

        if auth_strategy is not None:
            permission_result = await self.http_client.authenticated_request(
                "GET",
                "/api/v1/auth/permissions",
                token,
                params=params,
                auth_strategy=auth_strategy,
            )
        else:
            permission_result = await self.http_client.authenticated_request(
                "GET", "/api/v1/auth/permissions", token, params=params
            )

        permission_data = PermissionResult(**permission_result)
        return permission_data.permissions or []

    async def _cache_permissions(self, cache_key: str, permissions: List[str]) -> None:
        await self.cache.set(
            cache_key,
            {"permissions": permissions, "timestamp": int(time.time() * 1000)},
            self.permission_ttl,
        )

    async def get_permissions(
        self,
        token: str,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> List[str]:
        """Get user permissions with Redis caching.

        Optimized to extract userId from token first to check cache before API call.

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            List of user permissions

        """
        try:
            user_id = extract_user_id(token)
            cache_key = self._build_cache_key(user_id)
            cached_permissions = await self._get_cached_permissions(cache_key)
            if cached_permissions is not None:
                return cached_permissions

            resolved_user_id = await self._resolve_user_id(token, user_id, auth_strategy)
            if not resolved_user_id:
                return []

            cache_key = self._build_cache_key(resolved_user_id)
            environment, application = self._get_request_context()
            permissions = await self._fetch_permissions(
                token, environment, application, auth_strategy
            )

            assert cache_key is not None
            await self._cache_permissions(cache_key, permissions)
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
        self,
        token: str,
        permission: str,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> bool:
        """Check if user has specific permission.

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
        self,
        token: str,
        permissions: List[str],
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> bool:
        """Check if user has any of the specified permissions.

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
        self,
        token: str,
        permissions: List[str],
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> bool:
        """Check if user has all of the specified permissions.

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
        self,
        token: str,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> List[str]:
        """Force refresh permissions from controller (bypass cache).

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            Fresh list of user permissions

        """
        try:
            user_id = await self._resolve_user_id(token, None, auth_strategy)
            if not user_id:
                return []

            cache_key = self._build_cache_key(user_id)
            environment, application = self._get_request_context()
            permissions = await self._fetch_permissions_from_refresh(
                token, environment, application, auth_strategy
            )

            assert cache_key is not None
            await self._cache_permissions(cache_key, permissions)
            return permissions

        except Exception as error:
            correlation_id = extract_correlation_id_from_error(error)
            logger.error(
                "Failed to refresh permissions",
                exc_info=error,
                extra={"correlationId": correlation_id} if correlation_id else None,
            )
            return []

    async def _fetch_permissions_from_refresh(
        self,
        token: str,
        environment: Optional[str],
        application: Optional[str],
        auth_strategy: Optional[AuthStrategy],
    ) -> List[str]:
        if self.api_client:
            api_client = self.api_client
            assert api_client is not None
            response = await api_client.permissions.refresh_permissions(
                token,
                environment=environment,
                application=application,
                auth_strategy=auth_strategy,
            )
            return response.data.permissions or []

        params: dict[str, str] = {}
        if environment:
            params["environment"] = environment
        if application:
            params["application"] = application

        if auth_strategy is not None:
            permission_result = await self.http_client.authenticated_request(
                "GET",
                "/api/v1/auth/permissions/refresh",
                token,
                params=params,
                auth_strategy=auth_strategy,
            )
        else:
            permission_result = await self.http_client.authenticated_request(
                "GET", "/api/v1/auth/permissions/refresh", token, params=params
            )

        permission_data = PermissionResult(**permission_result)
        return permission_data.permissions or []

    async def clear_permissions_cache(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> None:
        """Clear cached permissions for a user.

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        """
        try:
            # Extract userId from token first (avoids API call if userId is in token)
            user_id = extract_user_id(token)
            if not user_id:
                # Fallback to validate endpoint if userId not in token
                user_info = await validate_token_request(
                    token, self.http_client, self.api_client, auth_strategy
                )
                # validate_token_request returns {"data": {"user": {...}}} format
                user_id = user_info.get("data", {}).get("user", {}).get("id") if user_info else None
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
