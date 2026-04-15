"""HTTP error handler utilities for InternalHttpClient.

This module provides error parsing and handling functionality for HTTP responses.
"""

from typing import Any, Dict, Literal, Optional

import httpx

from ..models.error_response import ErrorResponse

# Authentication method type for error tracking
AuthMethod = Literal["bearer", "client-token", "client-credentials", "api-key"]
_AUTH_HEADER_TO_METHOD: Dict[str, AuthMethod] = {
    "authorization": "bearer",
    "x-client-token": "client-token",
    "x-client-id": "client-credentials",
    "x-api-key": "api-key",
}
_CORRELATION_HEADERS = [
    "x-correlation-id",
    "x-request-id",
    "correlation-id",
    "correlationId",
    "x-correlationid",
    "request-id",
]


def _extract_correlation_from_headers(headers: Any) -> Optional[str]:
    """Extract correlation ID from a headers mapping."""
    for header_name in _CORRELATION_HEADERS:
        correlation_id = headers.get(header_name) or headers.get(header_name.lower())
        if correlation_id:
            return str(correlation_id)
    return None


def _is_structured_error_response(response_data: object) -> bool:
    """Check whether payload matches expected ErrorResponse structure."""
    return bool(
        isinstance(response_data, dict)
        and "errors" in response_data
        and "type" in response_data
        and "title" in response_data
        and "statusCode" in response_data
    )


def _enrich_error_response(data: Dict[str, object], response: httpx.Response, url: str) -> None:
    """Enrich parsed API error payload with instance/correlation fallback values."""
    if "instance" not in data or not data["instance"]:
        data["instance"] = url
    if "correlationId" in data and data["correlationId"]:
        return
    correlation_id = extract_correlation_id_from_response(response)
    if correlation_id:
        data["correlationId"] = correlation_id


def extract_correlation_id_from_response(
    response: Optional[httpx.Response] = None,
) -> Optional[str]:
    """Extract correlation ID from response headers."""
    if not response:
        return None
    return _extract_correlation_from_headers(getattr(response, "headers", None))


def detect_auth_method_from_headers(
    headers: Optional[Dict[str, str]] = None,
) -> Optional[AuthMethod]:
    """Detect attempted authentication method from request headers."""
    if not headers:
        return None
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    for header_name, auth_method in _AUTH_HEADER_TO_METHOD.items():
        if normalized_headers.get(header_name):
            return auth_method
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
        if not _is_structured_error_response(response_data):
            return None
        data = dict(response_data)
        _enrich_error_response(data, response, url)
        return ErrorResponse(**data)
    except (ValueError, TypeError, KeyError):
        return None
    return None
