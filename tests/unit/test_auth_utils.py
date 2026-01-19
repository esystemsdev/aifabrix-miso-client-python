"""
Unit tests for auth_utils shared utility functions.

Tests the validate_token_request shared utility function used by
RoleService and PermissionService.

All responses now follow OpenAPI spec format: {"data": {...}} without success/timestamp.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.api.types.auth_types import ValidateTokenResponse, ValidateTokenResponseData
from miso_client.models.config import AuthStrategy, MisoClientConfig, UserInfo
from miso_client.utils.auth_utils import validate_token_request
from miso_client.utils.http_client import HttpClient


class TestValidateTokenRequest:
    """Test cases for validate_token_request utility function."""

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
        http_client.authenticated_request = AsyncMock()
        return http_client

    @pytest.fixture
    def mock_api_client(self, mock_http_client):
        """Mock API client."""
        from miso_client.api import ApiClient

        api_client = MagicMock(spec=ApiClient)
        api_client.http_client = mock_http_client
        api_client.auth = MagicMock()
        return api_client

    @pytest.mark.asyncio
    async def test_validate_token_request_with_api_client(self, mock_api_client, mock_http_client):
        """Test validate_token_request using ApiClient path."""
        # Mock ApiClient response (matches OpenAPI spec format)
        mock_response = ValidateTokenResponse(
            data=ValidateTokenResponseData(
                authenticated=True,
                user=UserInfo(
                    id="user-123",
                    username="testuser",
                    email="test@example.com",
                    name="Test User",
                    roles=["admin"],
                    permissions=["read", "write"],
                ),
                expiresAt="2024-12-31T23:59:59Z",
            ),
        )
        mock_api_client.auth.validate_token = AsyncMock(return_value=mock_response)

        result = await validate_token_request("test-token", mock_http_client, mock_api_client, None)

        assert result["data"]["authenticated"] is True
        assert result["data"]["user"]["id"] == "user-123"
        assert result["data"]["user"]["email"] == "test@example.com"
        assert result["data"]["expiresAt"] == "2024-12-31T23:59:59Z"
        mock_api_client.auth.validate_token.assert_called_once_with(
            "test-token", auth_strategy=None
        )

    @pytest.mark.asyncio
    async def test_validate_token_request_with_api_client_and_auth_strategy(
        self, mock_api_client, mock_http_client
    ):
        """Test validate_token_request using ApiClient with auth_strategy."""
        auth_strategy = AuthStrategy(environment="dev", application="app1")
        mock_response = ValidateTokenResponse(
            data=ValidateTokenResponseData(
                authenticated=True,
                user=UserInfo(
                    id="user-456",
                    username="testuser2",
                    email="test2@example.com",
                    name="Test User 2",
                    roles=["user"],
                    permissions=["read"],
                ),
                expiresAt="2024-12-31T23:59:59Z",
            ),
        )
        mock_api_client.auth.validate_token = AsyncMock(return_value=mock_response)

        result = await validate_token_request(
            "test-token", mock_http_client, mock_api_client, auth_strategy
        )

        assert result["data"]["authenticated"] is True
        assert result["data"]["user"]["id"] == "user-456"
        mock_api_client.auth.validate_token.assert_called_once_with(
            "test-token", auth_strategy=auth_strategy
        )

    @pytest.mark.asyncio
    async def test_validate_token_request_with_api_client_no_user(
        self, mock_api_client, mock_http_client
    ):
        """Test validate_token_request using ApiClient when user is None."""
        mock_response = ValidateTokenResponse(
            data=ValidateTokenResponseData(
                authenticated=False,
                user=None,
                expiresAt=None,
            ),
        )
        mock_api_client.auth.validate_token = AsyncMock(return_value=mock_response)

        result = await validate_token_request("test-token", mock_http_client, mock_api_client, None)

        assert result["data"]["authenticated"] is False
        assert result["data"]["user"] is None
        assert result["data"]["expiresAt"] is None

    @pytest.mark.asyncio
    async def test_validate_token_request_with_http_client(self, mock_http_client):
        """Test validate_token_request using HttpClient fallback path."""
        mock_response = {
            "data": {
                "authenticated": True,
                "user": {"id": "user-789", "email": "test3@example.com"},
                "expiresAt": "2024-12-31T23:59:59Z",
            },
        }
        mock_http_client.authenticated_request = AsyncMock(return_value=mock_response)

        result = await validate_token_request("test-token", mock_http_client, None, None)

        assert result == mock_response
        mock_http_client.authenticated_request.assert_called_once_with(
            "POST", "/api/v1/auth/validate", "test-token", {"token": "test-token"}
        )

    @pytest.mark.asyncio
    async def test_validate_token_request_with_http_client_and_auth_strategy(
        self, mock_http_client
    ):
        """Test validate_token_request using HttpClient with auth_strategy."""
        auth_strategy = AuthStrategy(environment="prod", application="app2")
        mock_response = {
            "data": {
                "authenticated": True,
                "user": {"id": "user-999", "email": "test4@example.com"},
                "expiresAt": "2024-12-31T23:59:59Z",
            },
        }
        mock_http_client.authenticated_request = AsyncMock(return_value=mock_response)

        result = await validate_token_request("test-token", mock_http_client, None, auth_strategy)

        assert result == mock_response
        mock_http_client.authenticated_request.assert_called_once_with(
            "POST",
            "/api/v1/auth/validate",
            "test-token",
            {"token": "test-token"},
            auth_strategy=auth_strategy,
        )

    @pytest.mark.asyncio
    async def test_validate_token_request_prefers_api_client(
        self, mock_api_client, mock_http_client
    ):
        """Test that ApiClient is preferred over HttpClient when both are provided."""
        mock_response = ValidateTokenResponse(
            data=ValidateTokenResponseData(
                authenticated=True,
                user=UserInfo(
                    id="user-prefer-api",
                    username="preferapi",
                    email="prefer@example.com",
                    name="Prefer API",
                    roles=[],
                    permissions=[],
                ),
                expiresAt="2024-12-31T23:59:59Z",
            ),
        )
        mock_api_client.auth.validate_token = AsyncMock(return_value=mock_response)

        result = await validate_token_request("test-token", mock_http_client, mock_api_client, None)

        assert result["data"]["user"]["id"] == "user-prefer-api"
        mock_api_client.auth.validate_token.assert_called_once()
        # HttpClient should not be called when ApiClient is available
        mock_http_client.authenticated_request.assert_not_called()
