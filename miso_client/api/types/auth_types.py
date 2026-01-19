"""
Auth API request and response types.

All types follow OpenAPI specification with camelCase field names.
The controller returns responses in format: {"data": {...}} without success/timestamp.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from ...models.config import UserInfo


class LoginResponse(BaseModel):
    """Login response with login URL."""

    data: "LoginResponseData" = Field(..., description="Login data")


class LoginResponseData(BaseModel):
    """Login response data."""

    loginUrl: str = Field(..., description="Login URL for OAuth2 flow")


class ValidateTokenRequest(BaseModel):
    """Token validation request."""

    token: str = Field(..., description="JWT token to validate")
    environment: Optional[str] = Field(default=None, description="Optional environment key")
    application: Optional[str] = Field(default=None, description="Optional application key")


class ValidateTokenResponse(BaseModel):
    """Token validation response - matches OpenAPI spec."""

    data: "ValidateTokenResponseData" = Field(..., description="Validation data")


class ValidateTokenResponseData(BaseModel):
    """Token validation response data."""

    authenticated: bool = Field(..., description="Whether token is authenticated")
    user: Optional[UserInfo] = Field(default=None, description="User information if authenticated")
    expiresAt: Optional[str] = Field(default=None, description="Token expiration timestamp")
    environment: Optional[str] = Field(default=None, description="Environment key")
    application: Optional[str] = Field(default=None, description="Application key")


class GetUserResponse(BaseModel):
    """Get user response - matches OpenAPI spec."""

    data: "GetUserResponseData" = Field(..., description="User data")


class GetUserResponseData(BaseModel):
    """Get user response data."""

    user: Optional[UserInfo] = Field(default=None, description="User information")
    authenticated: bool = Field(..., description="Whether user is authenticated")


class LogoutResponse(BaseModel):
    """Logout response - matches OpenAPI spec."""

    data: Optional["LogoutResponseData"] = Field(
        default=None, description="Logout data (always null per OpenAPI spec)"
    )


class LogoutResponseData(BaseModel):
    """Logout response data (typically null)."""

    message: str = Field(default="Logged out successfully", description="Logout message")


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refreshToken: str = Field(..., description="Refresh token")


class DeviceCodeTokenResponse(BaseModel):
    """Device code token response."""

    accessToken: str = Field(..., description="JWT access token")
    refreshToken: Optional[str] = Field(default=None, description="Refresh token")
    expiresIn: int = Field(..., description="Token expiration in seconds")


class RefreshTokenResponse(BaseModel):
    """Refresh token response - matches OpenAPI spec."""

    data: DeviceCodeTokenResponse = Field(..., description="Token data")


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
    """Device code response wrapper - matches OpenAPI spec."""

    data: DeviceCodeResponse = Field(..., description="Device code data")


class DeviceCodeTokenPollRequest(BaseModel):
    """Device code token poll request."""

    deviceCode: str = Field(..., description="Device code from initiation")


class DeviceCodeTokenPollResponse(BaseModel):
    """Device code token poll response - matches OpenAPI spec."""

    data: Optional[DeviceCodeTokenResponse] = Field(default=None, description="Token data if ready")
    error: Optional[str] = Field(default=None, description="Error code if pending")
    errorDescription: Optional[str] = Field(default=None, description="Error description")


class GetRolesResponse(BaseModel):
    """Get roles response - matches OpenAPI spec."""

    data: "GetRolesResponseData" = Field(..., description="Roles data")


class GetRolesResponseData(BaseModel):
    """Get roles response data."""

    roles: List[str] = Field(default_factory=list, description="List of user roles")


class RefreshRolesResponse(BaseModel):
    """Refresh roles response - matches OpenAPI spec."""

    data: GetRolesResponseData = Field(..., description="Roles data")


class GetPermissionsResponse(BaseModel):
    """Get permissions response - matches OpenAPI spec."""

    data: "GetPermissionsResponseData" = Field(..., description="Permissions data")


class GetPermissionsResponseData(BaseModel):
    """Get permissions response data."""

    permissions: List[str] = Field(default_factory=list, description="List of user permissions")


class RefreshPermissionsResponse(BaseModel):
    """Refresh permissions response - matches OpenAPI spec."""

    data: GetPermissionsResponseData = Field(..., description="Permissions data")
