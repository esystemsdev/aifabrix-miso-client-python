"""
Role service for user authorization with caching.

This module handles role-based access control with caching support.
Roles are cached with Redis and in-memory fallback using CacheService.
Optimized to extract userId from JWT token before API calls for cache optimization.
"""

import time
from typing import List, cast

from ..models.config import RoleResult
from ..services.cache import CacheService
from ..utils.http_client import HttpClient
from ..utils.jwt_tools import extract_user_id


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

    async def get_roles(self, token: str) -> List[str]:
        """
        Get user roles with Redis caching.

        Optimized to extract userId from token first to check cache before API call.

        Args:
            token: JWT token

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
                user_info = await self.http_client.authenticated_request(
                    "POST", "/api/auth/validate", token
                )
                user_id = user_info.get("user", {}).get("id") if user_info else None
                if not user_id:
                    return []
                cache_key = f"roles:{user_id}"

            # Cache miss - fetch from controller
            role_result = await self.http_client.authenticated_request(
                "GET", "/api/auth/roles", token  # Backend knows app/env from client token
            )

            role_data = RoleResult(**role_result)
            roles = role_data.roles or []

            # Cache the result (CacheService handles Redis + in-memory automatically)
            assert cache_key is not None
            await self.cache.set(
                cache_key, {"roles": roles, "timestamp": int(time.time() * 1000)}, self.role_ttl
            )

            return roles

        except Exception:
            # Failed to get roles, return empty list
            return []

    async def has_role(self, token: str, role: str) -> bool:
        """
        Check if user has specific role.

        Args:
            token: JWT token
            role: Role to check

        Returns:
            True if user has the role, False otherwise
        """
        roles = await self.get_roles(token)
        return role in roles

    async def has_any_role(self, token: str, roles: List[str]) -> bool:
        """
        Check if user has any of the specified roles.

        Args:
            token: JWT token
            roles: List of roles to check

        Returns:
            True if user has any of the roles, False otherwise
        """
        user_roles = await self.get_roles(token)
        return any(role in user_roles for role in roles)

    async def has_all_roles(self, token: str, roles: List[str]) -> bool:
        """
        Check if user has all of the specified roles.

        Args:
            token: JWT token
            roles: List of roles to check

        Returns:
            True if user has all roles, False otherwise
        """
        user_roles = await self.get_roles(token)
        return all(role in user_roles for role in roles)

    async def refresh_roles(self, token: str) -> List[str]:
        """
        Force refresh roles from controller (bypass cache).

        Args:
            token: JWT token

        Returns:
            Fresh list of user roles
        """
        try:
            # Get user info to extract userId
            user_info = await self.http_client.authenticated_request(
                "POST", "/api/auth/validate", token
            )

            user_id = user_info.get("user", {}).get("id") if user_info else None
            if not user_id:
                return []

            cache_key = f"roles:{user_id}"

            # Fetch fresh roles from controller using refresh endpoint
            role_result = await self.http_client.authenticated_request(
                "GET", "/api/auth/roles/refresh", token
            )

            role_data = RoleResult(**role_result)
            roles = role_data.roles or []

            # Update cache with fresh data (CacheService handles Redis + in-memory automatically)
            await self.cache.set(
                cache_key, {"roles": roles, "timestamp": int(time.time() * 1000)}, self.role_ttl
            )

            return roles

        except Exception:
            # Failed to refresh roles, return empty list
            return []
