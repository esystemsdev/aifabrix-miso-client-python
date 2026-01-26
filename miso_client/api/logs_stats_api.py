"""
Log Statistics and Export API implementation.

Provides typed interfaces for log statistics and export endpoints:
- GET /api/v1/logs/stats/summary
- GET /api/v1/logs/stats/errors
- GET /api/v1/logs/stats/users
- GET /api/v1/logs/stats/applications
- GET /api/v1/logs/export
"""

from typing import Any, Dict, Literal, Optional

from ..models.config import AuthStrategy
from ..utils.http_client import HttpClient
from .response_utils import normalize_api_response
from .types.logs_types import (
    LogExportResponse,
    LogStatsApplicationsResponse,
    LogStatsErrorsResponse,
    LogStatsSummaryResponse,
    LogStatsUsersResponse,
)


class LogsStatsApi:
    """Log Statistics and Export API client."""

    # Endpoint constants
    LOGS_STATS_SUMMARY_ENDPOINT = "/api/v1/logs/stats/summary"
    LOGS_STATS_ERRORS_ENDPOINT = "/api/v1/logs/stats/errors"
    LOGS_STATS_USERS_ENDPOINT = "/api/v1/logs/stats/users"
    LOGS_STATS_APPLICATIONS_ENDPOINT = "/api/v1/logs/stats/applications"
    LOGS_EXPORT_ENDPOINT = "/api/v1/logs/export"

    def __init__(self, http_client: HttpClient):
        """
        Initialize Log Statistics API client.

        Args:
            http_client: HttpClient instance
        """
        self.http_client = http_client

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
