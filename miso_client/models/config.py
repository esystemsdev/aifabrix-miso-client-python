"""
Configuration types for MisoClient SDK.

This module contains Pydantic models that define the configuration structure
and data types used throughout the MisoClient SDK.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Authentication method types
AuthMethod = Literal["bearer", "client-token", "client-credentials", "api-key"]


class RedisConfig(BaseModel):
    """Redis connection configuration."""

    host: str = Field(..., description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    password: Optional[str] = Field(default=None, description="Redis password")
    db: int = Field(default=0, description="Redis database number")
    key_prefix: str = Field(default="miso:", description="Key prefix for Redis keys")


class AuditConfig(BaseModel):
    """Audit logging configuration for HTTP client."""

    enabled: Optional[bool] = Field(
        default=True, description="Enable/disable audit logging (default: true)"
    )
    level: Optional[Literal["minimal", "standard", "detailed", "full"]] = Field(
        default="detailed", description="Audit detail level (default: 'detailed')"
    )
    maxResponseSize: Optional[int] = Field(
        default=10000, description="Truncate responses larger than this (default: 10000 bytes)"
    )
    maxMaskingSize: Optional[int] = Field(
        default=50000,
        description="Skip masking for objects larger than this (default: 50000 bytes)",
    )
    batchSize: Optional[int] = Field(
        default=10, description="Batch size for queued logs (default: 10)"
    )
    batchInterval: Optional[int] = Field(
        default=100, description="Flush interval in milliseconds (default: 100)"
    )
    skipEndpoints: Optional[List[str]] = Field(
        default=None, description="Array of endpoint patterns to exclude from audit logging"
    )


class AuthStrategy(BaseModel):
    """Authentication strategy configuration.

    Defines which authentication methods to try and in what priority order.
    Methods are tried in the order specified until one succeeds.
    """

    methods: List[AuthMethod] = Field(
        default=["bearer", "client-token"],
        description="Array of auth methods in priority order (default: ['bearer', 'client-token'])",
    )
    bearerToken: Optional[str] = Field(
        default=None, description="Optional bearer token for bearer auth"
    )
    apiKey: Optional[str] = Field(default=None, description="Optional API key for api-key auth")


class MisoClientConfig(BaseModel):
    """Main MisoClient configuration.

    Required fields:
    - controller_url: Miso Controller base URL
    - client_id: Client identifier for authentication
    - client_secret: Client secret for authentication

    Optional fields:
    - redis: Redis configuration for caching
    - log_level: Logging level (debug, info, warn, error)
    - cache: Cache TTL settings for roles and permissions
    - api_key: API key for testing (bypasses OAuth2 authentication)
    """

    controller_url: str = Field(..., description="Miso Controller base URL")
    client_id: str = Field(..., description="Client identifier for authentication")
    client_secret: str = Field(..., description="Client secret for authentication")
    redis: Optional[RedisConfig] = Field(default=None, description="Optional Redis configuration")
    log_level: Literal["debug", "info", "warn", "error"] = Field(
        default="info", description="Log level"
    )
    cache: Optional[Dict[str, int]] = Field(
        default=None,
        description="Cache TTL settings: permission_ttl, role_ttl (default: 900 seconds)",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for testing - when set, bearer tokens matching this key bypass OAuth2 validation",
    )
    sensitive_fields_config: Optional[str] = Field(
        default=None, description="Path to sensitive fields configuration JSON file"
    )
    audit: Optional["AuditConfig"] = Field(default=None, description="Audit logging configuration")
    emit_events: Optional[bool] = Field(
        default=False,
        description="Emit log events instead of sending via HTTP/Redis (default: false)",
    )
    authStrategy: Optional["AuthStrategy"] = Field(
        default=None,
        description="Authentication strategy configuration (default: ['bearer', 'client-token'])",
    )

    @property
    def role_ttl(self) -> int:
        """Get role cache TTL in seconds."""
        if self.cache and "role_ttl" in self.cache:
            return self.cache["role_ttl"]
        return self.cache.get("roleTTL", 900) if self.cache else 900  # 15 minutes default

    @property
    def permission_ttl(self) -> int:
        """Get permission cache TTL in seconds."""
        if self.cache and "permission_ttl" in self.cache:
            return self.cache["permission_ttl"]
        return self.cache.get("permissionTTL", 900) if self.cache else 900  # 15 minutes default


class UserInfo(BaseModel):
    """User information from token validation."""

    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: Optional[str] = Field(default=None, description="User email")
    firstName: Optional[str] = Field(default=None, description="First name")
    lastName: Optional[str] = Field(default=None, description="Last name")
    roles: Optional[List[str]] = Field(default=None, description="User roles")


class AuthResult(BaseModel):
    """Authentication result."""

    authenticated: bool = Field(..., description="Whether authentication was successful")
    user: Optional[UserInfo] = Field(default=None, description="User information if authenticated")
    error: Optional[str] = Field(default=None, description="Error message if authentication failed")


class LogEntry(BaseModel):
    """Log entry structure."""

    timestamp: str = Field(..., description="ISO timestamp")
    level: Literal["error", "audit", "info", "debug"] = Field(..., description="Log level")
    environment: str = Field(..., description="Environment name (extracted by backend)")
    application: str = Field(..., description="Application identifier (clientId)")
    applicationId: Optional[str] = Field(default=None, description="Application ID")
    userId: Optional[str] = Field(default=None, description="User ID if available")
    message: str = Field(..., description="Log message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID for tracing")
    requestId: Optional[str] = Field(default=None, description="Request ID")
    sessionId: Optional[str] = Field(default=None, description="Session ID")
    stackTrace: Optional[str] = Field(default=None, description="Stack trace for errors")
    ipAddress: Optional[str] = Field(default=None, description="IP address")
    userAgent: Optional[str] = Field(default=None, description="User agent")
    hostname: Optional[str] = Field(default=None, description="Hostname")


class RoleResult(BaseModel):
    """Role query result."""

    userId: str = Field(..., description="User ID")
    roles: List[str] = Field(..., description="List of user roles")
    environment: str = Field(..., description="Environment name")
    application: str = Field(..., description="Application name")


class PermissionResult(BaseModel):
    """Permission query result."""

    userId: str = Field(..., description="User ID")
    permissions: List[str] = Field(..., description="List of user permissions")
    environment: str = Field(..., description="Environment name")
    application: str = Field(..., description="Application name")


class ClientTokenResponse(BaseModel):
    """Client token response."""

    success: bool = Field(..., description="Whether token request was successful")
    token: str = Field(..., description="Client token")
    expiresIn: int = Field(..., description="Token expiration in seconds")
    expiresAt: str = Field(..., description="Token expiration ISO timestamp")


class PerformanceMetrics(BaseModel):
    """Performance metrics for logging."""

    startTime: int = Field(..., description="Start time in milliseconds")
    endTime: Optional[int] = Field(default=None, description="End time in milliseconds")
    duration: Optional[int] = Field(default=None, description="Duration in milliseconds")
    memoryUsage: Optional[Dict[str, int]] = Field(
        default=None,
        description="Memory usage metrics (rss, heapTotal, heapUsed, external, arrayBuffers)",
    )


class ClientLoggingOptions(BaseModel):
    """Options for client logging."""

    applicationId: Optional[str] = Field(default=None, description="Application ID")
    userId: Optional[str] = Field(default=None, description="User ID")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")
    requestId: Optional[str] = Field(default=None, description="Request ID")
    sessionId: Optional[str] = Field(default=None, description="Session ID")
    token: Optional[str] = Field(default=None, description="JWT token for context extraction")
    maskSensitiveData: Optional[bool] = Field(default=None, description="Enable data masking")
    performanceMetrics: Optional[bool] = Field(
        default=None, description="Include performance metrics"
    )
