"""
Unit tests for AuthApi.

Tests all authentication API endpoints with proper mocking.
All responses now follow OpenAPI spec format: {"data": {...}} without success/timestamp.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.api.auth_api import AuthApi
from miso_client.api.types.auth_types import (
    DeviceCodeResponseWrapper,
    DeviceCodeTokenPollResponse,
    DeviceCodeTokenResponse,
    GetPermissionsResponse,
    GetRolesResponse,
    GetUserResponse,
    LoginResponse,
    LogoutResponse,
    RefreshPermissionsResponse,
    RefreshRolesResponse,
    RefreshTokenResponse,
    ValidateTokenResponse,
)
from miso_client.errors import MisoClientError
from miso_client.models.config import MisoClientConfig
from miso_client.utils.http_client import HttpClient


class TestAuthApi:
    """Test cases for AuthApi."""

    @pytest.fixture
    def config(self):
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
        )

    @pytest.fixture
    def mock_http_client(self, config):
        """Mock HTTP client."""
        http_client = MagicMock(spec=HttpClient)
        http_client.config = config
        http_client.get = AsyncMock()
        http_client.post = AsyncMock()
        http_client.authenticated_request = AsyncMock()
        return http_client

    @pytest.fixture
    def auth_api(self, mock_http_client):
        """Create AuthApi instance."""
        return AuthApi(mock_http_client)

    @pytest.mark.asyncio
    async def test_login_success(self, auth_api, mock_http_client):
        """Test successful login."""
        mock_response = {
            "data": {"loginUrl": "https://keycloak.example.com/auth"},
        }
        mock_http_client.get.return_value = mock_response

        result = await auth_api.login("https://example.com/callback", "state123")

        assert isinstance(result, LoginResponse)
        assert result.data.loginUrl == "https://keycloak.example.com/auth"
        mock_http_client.get.assert_called_once_with(
            auth_api.LOGIN_ENDPOINT,
            params={"redirect": "https://example.com/callback", "state": "state123"},
        )

    @pytest.mark.asyncio
    async def test_login_without_state(self, auth_api, mock_http_client):
        """Test login without state parameter."""
        mock_response = {
            "data": {"loginUrl": "https://keycloak.example.com/auth"},
        }
        mock_http_client.get.return_value = mock_response

        result = await auth_api.login("https://example.com/callback")

        assert isinstance(result, LoginResponse)
        mock_http_client.get.assert_called_once_with(
            auth_api.LOGIN_ENDPOINT, params={"redirect": "https://example.com/callback"}
        )

    @pytest.mark.asyncio
    async def test_validate_token_success(self, auth_api, mock_http_client):
        """Test successful token validation."""
        mock_response = {
            "data": {
                "authenticated": True,
                "user": {"id": "123", "username": "test", "email": "test@example.com"},
                "expiresAt": "2024-01-01T01:00:00Z",
            },
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await auth_api.validate_token("test-token", "dev", "app1")

        assert isinstance(result, ValidateTokenResponse)
        assert result.data.authenticated is True
        assert result.data.user is not None
        assert result.data.user.id == "123"
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == auth_api.VALIDATE_ENDPOINT
        assert call_args[0][2] == "test-token"

    @pytest.mark.asyncio
    async def test_get_user_with_token(self, auth_api, mock_http_client):
        """Test get user with token."""
        mock_response = {
            "data": {
                "user": {"id": "123", "username": "test", "email": "test@example.com"},
                "authenticated": True,
            },
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await auth_api.get_user("test-token")

        assert isinstance(result, GetUserResponse)
        assert result.data.user.id == "123"
        mock_http_client.authenticated_request.assert_called_once_with(
            "GET", auth_api.USER_ENDPOINT, "test-token", auth_strategy=None
        )

    @pytest.mark.asyncio
    async def test_get_user_without_token(self, auth_api, mock_http_client):
        """Test get user without token (uses x-client-token)."""
        mock_response = {
            "data": {
                "user": {"id": "123", "username": "test", "email": "test@example.com"},
                "authenticated": True,
            },
        }
        mock_http_client.get.return_value = mock_response

        result = await auth_api.get_user()

        assert isinstance(result, GetUserResponse)
        mock_http_client.get.assert_called_once_with(auth_api.USER_ENDPOINT)

    @pytest.mark.asyncio
    async def test_logout_success(self, auth_api, mock_http_client):
        """Test successful logout."""
        # OpenAPI spec shows logout returns {"data": null}
        mock_response = {
            "data": None,
        }
        mock_http_client.post.return_value = mock_response

        result = await auth_api.logout()

        assert isinstance(result, LogoutResponse)
        assert result.data is None
        mock_http_client.post.assert_called_once_with(auth_api.LOGOUT_ENDPOINT)

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, auth_api, mock_http_client):
        """Test successful token refresh."""
        mock_response = {
            "data": {
                "accessToken": "new-access-token",
                "refreshToken": "new-refresh-token",
                "expiresIn": 3600,
            },
        }
        mock_http_client.post.return_value = mock_response

        result = await auth_api.refresh_token("refresh-token")

        assert isinstance(result, RefreshTokenResponse)
        assert result.data.accessToken == "new-access-token"
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == auth_api.REFRESH_ENDPOINT

    @pytest.mark.asyncio
    async def test_initiate_device_code_success(self, auth_api, mock_http_client):
        """Test successful device code initiation."""
        mock_response = {
            "data": {
                "deviceCode": "device-code-123",
                "userCode": "ABCD-1234",
                "verificationUri": "https://example.com/verify",
                "verificationUriComplete": "https://example.com/verify?code=ABCD-1234",
                "expiresIn": 600,
                "interval": 5,
            },
        }
        mock_http_client.post.return_value = mock_response

        result = await auth_api.initiate_device_code("dev", "openid profile email")

        assert isinstance(result, DeviceCodeResponseWrapper)
        assert result.data.deviceCode == "device-code-123"
        mock_http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_device_code_token_success(self, auth_api, mock_http_client):
        """Test successful device code token poll."""
        mock_response = {
            "data": {
                "accessToken": "access-token",
                "refreshToken": "refresh-token",
                "expiresIn": 3600,
            },
        }
        mock_http_client.post.return_value = mock_response

        result = await auth_api.poll_device_code_token("device-code-123")

        assert isinstance(result, DeviceCodeTokenPollResponse)
        assert result.data is not None
        assert result.data.accessToken == "access-token"

    @pytest.mark.asyncio
    async def test_poll_device_code_token_pending(self, auth_api, mock_http_client):
        """Test device code token poll while pending."""
        mock_response = {
            "data": None,
            "error": "authorization_pending",
            "errorDescription": "Authorization pending",
        }
        mock_http_client.post.return_value = mock_response

        result = await auth_api.poll_device_code_token("device-code-123")

        assert isinstance(result, DeviceCodeTokenPollResponse)
        assert result.data is None
        assert result.error == "authorization_pending"

    @pytest.mark.asyncio
    async def test_refresh_device_code_token_success(self, auth_api, mock_http_client):
        """Test successful device code token refresh."""
        mock_response = {
            "data": {
                "accessToken": "new-access-token",
                "refreshToken": "new-refresh-token",
                "expiresIn": 3600,
            },
        }
        mock_http_client.post.return_value = mock_response

        result = await auth_api.refresh_device_code_token("refresh-token")

        assert isinstance(result, DeviceCodeTokenResponse)
        assert result.accessToken == "new-access-token"
        mock_http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_roles_with_token(self, auth_api, mock_http_client):
        """Test get roles with token."""
        mock_response = {
            "data": {"roles": ["admin", "user"]},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await auth_api.get_roles("test-token", "dev", "app1")

        assert isinstance(result, GetRolesResponse)
        assert result.data.roles == ["admin", "user"]
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[1]["params"] == {"environment": "dev", "application": "app1"}

    @pytest.mark.asyncio
    async def test_get_roles_without_token(self, auth_api, mock_http_client):
        """Test get roles without token."""
        mock_response = {
            "data": {"roles": ["admin", "user"]},
        }
        mock_http_client.get.return_value = mock_response

        result = await auth_api.get_roles()

        assert isinstance(result, GetRolesResponse)
        mock_http_client.get.assert_called_once_with(auth_api.ROLES_ENDPOINT, params={})

    @pytest.mark.asyncio
    async def test_refresh_roles_with_token(self, auth_api, mock_http_client):
        """Test refresh roles with token."""
        mock_response = {
            "data": {"roles": ["admin", "user"]},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await auth_api.refresh_roles("test-token")

        assert isinstance(result, RefreshRolesResponse)
        mock_http_client.authenticated_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_permissions_with_token(self, auth_api, mock_http_client):
        """Test get permissions with token."""
        mock_response = {
            "data": {"permissions": ["read", "write"]},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await auth_api.get_permissions("test-token", "dev", "app1")

        assert isinstance(result, GetPermissionsResponse)
        assert result.data.permissions == ["read", "write"]

    @pytest.mark.asyncio
    async def test_refresh_permissions_with_token(self, auth_api, mock_http_client):
        """Test refresh permissions with token."""
        mock_response = {
            "data": {"permissions": ["read", "write"]},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await auth_api.refresh_permissions("test-token")

        assert isinstance(result, RefreshPermissionsResponse)
        assert result.data.permissions == ["read", "write"]

    @pytest.mark.asyncio
    async def test_validate_token_error(self, auth_api, mock_http_client):
        """Test token validation error handling."""
        mock_http_client.authenticated_request.side_effect = MisoClientError("Validation failed")

        with pytest.raises(MisoClientError):
            await auth_api.validate_token("invalid-token")

    @pytest.mark.asyncio
    async def test_login_error(self, auth_api, mock_http_client):
        """Test login error handling."""
        mock_http_client.get.side_effect = MisoClientError("Login failed")

        with pytest.raises(MisoClientError):
            await auth_api.login("https://example.com/callback")
