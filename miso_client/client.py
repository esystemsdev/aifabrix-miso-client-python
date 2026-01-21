"""
MisoClient - Main SDK class for authentication, authorization, and logging.

This module contains the MisoClient class which provides a unified interface
for integrating with the Miso Controller.
"""

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from .models.config import AuthStrategy, MisoClientConfig, UserInfo
from .services.auth import AuthService
from .services.cache import CacheService
from .services.encryption import EncryptionService
from .services.logger import LoggerService
from .services.permission import PermissionService
from .services.redis import RedisService
from .services.role import RoleService
from .utils.audit_log_queue import AuditLogQueue
from .utils.http_client import HttpClient
from .utils.internal_http_client import InternalHttpClient
from .utils.jwt_tools import extract_user_id

if TYPE_CHECKING:
    from .models.encryption import EncryptResult


class MisoClient:
    """
    Main MisoClient SDK class for authentication, authorization, and logging.

    This client provides a unified interface for:
    - Token validation and user management
    - Role-based access control
    - Permission management
    - Application logging with Redis caching
    """

    def __init__(self, config: MisoClientConfig):
        """Initialize MisoClient with configuration."""
        self.config = config
        self._internal_http_client = InternalHttpClient(config)
        self.redis = RedisService(config.redis)
        self.logger = LoggerService(self._internal_http_client, self.redis)
        self.http_client = HttpClient(config, self.logger)

        from .api import ApiClient

        self.api_client = ApiClient(self.http_client)

        if config.audit and (config.audit.batchSize or config.audit.batchInterval):
            self.logger.audit_log_queue = AuditLogQueue(self.http_client, self.redis, config)
        self.logger.api_client = self.api_client

        from .utils.unified_logger_factory import set_default_logger_service

        set_default_logger_service(self.logger)

        self.cache = CacheService(self.redis)
        self.auth = AuthService(self.http_client, self.redis, self.cache, self.api_client)
        self.http_client.set_auth_service_for_refresh(self.auth)
        self.roles = RoleService(self.http_client, self.cache, self.api_client)
        self.permissions = PermissionService(self.http_client, self.cache, self.api_client)
        self.encryption = EncryptionService(self.http_client, config)
        self.initialized = False

    # ==================== LIFECYCLE METHODS ====================

    async def initialize(self) -> None:
        """Initialize the client (connect to Redis if configured)."""
        if self.initialized:
            return
        try:
            await self.redis.connect()
        except Exception:
            pass  # Redis connection failed, continue with controller fallback
        self.initialized = True

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        await self.redis.disconnect()
        await self.http_client.close()
        self.initialized = False

    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self.initialized

    # ==================== AUTHENTICATION METHODS ====================

    def get_token(self, req: dict) -> str | None:
        """Extract Bearer token from request headers."""
        headers_obj = (
            req.get("headers", {}) if isinstance(req, dict) else getattr(req, "headers", {})
        )
        headers: dict[str, Any] = headers_obj if isinstance(headers_obj, dict) else {}
        auth_value = headers.get("authorization") or headers.get("Authorization")
        if not isinstance(auth_value, str):
            return None
        return auth_value[7:] if auth_value.startswith("Bearer ") else auth_value

    async def get_environment_token(self) -> str:
        """Get environment token using client credentials."""
        return await self.auth.get_environment_token()

    async def login(self, redirect: str, state: Optional[str] = None) -> Dict[str, Any]:
        """Initiate login flow."""
        return await self.auth.login(redirect, state)

    async def validate_token(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """Validate token with controller."""
        return await self.auth.validate_token(token, auth_strategy=auth_strategy)

    async def get_user(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> UserInfo | None:
        """Get user information from token."""
        return await self.auth.get_user(token, auth_strategy=auth_strategy)

    async def get_user_info(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> UserInfo | None:
        """Get user information from GET /api/v1/auth/user endpoint."""
        return await self.auth.get_user_info(token, auth_strategy=auth_strategy)

    async def is_authenticated(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """Check if user is authenticated."""
        return await self.auth.is_authenticated(token, auth_strategy=auth_strategy)

    async def logout(self, token: str) -> Dict[str, Any]:
        """Logout user by invalidating the access token."""
        user_id = extract_user_id(token)
        response = await self.auth.logout(token)
        if user_id:
            self.clear_user_token_refresh(user_id)
        await asyncio.gather(
            self.roles.clear_roles_cache(token),
            self.permissions.clear_permissions_cache(token),
            return_exceptions=True,
        )
        return response

    def register_user_token_refresh_callback(self, user_id: str, callback: Any) -> None:
        """Register refresh callback for a user."""
        self.http_client.register_user_token_refresh_callback(user_id, callback)

    def register_user_refresh_token(self, user_id: str, refresh_token: str) -> None:
        """Register refresh token for a user."""
        self.http_client.register_user_refresh_token(user_id, refresh_token)

    def clear_user_token_refresh(self, user_id: str) -> None:
        """Clear refresh callback and tokens for a user."""
        self.http_client._user_token_refresh.clear_user_tokens(user_id)

    # ==================== AUTHORIZATION METHODS ====================

    async def get_roles(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> list[str]:
        """Get user roles (cached in Redis if available)."""
        return await self.roles.get_roles(token, auth_strategy=auth_strategy)

    async def has_role(
        self, token: str, role: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """Check if user has specific role."""
        return await self.roles.has_role(token, role, auth_strategy=auth_strategy)

    async def has_any_role(
        self, token: str, roles: list[str], auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """Check if user has any of the specified roles."""
        return await self.roles.has_any_role(token, roles, auth_strategy=auth_strategy)

    async def has_all_roles(
        self, token: str, roles: list[str], auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """Check if user has all of the specified roles."""
        return await self.roles.has_all_roles(token, roles, auth_strategy=auth_strategy)

    async def refresh_roles(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> list[str]:
        """Force refresh roles from controller (bypass cache)."""
        return await self.roles.refresh_roles(token, auth_strategy=auth_strategy)

    async def get_permissions(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> list[str]:
        """Get user permissions (cached in Redis if available)."""
        return await self.permissions.get_permissions(token, auth_strategy=auth_strategy)

    async def has_permission(
        self, token: str, permission: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """Check if user has specific permission."""
        return await self.permissions.has_permission(token, permission, auth_strategy=auth_strategy)

    async def has_any_permission(
        self, token: str, permissions: list[str], auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """Check if user has any of the specified permissions."""
        return await self.permissions.has_any_permission(
            token, permissions, auth_strategy=auth_strategy
        )

    async def has_all_permissions(
        self, token: str, permissions: list[str], auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """Check if user has all of the specified permissions."""
        return await self.permissions.has_all_permissions(
            token, permissions, auth_strategy=auth_strategy
        )

    async def refresh_permissions(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> list[str]:
        """Force refresh permissions from controller (bypass cache)."""
        return await self.permissions.refresh_permissions(token, auth_strategy=auth_strategy)

    async def clear_permissions_cache(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> None:
        """Clear cached permissions for a user."""
        return await self.permissions.clear_permissions_cache(token, auth_strategy=auth_strategy)

    # ==================== LOGGING METHODS ====================

    @property
    def log(self) -> LoggerService:
        """Get logger service for application logging."""
        return self.logger

    # ==================== ENCRYPTION METHODS ====================

    async def encrypt(self, plaintext: str, parameter_name: str) -> "EncryptResult":
        """Encrypt sensitive data via miso-controller."""
        return await self.encryption.encrypt(plaintext, parameter_name)

    async def decrypt(self, value: str, parameter_name: str) -> str:
        """Decrypt sensitive data via miso-controller."""
        return await self.encryption.decrypt(value, parameter_name)

    # ==================== CACHING METHODS ====================

    async def cache_get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        return await self.cache.get(key)

    async def cache_set(self, key: str, value: Any, ttl: int) -> bool:
        """Set cached value with TTL."""
        return await self.cache.set(key, value, ttl)

    async def cache_delete(self, key: str) -> bool:
        """Delete cached value."""
        return await self.cache.delete(key)

    async def cache_clear(self) -> None:
        """Clear all cached values."""
        await self.cache.clear()

    # ==================== UTILITY METHODS ====================

    def get_config(self) -> MisoClientConfig:
        """Get current configuration."""
        return self.config.model_copy()

    def is_redis_connected(self) -> bool:
        """Check if Redis is connected."""
        return self.redis.is_connected()

    # ==================== AUTHENTICATION STRATEGY METHODS ====================

    def create_auth_strategy(
        self,
        methods: List[Literal["bearer", "client-token", "client-credentials", "api-key"]],
        bearer_token: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> AuthStrategy:
        """Create an authentication strategy object."""
        return AuthStrategy(methods=methods, bearerToken=bearer_token, apiKey=api_key)

    async def request_with_auth_strategy(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """Make request with authentication strategy (priority-based fallback)."""
        return await self.http_client.request_with_auth_strategy(
            method, url, auth_strategy, data, **kwargs
        )
