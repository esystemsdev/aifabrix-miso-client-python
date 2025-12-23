"""
Unit tests for ApiClient wrapper.

Tests the main ApiClient class that wraps all API classes.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.api import ApiClient
from miso_client.models.config import MisoClientConfig
from miso_client.utils.http_client import HttpClient


class TestApiClient:
    """Test cases for ApiClient."""

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
    def api_client(self, mock_http_client):
        """Create ApiClient instance."""
        return ApiClient(mock_http_client)

    def test_api_client_initialization(self, api_client, mock_http_client):
        """Test ApiClient initialization."""
        assert api_client.http_client == mock_http_client
        assert api_client.auth is not None
        assert api_client.roles is not None
        assert api_client.permissions is not None
        assert api_client.logs is not None

    def test_api_client_has_auth_api(self, api_client):
        """Test ApiClient has AuthApi."""
        from miso_client.api.auth_api import AuthApi

        assert isinstance(api_client.auth, AuthApi)

    def test_api_client_has_roles_api(self, api_client):
        """Test ApiClient has RolesApi."""
        from miso_client.api.roles_api import RolesApi

        assert isinstance(api_client.roles, RolesApi)

    def test_api_client_has_permissions_api(self, api_client):
        """Test ApiClient has PermissionsApi."""
        from miso_client.api.permissions_api import PermissionsApi

        assert isinstance(api_client.permissions, PermissionsApi)

    def test_api_client_has_logs_api(self, api_client):
        """Test ApiClient has LogsApi."""
        from miso_client.api.logs_api import LogsApi

        assert isinstance(api_client.logs, LogsApi)

    def test_all_apis_share_same_http_client(self, api_client, mock_http_client):
        """Test all API classes share the same HttpClient instance."""
        assert api_client.auth.http_client == mock_http_client
        assert api_client.roles.http_client == mock_http_client
        assert api_client.permissions.http_client == mock_http_client
        assert api_client.logs.http_client == mock_http_client
