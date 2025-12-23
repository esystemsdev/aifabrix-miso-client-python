"""
Unit tests for RolesApi.

Tests all roles API endpoints with proper mocking.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.api.roles_api import RolesApi
from miso_client.api.types.roles_types import GetRolesResponse, RefreshRolesResponse
from miso_client.errors import MisoClientError
from miso_client.models.config import MisoClientConfig
from miso_client.utils.http_client import HttpClient


class TestRolesApi:
    """Test cases for RolesApi."""

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
        http_client.authenticated_request = AsyncMock()
        return http_client

    @pytest.fixture
    def roles_api(self, mock_http_client):
        """Create RolesApi instance."""
        return RolesApi(mock_http_client)

    @pytest.mark.asyncio
    async def test_get_roles_with_token(self, roles_api, mock_http_client):
        """Test get roles with token."""
        mock_response = {
            "success": True,
            "data": {"roles": ["admin", "user", "viewer"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await roles_api.get_roles("test-token", "dev", "app1")

        assert isinstance(result, GetRolesResponse)
        assert result.success is True
        assert result.data.roles == ["admin", "user", "viewer"]
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == roles_api.ROLES_ENDPOINT
        assert call_args[0][2] == "test-token"
        assert call_args[1]["params"] == {"environment": "dev", "application": "app1"}

    @pytest.mark.asyncio
    async def test_get_roles_without_token(self, roles_api, mock_http_client):
        """Test get roles without token (uses x-client-token)."""
        mock_response = {
            "success": True,
            "data": {"roles": ["admin", "user"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.get.return_value = mock_response

        result = await roles_api.get_roles()

        assert isinstance(result, GetRolesResponse)
        assert result.success is True
        assert result.data.roles == ["admin", "user"]
        mock_http_client.get.assert_called_once_with(roles_api.ROLES_ENDPOINT, params={})

    @pytest.mark.asyncio
    async def test_get_roles_with_environment_only(self, roles_api, mock_http_client):
        """Test get roles with environment filter only."""
        mock_response = {
            "success": True,
            "data": {"roles": ["admin"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.get.return_value = mock_response

        result = await roles_api.get_roles(environment="dev")

        assert isinstance(result, GetRolesResponse)
        mock_http_client.get.assert_called_once_with(
            roles_api.ROLES_ENDPOINT, params={"environment": "dev"}
        )

    @pytest.mark.asyncio
    async def test_refresh_roles_with_token(self, roles_api, mock_http_client):
        """Test refresh roles with token."""
        mock_response = {
            "success": True,
            "data": {"roles": ["admin", "user", "viewer"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await roles_api.refresh_roles("test-token")

        assert isinstance(result, RefreshRolesResponse)
        assert result.success is True
        assert result.data.roles == ["admin", "user", "viewer"]
        mock_http_client.authenticated_request.assert_called_once_with(
            "GET", roles_api.ROLES_REFRESH_ENDPOINT, "test-token", auth_strategy=None
        )

    @pytest.mark.asyncio
    async def test_refresh_roles_without_token(self, roles_api, mock_http_client):
        """Test refresh roles without token."""
        mock_response = {
            "success": True,
            "data": {"roles": ["admin", "user"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.get.return_value = mock_response

        result = await roles_api.refresh_roles()

        assert isinstance(result, RefreshRolesResponse)
        assert result.success is True
        mock_http_client.get.assert_called_once_with(roles_api.ROLES_REFRESH_ENDPOINT)

    @pytest.mark.asyncio
    async def test_get_roles_error(self, roles_api, mock_http_client):
        """Test get roles error handling."""
        mock_http_client.authenticated_request.side_effect = MisoClientError("Failed to get roles")

        with pytest.raises(MisoClientError):
            await roles_api.get_roles("test-token")

    @pytest.mark.asyncio
    async def test_refresh_roles_error(self, roles_api, mock_http_client):
        """Test refresh roles error handling."""
        mock_http_client.authenticated_request.side_effect = MisoClientError(
            "Failed to refresh roles"
        )

        with pytest.raises(MisoClientError):
            await roles_api.refresh_roles("test-token")
