"""
Auth API request and response types.

All types follow OpenAPI specification with camelCase field names.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from ...models.config import UserInfo


class LoginResponse(BaseModel):
    """Login response with login URL."""

    success: bool = Field(..., description="Whether request was successful")
    data: "LoginResponseData" = Field(..., description="Login data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class LoginResponseData(BaseModel):
    """Login response data."""

    loginUrl: str = Field(..., description="Login URL for OAuth2 flow")


class ValidateTokenRequest(BaseModel):
    """Token validation request."""

    token: str = Field(..., description="JWT token to validate")
    environment: Optional[str] = Field(default=None, description="Optional environment key")
    application: Optional[str] = Field(default=None, description="Optional application key")


class ValidateTokenResponse(BaseModel):
    """Token validation response."""

    success: bool = Field(..., description="Whether request was successful")
    data: "ValidateTokenResponseData" = Field(..., description="Validation data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class ValidateTokenResponseData(BaseModel):
    """Token validation response data."""

    authenticated: bool = Field(..., description="Whether token is authenticated")
    user: Optional[UserInfo] = Field(default=None, description="User information if authenticated")
    expiresAt: Optional[str] = Field(default=None, description="Token expiration timestamp")


class GetUserResponse(BaseModel):
    """Get user response."""

    success: bool = Field(..., description="Whether request was successful")
    data: "GetUserResponseData" = Field(..., description="User data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class GetUserResponseData(BaseModel):
    """Get user response data."""

    user: UserInfo = Field(..., description="User information")
    authenticated: bool = Field(..., description="Whether user is authenticated")


class LogoutResponse(BaseModel):
    """Logout response."""

    success: bool = Field(..., description="Whether request was successful")
    message: str = Field(..., description="Logout message")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refreshToken: str = Field(..., description="Refresh token")


class DeviceCodeTokenResponse(BaseModel):
    """Device code token response."""

    accessToken: str = Field(..., description="JWT access token")
    refreshToken: Optional[str] = Field(default=None, description="Refresh token")
    expiresIn: int = Field(..., description="Token expiration in seconds")


class RefreshTokenResponse(BaseModel):
    """Refresh token response."""

    success: bool = Field(..., description="Whether request was successful")
    data: DeviceCodeTokenResponse = Field(..., description="Token data")
    message: Optional[str] = Field(default=None, description="Optional message")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class DeviceCodeRequest(BaseModel):
    """Device code initiation request."""

    environment: Optional[str] = Field(default=None, description="Environment key")
    scope: Optional[str] = Field(default=None, description="OAuth2 scope string")


class DeviceCodeResponse(BaseModel):
    """Device code response."""

    deviceCode: str = Field(..., description="Device code for polling")
    userCode: str = Field(..., description="User code to enter")
    verificationUri: str = Field(..., description="Verification URI")
    verificationUriComplete: Optional[str] = Field(
        default=None, description="Complete URI with user code"
    )
    expiresIn: int = Field(..., description="Device code expiration in seconds")
    interval: int = Field(..., description="Polling interval in seconds")


class DeviceCodeResponseWrapper(BaseModel):
    """Device code response wrapper."""

    success: bool = Field(..., description="Whether request was successful")
    data: DeviceCodeResponse = Field(..., description="Device code data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class DeviceCodeTokenPollRequest(BaseModel):
    """Device code token poll request."""

    deviceCode: str = Field(..., description="Device code from initiation")


class DeviceCodeTokenPollResponse(BaseModel):
    """Device code token poll response."""

    success: bool = Field(..., description="Whether request was successful")
    data: Optional[DeviceCodeTokenResponse] = Field(default=None, description="Token data if ready")
    error: Optional[str] = Field(default=None, description="Error code if pending")
    errorDescription: Optional[str] = Field(default=None, description="Error description")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class GetRolesResponse(BaseModel):
    """Get roles response."""

    success: bool = Field(..., description="Whether request was successful")
    data: "GetRolesResponseData" = Field(..., description="Roles data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class GetRolesResponseData(BaseModel):
    """Get roles response data."""

    roles: List[str] = Field(..., description="List of user roles")


class RefreshRolesResponse(BaseModel):
    """Refresh roles response."""

    success: bool = Field(..., description="Whether request was successful")
    data: GetRolesResponseData = Field(..., description="Roles data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class GetPermissionsResponse(BaseModel):
    """Get permissions response."""

    success: bool = Field(..., description="Whether request was successful")
    data: "GetPermissionsResponseData" = Field(..., description="Permissions data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class GetPermissionsResponseData(BaseModel):
    """Get permissions response data."""

    permissions: List[str] = Field(..., description="List of user permissions")


class RefreshPermissionsResponse(BaseModel):
    """Refresh permissions response."""

    success: bool = Field(..., description="Whether request was successful")
    data: GetPermissionsResponseData = Field(..., description="Permissions data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")
