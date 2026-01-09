"""
HTTP log formatting utilities for ISO 27001 compliant audit and debug logging.

This module provides formatting functions for building audit and debug log contexts.
All sensitive data should be masked before passing to these formatters.
"""

from typing import Any, Dict, Optional


def _add_optional_fields(context: Dict[str, Any], **fields: Any) -> None:
    """
    Add optional fields to context dictionary if they are not None.

    Args:
        context: Context dictionary to add fields to
        **fields: Optional fields to add (value is None if field should be skipped)
    """
    for key, value in fields.items():
        if value is not None:
            context[key] = value


def build_audit_context(
    method: str,
    url: str,
    status_code: Optional[int],
    duration_ms: int,
    user_id: Optional[str],
    request_size: Optional[int],
    response_size: Optional[int],
    error_message: Optional[str],
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build audit context dictionary for logging.

    Args:
        method: HTTP method
        url: Request URL
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        user_id: User ID if available
        request_size: Request size in bytes (optional)
        response_size: Response size in bytes (optional)
        error_message: Error message if request failed (optional)
        correlation_id: Correlation ID if available (optional)

    Returns:
        Audit context dictionary
    """
    audit_context: Dict[str, Any] = {
        "method": method,
        "url": url,
        "statusCode": status_code,
        "duration": duration_ms,
    }
    _add_optional_fields(
        audit_context,
        userId=user_id,
        requestSize=request_size,
        responseSize=response_size,
        error=error_message,
        correlationId=correlation_id,
    )
    return audit_context


def build_debug_context(
    method: str,
    url: str,
    status_code: Optional[int],
    duration_ms: int,
    base_url: str,
    user_id: Optional[str],
    masked_headers: Optional[Dict[str, Any]],
    masked_body: Optional[Any],
    masked_response: Optional[str],
    query_params: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build debug context dictionary for detailed logging.

    Args:
        method: HTTP method
        url: Request URL
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        base_url: Base URL from config
        user_id: User ID if available
        masked_headers: Masked request headers
        masked_body: Masked request body
        masked_response: Masked response body
        query_params: Masked query parameters

    Returns:
        Debug context dictionary
    """
    debug_context: Dict[str, Any] = {
        "method": method,
        "url": url,
        "statusCode": status_code,
        "duration": duration_ms,
        "baseURL": base_url,
        "timeout": 30.0,  # Default timeout
    }
    _add_optional_fields(
        debug_context,
        userId=user_id,
        requestHeaders=masked_headers,
        requestBody=masked_body,
        responseBody=masked_response,
        queryParams=query_params,
    )
    return debug_context
