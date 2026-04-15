"""Stats/export delegation mixin for LogsApi."""

from typing import TYPE_CHECKING, Literal, Optional

from ..models.config import AuthStrategy
from .types.logs_types import (
    LogExportResponse,
    LogStatsApplicationsResponse,
    LogStatsErrorsResponse,
    LogStatsSummaryResponse,
    LogStatsUsersResponse,
)

if TYPE_CHECKING:
    from .logs_stats_api import LogsStatsApi


class LogsStatsDelegationMixin:
    """Mixin with stats/export wrappers delegated to LogsStatsApi."""

    _stats: "LogsStatsApi"

    async def get_stats_summary(
        self,
        token: str,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application_id: Optional[str] = None,
        source_id: Optional[str] = None,
        external_system_id: Optional[str] = None,
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogStatsSummaryResponse:
        """Get log statistics summary. See LogsStatsApi.get_stats_summary for details."""
        return await self._stats.get_stats_summary(
            token=token,
            environment=environment,
            application_id=application_id,
            source_id=source_id,
            external_system_id=external_system_id,
            record_id=record_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            auth_strategy=auth_strategy,
        )

    async def get_stats_errors(
        self,
        token: str,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application_id: Optional[str] = None,
        source_id: Optional[str] = None,
        external_system_id: Optional[str] = None,
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogStatsErrorsResponse:
        """Get error statistics. See LogsStatsApi.get_stats_errors for details."""
        return await self._stats.get_stats_errors(
            token=token,
            environment=environment,
            application_id=application_id,
            source_id=source_id,
            external_system_id=external_system_id,
            record_id=record_id,
            user_id=user_id,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            auth_strategy=auth_strategy,
        )

    async def get_stats_users(
        self,
        token: str,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application_id: Optional[str] = None,
        source_id: Optional[str] = None,
        external_system_id: Optional[str] = None,
        record_id: Optional[str] = None,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogStatsUsersResponse:
        """Get user activity statistics. See LogsStatsApi.get_stats_users for details."""
        return await self._stats.get_stats_users(
            token=token,
            environment=environment,
            application_id=application_id,
            source_id=source_id,
            external_system_id=external_system_id,
            record_id=record_id,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            auth_strategy=auth_strategy,
        )

    async def get_stats_applications(
        self,
        token: str,
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogStatsApplicationsResponse:
        """Get application statistics. See LogsStatsApi.get_stats_applications for details."""
        return await self._stats.get_stats_applications(
            token, environment, start_date, end_date, auth_strategy
        )

    async def export_logs(
        self,
        token: str,
        log_type: Literal["general", "audit", "jobs"],
        format: Literal["csv", "json"],
        environment: Optional[Literal["dev", "tst", "pro", "miso"]] = None,
        application_id: Optional[str] = None,
        source_id: Optional[str] = None,
        external_system_id: Optional[str] = None,
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
        auth_strategy: Optional[AuthStrategy] = None,
    ) -> LogExportResponse:
        """Export logs. See LogsStatsApi.export_logs for details."""
        return await self._stats.export_logs(
            token,
            log_type,
            format,
            environment,
            application_id,
            source_id,
            external_system_id,
            record_id,
            user_id,
            start_date,
            end_date,
            limit,
            auth_strategy,
        )
