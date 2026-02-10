"""Applications API request and response types.

All types follow OpenAPI specification with camelCase field names.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    """Allowed values for application status (update and response).

    API expects one of: healthy | degraded | deploying | error | maintenance.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DEPLOYING = "deploying"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class UpdateSelfStatusRequest(BaseModel):
    """Request body for POST /api/v1/environments/{envKey}/applications/self/status.

    All fields optional; at least one typically sent when updating status.
    """

    status: Optional[ApplicationStatus] = Field(
        default=None,
        description="Application status (healthy, degraded, deploying, error, maintenance)",
    )
    url: Optional[str] = Field(default=None, description="Application public URL")
    internalUrl: Optional[str] = Field(default=None, description="Application internal URL")
    port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="Application port (1-65535)",
    )


class ApplicationStatusResponse(BaseModel):
    """Application status response (without configuration)."""

    id: Optional[str] = Field(default=None, description="Application ID")
    key: Optional[str] = Field(default=None, description="Application key")
    displayName: Optional[str] = Field(default=None, description="Display name")
    url: Optional[str] = Field(default=None, description="Application public URL")
    internalUrl: Optional[str] = Field(default=None, description="Application internal URL")
    port: Optional[int] = Field(default=None, description="Application port")
    status: Optional[str] = Field(default=None, description="Application status")
    runtimeStatus: Optional[str] = Field(default=None, description="Runtime status")
    environmentId: Optional[str] = Field(default=None, description="Environment ID")
    createdAt: Optional[str] = Field(default=None, description="Creation timestamp (ISO 8601)")
    updatedAt: Optional[str] = Field(default=None, description="Update timestamp (ISO 8601)")


class UpdateSelfStatusResponse(BaseModel):
    """Response for POST /api/v1/environments/{envKey}/applications/self/status."""

    success: Optional[bool] = Field(default=None, description="Whether update was successful")
    application: Optional[ApplicationStatusResponse] = Field(
        default=None, description="Updated application data"
    )
    message: Optional[str] = Field(default=None, description="Response message")
