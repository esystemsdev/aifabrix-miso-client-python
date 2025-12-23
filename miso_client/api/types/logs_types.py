"""
Logs API request and response types.

All types follow OpenAPI specification with camelCase field names.
"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from ...models.config import LogEntry


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
    message: str = Field(..., description="Response message")
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
