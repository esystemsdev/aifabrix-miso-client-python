"""
HTTP client logging utilities for ISO 27001 compliant audit and debug logging.

This module provides logging functionality extracted from HttpClient to keep
the main HTTP client class focused and within size limits. All sensitive data
is automatically masked using DataMasker before logging.
"""

import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from ..utils.data_masker import DataMasker


def should_skip_logging(url: str) -> bool:
    """
    Check if logging should be skipped for this URL.

    Skips logging for /api/logs and /api/auth/token to prevent infinite loops.

    Args:
        url: Request URL

    Returns:
        True if logging should be skipped, False otherwise
    """
    if url == "/api/logs" or url.startswith("/api/logs"):
        return True
    if url == "/api/auth/token" or url.startswith("/api/auth/token"):
        return True
    return False


def calculate_request_metrics(
    start_time: float, response: Optional[Any] = None, error: Optional[Exception] = None
) -> tuple[int, Optional[int]]:
    """
    Calculate request duration and status code.

    Args:
        start_time: Request start time from time.perf_counter()
        response: Response data (if successful)
        error: Exception (if request failed)

    Returns:
        Tuple of (duration_ms, status_code)
    """
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    status_code: Optional[int] = None
    if response is not None:
        status_code = 200  # Default assumption if response exists
    elif error is not None:
        if hasattr(error, "status_code"):
            status_code = error.status_code
        else:
            status_code = 500  # Default for errors

    return duration_ms, status_code


def calculate_request_sizes(
    request_data: Optional[Dict[str, Any]], response: Optional[Any]
) -> tuple[Optional[int], Optional[int]]:
    """
    Calculate request and response sizes in bytes.

    Args:
        request_data: Request body data
        response: Response data

    Returns:
        Tuple of (request_size, response_size) in bytes, None if unavailable
    """
    request_size: Optional[int] = None
    if request_data is not None:
        try:
            request_str = str(request_data)
            request_size = len(request_str.encode("utf-8"))
        except Exception:
            pass

    response_size: Optional[int] = None
    if response is not None:
        try:
            response_str = str(response)
            response_size = len(response_str.encode("utf-8"))
        except Exception:
            pass

    return request_size, response_size


def mask_error_message(error: Exception) -> Optional[str]:
    """
    Mask sensitive data in error message.

    Args:
        error: Exception object

    Returns:
        Masked error message string, or None if no error
    """
    if error is None:
        return None

    try:
        error_message = str(error)
        # Mask if error message contains sensitive keywords
        if isinstance(error_message, str) and any(
            keyword in error_message.lower()
            for keyword in ["password", "token", "secret", "key"]
        ):
            return DataMasker.MASKED_VALUE
        return error_message
    except Exception:
        return None


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
    )
    return audit_context


def _prepare_audit_context(
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    log_level: str,
) -> Optional[Dict[str, Any]]:
    """
    Prepare audit context for logging.

    Returns:
        Audit context dictionary or None if logging should be skipped
    """
    if should_skip_logging(url):
        return None

    duration_ms, status_code = calculate_request_metrics(start_time, response, error)

    request_size: Optional[int] = None
    response_size: Optional[int] = None
    if log_level == "debug":
        request_size, response_size = calculate_request_sizes(request_data, response)

    error_message = mask_error_message(error)
    return build_audit_context(
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        request_size=request_size,
        response_size=response_size,
        error_message=error_message,
    )


async def log_http_request_audit(
    logger: Any,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    log_level: str,
) -> None:
    """
    Log HTTP request audit event with ISO 27001 compliant data masking.

    Args:
        logger: LoggerService instance
        method: HTTP method
        url: Request URL
        response: Response data (if successful)
        error: Exception (if request failed)
        start_time: Request start time
        request_data: Request body data
        user_id: User ID if available
        log_level: Log level configuration
    """
    try:
        audit_context = _prepare_audit_context(
            method, url, response, error, start_time, request_data, user_id, log_level
        )
        if audit_context is None:
            return

        action = f"http.request.{method.upper()}"
        await logger.audit(action, url, audit_context)

    except Exception:
        # Silently swallow all logging errors - never break HTTP requests
        pass


def mask_request_data(request_headers: Optional[Dict[str, Any]], request_data: Optional[Dict[str, Any]]) -> tuple[Optional[Dict[str, Any]], Optional[Any]]:
    """
    Mask sensitive data in request headers and body.

    Args:
        request_headers: Request headers dictionary
        request_data: Request body data

    Returns:
        Tuple of (masked_headers, masked_body)
    """
    masked_headers: Optional[Dict[str, Any]] = None
    if request_headers:
        masked_headers = DataMasker.mask_sensitive_data(request_headers)

    masked_body: Optional[Any] = None
    if request_data is not None:
        masked_body = DataMasker.mask_sensitive_data(request_data)

    return masked_headers, masked_body


def mask_response_data(response: Optional[Any]) -> Optional[str]:
    """
    Mask sensitive data in response body and limit size.

    Args:
        response: Response data

    Returns:
        Masked response body as string (limited to 1000 chars), or None
    """
    if response is None:
        return None

    try:
        response_str = str(response)
        # Limit to first 1000 characters
        if len(response_str) > 1000:
            response_str = response_str[:1000] + "..."

        # Mask sensitive data
        try:
            if isinstance(response, dict):
                masked_dict = DataMasker.mask_sensitive_data(response)
                return str(masked_dict)
            return response_str
        except Exception:
            return response_str
    except Exception:
        return None


def extract_and_mask_query_params(url: str) -> Optional[Dict[str, Any]]:
    """
    Extract query parameters from URL and mask sensitive data.

    Args:
        url: Request URL with query string

    Returns:
        Masked query parameters dictionary, or None if no query params
    """
    try:
        parsed_url = urlparse(url)
        if not parsed_url.query:
            return None

        query_dict = parse_qs(parsed_url.query)
        # Convert lists to single values for simplicity
        query_simple: Dict[str, Any] = {
            k: v[0] if len(v) == 1 else v for k, v in query_dict.items()
        }
        return DataMasker.mask_sensitive_data(query_simple)
    except Exception:
        return None


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


def _prepare_debug_context(
    method: str,
    url: str,
    response: Optional[Any],
    duration_ms: int,
    status_code: Optional[int],
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
    base_url: str,
) -> Dict[str, Any]:
    """
    Prepare debug context for logging.

    Returns:
        Debug context dictionary
    """
    masked_headers, masked_body = mask_request_data(request_headers, request_data)
    masked_response = mask_response_data(response)
    query_params = extract_and_mask_query_params(url)

    return build_debug_context(
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms,
        base_url=base_url,
        user_id=user_id,
        masked_headers=masked_headers,
        masked_body=masked_body,
        masked_response=masked_response,
        query_params=query_params,
    )


async def log_http_request_debug(
    logger: Any,
    method: str,
    url: str,
    response: Optional[Any],
    duration_ms: int,
    status_code: Optional[int],
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
    base_url: str,
) -> None:
    """
    Log detailed debug information for HTTP request.

    All sensitive data is masked before logging.

    Args:
        logger: LoggerService instance
        method: HTTP method
        url: Request URL
        response: Response data
        duration_ms: Request duration in milliseconds
        status_code: HTTP status code
        user_id: User ID if available
        request_data: Request body data
        request_headers: Request headers
        base_url: Base URL from config
    """
    try:
        debug_context = _prepare_debug_context(
            method, url, response, duration_ms, status_code, user_id, request_data, request_headers, base_url
        )
        message = f"HTTP {method} {url} - Status: {status_code}, Duration: {duration_ms}ms"
        await logger.debug(message, debug_context)

    except Exception:
        # Silently swallow all logging errors - never break HTTP requests
        pass

