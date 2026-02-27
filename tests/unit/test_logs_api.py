"""
Unit tests for LogsApi.

Tests all logging API endpoints with proper mocking.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from miso_client.api.logs_api import LogsApi
from miso_client.api.types.logs_types import (
    AuditLogData,
    BatchLogResponse,
    GeneralLogData,
    GetJobLogResponse,
    ListAuditLogsResponse,
    ListGeneralLogsResponse,
    ListJobLogsResponse,
    LogExportResponse,
    LogRequest,
    LogResponse,
    LogStatsApplicationsResponse,
    LogStatsErrorsResponse,
    LogStatsSummaryResponse,
    LogStatsUsersResponse,
)
from miso_client.errors import MisoClientError
from miso_client.models.config import AuthStrategy, LogEntry, MisoClientConfig
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
    async def test_send_log_accepts_minimal_data_null_response(
        self, logs_api, mock_http_client, general_log_data
    ):
        """Test send log accepts minimal response with null data."""
        log_request = LogRequest(type="general", data=general_log_data)
        mock_http_client.post.return_value = {"data": None}

        result = await logs_api.send_log(log_request)

        assert isinstance(result, LogResponse)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_batch_logs_accepts_minimal_nested_processed_failed(
        self, logs_api, mock_http_client
    ):
        """Test batch logs accepts minimal response with processed/failed in data."""
        logs = [
            LogEntry(
                timestamp="2024-01-01T00:00:00Z",
                level="error",
                environment="dev",
                application="app1",
                message="Error 1",
            ),
        ]
        mock_http_client.post.return_value = {"data": {"processed": 1, "failed": 0}}

        result = await logs_api.send_batch_logs(logs)

        assert isinstance(result, BatchLogResponse)
        assert result.success is True
        assert result.processed == 1
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_send_batch_logs_accepts_minimal_top_level_processed_failed(
        self, logs_api, mock_http_client
    ):
        """Test batch logs accepts minimal response with top-level processed/failed."""
        logs = [
            LogEntry(
                timestamp="2024-01-01T00:00:00Z",
                level="error",
                environment="dev",
                application="app1",
                message="Error 1",
            ),
        ]
        mock_http_client.post.return_value = {"processed": 1, "failed": 0}

        result = await logs_api.send_batch_logs(logs)

        assert isinstance(result, BatchLogResponse)
        assert result.success is True
        assert result.processed == 1
        assert result.failed == 0

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

    # =========================================================================
    # Log Listing Endpoints Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_general_logs_basic(self, logs_api, mock_http_client):
        """Test list general logs with basic parameters."""
        mock_response = {
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "level": "error",
                    "environment": "dev",
                    "application": "app1",
                    "message": "Test error",
                    "correlationId": "corr-123",
                }
            ],
            "meta": {
                "currentPage": 1,
                "pageSize": 10,
                "totalItems": 1,
                "totalPages": 1,
                "type": "generalLog",
            },
            "links": {
                "first": None,
                "prev": None,
                "next": None,
                "last": None,
            },
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.list_general_logs("test-token")

        assert isinstance(result, ListGeneralLogsResponse)
        assert len(result.data) == 1
        assert result.data[0].level == "error"
        assert result.data[0].message == "Test error"
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == logs_api.LOGS_GENERAL_ENDPOINT
        assert call_args[0][2] == "test-token"

    @pytest.mark.asyncio
    async def test_list_general_logs_with_filters(self, logs_api, mock_http_client):
        """Test list general logs with all filter parameters."""
        mock_response = {
            "data": [],
            "meta": {
                "currentPage": 1,
                "pageSize": 25,
                "totalItems": 0,
                "totalPages": 0,
                "type": "generalLog",
            },
            "links": {"first": None, "prev": None, "next": None, "last": None},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["bearer"])
        result = await logs_api.list_general_logs(
            "test-token",
            page=2,
            page_size=25,
            sort="-timestamp",
            level="error",
            environment="pro",
            application="app1",
            user_id="user-123",
            correlation_id="corr-456",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            search="test query",
            auth_strategy=auth_strategy,
        )

        assert isinstance(result, ListGeneralLogsResponse)
        mock_http_client.authenticated_request.assert_called_once()
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        params = call_kwargs["params"]
        assert params["page"] == 2
        assert params["pageSize"] == 25
        assert params["sort"] == "-timestamp"
        assert params["level"] == "error"
        assert params["environment"] == "pro"
        assert params["application"] == "app1"
        assert params["userId"] == "user-123"
        assert params["correlationId"] == "corr-456"
        assert params["startDate"] == "2024-01-01T00:00:00Z"
        assert params["endDate"] == "2024-01-31T23:59:59Z"
        assert params["search"] == "test query"
        assert call_kwargs["auth_strategy"] == auth_strategy

    @pytest.mark.asyncio
    async def test_list_audit_logs_basic(self, logs_api, mock_http_client):
        """Test list audit logs with basic parameters."""
        mock_response = {
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "environment": "dev",
                    "application": "app1",
                    "entityType": "User",
                    "entityId": "user-123",
                    "action": "CREATE",
                    "correlationId": "corr-123",
                }
            ],
            "meta": {
                "currentPage": 1,
                "pageSize": 10,
                "totalItems": 1,
                "totalPages": 1,
                "type": "auditLog",
            },
            "links": {"first": None, "prev": None, "next": None, "last": None},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.list_audit_logs("test-token")

        assert isinstance(result, ListAuditLogsResponse)
        assert len(result.data) == 1
        assert result.data[0].entityType == "User"
        assert result.data[0].action == "CREATE"
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][1] == logs_api.LOGS_AUDIT_ENDPOINT

    @pytest.mark.asyncio
    async def test_list_audit_logs_with_filters(self, logs_api, mock_http_client):
        """Test list audit logs with all filter parameters."""
        mock_response = {
            "data": [],
            "meta": {
                "currentPage": 1,
                "pageSize": 25,
                "totalItems": 0,
                "totalPages": 0,
                "type": "auditLog",
            },
            "links": {"first": None, "prev": None, "next": None, "last": None},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["api-key"])
        result = await logs_api.list_audit_logs(
            "test-token",
            page=1,
            page_size=25,
            sort="timestamp",
            environment="tst",
            application="app2",
            user_id="user-456",
            correlation_id="corr-789",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            entity_type="Group",
            entity_id="group-123",
            action="UPDATE",
            auth_strategy=auth_strategy,
        )

        assert isinstance(result, ListAuditLogsResponse)
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        params = call_kwargs["params"]
        assert params["entityType"] == "Group"
        assert params["entityId"] == "group-123"
        assert params["action"] == "UPDATE"
        assert call_kwargs["auth_strategy"] == auth_strategy

    @pytest.mark.asyncio
    async def test_list_job_logs_basic(self, logs_api, mock_http_client):
        """Test list job logs with basic parameters."""
        mock_response = {
            "data": [
                {
                    "id": "log-123",
                    "jobId": "job-456",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "level": "info",
                    "message": "Job started",
                    "correlationId": "corr-123",
                }
            ],
            "meta": {
                "currentPage": 1,
                "pageSize": 10,
                "totalItems": 1,
                "totalPages": 1,
                "type": "jobLog",
            },
            "links": {"first": None, "prev": None, "next": None, "last": None},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.list_job_logs("test-token")

        assert isinstance(result, ListJobLogsResponse)
        assert len(result.data) == 1
        assert result.data[0].jobId == "job-456"
        assert result.data[0].level == "info"
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][1] == logs_api.LOGS_JOBS_ENDPOINT

    @pytest.mark.asyncio
    async def test_list_job_logs_with_filters(self, logs_api, mock_http_client):
        """Test list job logs with all filter parameters."""
        mock_response = {
            "data": [],
            "meta": {
                "currentPage": 1,
                "pageSize": 50,
                "totalItems": 0,
                "totalPages": 0,
                "type": "jobLog",
            },
            "links": {"first": None, "prev": None, "next": None, "last": None},
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["bearer"])
        result = await logs_api.list_job_logs(
            "test-token",
            page=1,
            page_size=50,
            sort="-timestamp",
            job_id="job-789",
            level="error",
            correlation_id="corr-999",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            search="failed",
            auth_strategy=auth_strategy,
        )

        assert isinstance(result, ListJobLogsResponse)
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        params = call_kwargs["params"]
        assert params["jobId"] == "job-789"
        assert params["level"] == "error"
        assert params["search"] == "failed"
        assert call_kwargs["auth_strategy"] == auth_strategy

    @pytest.mark.asyncio
    async def test_get_job_log(self, logs_api, mock_http_client):
        """Test get job log by ID."""
        mock_response = {
            "success": True,
            "data": {
                "id": "log-123",
                "jobId": "job-456",
                "timestamp": "2024-01-01T00:00:00Z",
                "level": "error",
                "message": "Job failed",
                "correlationId": "corr-123",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.get_job_log("test-token", "log-123")

        assert isinstance(result, GetJobLogResponse)
        assert result.success is True
        assert result.data.id == "log-123"
        assert result.data.jobId == "job-456"
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][1] == f"{logs_api.LOGS_JOBS_ENDPOINT}/log-123"

    @pytest.mark.asyncio
    async def test_get_job_log_with_auth_strategy(self, logs_api, mock_http_client):
        """Test get job log with auth strategy."""
        mock_response = {
            "success": True,
            "data": {
                "id": "log-123",
                "jobId": "job-456",
                "timestamp": "2024-01-01T00:00:00Z",
                "level": "info",
                "message": "Job completed",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["api-key"])
        result = await logs_api.get_job_log("test-token", "log-123", auth_strategy=auth_strategy)

        assert isinstance(result, GetJobLogResponse)
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        assert call_kwargs["auth_strategy"] == auth_strategy

    # =========================================================================
    # Log Statistics Endpoints Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_get_stats_summary_basic(self, logs_api, mock_http_client):
        """Test get stats summary with basic parameters."""
        mock_response = {
            "success": True,
            "data": {
                "totalLogs": 1000,
                "byLevel": {"error": 100, "warn": 200, "info": 600, "debug": 100},
                "byApplication": {"app1": 500, "app2": 500},
                "environment": "dev",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.get_stats_summary("test-token")

        assert isinstance(result, LogStatsSummaryResponse)
        assert result.success is True
        assert result.data.totalLogs == 1000
        assert result.data.byLevel["error"] == 100
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][1] == logs_api._stats.LOGS_STATS_SUMMARY_ENDPOINT

    @pytest.mark.asyncio
    async def test_get_stats_summary_with_filters(self, logs_api, mock_http_client):
        """Test get stats summary with all filter parameters."""
        mock_response = {
            "success": True,
            "data": {
                "totalLogs": 500,
                "byLevel": {"error": 50},
                "byApplication": {"app1": 500},
                "environment": "pro",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["bearer"])
        result = await logs_api.get_stats_summary(
            "test-token",
            environment="pro",
            application="app1",
            user_id="user-123",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            auth_strategy=auth_strategy,
        )

        assert isinstance(result, LogStatsSummaryResponse)
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        params = call_kwargs["params"]
        assert params["environment"] == "pro"
        assert params["application"] == "app1"
        assert params["userId"] == "user-123"
        assert call_kwargs["auth_strategy"] == auth_strategy

    @pytest.mark.asyncio
    async def test_get_stats_errors_basic(self, logs_api, mock_http_client):
        """Test get stats errors with basic parameters."""
        mock_response = {
            "success": True,
            "data": {
                "totalErrors": 50,
                "topErrors": [
                    {"message": "Database connection failed", "count": 20},
                    {"message": "Invalid input", "count": 30},
                ],
                "environment": "dev",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.get_stats_errors("test-token")

        assert isinstance(result, LogStatsErrorsResponse)
        assert result.success is True
        assert result.data.totalErrors == 50
        assert len(result.data.topErrors) == 2
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][1] == logs_api._stats.LOGS_STATS_ERRORS_ENDPOINT

    @pytest.mark.asyncio
    async def test_get_stats_errors_with_filters(self, logs_api, mock_http_client):
        """Test get stats errors with all filter parameters."""
        mock_response = {
            "success": True,
            "data": {
                "totalErrors": 25,
                "topErrors": [{"message": "Test error", "count": 25}],
                "environment": "tst",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["api-key"])
        result = await logs_api.get_stats_errors(
            "test-token",
            environment="tst",
            application="app1",
            user_id="user-123",
            limit=20,
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            auth_strategy=auth_strategy,
        )

        assert isinstance(result, LogStatsErrorsResponse)
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        params = call_kwargs["params"]
        assert params["limit"] == 20
        assert call_kwargs["auth_strategy"] == auth_strategy

    @pytest.mark.asyncio
    async def test_get_stats_users_basic(self, logs_api, mock_http_client):
        """Test get stats users with basic parameters."""
        mock_response = {
            "success": True,
            "data": {
                "totalUsers": 10,
                "topUsers": [
                    {"userId": "user-1", "actionCount": 100},
                    {"userId": "user-2", "actionCount": 50},
                ],
                "byAction": {"CREATE": 50, "UPDATE": 100},
                "environment": "dev",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.get_stats_users("test-token")

        assert isinstance(result, LogStatsUsersResponse)
        assert result.success is True
        assert result.data.totalUsers == 10
        assert len(result.data.topUsers) == 2
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][1] == logs_api._stats.LOGS_STATS_USERS_ENDPOINT

    @pytest.mark.asyncio
    async def test_get_stats_users_with_filters(self, logs_api, mock_http_client):
        """Test get stats users with all filter parameters."""
        mock_response = {
            "success": True,
            "data": {
                "totalUsers": 5,
                "topUsers": [{"userId": "user-1", "actionCount": 50}],
                "byAction": {"CREATE": 50},
                "environment": "pro",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["bearer"])
        result = await logs_api.get_stats_users(
            "test-token",
            environment="pro",
            application="app1",
            limit=15,
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            auth_strategy=auth_strategy,
        )

        assert isinstance(result, LogStatsUsersResponse)
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        params = call_kwargs["params"]
        assert params["limit"] == 15
        assert call_kwargs["auth_strategy"] == auth_strategy

    @pytest.mark.asyncio
    async def test_get_stats_applications_basic(self, logs_api, mock_http_client):
        """Test get stats applications with basic parameters."""
        mock_response = {
            "success": True,
            "data": {
                "totalApplications": 3,
                "applications": [
                    {"application": "app1", "logCount": 500},
                    {"application": "app2", "logCount": 300},
                    {"application": "app3", "logCount": 200},
                ],
                "environment": "dev",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.get_stats_applications("test-token")

        assert isinstance(result, LogStatsApplicationsResponse)
        assert result.success is True
        assert result.data.totalApplications == 3
        assert len(result.data.applications) == 3
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][1] == logs_api._stats.LOGS_STATS_APPLICATIONS_ENDPOINT

    @pytest.mark.asyncio
    async def test_get_stats_applications_with_filters(self, logs_api, mock_http_client):
        """Test get stats applications with filter parameters."""
        mock_response = {
            "success": True,
            "data": {
                "totalApplications": 2,
                "applications": [
                    {"application": "app1", "logCount": 400},
                    {"application": "app2", "logCount": 100},
                ],
                "environment": "tst",
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["api-key"])
        result = await logs_api.get_stats_applications(
            "test-token",
            environment="tst",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            auth_strategy=auth_strategy,
        )

        assert isinstance(result, LogStatsApplicationsResponse)
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        params = call_kwargs["params"]
        assert params["environment"] == "tst"
        assert call_kwargs["auth_strategy"] == auth_strategy

    # =========================================================================
    # Log Export Endpoint Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_export_logs_json(self, logs_api, mock_http_client):
        """Test export logs in JSON format."""
        mock_response = {
            "success": True,
            "data": [
                {
                    "timestamp": "2024-01-01T00:00:00Z",
                    "level": "error",
                    "message": "Test error",
                }
            ],
            "meta": {
                "type": "general",
                "environment": "dev",
                "exportedAt": "2024-01-01T00:00:00Z",
                "count": 1,
            },
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.export_logs("test-token", log_type="general", format="json")

        assert isinstance(result, LogExportResponse)
        assert result.success is True
        assert len(result.data) == 1
        assert result.meta.type == "general"
        mock_http_client.authenticated_request.assert_called_once()
        call_args = mock_http_client.authenticated_request.call_args
        assert call_args[0][1] == logs_api._stats.LOGS_EXPORT_ENDPOINT

    @pytest.mark.asyncio
    async def test_export_logs_csv(self, logs_api, mock_http_client):
        """Test export logs in CSV format."""
        mock_response = {
            "success": True,
            "data": [],
            "meta": {
                "type": "audit",
                "environment": "pro",
                "exportedAt": "2024-01-01T00:00:00Z",
                "count": 0,
            },
        }
        mock_http_client.authenticated_request.return_value = mock_response

        result = await logs_api.export_logs("test-token", log_type="audit", format="csv")

        assert isinstance(result, LogExportResponse)
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        params = call_kwargs["params"]
        assert params["type"] == "audit"
        assert params["format"] == "csv"

    @pytest.mark.asyncio
    async def test_export_logs_with_filters(self, logs_api, mock_http_client):
        """Test export logs with all filter parameters."""
        mock_response = {
            "success": True,
            "data": [],
            "meta": {
                "type": "jobs",
                "environment": "tst",
                "exportedAt": "2024-01-01T00:00:00Z",
                "count": 0,
            },
        }
        mock_http_client.authenticated_request.return_value = mock_response

        auth_strategy = AuthStrategy(methods=["bearer"])
        result = await logs_api.export_logs(
            "test-token",
            log_type="jobs",
            format="json",
            environment="tst",
            application="app1",
            user_id="user-123",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            limit=5000,
            auth_strategy=auth_strategy,
        )

        assert isinstance(result, LogExportResponse)
        call_kwargs = mock_http_client.authenticated_request.call_args[1]
        params = call_kwargs["params"]
        assert params["type"] == "jobs"
        assert params["format"] == "json"
        assert params["environment"] == "tst"
        assert params["application"] == "app1"
        assert params["userId"] == "user-123"
        assert params["limit"] == 5000
        assert call_kwargs["auth_strategy"] == auth_strategy

    # =========================================================================
    # Helper Methods Tests
    # =========================================================================

    def test_build_list_params_minimal(self, logs_api):
        """Test _build_list_params with minimal parameters."""
        params = logs_api._build_list_params()

        assert params["page"] == 1
        assert params["pageSize"] == 10
        assert "sort" not in params
        assert "level" not in params

    def test_build_list_params_all(self, logs_api):
        """Test _build_list_params with all parameters."""
        params = logs_api._build_list_params(
            page=2,
            page_size=25,
            sort="-timestamp",
            level="error",
            environment="pro",
            application="app1",
            user_id="user-123",
            correlation_id="corr-456",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            search="test query",
        )

        assert params["page"] == 2
        assert params["pageSize"] == 25
        assert params["sort"] == "-timestamp"
        assert params["level"] == "error"
        assert params["environment"] == "pro"
        assert params["application"] == "app1"
        assert params["userId"] == "user-123"
        assert params["correlationId"] == "corr-456"
        assert params["startDate"] == "2024-01-01T00:00:00Z"
        assert params["endDate"] == "2024-01-31T23:59:59Z"
        assert params["search"] == "test query"

    def test_build_list_params_optional_none(self, logs_api):
        """Test _build_list_params with None optional parameters."""
        params = logs_api._build_list_params(
            page=1,
            page_size=10,
            sort=None,
            level=None,
            environment=None,
            application=None,
            user_id=None,
            correlation_id=None,
            start_date=None,
            end_date=None,
            search=None,
        )

        assert params["page"] == 1
        assert params["pageSize"] == 10
        assert "sort" not in params
        assert "level" not in params
        assert "environment" not in params

    def test_build_stats_params_minimal(self, logs_api):
        """Test _build_stats_params with minimal parameters."""
        params = logs_api._stats._build_stats_params()

        assert len(params) == 0

    def test_build_stats_params_all(self, logs_api):
        """Test _build_stats_params with all parameters."""
        params = logs_api._stats._build_stats_params(
            environment="pro",
            application="app1",
            user_id="user-123",
            start_date="2024-01-01T00:00:00Z",
            end_date="2024-01-31T23:59:59Z",
            limit=20,
        )

        assert params["environment"] == "pro"
        assert params["application"] == "app1"
        assert params["userId"] == "user-123"
        assert params["startDate"] == "2024-01-01T00:00:00Z"
        assert params["endDate"] == "2024-01-31T23:59:59Z"
        assert params["limit"] == 20

    def test_build_stats_params_optional_none(self, logs_api):
        """Test _build_stats_params with None optional parameters."""
        params = logs_api._stats._build_stats_params(
            environment=None,
            application=None,
            user_id=None,
            start_date=None,
            end_date=None,
            limit=None,
        )

        assert len(params) == 0

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_list_general_logs_error(self, logs_api, mock_http_client):
        """Test list general logs error handling."""
        mock_http_client.authenticated_request.side_effect = MisoClientError("Failed to list logs")

        with pytest.raises(MisoClientError):
            await logs_api.list_general_logs("test-token")

    @pytest.mark.asyncio
    async def test_list_general_logs_rejects_minimal_log_create_shape(self, logs_api, mock_http_client):
        """Test non-logs-create endpoint still rejects minimal log-create shape."""
        mock_http_client.authenticated_request.return_value = {"processed": 1, "failed": 0}

        with pytest.raises(ValidationError):
            await logs_api.list_general_logs("test-token")

    @pytest.mark.asyncio
    async def test_get_stats_summary_error(self, logs_api, mock_http_client):
        """Test get stats summary error handling."""
        mock_http_client.authenticated_request.side_effect = MisoClientError("Failed to get stats")

        with pytest.raises(MisoClientError):
            await logs_api.get_stats_summary("test-token")

    @pytest.mark.asyncio
    async def test_export_logs_error(self, logs_api, mock_http_client):
        """Test export logs error handling."""
        mock_http_client.authenticated_request.side_effect = MisoClientError(
            "Failed to export logs"
        )

        with pytest.raises(MisoClientError):
            await logs_api.export_logs("test-token", log_type="general", format="json")
