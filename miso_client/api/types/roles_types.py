"""
Roles API request and response types.

All types follow OpenAPI specification with camelCase field names.
"""

from typing import List

from pydantic import BaseModel, Field


class GetRolesResponse(BaseModel):
    """Get roles response."""

    success: bool = Field(..., description="Whether request was successful")
    data: "GetRolesResponseData" = Field(..., description="Roles data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")


class GetRolesResponseData(BaseModel):
    """Get roles response data."""

    roles: List[str] = Field(..., description="List of user roles")


class RefreshRolesResponse(BaseModel):
    """Refresh roles response."""

    success: bool = Field(..., description="Whether request was successful")
    data: GetRolesResponseData = Field(..., description="Roles data")
    timestamp: str = Field(..., description="Response timestamp (ISO 8601)")
