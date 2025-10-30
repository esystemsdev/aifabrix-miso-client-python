"""
MisoClient SDK - Python client for AI Fabrix authentication, authorization, and logging.

This package provides a reusable client SDK for integrating with the Miso Controller
for authentication, role-based access control, permission management, and logging.
"""

from typing import Any, Optional

from .models.config import (
    RedisConfig,
    MisoClientConfig,
    UserInfo,
    AuthResult,
    LogEntry,
    RoleResult,
    PermissionResult,
    ClientTokenResponse,
    PerformanceMetrics,
    ClientLoggingOptions,
)
from .services.auth import AuthService
from .services.role import RoleService
from .services.permission import PermissionService
from .services.logger import LoggerService, LoggerChain
from .services.redis import RedisService
from .services.encryption import EncryptionService
from .services.cache import CacheService
from .utils.http_client import HttpClient
from .utils.config_loader import load_config
from .errors import (
    MisoClientError,
    AuthenticationError,
    AuthorizationError,
    ConnectionError,
    ConfigurationError,
)

__version__ = "0.1.0"
__author__ = "AI Fabrix Team"
__license__ = "MIT"


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
        """
        Initialize MisoClient with configuration.
        
        Args:
            config: MisoClient configuration including controller URL, client credentials, etc.
        """
        self.config = config
        self.http_client = HttpClient(config)
        self.redis = RedisService(config.redis)
        # Cache service (uses Redis if available, falls back to in-memory)
        self.cache = CacheService(self.redis)
        self.auth = AuthService(self.http_client, self.redis)
        self.roles = RoleService(self.http_client, self.cache)
        self.permissions = PermissionService(self.http_client, self.cache)
        self.logger = LoggerService(self.http_client, self.redis)
        # Encryption service (reads ENCRYPTION_KEY from environment by default)
        self.encryption = EncryptionService()
        self.initialized = False

    async def initialize(self) -> None:
        """
        Initialize the client (connect to Redis if configured).
        
        This method should be called before using the client. It will attempt
        to connect to Redis if configured, but will gracefully fall back to
        controller-only mode if Redis is unavailable.
        """
        if self.initialized:
            return

        try:
            await self.redis.connect()
            self.initialized = True
        except Exception:
            # Redis connection failed, continue with controller fallback mode
            self.initialized = True  # Still mark as initialized for fallback mode

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
        """
        Extract Bearer token from request headers.
        
        Supports common request object patterns (dict with headers).
        
        Args:
            req: Request object with headers dict containing 'authorization' key
            
        Returns:
            Bearer token string or None if not found
        """
        headers = req.get("headers", {}) if isinstance(req, dict) else getattr(req, "headers", {})
        auth_header = headers.get("authorization") or headers.get("Authorization")
        if not auth_header:
            return None

        # Support "Bearer <token>" format
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        # If no Bearer prefix, assume the whole header is the token
        return auth_header

    async def get_environment_token(self) -> str:
        """
        Get environment token using client credentials.
        
        This is called automatically by HttpClient but can be called manually.
        
        Returns:
            Client token string
        """
        return await self.auth.get_environment_token()

    def login(self, redirect_uri: str) -> str:
        """
        Initiate login flow by redirecting to controller.
        
        Returns the login URL for browser redirect or manual navigation.
        
        Args:
            redirect_uri: URI to redirect to after successful login
            
        Returns:
            Login URL string
        """
        return self.auth.login(redirect_uri)

    async def validate_token(self, token: str) -> bool:
        """
        Validate token with controller.
        
        Args:
            token: JWT token to validate
            
        Returns:
            True if token is valid, False otherwise
        """
        return await self.auth.validate_token(token)

    async def get_user(self, token: str) -> UserInfo | None:
        """
        Get user information from token.
        
        Args:
            token: JWT token
            
        Returns:
            UserInfo if token is valid, None otherwise
        """
        return await self.auth.get_user(token)

    async def get_user_info(self, token: str) -> UserInfo | None:
        """
        Get user information from GET /api/auth/user endpoint.
        
        Args:
            token: JWT token
            
        Returns:
            UserInfo if token is valid, None otherwise
        """
        return await self.auth.get_user_info(token)

    async def is_authenticated(self, token: str) -> bool:
        """
        Check if user is authenticated.
        
        Args:
            token: JWT token
            
        Returns:
            True if user is authenticated, False otherwise
        """
        return await self.auth.is_authenticated(token)

    async def logout(self) -> None:
        """Logout user."""
        return await self.auth.logout()

    # ==================== AUTHORIZATION METHODS ====================

    async def get_roles(self, token: str) -> list[str]:
        """
        Get user roles (cached in Redis if available).
        
        Args:
            token: JWT token
            
        Returns:
            List of user roles
        """
        return await self.roles.get_roles(token)

    async def has_role(self, token: str, role: str) -> bool:
        """
        Check if user has specific role.
        
        Args:
            token: JWT token
            role: Role to check
            
        Returns:
            True if user has the role, False otherwise
        """
        return await self.roles.has_role(token, role)

    async def has_any_role(self, token: str, roles: list[str]) -> bool:
        """
        Check if user has any of the specified roles.
        
        Args:
            token: JWT token
            roles: List of roles to check
            
        Returns:
            True if user has any of the roles, False otherwise
        """
        return await self.roles.has_any_role(token, roles)

    async def has_all_roles(self, token: str, roles: list[str]) -> bool:
        """
        Check if user has all of the specified roles.
        
        Args:
            token: JWT token
            roles: List of roles to check
            
        Returns:
            True if user has all roles, False otherwise
        """
        return await self.roles.has_all_roles(token, roles)

    async def refresh_roles(self, token: str) -> list[str]:
        """
        Force refresh roles from controller (bypass cache).
        
        Args:
            token: JWT token
            
        Returns:
            Fresh list of user roles
        """
        return await self.roles.refresh_roles(token)

    async def get_permissions(self, token: str) -> list[str]:
        """
        Get user permissions (cached in Redis if available).
        
        Args:
            token: JWT token
            
        Returns:
            List of user permissions
        """
        return await self.permissions.get_permissions(token)

    async def has_permission(self, token: str, permission: str) -> bool:
        """
        Check if user has specific permission.
        
        Args:
            token: JWT token
            permission: Permission to check
            
        Returns:
            True if user has the permission, False otherwise
        """
        return await self.permissions.has_permission(token, permission)

    async def has_any_permission(self, token: str, permissions: list[str]) -> bool:
        """
        Check if user has any of the specified permissions.
        
        Args:
            token: JWT token
            permissions: List of permissions to check
            
        Returns:
            True if user has any of the permissions, False otherwise
        """
        return await self.permissions.has_any_permission(token, permissions)

    async def has_all_permissions(self, token: str, permissions: list[str]) -> bool:
        """
        Check if user has all of the specified permissions.
        
        Args:
            token: JWT token
            permissions: List of permissions to check
            
        Returns:
            True if user has all permissions, False otherwise
        """
        return await self.permissions.has_all_permissions(token, permissions)

    async def refresh_permissions(self, token: str) -> list[str]:
        """
        Force refresh permissions from controller (bypass cache).
        
        Args:
            token: JWT token
            
        Returns:
            Fresh list of user permissions
        """
        return await self.permissions.refresh_permissions(token)

    async def clear_permissions_cache(self, token: str) -> None:
        """
        Clear cached permissions for a user.
        
        Args:
            token: JWT token
        """
        return await self.permissions.clear_permissions_cache(token)

    # ==================== LOGGING METHODS ====================

    @property
    def log(self) -> LoggerService:
        """
        Get logger service for application logging.
        
        Returns:
            LoggerService instance
        """
        return self.logger

    # ==================== ENCRYPTION METHODS ====================

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt sensitive data.
        
        Convenience method that delegates to encryption service.
        
        Args:
            plaintext: Plain text string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        return self.encryption.encrypt(plaintext)

    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt sensitive data.
        
        Convenience method that delegates to encryption service.
        
        Args:
            encrypted_text: Base64-encoded encrypted string
            
        Returns:
            Decrypted plain text string
        """
        return self.encryption.decrypt(encrypted_text)

    # ==================== CACHING METHODS ====================

    async def cache_get(self, key: str) -> Optional[Any]:
        """
        Get cached value.
        
        Convenience method that delegates to cache service.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if found, None otherwise
        """
        return await self.cache.get(key)

    async def cache_set(self, key: str, value: Any, ttl: int) -> bool:
        """
        Set cached value with TTL.
        
        Convenience method that delegates to cache service.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        return await self.cache.set(key, value, ttl)

    async def cache_delete(self, key: str) -> bool:
        """
        Delete cached value.
        
        Convenience method that delegates to cache service.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False otherwise
        """
        return await self.cache.delete(key)

    async def cache_clear(self) -> None:
        """
        Clear all cached values.
        
        Convenience method that delegates to cache service.
        """
        await self.cache.clear()

    # ==================== UTILITY METHODS ====================

    def get_config(self) -> MisoClientConfig:
        """
        Get current configuration.
        
        Returns:
            Copy of current configuration
        """
        return self.config.model_copy()

    def is_redis_connected(self) -> bool:
        """
        Check if Redis is connected.
        
        Returns:
            True if Redis is connected, False otherwise
        """
        return self.redis.is_connected()


# Export types
__all__ = [
    "MisoClient",
    "RedisConfig",
    "MisoClientConfig",
    "UserInfo",
    "AuthResult",
    "LogEntry",
    "RoleResult",
    "PermissionResult",
    "ClientTokenResponse",
    "PerformanceMetrics",
    "ClientLoggingOptions",
    "AuthService",
    "RoleService",
    "PermissionService",
    "LoggerService",
    "LoggerChain",
    "RedisService",
    "EncryptionService",
    "CacheService",
    "HttpClient",
    "load_config",
    "MisoClientError",
    "AuthenticationError",
    "AuthorizationError",
    "ConnectionError",
    "ConfigurationError",
]
