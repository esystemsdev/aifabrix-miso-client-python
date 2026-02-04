"""HTTP error handler utilities for InternalHttpClient.

This module provides error parsing and handling functionality for HTTP responses.
"""

from typing import Dict, Literal, Optional

import httpx

from ..models.error_response import ErrorResponse

# Authentication method type for error tracking
AuthMethod = Literal["bearer", "client-token", "client-credentials", "api-key"]


def extract_correlation_id_from_response(
    response: Optional[httpx.Response] = None,
) -> Optional[str]:
    """Extract correlation ID from response headers.

    Checks common correlation ID header names.

    Args:
        response: HTTP response object (optional)

    Returns:
        Correlation ID string if found, None otherwise

    """
    if not response:
        return None

    # Check common correlation ID header names (case-insensitive)
    correlation_headers = [
        "x-correlation-id",
        "x-request-id",
        "correlation-id",
        "correlationId",
        "x-correlationid",
        "request-id",
    ]

    for header_name in correlation_headers:
        correlation_id = response.headers.get(header_name) or response.headers.get(
            header_name.lower()
        )
        if correlation_id:
            return str(correlation_id)

    return None


def detect_auth_method_from_headers(
    headers: Optional[Dict[str, str]] = None,
) -> Optional[AuthMethod]:
    """Detect authentication method from request headers.

    This is a fallback detection mechanism used when the controller doesn't
    return an authMethod field in the error response. It inspects the request
    headers to determine which authentication method was attempted.

    Args:
        headers: Request headers dictionary (optional)

    Returns:
        The detected auth method ('bearer', 'client-token', 'client-credentials',
        'api-key') or None if no auth headers found.

    Examples:
        >>> detect_auth_method_from_headers({"Authorization": "Bearer token123"})
        'bearer'
        >>> detect_auth_method_from_headers({"x-client-token": "token123"})
        'client-token'
        >>> detect_auth_method_from_headers({"x-api-key": "key123"})
        'api-key'
        >>> detect_auth_method_from_headers({})
        None

    """
    if not headers:
        return None

    normalized_headers = {key.lower(): value for key, value in headers.items()}

    # Check for Bearer token (Authorization header)
    if normalized_headers.get("authorization"):
        return "bearer"

    # Check for client token
    if normalized_headers.get("x-client-token"):
        return "client-token"

    # Check for client credentials (client ID header indicates client-credentials auth)
    if normalized_headers.get("x-client-id"):
        return "client-credentials"

    # Check for API key
    if normalized_headers.get("x-api-key"):
        return "api-key"

    return None


def parse_error_response(response: httpx.Response, url: str) -> Optional[ErrorResponse]:
    """Parse structured error response from HTTP response.

    Extracts correlation ID from response headers if not present in response body.
    Also extracts authMethod from response data if present (for 401 errors).

    Args:
        response: HTTP response object
        url: Request URL (used for instance URI if not in response)

    Returns:
        ErrorResponse if response matches structure, None otherwise

    """
    if not response.headers.get("content-type", "").startswith("application/json"):
        return None

    try:
        response_data = response.json()
        # Check if response matches ErrorResponse structure
        if (
            isinstance(response_data, dict)
            and "errors" in response_data
            and "type" in response_data
            and "title" in response_data
            and "statusCode" in response_data
        ):
            # Set instance from URL if not provided
            if "instance" not in response_data or not response_data["instance"]:
                response_data["instance"] = url

            # Extract correlation ID from headers if not present in response body
            if "correlationId" not in response_data or not response_data["correlationId"]:
                correlation_id = extract_correlation_id_from_response(response)
                if correlation_id:
                    response_data["correlationId"] = correlation_id

            # authMethod is extracted from response data if present (controller may send it)
            # No need to set default here - ErrorResponse model handles it

            return ErrorResponse(**response_data)
    except (ValueError, TypeError, KeyError):
        # JSON parsing failed or structure doesn't match
        pass

    return None
