"""
Error utilities for MisoClient SDK.

This module provides error transformation utilities for handling
snake_case error responses from the API.
"""

from typing import Optional

from ..errors import MisoClientError
from ..models.error_response import ErrorResponse


def transform_error_to_snake_case(error_data: dict) -> ErrorResponse:
    """
    Transform errors to snake_case format.

    Converts error data dictionary to ErrorResponse object,
    supporting both camelCase and snake_case field names.

    Args:
        error_data: Dictionary with error data (can be camelCase or snake_case)

    Returns:
        ErrorResponse object with standardized format

    Examples:
        >>> error_data = {
        ...     'errors': ['Error message'],
        ...     'type': '/Errors/Bad Input',
        ...     'title': 'Bad Request',
        ...     'status_code': 400,
        ...     'instance': '/api/endpoint'
        ... }
        >>> error_response = transform_error_to_snake_case(error_data)
        >>> error_response.statusCode
        400
    """
    # ErrorResponse already supports both formats via populate_by_name=True
    return ErrorResponse(**error_data)


def handle_api_error_snake_case(
    response_data: dict, status_code: int, instance: Optional[str] = None
) -> MisoClientError:
    """
    Handle errors with snake_case response format.

    Creates MisoClientError with ErrorResponse from snake_case API response.

    Args:
        response_data: Error response data from API (can be camelCase or snake_case)
        status_code: HTTP status code (overrides status_code in response_data)
        instance: Optional request instance URI (overrides instance in response_data)

    Returns:
        MisoClientError with structured ErrorResponse

    Examples:
        >>> response_data = {
        ...     'errors': ['Validation failed'],
        ...     'type': '/Errors/Validation',
        ...     'title': 'Validation Error',
        ...     'status_code': 422
        ... }
        >>> error = handle_api_error_snake_case(response_data, 422, '/api/endpoint')
        >>> error.error_response.statusCode
        422
    """
    # Create a copy to avoid mutating the original
    data = response_data.copy()

    # Override instance if provided
    if instance:
        data["instance"] = instance

    # Override status_code if provided
    data["status_code"] = status_code
    # Also set camelCase version for consistency
    data["statusCode"] = status_code

    # Ensure title has a default if missing
    if "title" not in data:
        data["title"] = None

    # Transform to ErrorResponse
    error_response = transform_error_to_snake_case(data)

    # Create error message from errors list
    if error_response.errors:
        if len(error_response.errors) == 1:
            message = error_response.errors[0]
        else:
            title_prefix = f"{error_response.title}: " if error_response.title else ""
            message = f"{title_prefix}{'; '.join(error_response.errors)}"
    else:
        message = error_response.title or "API Error"

    # Create MisoClientError with ErrorResponse
    return MisoClientError(
        message=message,
        status_code=status_code,
        error_response=error_response,
    )
