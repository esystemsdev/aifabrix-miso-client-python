"""
Logs API request and response types.

All types follow OpenAPI specification with camelCase field names.
"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from ...models.config import LogEntry
from ...models.pagination import Meta


class ForeignKeyReference(BaseModel):
    """Foreign key reference for application/user IDs."""

    id: str = Field(..., description="Entity ID")
    key: Optional[str] = Field(default=None, description="Entity key")
    displayName: Optional[str] = Field(default=None, description="Display name")


class PaginationLinks(BaseModel):
    """Pagination links for navigating pages."""

    first: Optional[str] = Field(default=None, description="First page URL")
    prev: Optional[str] = Field(default=None, description="Previous page URL")
    next: Optional[str] = Field(default=None, description="Next page URL")
    last: Optional[str] = Field(default=None, description="Last page URL")


class GeneralLogData(BaseModel):
    """General log data structure."""

    level: Literal["error", "warn", "info", "debug"] = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")


class AuditLogData(BaseModel):
    """Audit log data structure."""

    entityType: str = Field(..., description="Entity type")
    entityId: str = Field(..., description="Entity ID")
    action: str = Field(..., description="Action performed")
    oldValues: Optional[Dict[str, Any]] = Field(default=None, description="Previous values")
    newValues: Optional[Dict[str, Any]] = Field(default=None, description="New values")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")


class LogRequest(BaseModel):
    """Log request with type and data."""

    type: Literal["error", "general", "audit"] = Field(..., description="Log entry type")
    data: Union[GeneralLogData, AuditLogData] = Field(..., description="Log data")


class BatchLogRequest(BaseModel):
    """Batch log request."""

    logs: List[LogEntry] = Field(..., description="List of log entries")


class LogResponse(BaseModel):
    """Log response."""

    success: bool = Field(..., description="Whether request was successful")
    message: Optional[str] = Field(default=None, description="Response message")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class BatchLogError(BaseModel):
    """Batch log error entry."""

    index: int = Field(..., description="Index of failed log entry")
    error: str = Field(..., description="Error message")
    log: Dict[str, Any] = Field(..., description="Failed log entry")


class BatchLogResponse(BaseModel):
    """Batch log response."""

    success: bool = Field(..., description="Whether request was successful")
    message: str = Field(..., description="Response message")
    processed: int = Field(..., description="Number of logs successfully processed")
    failed: int = Field(..., description="Number of logs that failed")
    errors: Optional[List[BatchLogError]] = Field(default=None, description="Error details")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


# ============================================================================
# Log List Types (GET /api/v1/logs/general, /api/v1/logs/audit, /api/v1/logs/jobs)
# ============================================================================


class GeneralLogEntry(BaseModel):
    """General log entry from list endpoint."""

    timestamp: str = Field(..., description="Log entry timestamp (ISO 8601)")
    level: Literal["error", "warn", "info", "debug"] = Field(..., description="Log level")
    environment: str = Field(..., description="Environment where log originated")
    application: str = Field(..., description="Application name")
    applicationId: Optional[ForeignKeyReference] = Field(
        default=None, description="Application reference"
    )
    userId: Optional[ForeignKeyReference] = Field(default=None, description="User reference")
    message: str = Field(..., description="Log message")
    stackTrace: Optional[str] = Field(default=None, description="Stack trace for errors")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")
    ipAddress: Optional[str] = Field(default=None, description="Client IP address")
    userAgent: Optional[str] = Field(default=None, description="User agent string")
    hostname: Optional[str] = Field(default=None, description="Client hostname")
    requestId: Optional[str] = Field(default=None, description="Request tracking ID")
    sessionId: Optional[str] = Field(default=None, description="Session identifier")


class AuditLogEntry(BaseModel):
    """Audit log entry from list endpoint."""

    timestamp: str = Field(..., description="Audit log timestamp (ISO 8601)")
    environment: str = Field(..., description="Environment where action occurred")
    application: str = Field(..., description="Application name")
    applicationId: Optional[ForeignKeyReference] = Field(
        default=None, description="Application reference"
    )
    userId: Optional[ForeignKeyReference] = Field(default=None, description="User reference")
    entityType: str = Field(..., description="Type of entity modified")
    entityId: str = Field(..., description="ID of the entity modified")
    action: str = Field(..., description="Action performed (CREATE, UPDATE, DELETE)")
    oldValues: Optional[Dict[str, Any]] = Field(default=None, description="Previous values")
    newValues: Optional[Dict[str, Any]] = Field(default=None, description="New values")
    ipAddress: Optional[str] = Field(default=None, description="Client IP address")
    userAgent: Optional[str] = Field(default=None, description="User agent string")
    hostname: Optional[str] = Field(default=None, description="Client hostname")
    requestId: Optional[str] = Field(default=None, description="Request tracking ID")
    sessionId: Optional[str] = Field(default=None, description="Session identifier")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")


class JobLogEntry(BaseModel):
    """Job log entry from list endpoint."""

    id: str = Field(..., description="Job log entry ID")
    jobId: str = Field(..., description="Job ID")
    timestamp: str = Field(..., description="Log entry timestamp (ISO 8601)")
    level: Literal["debug", "info", "warn", "error"] = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional job details")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")


class ListGeneralLogsResponse(BaseModel):
    """Response for GET /api/v1/logs/general."""

    data: List[GeneralLogEntry] = Field(..., description="List of general log entries")
    meta: Meta = Field(..., description="Pagination metadata")
    links: PaginationLinks = Field(..., description="Pagination links")


class ListAuditLogsResponse(BaseModel):
    """Response for GET /api/v1/logs/audit."""

    data: List[AuditLogEntry] = Field(..., description="List of audit log entries")
    meta: Meta = Field(..., description="Pagination metadata")
    links: PaginationLinks = Field(..., description="Pagination links")


class ListJobLogsResponse(BaseModel):
    """Response for GET /api/v1/logs/jobs."""

    data: List[JobLogEntry] = Field(..., description="List of job log entries")
    meta: Meta = Field(..., description="Pagination metadata")
    links: PaginationLinks = Field(..., description="Pagination links")


class GetJobLogResponse(BaseModel):
    """Response for GET /api/v1/logs/jobs/{id}."""

    success: bool = Field(..., description="Whether request was successful")
    data: JobLogEntry = Field(..., description="Job log entry")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


# ============================================================================
# Log Statistics Types (GET /api/v1/logs/stats/*)
# ============================================================================


class LogStatsSummaryData(BaseModel):
    """Data for log statistics summary."""

    totalLogs: int = Field(..., description="Total number of logs")
    byLevel: Dict[str, int] = Field(..., description="Log counts by level")
    byApplication: Dict[str, int] = Field(..., description="Log counts by application")
    environment: str = Field(..., description="Environment")


class LogStatsSummaryResponse(BaseModel):
    """Response for GET /api/v1/logs/stats/summary."""

    success: bool = Field(..., description="Whether request was successful")
    data: LogStatsSummaryData = Field(..., description="Statistics data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class TopError(BaseModel):
    """Top error entry."""

    message: str = Field(..., description="Error message")
    count: int = Field(..., description="Error count")


class LogStatsErrorsData(BaseModel):
    """Data for error statistics."""

    totalErrors: int = Field(..., description="Total number of errors")
    topErrors: List[TopError] = Field(..., description="Top error messages")
    environment: str = Field(..., description="Environment")


class LogStatsErrorsResponse(BaseModel):
    """Response for GET /api/v1/logs/stats/errors."""

    success: bool = Field(..., description="Whether request was successful")
    data: LogStatsErrorsData = Field(..., description="Error statistics data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class TopUser(BaseModel):
    """Top user entry."""

    userId: str = Field(..., description="User ID")
    actionCount: int = Field(..., description="Action count")


class LogStatsUsersData(BaseModel):
    """Data for user activity statistics."""

    totalUsers: int = Field(..., description="Total number of users")
    topUsers: List[TopUser] = Field(..., description="Top users by action count")
    byAction: Dict[str, int] = Field(..., description="Counts by action type")
    environment: str = Field(..., description="Environment")


class LogStatsUsersResponse(BaseModel):
    """Response for GET /api/v1/logs/stats/users."""

    success: bool = Field(..., description="Whether request was successful")
    data: LogStatsUsersData = Field(..., description="User statistics data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class ApplicationStats(BaseModel):
    """Application statistics entry."""

    application: str = Field(..., description="Application name")
    logCount: int = Field(..., description="Log count")


class LogStatsApplicationsData(BaseModel):
    """Data for application statistics."""

    totalApplications: int = Field(..., description="Total number of applications")
    applications: List[ApplicationStats] = Field(..., description="Applications by log count")
    environment: str = Field(..., description="Environment")


class LogStatsApplicationsResponse(BaseModel):
    """Response for GET /api/v1/logs/stats/applications."""

    success: bool = Field(..., description="Whether request was successful")
    data: LogStatsApplicationsData = Field(..., description="Application statistics data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


# ============================================================================
# Log Export Types (GET /api/v1/logs/export)
# ============================================================================


class LogExportMeta(BaseModel):
    """Metadata for log export."""

    type: str = Field(..., description="Log type (general, audit, jobs)")
    environment: str = Field(..., description="Environment")
    exportedAt: str = Field(..., description="Export timestamp (ISO 8601)")
    count: int = Field(..., description="Number of exported entries")


class LogExportResponse(BaseModel):
    """Response for GET /api/v1/logs/export (JSON format)."""

    success: bool = Field(..., description="Whether request was successful")
    data: List[Dict[str, Any]] = Field(..., description="Exported log entries")
    meta: LogExportMeta = Field(..., description="Export metadata")
