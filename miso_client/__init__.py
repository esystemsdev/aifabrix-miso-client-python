"""
MisoClient SDK - Python client for AI Fabrix authentication, authorization, and logging.

This package provides a reusable client SDK for integrating with the Miso Controller
for authentication, role-based access control, permission management, and logging.
"""

import asyncio
from typing import Any, Dict, List, Literal, Optional

from .errors import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConnectionError,
    MisoClientError,
)
from .models.config import (
    AuthResult,
    AuthStrategy,
    CircuitBreakerConfig,
    ClientLoggingOptions,
    ClientTokenEndpointOptions,
    ClientTokenEndpointResponse,
    ClientTokenResponse,
    DataClientConfigResponse,
    LogEntry,
    MisoClientConfig,
    PermissionResult,
    RedisConfig,
    RoleResult,
    UserInfo,
)
from .models.error_response import ErrorResponse
from .models.filter import (
    FilterBuilder,
    FilterGroup,
    FilterOperator,
    FilterOption,
    FilterQuery,
    JsonFilter,
)
from .models.pagination import Meta, PaginatedListResponse
from .models.sort import SortOption
from .services.auth import AuthService
from .services.cache import CacheService
from .services.encryption import EncryptionService
from .services.logger import LoggerService
from .services.logger_chain import LoggerChain
from .services.permission import PermissionService
from .services.redis import RedisService
from .services.role import RoleService
from .utils.audit_log_queue import AuditLogQueue
from .utils.config_loader import load_config
from .utils.controller_url_resolver import is_browser, resolve_controller_url
from .utils.environment_token import get_environment_token
from .utils.error_utils import (
    ApiErrorException,
    handle_api_error_snake_case,
    handleApiError,
    transform_error_to_snake_case,
    transformError,
)
from .utils.fastapi_endpoints import create_fastapi_client_token_endpoint
from .utils.filter import (
    apply_filters,
    build_query_string,
    filter_query_to_json,
    json_filter_to_query_string,
    json_to_filter_query,
    parse_filter_params,
    query_string_to_json_filter,
    validate_filter_option,
    validate_json_filter,
)
from .utils.flask_endpoints import create_flask_client_token_endpoint
from .utils.http_client import HttpClient
from .utils.internal_http_client import InternalHttpClient
from .utils.jwt_tools import extract_user_id
from .utils.logging_helpers import extract_logging_context
from .utils.origin_validator import validate_origin
from .utils.pagination import (
    apply_pagination_to_array,
    applyPaginationToArray,
    create_meta_object,
    create_paginated_list_response,
    createMetaObject,
    createPaginatedListResponse,
    parse_pagination_params,
    parsePaginationParams,
)
from .utils.request_context import RequestContext, extract_request_context
from .utils.sort import build_sort_string, parse_sort_params
from .utils.token_utils import extract_client_token_info
from .utils.url_validator import validate_url

__version__ = "3.7.0"
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

        # Create InternalHttpClient first (pure HTTP functionality, no logging)
        self._internal_http_client = InternalHttpClient(config)

        # Create Redis service
        self.redis = RedisService(config.redis)

        # Create LoggerService with InternalHttpClient (to avoid circular dependency)
        # LoggerService uses InternalHttpClient for sending logs to prevent audit loops
        self.logger = LoggerService(self._internal_http_client, self.redis)

        # Create public HttpClient wrapping InternalHttpClient with logger
        # This HttpClient adds automatic ISO 27001 compliant audit and debug logging
        self.http_client = HttpClient(config, self.logger)

        # Create ApiClient for typed API calls (import here to avoid circular import)
        from .api import ApiClient

        self.api_client = ApiClient(self.http_client)

        # Update LoggerService with http_client and api_client for audit log queue (if needed)
        # This is safe because http_client is already created and logger is already set
        if config.audit and (
            config.audit.batchSize is not None or config.audit.batchInterval is not None
        ):
            self.logger.audit_log_queue = AuditLogQueue(self.http_client, self.redis, config)

        # Update LoggerService with api_client (optional, for typed API calls)
        # Note: LoggerService primarily uses InternalHttpClient to avoid circular dependency
        # ApiClient is provided as optional fallback
        self.logger.api_client = self.api_client

        # Cache service (uses Redis if available, falls back to in-memory)
        self.cache = CacheService(self.redis)

        # Services use ApiClient for typed API calls (with HttpClient fallback for backward compatibility)
        self.auth = AuthService(self.http_client, self.redis, self.cache, self.api_client)
        # Set auth_service on refresh manager for refresh endpoint calls
        self.http_client.set_auth_service_for_refresh(self.auth)
        self.roles = RoleService(self.http_client, self.cache, self.api_client)
        self.permissions = PermissionService(self.http_client, self.cache, self.api_client)

        # Encryption service (optional - only initialized if ENCRYPTION_KEY is configured)
        self.encryption: Optional[EncryptionService]
        try:
            self.encryption = EncryptionService()
        except ConfigurationError:
            # ENCRYPTION_KEY not configured or invalid - encryption service unavailable
            self.encryption = None
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
        headers_obj = (
            req.get("headers", {}) if isinstance(req, dict) else getattr(req, "headers", {})
        )
        headers: dict[str, Any] = headers_obj if isinstance(headers_obj, dict) else {}
        auth_value = headers.get("authorization") or headers.get("Authorization")
        if not isinstance(auth_value, str):
            return None

        # Support "Bearer <token>" format
        if auth_value.startswith("Bearer "):
            return auth_value[7:]

        # If no Bearer prefix, assume the whole header is the token
        return auth_value

    async def get_environment_token(self) -> str:
        """
        Get environment token using client credentials.

        This is called automatically by HttpClient but can be called manually.

        Returns:
            Client token string
        """
        return await self.auth.get_environment_token()

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
            >>> response = await client.login(
            ...     redirect="http://localhost:3000/auth/callback",
            ...     state="abc123"
            ... )
            >>> login_url = response["data"]["loginUrl"]
            >>> state = response["data"]["state"]
        """
        return await self.auth.login(redirect, state)

    async def validate_token(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Validate token with controller.

        Args:
            token: JWT token to validate
            auth_strategy: Optional authentication strategy

        Returns:
            True if token is valid, False otherwise
        """
        return await self.auth.validate_token(token, auth_strategy=auth_strategy)

    async def get_user(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> UserInfo | None:
        """
        Get user information from token.

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            UserInfo if token is valid, None otherwise
        """
        return await self.auth.get_user(token, auth_strategy=auth_strategy)

    async def get_user_info(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> UserInfo | None:
        """
        Get user information from GET /api/v1/auth/user endpoint.

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            UserInfo if token is valid, None otherwise
        """
        return await self.auth.get_user_info(token, auth_strategy=auth_strategy)

    async def is_authenticated(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> bool:
        """
        Check if user is authenticated.

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            True if user is authenticated, False otherwise
        """
        return await self.auth.is_authenticated(token, auth_strategy=auth_strategy)

    async def logout(self, token: str) -> Dict[str, Any]:
        """
        Logout user by invalidating the access token.

        This method calls POST /api/v1/auth/logout with the user's access token in the request body.
        The token will be invalidated on the server side, and all local caches (roles, permissions, JWT)
        will be cleared automatically. Refresh tokens and callbacks are also cleared.

        Args:
            token: Access token to invalidate (required)

        Returns:
            Dictionary containing:
                - success: True if successful
                - message: Success message
                - timestamp: Response timestamp

        Example:
            >>> response = await client.logout(token="jwt-token-here")
            >>> if response.get("success"):
            ...     print("Logout successful")
        """
        # Extract user ID before logout
        user_id = extract_user_id(token)

        # Call AuthService logout (invalidates token on server)
        response = await self.auth.logout(token)

        # Clear refresh data for user
        if user_id:
            self.clear_user_token_refresh(user_id)

        # Clear all caches after logout (even if logout failed, clear caches for security)
        # Use asyncio.gather() for concurrent cache clearing
        await asyncio.gather(
            self.roles.clear_roles_cache(token),
            self.permissions.clear_permissions_cache(token),
            return_exceptions=True,  # Don't fail if any cache clear fails
        )

        return response

    def register_user_token_refresh_callback(self, user_id: str, callback: Any) -> None:
        """
        Register refresh callback for a user.

        The callback will be called when the user's token needs to be refreshed.
        The callback should be an async function that takes the old token and returns
        the new token.

        Args:
            user_id: User ID
            callback: Async function that takes old token and returns new token

        Example:
            >>> async def refresh_token(old_token: str) -> str:
            ...     # Call your refresh endpoint
            ...     response = await your_auth_client.refresh(old_token)
            ...     return response["access_token"]
            >>>
            >>> client.register_user_token_refresh_callback("user-123", refresh_token)
        """
        self.http_client.register_user_token_refresh_callback(user_id, callback)

    def register_user_refresh_token(self, user_id: str, refresh_token: str) -> None:
        """
        Register refresh token for a user.

        The SDK will use this refresh token to automatically refresh the user's
        access token when it expires.

        Args:
            user_id: User ID
            refresh_token: Refresh token string

        Example:
            >>> client.register_user_refresh_token("user-123", "refresh-token-abc")
        """
        self.http_client.register_user_refresh_token(user_id, refresh_token)

    def clear_user_token_refresh(self, user_id: str) -> None:
        """
        Clear refresh callback and tokens for a user.

        Useful when user logs out or refresh tokens are revoked.

        Args:
            user_id: User ID

        Example:
            >>> client.clear_user_token_refresh("user-123")
        """
        self.http_client._user_token_refresh.clear_user_tokens(user_id)

    # ==================== AUTHORIZATION METHODS ====================

    async def get_roles(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> list[str]:
        """
        Get user roles (cached in Redis if available).

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            List of user roles
        """
        return await self.roles.get_roles(token, auth_strategy=auth_strategy)

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
        return await self.roles.has_role(token, role, auth_strategy=auth_strategy)

    async def has_any_role(
        self, token: str, roles: list[str], auth_strategy: Optional[AuthStrategy] = None
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
        return await self.roles.has_any_role(token, roles, auth_strategy=auth_strategy)

    async def has_all_roles(
        self, token: str, roles: list[str], auth_strategy: Optional[AuthStrategy] = None
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
        return await self.roles.has_all_roles(token, roles, auth_strategy=auth_strategy)

    async def refresh_roles(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> list[str]:
        """
        Force refresh roles from controller (bypass cache).

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            Fresh list of user roles
        """
        return await self.roles.refresh_roles(token, auth_strategy=auth_strategy)

    async def get_permissions(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> list[str]:
        """
        Get user permissions (cached in Redis if available).

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            List of user permissions
        """
        return await self.permissions.get_permissions(token, auth_strategy=auth_strategy)

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
        return await self.permissions.has_permission(token, permission, auth_strategy=auth_strategy)

    async def has_any_permission(
        self, token: str, permissions: list[str], auth_strategy: Optional[AuthStrategy] = None
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
        return await self.permissions.has_any_permission(
            token, permissions, auth_strategy=auth_strategy
        )

    async def has_all_permissions(
        self, token: str, permissions: list[str], auth_strategy: Optional[AuthStrategy] = None
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
        return await self.permissions.has_all_permissions(
            token, permissions, auth_strategy=auth_strategy
        )

    async def refresh_permissions(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> list[str]:
        """
        Force refresh permissions from controller (bypass cache).

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy

        Returns:
            Fresh list of user permissions
        """
        return await self.permissions.refresh_permissions(token, auth_strategy=auth_strategy)

    async def clear_permissions_cache(
        self, token: str, auth_strategy: Optional[AuthStrategy] = None
    ) -> None:
        """
        Clear cached permissions for a user.

        Args:
            token: JWT token
            auth_strategy: Optional authentication strategy
        """
        return await self.permissions.clear_permissions_cache(token, auth_strategy=auth_strategy)

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

        Raises:
            ConfigurationError: If encryption service is not available (ENCRYPTION_KEY not configured)
        """
        if self.encryption is None:
            raise ConfigurationError(
                "Encryption service is not available. Set ENCRYPTION_KEY environment variable "
                "to enable encryption functionality."
            )
        return self.encryption.encrypt(plaintext)

    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt sensitive data.

        Convenience method that delegates to encryption service.

        Args:
            encrypted_text: Base64-encoded encrypted string

        Returns:
            Decrypted plain text string

        Raises:
            ConfigurationError: If encryption service is not available (ENCRYPTION_KEY not configured)
        """
        if self.encryption is None:
            raise ConfigurationError(
                "Encryption service is not available. Set ENCRYPTION_KEY environment variable "
                "to enable encryption functionality."
            )
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

    # ==================== AUTHENTICATION STRATEGY METHODS ====================

    def create_auth_strategy(
        self,
        methods: List[Literal["bearer", "client-token", "client-credentials", "api-key"]],
        bearer_token: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> AuthStrategy:
        """
        Create an authentication strategy object.

        Args:
            methods: List of authentication methods in priority order
            bearer_token: Optional bearer token for bearer auth
            api_key: Optional API key for api-key auth

        Returns:
            AuthStrategy instance

        Example:
            >>> strategy = client.create_auth_strategy(
            ...     ['api-key'],
            ...     bearer_token=None,
            ...     api_key='your-api-key-here'
            ... )
        """
        return AuthStrategy(methods=methods, bearerToken=bearer_token, apiKey=api_key)

    async def request_with_auth_strategy(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        url: str,
        auth_strategy: AuthStrategy,
        data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Make request with authentication strategy (priority-based fallback).

        Tries authentication methods in priority order until one succeeds.
        If a method returns 401, automatically tries the next method in the strategy.

        Args:
            method: HTTP method
            url: Request URL
            auth_strategy: Authentication strategy configuration
            data: Request data (for POST/PUT)
            **kwargs: Additional httpx request parameters

        Returns:
            Response data (JSON parsed)

        Raises:
            MisoClientError: If all authentication methods fail

        Example:
            >>> strategy = client.create_auth_strategy(['api-key'], api_key='your-key')
            >>> response = await client.request_with_auth_strategy('GET', '/api/data', strategy)
        """
        return await self.http_client.request_with_auth_strategy(
            method, url, auth_strategy, data, **kwargs
        )


# Export types
__all__ = [
    "MisoClient",
    "RedisConfig",
    "MisoClientConfig",
    "UserInfo",
    "AuthResult",
    "AuthStrategy",
    "LogEntry",
    "RoleResult",
    "PermissionResult",
    "ClientTokenResponse",
    "ClientTokenEndpointResponse",
    "ClientTokenEndpointOptions",
    "DataClientConfigResponse",
    "CircuitBreakerConfig",
    "ClientLoggingOptions",
    "ErrorResponse",
    # Pagination models
    "Meta",
    "PaginatedListResponse",
    # Filter models
    "FilterOperator",
    "FilterOption",
    "FilterQuery",
    "FilterBuilder",
    "JsonFilter",
    "FilterGroup",
    # Sort models
    "SortOption",
    # Pagination utilities (camelCase)
    "parsePaginationParams",
    "createMetaObject",
    "applyPaginationToArray",
    "createPaginatedListResponse",
    # Pagination utilities (legacy snake_case aliases)
    "parse_pagination_params",
    "create_meta_object",
    "apply_pagination_to_array",
    "create_paginated_list_response",
    # Filter utilities
    "parse_filter_params",
    "build_query_string",
    "apply_filters",
    "filter_query_to_json",
    "json_to_filter_query",
    "json_filter_to_query_string",
    "query_string_to_json_filter",
    "validate_filter_option",
    "validate_json_filter",
    # Sort utilities
    "parse_sort_params",
    "build_sort_string",
    # Error utilities (camelCase)
    "transformError",
    "handleApiError",
    "ApiErrorException",
    # Error utilities (legacy snake_case aliases)
    "transform_error_to_snake_case",
    "handle_api_error_snake_case",
    # Services
    "AuthService",
    "RoleService",
    "PermissionService",
    "LoggerService",
    "LoggerChain",
    "RedisService",
    "EncryptionService",
    "CacheService",
    "HttpClient",
    "AuditLogQueue",
    "load_config",
    "MisoClientError",
    "AuthenticationError",
    "AuthorizationError",
    "ConnectionError",
    "ConfigurationError",
    # Server-side utilities
    "get_environment_token",
    "validate_origin",
    "extract_client_token_info",
    "validate_url",
    "resolve_controller_url",
    "is_browser",
    "create_flask_client_token_endpoint",
    "create_fastapi_client_token_endpoint",
    # Request context utilities
    "extract_request_context",
    "RequestContext",
    # Logging utilities
    "extract_logging_context",
]
