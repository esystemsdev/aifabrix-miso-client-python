"""
Unit tests for ApplicationsApi.

Tests application status endpoints with proper mocking.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.api.applications_api import ApplicationsApi
from miso_client.api.types.applications_types import (
    ApplicationStatus,
    ApplicationStatusResponse,
    UpdateSelfStatusRequest,
    UpdateSelfStatusResponse,
)
from miso_client.models.config import AuthStrategy, MisoClientConfig
from miso_client.utils.http_client import HttpClient


class TestApplicationsApi:
    """Test cases for ApplicationsApi."""

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
        http_client.post = AsyncMock()
        http_client.get = AsyncMock()
        http_client.authenticated_request = AsyncMock()
        http_client.request_with_auth_strategy = AsyncMock()
        return http_client

    @pytest.fixture
    def applications_api(self, mock_http_client):
        """Create ApplicationsApi instance."""
        return ApplicationsApi(mock_http_client)

    @pytest.mark.asyncio
    async def test_update_self_status_client_credentials(self, applications_api, mock_http_client):
        """Test update_self_status without auth_strategy (client credentials)."""
        body = UpdateSelfStatusRequest(
            status=ApplicationStatus.HEALTHY, url="https://app.example.com"
        )
        mock_response = {
            "success": True,
            "application": {
                "id": "app-123",
                "key": "my-app",
                "status": "healthy",
                "url": "https://app.example.com",
            },
            "message": "Updated",
        }
        mock_http_client.post.return_value = mock_response

        result = await applications_api.update_self_status("dev", body)

        assert isinstance(result, UpdateSelfStatusResponse)
        assert result.success is True
        assert result.application is not None
        assert result.application.status == "healthy"
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == "/api/v1/environments/dev/applications/self/status"
        assert call_args[1]["data"] == {"status": "healthy", "url": "https://app.example.com"}

    @pytest.mark.asyncio
    async def test_update_self_status_with_bearer_auth_strategy(
        self, applications_api, mock_http_client
    ):
        """Test update_self_status with bearer auth strategy."""
        body = UpdateSelfStatusRequest(internalUrl="http://internal:8080")
        mock_response = {
            "success": True,
            "application": {"id": "app-123", "internalUrl": "http://internal:8080"},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["bearer"], bearerToken="test-token")
        result = await applications_api.update_self_status("dev", body, auth_strategy)

        assert isinstance(result, UpdateSelfStatusResponse)
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][2] == "test-token"
        assert call_args[1]["auth_strategy"] == auth_strategy

    @pytest.mark.asyncio
    async def test_update_self_status_with_api_key_auth_strategy(
        self, applications_api, mock_http_client
    ):
        """Test update_self_status with api-key auth strategy."""
        body = UpdateSelfStatusRequest(port=8080)
        mock_response = {"success": True, "application": {"port": 8080}}
        mock_http_client.request_with_auth_strategy.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["api-key"], apiKey="key-123")
        result = await applications_api.update_self_status("dev", body, auth_strategy)

        assert isinstance(result, UpdateSelfStatusResponse)
        mock_http_client.request_with_auth_strategy.assert_called_once()
        call_args = mock_http_client.request_with_auth_strategy.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][2] == auth_strategy

    @pytest.mark.asyncio
    async def test_get_application_status_client_credentials(
        self, applications_api, mock_http_client
    ):
        """Test get_application_status without auth_strategy (client credentials)."""
        mock_response = {
            "id": "app-123",
            "key": "my-app",
            "displayName": "My App",
            "status": "running",
            "url": "https://app.example.com",
        }
        mock_http_client.get.return_value = mock_response

        result = await applications_api.get_application_status("dev", "my-app")

        assert isinstance(result, ApplicationStatusResponse)
        assert result.key == "my-app"
        assert result.status == "running"
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert call_args[0][0] == "/api/v1/environments/dev/applications/my-app/status"

    @pytest.mark.asyncio
    async def test_get_application_status_with_bearer_auth_strategy(
        self, applications_api, mock_http_client
    ):
        """Test get_application_status with bearer auth strategy."""
        mock_response = {"id": "app-456", "key": "other-app", "status": "stopped"}
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["bearer"], bearerToken="user-token")
        result = await applications_api.get_application_status("pro", "other-app", auth_strategy)

        assert isinstance(result, ApplicationStatusResponse)
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][2] == "user-token"

    @pytest.mark.asyncio
    async def test_get_application_status_with_api_key_auth_strategy(
        self, applications_api, mock_http_client
    ):
        """Test get_application_status with api-key auth strategy."""
        mock_response = {"id": "app-789", "key": "api-app"}
        mock_http_client.request_with_auth_strategy.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["api-key"], apiKey="key-456")
        result = await applications_api.get_application_status("tst", "api-app", auth_strategy)

        assert isinstance(result, ApplicationStatusResponse)
        mock_http_client.request_with_auth_strategy.assert_called_once()
        call_args = mock_http_client.request_with_auth_strategy.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][2] == auth_strategy

    @pytest.mark.asyncio
    async def test_update_self_status_with_all_fields(self, applications_api, mock_http_client):
        """Test update_self_status with all optional fields."""
        body = UpdateSelfStatusRequest(
            status=ApplicationStatus.DEPLOYING,
            url="https://app.example.com",
            internalUrl="http://internal:9000",
            port=9000,
        )
        mock_response = {
            "success": True,
            "application": {
                "status": "deploying",
                "url": "https://app.example.com",
                "internalUrl": "http://internal:9000",
                "port": 9000,
            },
        }
        mock_http_client.post.return_value = mock_response

        result = await applications_api.update_self_status("dev", body)

        assert result.success is True
        assert result.application.status == "deploying"
        assert result.application.port == 9000
        call_data = mock_http_client.post.call_args[1]["data"]
        assert call_data["status"] == "deploying"
        assert call_data["url"] == "https://app.example.com"
        assert call_data["internalUrl"] == "http://internal:9000"
        assert call_data["port"] == 9000
