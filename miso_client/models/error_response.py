"""
Structured error response model following RFC 7807-style format.

This module provides a generic error response interface that can be used
across different applications for consistent error handling.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Structured error response following RFC 7807-style format.

    This model represents a standardized error response structure that includes:
    - Multiple error messages
    - Error type identifier
    - Human-readable title
    - HTTP status code
    - Request instance URI (optional)

    Example:
        {
            "errors": ["Error message 1", "Error message 2"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "instance": "/OpenApi/rest/Xzy"
        }
    """

    errors: List[str] = Field(..., description="List of error messages")
    type: str = Field(..., description="Error type URI (e.g., '/Errors/Bad Input')")
    title: Optional[str] = Field(default=None, description="Human-readable error title")
    statusCode: int = Field(..., description="HTTP status code")
    instance: Optional[str] = Field(default=None, description="Request instance URI")
    correlationId: Optional[str] = Field(default=None, description="Request key for error tracking")
