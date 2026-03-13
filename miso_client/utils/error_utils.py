"""Error utilities for MisoClient SDK.

This module provides error transformation utilities for handling
camelCase error responses from the API.
"""

from typing import Optional

from ..errors import MisoClientError
from ..models.error_response import ErrorResponse


class ApiErrorException(Exception):
    """Exception class for camelCase error responses.

    Used with camelCase ErrorResponse format matching TypeScript SDK.
    """

    def __init__(self, error: ErrorResponse):
        """Initialize ApiErrorException.

        Args:
            error: ErrorResponse object with camelCase properties

        """
        super().__init__(error.title or "API Error")
        self.name = "ApiErrorException"
        self.statusCode = error.statusCode
        self.correlationId = error.correlationId
        self.type = error.type
        self.instance = error.instance
        self.errors = error.errors


def transformError(error_data: dict) -> ErrorResponse:
    """Transform arbitrary error into standardized camelCase ErrorResponse.

    Converts error data dictionary to ErrorResponse object with camelCase field names.

    Args:
        error_data: Dictionary with error data (must be camelCase)

    Returns:
        ErrorResponse object with standardized format

    Examples:
        >>> error_data = {
        ...     'errors': ['Error message'],
        ...     'type': '/Errors/Bad Input',
        ...     'title': 'Bad Request',
        ...     'statusCode': 400,
        ...     'instance': '/api/endpoint'
        ... }
        >>> error_response = transformError(error_data)
        >>> error_response.statusCode
        400

    """
    return ErrorResponse(**error_data)


def _prepare_error_data(response_data: dict, status_code: int, instance: Optional[str]) -> dict:
    """Prepare normalized error payload for ErrorResponse construction."""
    data = response_data.copy()
    if instance:
        data["instance"] = instance
    data["statusCode"] = status_code
    data.setdefault("title", None)
    return data


def handleApiError(
    response_data: dict, status_code: int, instance: Optional[str] = None
) -> ApiErrorException:
    """Handle API error and raise camelCase ApiErrorException."""
    raise ApiErrorException(
        transformError(_prepare_error_data(response_data, status_code, instance))
    )


def extract_correlation_id_from_error(error: Exception) -> Optional[str]:
    """Extract correlation ID from supported exception types."""
    if isinstance(error, MisoClientError) and error.error_response:
        correlation_id = error.error_response.correlationId
        if correlation_id is not None:
            return str(correlation_id)
    if isinstance(error, ApiErrorException):
        correlation_id = error.correlationId
        if correlation_id is not None:
            return str(correlation_id)
    return None
