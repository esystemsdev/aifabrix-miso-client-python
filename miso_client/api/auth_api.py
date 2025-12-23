"""
Auth API implementation.

Provides typed interfaces for authentication endpoints.
"""

from typing import Optional

from ..models.config import AuthStrategy
from ..utils.http_client import HttpClient
from .types.auth_types import (
    DeviceCodeRequest,
    DeviceCodeResponseWrapper,
    DeviceCodeTokenPollRequest,
    DeviceCodeTokenPollResponse,
    DeviceCodeTokenResponse,
    GetPermissionsResponse,
    GetRolesResponse,
    GetUserResponse,
    LoginResponse,
    LogoutResponse,
    RefreshPermissionsResponse,
    RefreshRolesResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ValidateTokenRequest,
    ValidateTokenResponse,
)


class AuthApi:
    """Auth API client for authentication endpoints."""

    # Endpoint constants
    LOGIN_ENDPOINT = "/api/v1/auth/login"
    VALIDATE_ENDPOINT = "/api/v1/auth/validate"
    USER_ENDPOINT = "/api/v1/auth/user"
    LOGOUT_ENDPOINT = "/api/v1/auth/logout"
    REFRESH_ENDPOINT = "/api/v1/auth/refresh"
    DEVICE_CODE_ENDPOINT = "/api/v1/auth/login"
    DEVICE_CODE_TOKEN_ENDPOINT = "/api/v1/auth/login/device/token"
    DEVICE_CODE_REFRESH_ENDPOINT = "/api/v1/auth/login/device/refresh"
    ROLES_ENDPOINT = "/api/v1/auth/roles"
    ROLES_REFRESH_ENDPOINT = "/api/v1/auth/roles/refresh"
    PERMISSIONS_ENDPOINT = "/api/v1/auth/permissions"
    PERMISSIONS_REFRESH_ENDPOINT = "/api/v1/auth/permissions/refresh"

    def __init__(self, http_client: HttpClient):
        """
        Initialize Auth API client.

        Args:
            http_client: HttpClient instance
        """
        self.http_client = http_client

    async def login(self, redirect: str, state: Optional[str] = None) -> LoginResponse:
        """
        Initiate login flow (GET with query params).

        Args:
            redirect: Redirect URI for OAuth2 callback
            state: Optional state parameter for CSRF protection

        Returns:
            LoginResponse with login URL

        Raises:
            MisoClientError: If request fails
        """
        params = {"redirect": redirect}
        if state:
            params["state"] = state

        response = await self.http_client.get(self.LOGIN_ENDPOINT, params=params)
        return LoginResponse(**response)

    async def validate_token(
        self,
        token: str,
        environment: Optional[str] = None,
        application: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> ValidateTokenResponse:
        """
        Validate authentication token (POST).

        Uses authenticated_request to send the token as Bearer token for authentication,
        while also including it in the request body for validation.

        Args:
            token: JWT token to validate
            environment: Optional environment key
            application: Optional application key
            auth_strategy: Optional authentication strategy

        Returns:
            ValidateTokenResponse with validation result

        Raises:
            MisoClientError: If request fails
        """
        request_data = ValidateTokenRequest(
            token=token, environment=environment, application=application
        )
        response = await self.http_client.authenticated_request(
            "POST",
            self.VALIDATE_ENDPOINT,
            token,
            data=request_data.model_dump(exclude_none=True),
            auth_strategy=auth_strategy,
        )
        return ValidateTokenResponse(**response)

    async def get_user(
        self, token: Optional[str] = None, auth_strategy: Optional[AuthStrategy] = None
    ) -> GetUserResponse:
        """
        Get current user information (GET).

        Token is optional - can use x-client-token header instead.

        Args:
            token: Optional user token (if not provided, uses x-client-token)
            auth_strategy: Optional authentication strategy

        Returns:
            GetUserResponse with user information

        Raises:
            MisoClientError: If request fails
        """
        if token:
            response = await self.http_client.authenticated_request(
                "GET", self.USER_ENDPOINT, token, auth_strategy=auth_strategy
            )
        else:
            response = await self.http_client.get(self.USER_ENDPOINT)
        return GetUserResponse(**response)

    async def logout(self, token: Optional[str] = None) -> LogoutResponse:
        """
        Logout user (POST).

        If token is provided, sends it in the request body for server-side invalidation.
        Otherwise, uses client credentials authentication.

        Args:
            token: Optional user token to invalidate (sent in request body if provided)

        Returns:
            LogoutResponse with logout message

        Raises:
            MisoClientError: If request fails
        """
        if token:
            # Send token in body for server-side invalidation
            response = await self.http_client.authenticated_request(
                "POST", self.LOGOUT_ENDPOINT, token, data={"token": token}
            )
        else:
            # Use client credentials (no user token)
            response = await self.http_client.post(self.LOGOUT_ENDPOINT)
        return LogoutResponse(**response)

    async def refresh_token(self, refresh_token: str) -> RefreshTokenResponse:
        """
        Refresh user access token (POST).

        Args:
            refresh_token: Refresh token

        Returns:
            RefreshTokenResponse with new tokens

        Raises:
            MisoClientError: If request fails
        """
        request_data = RefreshTokenRequest(refreshToken=refresh_token)
        response = await self.http_client.post(
            self.REFRESH_ENDPOINT, data=request_data.model_dump()
        )
        return RefreshTokenResponse(**response)

    async def initiate_device_code(
        self, environment: Optional[str] = None, scope: Optional[str] = None
    ) -> DeviceCodeResponseWrapper:
        """
        Initiate device code flow (POST).

        Args:
            environment: Optional environment key
            scope: Optional OAuth2 scope string

        Returns:
            DeviceCodeResponseWrapper with device code information

        Raises:
            MisoClientError: If request fails
        """
        request_data = DeviceCodeRequest(environment=environment, scope=scope)
        response = await self.http_client.post(
            self.DEVICE_CODE_ENDPOINT, data=request_data.model_dump(exclude_none=True)
        )
        return DeviceCodeResponseWrapper(**response)

    async def poll_device_code_token(self, device_code: str) -> DeviceCodeTokenPollResponse:
        """
        Poll for device code token (POST).

        Returns 202 while authorization is pending.

        Args:
            device_code: Device code from initiation

        Returns:
            DeviceCodeTokenPollResponse with token or pending status

        Raises:
            MisoClientError: If request fails
        """
        request_data = DeviceCodeTokenPollRequest(deviceCode=device_code)
        response = await self.http_client.post(
            self.DEVICE_CODE_TOKEN_ENDPOINT, data=request_data.model_dump()
        )
        return DeviceCodeTokenPollResponse(**response)

    async def refresh_device_code_token(self, refresh_token: str) -> DeviceCodeTokenResponse:
        """
        Refresh device code access token (POST).

        Args:
            refresh_token: Refresh token from device code flow

        Returns:
            DeviceCodeTokenResponse with new tokens

        Raises:
            MisoClientError: If request fails
        """
        request_data = RefreshTokenRequest(refreshToken=refresh_token)
        response = await self.http_client.post(
            self.DEVICE_CODE_REFRESH_ENDPOINT, data=request_data.model_dump()
        )
        response_data = response.get("data", {})
        return DeviceCodeTokenResponse(**response_data)

    async def get_roles(
        self,
        token: Optional[str] = None,
        environment: Optional[str] = None,
        application: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> GetRolesResponse:
        """
        Get user roles (GET).

        Args:
            token: Optional user token (if not provided, uses x-client-token)
            environment: Optional environment key filter
            application: Optional application key filter
            auth_strategy: Optional authentication strategy

        Returns:
            GetRolesResponse with user roles

        Raises:
            MisoClientError: If request fails
        """
        params = {}
        if environment:
            params["environment"] = environment
        if application:
            params["application"] = application

        if token:
            response = await self.http_client.authenticated_request(
                "GET", self.ROLES_ENDPOINT, token, params=params, auth_strategy=auth_strategy
            )
        else:
            response = await self.http_client.get(self.ROLES_ENDPOINT, params=params)
        return GetRolesResponse(**response)

    async def refresh_roles(
        self, token: Optional[str] = None, auth_strategy: Optional[AuthStrategy] = None
    ) -> RefreshRolesResponse:
        """
        Refresh user roles (GET).

        Args:
            token: Optional user token (if not provided, uses x-client-token)
            auth_strategy: Optional authentication strategy

        Returns:
            RefreshRolesResponse with refreshed roles

        Raises:
            MisoClientError: If request fails
        """
        if token:
            response = await self.http_client.authenticated_request(
                "GET", self.ROLES_REFRESH_ENDPOINT, token, auth_strategy=auth_strategy
            )
        else:
            response = await self.http_client.get(self.ROLES_REFRESH_ENDPOINT)
        return RefreshRolesResponse(**response)

    async def get_permissions(
        self,
        token: Optional[str] = None,
        environment: Optional[str] = None,
        application: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> GetPermissionsResponse:
        """
        Get user permissions (GET).

        Args:
            token: Optional user token (if not provided, uses x-client-token)
            environment: Optional environment key filter
            application: Optional application key filter
            auth_strategy: Optional authentication strategy

        Returns:
            GetPermissionsResponse with user permissions

        Raises:
            MisoClientError: If request fails
        """
        params = {}
        if environment:
            params["environment"] = environment
        if application:
            params["application"] = application

        if token:
            response = await self.http_client.authenticated_request(
                "GET", self.PERMISSIONS_ENDPOINT, token, params=params, auth_strategy=auth_strategy
            )
        else:
            response = await self.http_client.get(self.PERMISSIONS_ENDPOINT, params=params)
        return GetPermissionsResponse(**response)

    async def refresh_permissions(
        self, token: Optional[str] = None, auth_strategy: Optional[AuthStrategy] = None
    ) -> RefreshPermissionsResponse:
        """
        Refresh user permissions (GET).

        Args:
            token: Optional user token (if not provided, uses x-client-token)
            auth_strategy: Optional authentication strategy

        Returns:
            RefreshPermissionsResponse with refreshed permissions

        Raises:
            MisoClientError: If request fails
        """
        if token:
            response = await self.http_client.authenticated_request(
                "GET", self.PERMISSIONS_REFRESH_ENDPOINT, token, auth_strategy=auth_strategy
            )
        else:
            response = await self.http_client.get(self.PERMISSIONS_REFRESH_ENDPOINT)
        return RefreshPermissionsResponse(**response)
