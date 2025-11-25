"""
Role service for user authorization with caching.

This module handles role-based access control with caching support.
Roles are cached with Redis and in-memory fallback using CacheService.
Optimized to extract userId from JWT token before API calls for cache optimization.
"""

import logging
import time
from typing import Any, Dict, List, Optional, cast

from ..models.config import AuthStrategy, RoleResult
from ..services.cache import CacheService
from ..utils.http_client import HttpClient
from ..utils.jwt_tools import extract_user_id

logger = logging.getLogger(__name__)


class RoleService:
    """Role service for user authorization with caching."""

    def __init__(self, http_client: HttpClient, cache: CacheService):
        """
        Initialize role service.

        Args:
            http_client: HTTP client instance
            cache: Cache service instance (handles Redis + in-memory fallback)
        """
        self.config = http_client.config
        self.http_client = http_client
        self.cache = cache
        self.role_ttl = self.config.role_ttl

    async def _validate_token_request(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> Dict[str, Any]:
        """
        Helper method to call /api/v1/auth/validate endpoint with proper request body.

        Args:
            token: JWT token to validate
            auth_strategy: Optional authentication strategy

        Returns:
            Validation result dictionary
        """
        if auth_strategy is not None:
            return await self.http_client.authenticated_request(
                "POST",
                "/api/v1/auth/validate",
                token,
                {"token": token},
                auth_strategy=auth_strategy,
            )
        else:
            return await self.http_client.authenticated_request(
                "POST", "/api/v1/auth/validate", token, {"token": token}
            )

    async def get_roles(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> List[str]:
        """
        Get user roles with Redis caching.

        Optimized to extract userId from token first to check cache before API call.

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            List of user roles
        """
        try:
            # Extract userId from token to check cache first (avoids API call on cache hit)
            user_id = extract_user_id(token)
            cache_key = f"roles:{user_id}" if user_id else None

            # Check cache first if we have userId
            if cache_key:
                cached_data = await self.cache.get(cache_key)
                if cached_data and isinstance(cached_data, dict):
                    return cast(List[str], cached_data.get("roles", []))

            # Cache miss or no userId in token - fetch from controller
            # If we don't have userId, get it from validate endpoint
            if not user_id:
                user_info = await self._validate_token_request(token, auth_strategy)
                user_id = user_info.get("user", {}).get("id") if user_info else None
                if not user_id:
                    return []
                cache_key = f"roles:{user_id}"

            # Cache miss - fetch from controller
            if auth_strategy is not None:
                role_result = await self.http_client.authenticated_request(
                    "GET", "/api/v1/auth/roles", token, auth_strategy=auth_strategy
                )
            else:
                role_result = await self.http_client.authenticated_request(
                    "GET", "/api/v1/auth/roles", token
                )

            role_data = RoleResult(**role_result)
            roles = role_data.roles or []

            # Cache the result (CacheService handles Redis + in-memory automatically)
            assert cache_key is not None
            await self.cache.set(
                cache_key, {"roles": roles, "timestamp": int(time.time() * 1000)}, self.role_ttl
            )

            return roles

        except Exception as error:
            logger.error("Failed to get roles", exc_info=error)
            return []

    async def has_role(
        self, token: str, role: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Check if user has specific role.

        Args:
            token: JWT token
            role: Role to check
            auth_strategy: Optional authentication strategy

        Returns:
            True if user has the role, False otherwise
        """
        roles = await self.get_roles(token, auth_strategy=auth_strategy)
        return role in roles

    async def has_any_role(
        self, token: str, roles: List[str], auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Check if user has any of the specified roles.

        Args:
            token: JWT token
            roles: List of roles to check
            auth_strategy: Optional authentication strategy

        Returns:
            True if user has any of the roles, False otherwise
        """
        user_roles = await self.get_roles(token, auth_strategy=auth_strategy)
        return any(role in user_roles for role in roles)

    async def has_all_roles(
        self, token: str, roles: List[str], auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Check if user has all of the specified roles.

        Args:
            token: JWT token
            roles: List of roles to check
            auth_strategy: Optional authentication strategy

        Returns:
            True if user has all roles, False otherwise
        """
        user_roles = await self.get_roles(token, auth_strategy=auth_strategy)
        return all(role in user_roles for role in roles)

    async def refresh_roles(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> List[str]:
        """
        Force refresh roles from controller (bypass cache).

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            Fresh list of user roles
        """
        try:
            # Get user info to extract userId
            user_info = await self._validate_token_request(token, auth_strategy)
            user_id = user_info.get("user", {}).get("id") if user_info else None
            if not user_id:
                return []

            cache_key = f"roles:{user_id}"

            # Fetch fresh roles from controller using refresh endpoint
            if auth_strategy is not None:
                role_result = await self.http_client.authenticated_request(
                    "GET", "/api/v1/auth/roles/refresh", token, auth_strategy=auth_strategy
                )
            else:
                role_result = await self.http_client.authenticated_request(
                    "GET", "/api/v1/auth/roles/refresh", token
                )

            role_data = RoleResult(**role_result)
            roles = role_data.roles or []

            # Update cache with fresh data (CacheService handles Redis + in-memory automatically)
            await self.cache.set(
                cache_key, {"roles": roles, "timestamp": int(time.time() * 1000)}, self.role_ttl
            )

            return roles

        except Exception as error:
            logger.error("Failed to refresh roles", exc_info=error)
            return []
