"""
Unit tests for PermissionsApi.

Tests all permissions API endpoints with proper mocking.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.api.permissions_api import PermissionsApi
from miso_client.api.types.permissions_types import (
    GetPermissionsResponse,
    RefreshPermissionsResponse,
)
from miso_client.errors import MisoClientError
from miso_client.models.config import MisoClientConfig
from miso_client.utils.http_client import HttpClient


class TestPermissionsApi:
    """Test cases for PermissionsApi."""

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
    def permissions_api(self, mock_http_client):
        """Create PermissionsApi instance."""
        return PermissionsApi(mock_http_client)

    @pytest.mark.asyncio
    async def test_get_permissions_with_token(self, permissions_api, mock_http_client):
        """Test get permissions with token."""
        mock_response = {
            "success": True,
            "data": {"permissions": ["read", "write", "delete"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await permissions_api.get_permissions("test-token", "dev", "app1")

        assert isinstance(result, GetPermissionsResponse)
        assert result.success is True
        assert result.data.permissions == ["read", "write", "delete"]
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == permissions_api.PERMISSIONS_ENDPOINT
        assert call_args[0][2] == "test-token"
        assert call_args[1]["params"] == {"environment": "dev", "application": "app1"}

    @pytest.mark.asyncio
    async def test_get_permissions_without_token(self, permissions_api, mock_http_client):
        """Test get permissions without token (uses x-client-token)."""
        mock_response = {
            "success": True,
            "data": {"permissions": ["read", "write"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.get.return_value = mock_response

        result = await permissions_api.get_permissions()

        assert isinstance(result, GetPermissionsResponse)
        assert result.success is True
        assert result.data.permissions == ["read", "write"]
        mock_http_client.get.assert_called_once_with(
            permissions_api.PERMISSIONS_ENDPOINT, params={}
        )

    @pytest.mark.asyncio
    async def test_get_permissions_with_application_only(self, permissions_api, mock_http_client):
        """Test get permissions with application filter only."""
        mock_response = {
            "success": True,
            "data": {"permissions": ["read"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.get.return_value = mock_response

        result = await permissions_api.get_permissions(application="app1")

        assert isinstance(result, GetPermissionsResponse)
        mock_http_client.get.assert_called_once_with(
            permissions_api.PERMISSIONS_ENDPOINT, params={"application": "app1"}
        )

    @pytest.mark.asyncio
    async def test_refresh_permissions_with_token(self, permissions_api, mock_http_client):
        """Test refresh permissions with token."""
        mock_response = {
            "success": True,
            "data": {"permissions": ["read", "write", "delete"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await permissions_api.refresh_permissions("test-token")

        assert isinstance(result, RefreshPermissionsResponse)
        assert result.success is True
        assert result.data.permissions == ["read", "write", "delete"]
        mock_http_client.authenticated_request.assert_called_once_with(
            "GET",
            permissions_api.PERMISSIONS_REFRESH_ENDPOINT,
            "test-token",
            params={},
            auth_strategy=None,
        )

    @pytest.mark.asyncio
    async def test_refresh_permissions_without_token(self, permissions_api, mock_http_client):
        """Test refresh permissions without token."""
        mock_response = {
            "success": True,
            "data": {"permissions": ["read", "write"]},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.get.return_value = mock_response

        result = await permissions_api.refresh_permissions()

        assert isinstance(result, RefreshPermissionsResponse)
        assert result.success is True
        mock_http_client.get.assert_called_once_with(
            permissions_api.PERMISSIONS_REFRESH_ENDPOINT, params={}
        )

    @pytest.mark.asyncio
    async def test_get_permissions_error(self, permissions_api, mock_http_client):
        """Test get permissions error handling."""
        mock_http_client.authenticated_request.side_effect = MisoClientError(
            "Failed to get permissions"
        )

        with pytest.raises(MisoClientError):
            await permissions_api.get_permissions("test-token")

    @pytest.mark.asyncio
    async def test_refresh_permissions_error(self, permissions_api, mock_http_client):
        """Test refresh permissions error handling."""
        mock_http_client.authenticated_request.side_effect = MisoClientError(
            "Failed to refresh permissions"
        )

        with pytest.raises(MisoClientError):
            await permissions_api.refresh_permissions("test-token")
