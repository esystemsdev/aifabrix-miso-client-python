"""
Error utilities for MisoClient SDK.

This module provides error transformation utilities for handling
camelCase error responses from the API.
"""

from typing import Optional

from ..errors import MisoClientError
from ..models.error_response import ErrorResponse


class ApiErrorException(Exception):
    """
    Exception class for camelCase error responses.

    Used with camelCase ErrorResponse format matching TypeScript SDK.
    """

    def __init__(self, error: ErrorResponse):
        """
        Initialize ApiErrorException.

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
    """
    Transform arbitrary error into standardized camelCase ErrorResponse.

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


# Alias for backward compatibility
transform_error_to_snake_case = transformError


def handleApiError(
    response_data: dict, status_code: int, instance: Optional[str] = None
) -> ApiErrorException:
    """
    Handle API error and raise camelCase ApiErrorException.

    Creates ApiErrorException from camelCase API response.

    Args:
        response_data: Error response data from API (must be camelCase)
        status_code: HTTP status code (overrides statusCode in response_data)
        instance: Optional request instance URI (overrides instance in response_data)

    Returns:
        ApiErrorException with camelCase error format

    Raises:
        ApiErrorException: Always raises this exception

    Examples:
        >>> response_data = {
        ...     'errors': ['Validation failed'],
        ...     'type': '/Errors/Validation',
        ...     'title': 'Validation Error',
        ...     'statusCode': 422
        ... }
        >>> try:
        ...     handleApiError(response_data, 422, '/api/endpoint')
        ... except ApiErrorException as e:
        ...     e.statusCode
        422
    """
    # Create a copy to avoid mutating the original
    data = response_data.copy()

    # Override instance if provided
    if instance:
        data["instance"] = instance

    # Override statusCode if provided
    data["statusCode"] = status_code

    # Ensure title has a default if missing
    if "title" not in data:
        data["title"] = None

    # Transform to ErrorResponse
    error_response = transformError(data)

    # Raise ApiErrorException
    raise ApiErrorException(error_response)


def handle_api_error_snake_case(
    response_data: dict, status_code: int, instance: Optional[str] = None
) -> MisoClientError:
    """
    Handle errors with camelCase response format (legacy function).

    Creates MisoClientError with ErrorResponse from camelCase API response.
    This is kept for backward compatibility. New code should use handleApiError().

    Args:
        response_data: Error response data from API (must be camelCase)
        status_code: HTTP status code (overrides statusCode in response_data)
        instance: Optional request instance URI (overrides instance in response_data)

    Returns:
        MisoClientError with structured ErrorResponse

    Examples:
        >>> response_data = {
        ...     'errors': ['Validation failed'],
        ...     'type': '/Errors/Validation',
        ...     'title': 'Validation Error',
        ...     'statusCode': 422
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

    # Override statusCode if provided
    data["statusCode"] = status_code

    # Ensure title has a default if missing
    if "title" not in data:
        data["title"] = None

    # Transform to ErrorResponse
    error_response = transformError(data)

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


def extract_correlation_id_from_error(error: Exception) -> Optional[str]:
    """
    Extract correlation ID from exception if available.

    Checks MisoClientError.error_response.correlationId and ApiErrorException.correlationId.

    Args:
        error: Exception object

    Returns:
        Correlation ID string if found, None otherwise

    Examples:
        >>> error = MisoClientError("Error", error_response=ErrorResponse(
        ...     errors=["Error"], type="/Errors/Test", statusCode=400,
        ...     correlationId="req-123"
        ... ))
        >>> extract_correlation_id_from_error(error)
        'req-123'
    """
    # Check MisoClientError with error_response
    if isinstance(error, MisoClientError) and error.error_response:
        correlation_id = error.error_response.correlationId
        if correlation_id is not None:
            return str(correlation_id)

    # Check ApiErrorException with correlationId property
    if isinstance(error, ApiErrorException):
        correlation_id = error.correlationId
        if correlation_id is not None:
            return str(correlation_id)

    return None
