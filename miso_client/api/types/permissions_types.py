"""
Permissions API request and response types.

All types follow OpenAPI specification with camelCase field names.
"""

from typing import List

from pydantic import BaseModel, Field


class GetPermissionsResponse(BaseModel):
    """Get permissions response."""

    success: bool = Field(..., description="Whether request was successful")
    data: "GetPermissionsResponseData" = Field(..., description="Permissions data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class GetPermissionsResponseData(BaseModel):
    """Get permissions response data."""

    permissions: List[str] = Field(..., description="List of user permissions")


class RefreshPermissionsResponse(BaseModel):
    """Refresh permissions response."""

    success: bool = Field(..., description="Whether request was successful")
    data: GetPermissionsResponseData = Field(..., description="Permissions data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")
