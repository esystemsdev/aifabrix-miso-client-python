"""
Logs API implementation.

Provides typed interfaces for logging endpoints including:
- Log ingestion (POST /api/v1/logs, POST /api/v1/logs/batch)
- Log listing (GET /api/v1/logs/general, /api/v1/logs/audit, /api/v1/logs/jobs)
- Log statistics (GET /api/v1/logs/stats/*)
- Log export (GET /api/v1/logs/export)
"""

from typing import Any, Dict, List, Literal, Optional

from ..models.config import AuthStrategy, LogEntry
from ..utils.http_client import HttpClient
from .response_utils import normalize_api_response
from .types.logs_types import (
    BatchLogRequest,
    BatchLogResponse,
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


class LogsApi:
    """Logs API client for logging endpoints."""

    # Endpoint constants
    LOGS_ENDPOINT = "/api/v1/logs"
    LOGS_BATCH_ENDPOINT = "/api/v1/logs/batch"
    LOGS_GENERAL_ENDPOINT = "/api/v1/logs/general"
    LOGS_AUDIT_ENDPOINT = "/api/v1/logs/audit"
    LOGS_JOBS_ENDPOINT = "/api/v1/logs/jobs"
    LOGS_STATS_SUMMARY_ENDPOINT = "/api/v1/logs/stats/summary"
    LOGS_STATS_ERRORS_ENDPOINT = "/api/v1/logs/stats/errors"
    LOGS_STATS_USERS_ENDPOINT = "/api/v1/logs/stats/users"
    LOGS_STATS_APPLICATIONS_ENDPOINT = "/api/v1/logs/stats/applications"
    LOGS_EXPORT_ENDPOINT = "/api/v1/logs/export"

    def __init__(self, http_client: HttpClient):
        """
        Initialize Logs API client.

        Args:
            http_client: HttpClient instance
        """
        self.http_client = http_client

    # =========================================================================
    # Log Ingestion Endpoints
    # =========================================================================

    async def send_log(self, log_entry: LogRequest, token: Optional[str] = None) -> LogResponse:
        """
        Send log entry (POST /api/v1/logs).

        Supports Bearer token, x-client-token, or client credentials authentication.
        If token is provided, uses authenticated_request. Otherwise uses client credentials.

        Args:
            log_entry: LogRequest with type and data
            token: Optional user token (if not provided, uses x-client-token/client credentials)

        Returns:
            LogResponse with success status

        Raises:
            MisoClientError: If request fails
        """
        if token:
            response = await self.http_client.authenticated_request(
                "POST",
                self.LOGS_ENDPOINT,
                token,
                data=log_entry.model_dump(exclude_none=True),
            )
        else:
            response = await self.http_client.post(
                self.LOGS_ENDPOINT, data=log_entry.model_dump(exclude_none=True)
            )
        response = normalize_api_response(response)
        return LogResponse(**response)

    async def send_batch_logs(
        self, logs: List[LogEntry], token: Optional[str] = None
    ) -> BatchLogResponse:
        """
        Send multiple log entries in batch (POST /api/v1/logs/batch).

        Supports Bearer token, x-client-token, or client credentials authentication.
        If token is provided, uses authenticated_request. Otherwise uses client credentials.

        Args:
            logs: List of LogEntry objects
            token: Optional user token (if not provided, uses x-client-token/client credentials)

        Returns:
            BatchLogResponse with processing results

        Raises:
            MisoClientError: If request fails
        """
        request_data = BatchLogRequest(logs=logs)
        if token:
            response = await self.http_client.authenticated_request(
                "POST",
                self.LOGS_BATCH_ENDPOINT,
                token,
                data=request_data.model_dump(exclude_none=True),
            )
        else:
            response = await self.http_client.post(
                self.LOGS_BATCH_ENDPOINT, data=request_data.model_dump(exclude_none=True)
            )
        response = normalize_api_response(response)
        return BatchLogResponse(**response)

    # =========================================================================
    # Log Listing Endpoints
    # =========================================================================

    async def list_general_logs(
        self,
        token: str,
        page: int = 1,
        page_size: int = 10,
        sort: Optional[str] = None,
        level: Optional[Literal["error", "warn", "info", "debug"]] = None,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application: Optional[str] = None,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> ListGeneralLogsResponse:
        """
        List general logs (GET /api/v1/logs/general).

        Args:
            token: User authentication token
            page: Page number (1-based, default 1)
            page_size: Number of items per page (default 10, max 100)
            sort: Sort field with optional direction prefix (e.g., '-timestamp')
            level: Filter by log level
            environment: Filter by environment
            application: Filter by application name
            user_id: Filter by user ID
            correlation_id: Filter by correlation ID
            start_date: Filter from date (ISO 8601)
            end_date: Filter until date (ISO 8601)
            search: Search term for message/context
            auth_strategy: Optional authentication strategy

        Returns:
            ListGeneralLogsResponse with paginated log entries

        Raises:
            MisoClientError: If request fails
        """
        params = self._build_list_params(
            page=page,
            page_size=page_size,
            sort=sort,
            level=level,
            environment=environment,
            application=application,
            user_id=user_id,
            correlation_id=correlation_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )
        response = await self.http_client.authenticated_request(
            "GET",
            self.LOGS_GENERAL_ENDPOINT,
            token,
            params=params,
            auth_strategy=auth_strategy,
        )
        response = normalize_api_response(response)
        return ListGeneralLogsResponse(**response)

    async def list_audit_logs(
        self,
        token: str,
        page: int = 1,
        page_size: int = 10,
        sort: Optional[str] = None,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application: Optional[str] = None,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> ListAuditLogsResponse:
        """
        List audit logs (GET /api/v1/logs/audit).

        Args:
            token: User authentication token
            page: Page number (1-based, default 1)
            page_size: Number of items per page (default 10, max 100)
            sort: Sort field with optional direction prefix (e.g., '-timestamp')
            environment: Filter by environment
            application: Filter by application name
            user_id: Filter by user ID
            correlation_id: Filter by correlation ID
            start_date: Filter from date (ISO 8601)
            end_date: Filter until date (ISO 8601)
            entity_type: Filter by entity type (e.g., User, Group)
            entity_id: Filter by entity ID
            action: Filter by action (e.g., CREATE, UPDATE, DELETE)
            auth_strategy: Optional authentication strategy

        Returns:
            ListAuditLogsResponse with paginated audit entries

        Raises:
            MisoClientError: If request fails
        """
        params = self._build_list_params(
            page=page,
            page_size=page_size,
            sort=sort,
            environment=environment,
            application=application,
            user_id=user_id,
            correlation_id=correlation_id,
            start_date=start_date,
            end_date=end_date,
        )
        if entity_type:
            params["entityType"] = entity_type
        if entity_id:
            params["entityId"] = entity_id
        if action:
            params["action"] = action

        response = await self.http_client.authenticated_request(
            "GET",
            self.LOGS_AUDIT_ENDPOINT,
            token,
            params=params,
            auth_strategy=auth_strategy,
        )
        response = normalize_api_response(response)
        return ListAuditLogsResponse(**response)

    async def list_job_logs(
        self,
        token: str,
        page: int = 1,
        page_size: int = 10,
        sort: Optional[str] = None,
        job_id: Optional[str] = None,
        level: Optional[Literal["debug", "info", "warn", "error"]] = None,
        correlation_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> ListJobLogsResponse:
        """
        List job logs (GET /api/v1/logs/jobs).

        Args:
            token: User authentication token
            page: Page number (1-based, default 1)
            page_size: Number of items per page (default 10, max 100)
            sort: Sort field with optional direction prefix (e.g., '-timestamp')
            job_id: Filter by job ID
            level: Filter by log level
            correlation_id: Filter by correlation ID
            start_date: Filter from date (ISO 8601)
            end_date: Filter until date (ISO 8601)
            search: Search term for message/jobId
            auth_strategy: Optional authentication strategy

        Returns:
            ListJobLogsResponse with paginated job log entries

        Raises:
            MisoClientError: If request fails
        """
        params: Dict[str, Any] = {
            "page": page,
            "pageSize": page_size,
        }
        if sort:
            params["sort"] = sort
        if job_id:
            params["jobId"] = job_id
        if level:
            params["level"] = level
        if correlation_id:
            params["correlationId"] = correlation_id
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if search:
            params["search"] = search

        response = await self.http_client.authenticated_request(
            "GET",
            self.LOGS_JOBS_ENDPOINT,
            token,
            params=params,
            auth_strategy=auth_strategy,
        )
        response = normalize_api_response(response)
        return ListJobLogsResponse(**response)

    async def get_job_log(
        self,
        token: str,
        log_id: str,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> GetJobLogResponse:
        """
        Get job log by ID (GET /api/v1/logs/jobs/{id}).

        Args:
            token: User authentication token
            log_id: Job log entry ID
            auth_strategy: Optional authentication strategy

        Returns:
            GetJobLogResponse with job log entry

        Raises:
            MisoClientError: If request fails
        """
        response = await self.http_client.authenticated_request(
            "GET",
            f"{self.LOGS_JOBS_ENDPOINT}/{log_id}",
            token,
            auth_strategy=auth_strategy,
        )
        response = normalize_api_response(response)
        return GetJobLogResponse(**response)

    # =========================================================================
    # Log Statistics Endpoints
    # =========================================================================

    async def get_stats_summary(
        self,
        token: str,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogStatsSummaryResponse:
        """
        Get log statistics summary (GET /api/v1/logs/stats/summary).

        Args:
            token: User authentication token
            environment: Filter by environment
            application: Filter by application
            user_id: Filter by user ID
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            auth_strategy: Optional authentication strategy

        Returns:
            LogStatsSummaryResponse with aggregated statistics

        Raises:
            MisoClientError: If request fails
        """
        params = self._build_stats_params(
            environment=environment,
            application=application,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        response = await self.http_client.authenticated_request(
            "GET",
            self.LOGS_STATS_SUMMARY_ENDPOINT,
            token,
            params=params,
            auth_strategy=auth_strategy,
        )
        response = normalize_api_response(response)
        return LogStatsSummaryResponse(**response)

    async def get_stats_errors(
        self,
        token: str,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogStatsErrorsResponse:
        """
        Get error statistics (GET /api/v1/logs/stats/errors).

        Args:
            token: User authentication token
            environment: Filter by environment
            application: Filter by application
            user_id: Filter by user ID
            limit: Number of top errors to return (default 10, max 100)
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            auth_strategy: Optional authentication strategy

        Returns:
            LogStatsErrorsResponse with error statistics

        Raises:
            MisoClientError: If request fails
        """
        params = self._build_stats_params(
            environment=environment,
            application=application,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        response = await self.http_client.authenticated_request(
            "GET",
            self.LOGS_STATS_ERRORS_ENDPOINT,
            token,
            params=params,
            auth_strategy=auth_strategy,
        )
        response = normalize_api_response(response)
        return LogStatsErrorsResponse(**response)

    async def get_stats_users(
        self,
        token: str,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application: Optional[str] = None,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogStatsUsersResponse:
        """
        Get user activity statistics (GET /api/v1/logs/stats/users).

        Args:
            token: User authentication token
            environment: Filter by environment
            application: Filter by application
            limit: Number of top users to return (default 10, max 100)
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            auth_strategy: Optional authentication strategy

        Returns:
            LogStatsUsersResponse with user activity statistics

        Raises:
            MisoClientError: If request fails
        """
        params = self._build_stats_params(
            environment=environment,
            application=application,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        response = await self.http_client.authenticated_request(
            "GET",
            self.LOGS_STATS_USERS_ENDPOINT,
            token,
            params=params,
            auth_strategy=auth_strategy,
        )
        response = normalize_api_response(response)
        return LogStatsUsersResponse(**response)

    async def get_stats_applications(
        self,
        token: str,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogStatsApplicationsResponse:
        """
        Get application statistics (GET /api/v1/logs/stats/applications).

        Args:
            token: User authentication token
            environment: Filter by environment
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            auth_strategy: Optional authentication strategy

        Returns:
            LogStatsApplicationsResponse with application statistics

        Raises:
            MisoClientError: If request fails
        """
        params = self._build_stats_params(
            environment=environment,
            start_date=start_date,
            end_date=end_date,
        )
        response = await self.http_client.authenticated_request(
            "GET",
            self.LOGS_STATS_APPLICATIONS_ENDPOINT,
            token,
            params=params,
            auth_strategy=auth_strategy,
        )
        response = normalize_api_response(response)
        return LogStatsApplicationsResponse(**response)

    # =========================================================================
    # Log Export Endpoint
    # =========================================================================

    async def export_logs(
        self,
        token: str,
        log_type: Literal["general", "audit", "jobs"],
        format: Literal["csv", "json"],
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogExportResponse:
        """
        Export logs (GET /api/v1/logs/export).

        Note: CSV format returns raw text, JSON format returns LogExportResponse.

        Args:
            token: User authentication token
            log_type: Type of logs to export (general, audit, jobs)
            format: Export format (csv, json)
            environment: Filter by environment
            application: Filter by application
            user_id: Filter by user ID
            start_date: Start date (ISO 8601)
            end_date: End date (ISO 8601)
            limit: Maximum entries to export (default 1000, max 10000)
            auth_strategy: Optional authentication strategy

        Returns:
            LogExportResponse with exported data (JSON format only)

        Raises:
            MisoClientError: If request fails
        """
        params: Dict[str, Any] = {
            "type": log_type,
            "format": format,
        }
        if environment:
            params["environment"] = environment
        if application:
            params["application"] = application
        if user_id:
            params["userId"] = user_id
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if limit:
            params["limit"] = limit

        response = await self.http_client.authenticated_request(
            "GET",
            self.LOGS_EXPORT_ENDPOINT,
            token,
            params=params,
            auth_strategy=auth_strategy,
        )
        response = normalize_api_response(response)
        return LogExportResponse(**response)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_list_params(
        self,
        page: int = 1,
        page_size: int = 10,
        sort: Optional[str] = None,
        level: Optional[str] = None,
        environment: Optional[str] = None,
        application: Optional[str] = None,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build query parameters for list endpoints."""
        params: Dict[str, Any] = {
            "page": page,
            "pageSize": page_size,
        }
        if sort:
            params["sort"] = sort
        if level:
            params["level"] = level
        if environment:
            params["environment"] = environment
        if application:
            params["application"] = application
        if user_id:
            params["userId"] = user_id
        if correlation_id:
            params["correlationId"] = correlation_id
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if search:
            params["search"] = search
        return params

    def _build_stats_params(
        self,
        environment: Optional[str] = None,
        application: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build query parameters for stats endpoints."""
        params: Dict[str, Any] = {}
        if environment:
            params["environment"] = environment
        if application:
            params["application"] = application
        if user_id:
            params["userId"] = user_id
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if limit:
            params["limit"] = limit
        return params
