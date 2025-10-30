"""
Configuration types for MisoClient SDK.

This module contains Pydantic models that define the configuration structure
and data types used throughout the MisoClient SDK.
"""

from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field


class RedisConfig(BaseModel):
    """Redis connection configuration."""
    
    host: str = Field(..., description="Redis host")
    port: int = Field(default=6379, description="Redis port")
    password: Optional[str] = Field(default=None, description="Redis password")
    db: int = Field(default=0, description="Redis database number")
    key_prefix: str = Field(default="miso:", description="Key prefix for Redis keys")


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
    """
    
    controller_url: str = Field(..., description="Miso Controller base URL")
    client_id: str = Field(..., description="Client identifier for authentication")
    client_secret: str = Field(..., description="Client secret for authentication")
    redis: Optional[RedisConfig] = Field(default=None, description="Optional Redis configuration")
    log_level: Literal["debug", "info", "warn", "error"] = Field(
        default="info", 
        description="Log level"
    )
    cache: Optional[Dict[str, int]] = Field(
        default=None,
        description="Cache TTL settings: permission_ttl, role_ttl (default: 900 seconds)"
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
    firstName: Optional[str] = Field(default=None, alias="first_name", description="First name")
    lastName: Optional[str] = Field(default=None, alias="last_name", description="Last name")
    roles: Optional[List[str]] = Field(default=None, description="User roles")
    
    class Config:
        populate_by_name = True  # Allow both snake_case and camelCase


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
    applicationId: Optional[str] = Field(default=None, alias="application_id", description="Application ID")
    userId: Optional[str] = Field(default=None, alias="user_id", description="User ID if available")
    message: str = Field(..., description="Log message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    correlationId: Optional[str] = Field(default=None, alias="correlation_id", description="Correlation ID for tracing")
    requestId: Optional[str] = Field(default=None, alias="request_id", description="Request ID")
    sessionId: Optional[str] = Field(default=None, alias="session_id", description="Session ID")
    stackTrace: Optional[str] = Field(default=None, alias="stack_trace", description="Stack trace for errors")
    ipAddress: Optional[str] = Field(default=None, alias="ip_address", description="IP address")
    userAgent: Optional[str] = Field(default=None, alias="user_agent", description="User agent")
    hostname: Optional[str] = Field(default=None, description="Hostname")
    
    class Config:
        populate_by_name = True


class RoleResult(BaseModel):
    """Role query result."""
    
    userId: str = Field(..., alias="user_id", description="User ID")
    roles: List[str] = Field(..., description="List of user roles")
    environment: str = Field(..., description="Environment name")
    application: str = Field(..., description="Application name")
    
    class Config:
        populate_by_name = True


class PermissionResult(BaseModel):
    """Permission query result."""
    
    userId: str = Field(..., alias="user_id", description="User ID")
    permissions: List[str] = Field(..., description="List of user permissions")
    environment: str = Field(..., description="Environment name")
    application: str = Field(..., description="Application name")
    
    class Config:
        populate_by_name = True


class ClientTokenResponse(BaseModel):
    """Client token response."""
    
    success: bool = Field(..., description="Whether token request was successful")
    token: str = Field(..., description="Client token")
    expiresIn: int = Field(..., alias="expires_in", description="Token expiration in seconds")
    expiresAt: str = Field(..., alias="expires_at", description="Token expiration ISO timestamp")
    
    class Config:
        populate_by_name = True


class PerformanceMetrics(BaseModel):
    """Performance metrics for logging."""
    
    startTime: int = Field(..., alias="start_time", description="Start time in milliseconds")
    endTime: Optional[int] = Field(default=None, alias="end_time", description="End time in milliseconds")
    duration: Optional[int] = Field(default=None, description="Duration in milliseconds")
    memoryUsage: Optional[Dict[str, int]] = Field(
        default=None, 
        alias="memory_usage",
        description="Memory usage metrics (rss, heapTotal, heapUsed, external, arrayBuffers)"
    )
    
    class Config:
        populate_by_name = True


class ClientLoggingOptions(BaseModel):
    """Options for client logging."""
    
    applicationId: Optional[str] = Field(default=None, alias="application_id", description="Application ID")
    userId: Optional[str] = Field(default=None, alias="user_id", description="User ID")
    correlationId: Optional[str] = Field(default=None, alias="correlation_id", description="Correlation ID")
    requestId: Optional[str] = Field(default=None, alias="request_id", description="Request ID")
    sessionId: Optional[str] = Field(default=None, alias="session_id", description="Session ID")
    token: Optional[str] = Field(default=None, description="JWT token for context extraction")
    maskSensitiveData: Optional[bool] = Field(default=None, alias="mask_sensitive_data", description="Enable data masking")
    performanceMetrics: Optional[bool] = Field(default=None, alias="performance_metrics", description="Include performance metrics")
    
    class Config:
        populate_by_name = True
