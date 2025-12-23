"""
Unit tests for LogsApi.

Tests all logging API endpoints with proper mocking.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.api.logs_api import LogsApi
from miso_client.api.types.logs_types import (
    AuditLogData,
    BatchLogResponse,
    GeneralLogData,
    LogRequest,
    LogResponse,
)
from miso_client.errors import MisoClientError
from miso_client.models.config import LogEntry, MisoClientConfig
from miso_client.utils.http_client import HttpClient


class TestLogsApi:
    """Test cases for LogsApi."""

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
        http_client.authenticated_request = AsyncMock()
        return http_client

    @pytest.fixture
    def logs_api(self, mock_http_client):
        """Create LogsApi instance."""
        return LogsApi(mock_http_client)

    @pytest.fixture
    def general_log_data(self):
        """Create general log data."""
        return GeneralLogData(level="error", message="Test error message", correlationId="corr-123")

    @pytest.fixture
    def audit_log_data(self):
        """Create audit log data."""
        return AuditLogData(
            entityType="User",
            entityId="user-123",
            action="CREATE",
            oldValues=None,
            newValues={"name": "Test User"},
            correlationId="corr-123",
        )

    @pytest.mark.asyncio
    async def test_send_log_general_without_token(
        self, logs_api, mock_http_client, general_log_data
    ):
        """Test send general log without token (uses client credentials)."""
        log_request = LogRequest(type="general", data=general_log_data)
        mock_response = {
            "success": True,
            "message": "Log entry created",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.post.return_value = mock_response

        result = await logs_api.send_log(log_request)

        assert isinstance(result, LogResponse)
        assert result.success is True
        assert result.message == "Log entry created"
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == logs_api.LOGS_ENDPOINT

    @pytest.mark.asyncio
    async def test_send_log_general_with_token(self, logs_api, mock_http_client, general_log_data):
        """Test send general log with token."""
        log_request = LogRequest(type="general", data=general_log_data)
        mock_response = {
            "success": True,
            "message": "Log entry created",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.send_log(log_request, "test-token")

        assert isinstance(result, LogResponse)
        assert result.success is True
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == logs_api.LOGS_ENDPOINT
        assert call_args[0][2] == "test-token"

    @pytest.mark.asyncio
    async def test_send_log_audit_without_token(self, logs_api, mock_http_client, audit_log_data):
        """Test send audit log without token."""
        log_request = LogRequest(type="audit", data=audit_log_data)
        mock_response = {
            "success": True,
            "message": "Log entry created",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.post.return_value = mock_response

        result = await logs_api.send_log(log_request)

        assert isinstance(result, LogResponse)
        assert result.success is True
        mock_http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_log_error_type(self, logs_api, mock_http_client, general_log_data):
        """Test send error type log."""
        log_request = LogRequest(type="error", data=general_log_data)
        mock_response = {
            "success": True,
            "message": "Log entry created",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.post.return_value = mock_response

        result = await logs_api.send_log(log_request)

        assert isinstance(result, LogResponse)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_batch_logs_without_token(self, logs_api, mock_http_client):
        """Test send batch logs without token."""
        logs = [
            LogEntry(
                timestamp="2024-01-01T00:00:00Z",
                level="error",
                environment="dev",
                application="app1",
                message="Error 1",
            ),
            LogEntry(
                timestamp="2024-01-01T00:01:00Z",
                level="info",
                environment="dev",
                application="app1",
                message="Info 1",
            ),
        ]
        mock_response = {
            "success": True,
            "message": "Logs processed successfully",
            "processed": 2,
            "failed": 0,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.post.return_value = mock_response

        result = await logs_api.send_batch_logs(logs)

        assert isinstance(result, BatchLogResponse)
        assert result.success is True
        assert result.processed == 2
        assert result.failed == 0
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[0][0] == logs_api.LOGS_BATCH_ENDPOINT

    @pytest.mark.asyncio
    async def test_send_batch_logs_with_token(self, logs_api, mock_http_client):
        """Test send batch logs with token."""
        logs = [
            LogEntry(
                timestamp="2024-01-01T00:00:00Z",
                level="error",
                environment="dev",
                application="app1",
                message="Error 1",
            ),
        ]
        mock_response = {
            "success": True,
            "message": "Logs processed successfully",
            "processed": 1,
            "failed": 0,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.send_batch_logs(logs, "test-token")

        assert isinstance(result, BatchLogResponse)
        assert result.success is True
        assert result.processed == 1
        mock_http_client.authenticated_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_batch_logs_partial_failure(self, logs_api, mock_http_client):
        """Test send batch logs with partial failure."""
        logs = [
            LogEntry(
                timestamp="2024-01-01T00:00:00Z",
                level="error",
                environment="dev",
                application="app1",
                message="Error 1",
            ),
        ]
        mock_response = {
            "success": True,
            "message": "Some logs failed validation",
            "processed": 1,
            "failed": 1,
            "errors": [{"index": 0, "error": "Invalid log level", "log": {}}],
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.post.return_value = mock_response

        result = await logs_api.send_batch_logs(logs)

        assert isinstance(result, BatchLogResponse)
        assert result.success is True
        assert result.processed == 1
        assert result.failed == 1
        assert result.errors is not None
        assert len(result.errors) == 1

    @pytest.mark.asyncio
    async def test_send_log_error(self, logs_api, mock_http_client, general_log_data):
        """Test send log error handling."""
        log_request = LogRequest(type="general", data=general_log_data)
        mock_http_client.post.side_effect = MisoClientError("Failed to send log")

        with pytest.raises(MisoClientError):
            await logs_api.send_log(log_request)

    @pytest.mark.asyncio
    async def test_send_batch_logs_error(self, logs_api, mock_http_client):
        """Test send batch logs error handling."""
        logs = [
            LogEntry(
                timestamp="2024-01-01T00:00:00Z",
                level="error",
                environment="dev",
                application="app1",
                message="Error 1",
            ),
        ]
        mock_http_client.post.side_effect = MisoClientError("Failed to send batch logs")

        with pytest.raises(MisoClientError):
            await logs_api.send_batch_logs(logs)
