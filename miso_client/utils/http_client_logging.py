"""
HTTP client logging utilities for ISO 27001 compliant audit and debug logging.

This module provides logging functionality extracted from HttpClient to keep
the main HTTP client class focused and within size limits. All sensitive data
is automatically masked using DataMasker before logging.
"""

import time
from typing import Any, Dict, Optional

from .http_log_formatter import build_audit_context, build_debug_context
from .http_log_masker import (
    extract_and_mask_query_params,
    mask_error_message,
    mask_request_data,
    mask_response_data,
)


def should_skip_logging(url: str, config: Optional[Any] = None) -> bool:
    """
    Check if logging should be skipped for this URL.

    Skips logging for /api/logs and /api/auth/token to prevent infinite loops.
    Also checks audit config skipEndpoints.

    Args:
        url: Request URL
        config: Optional MisoClientConfig to check audit.skipEndpoints

    Returns:
        True if logging should be skipped, False otherwise
    """
    # Check if audit is explicitly disabled
    if config and config.audit and config.audit.enabled is False:
        return True

    # If no config or no audit config, default to enabled (don't skip)
    # Only skip if explicitly disabled

    # Check skip endpoints from config
    if config and config.audit and config.audit.skipEndpoints:
        for endpoint in config.audit.skipEndpoints:
            if endpoint in url:
                return True

    # Default skip endpoints (always skip these regardless of config)
    if url == "/api/v1/logs" or url.startswith("/api/v1/logs"):
        return True

    # Check configurable client token URI or default
    client_token_uri = "/api/v1/auth/token"
    if config and config.clientTokenUri:
        client_token_uri = config.clientTokenUri

    if url == client_token_uri or url.startswith(client_token_uri):
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


def _prepare_audit_context(
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    log_level: str,
    audit_config: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Prepare audit context for logging.

    Returns:
        Audit context dictionary or None if logging should be skipped
    """
    duration_ms, status_code = calculate_request_metrics(start_time, response, error)

    audit_config = audit_config or {}
    audit_level = audit_config.get("level", "detailed")

    request_size: Optional[int] = None
    response_size: Optional[int] = None
    if audit_level in ("detailed", "full"):
        request_size, response_size = calculate_request_sizes(request_data, response)

    error_message = mask_error_message(error) if error is not None else None
    return build_audit_context(
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        request_size=request_size,
        response_size=response_size,
        error_message=error_message,
        correlation_id=correlation_id,
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
    config: Optional[Any] = None,
) -> None:
    """
    Log HTTP request audit event with ISO 27001 compliant data masking.

    Supports configurable audit levels: minimal, standard, detailed, full.

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
        config: Optional MisoClientConfig for audit configuration
    """
    try:
        # Check if logging should be skipped
        if should_skip_logging(url, config):
            return

        # Extract correlation ID from error if available
        correlation_id: Optional[str] = None
        if error:
            from ..utils.error_utils import extract_correlation_id_from_error

            correlation_id = extract_correlation_id_from_error(error)

        if config and config.audit:
            audit_config = config.audit
            audit_level = audit_config.level or "detailed"
        else:
            audit_config = None
            audit_level = "detailed"

        # Minimal audit level - just metadata, no masking
        if audit_level == "minimal":
            duration_ms, status_code = calculate_request_metrics(start_time, response, error)
            audit_context = {
                "method": method,
                "url": url,
                "statusCode": status_code,
                "duration": duration_ms,
            }
            if user_id:
                audit_context["userId"] = user_id
            if error:
                audit_context["error"] = str(error)
            if correlation_id:
                audit_context["correlationId"] = correlation_id
            action = f"http.request.{method.upper()}"
            await logger.audit(action, url, audit_context)
            return

        # Standard, detailed, or full audit levels
        # Convert AuditConfig to dict for _prepare_audit_context
        audit_config_dict: Dict[str, Any] = {}
        if audit_config:
            if hasattr(audit_config, "model_dump"):
                audit_config_dict = audit_config.model_dump()
            elif hasattr(audit_config, "dict"):
                audit_config_dict = audit_config.dict()  # type: ignore[attr-defined]
        prepared_context = _prepare_audit_context(
            method,
            url,
            response,
            error,
            start_time,
            request_data,
            user_id,
            log_level,
            audit_config_dict,
            correlation_id=correlation_id,
        )
        if prepared_context is None:
            return

        audit_context = prepared_context
        action = f"http.request.{method.upper()}"
        await logger.audit(action, url, audit_context)

    except Exception:
        # Silently swallow all logging errors - never break HTTP requests
        pass


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
    max_response_size: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Prepare debug context for logging.

    Returns:
        Debug context dictionary
    """
    masked_headers, masked_body = mask_request_data(request_headers, request_data)
    masked_response = mask_response_data(response, max_size=max_response_size)
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
    config: Optional[Any] = None,
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
        # Get maxResponseSize from audit config if available
        max_response_size = None
        if config and config.audit and hasattr(config.audit, "maxResponseSize"):
            max_response_size = config.audit.maxResponseSize

        debug_context = _prepare_debug_context(
            method,
            url,
            response,
            duration_ms,
            status_code,
            user_id,
            request_data,
            request_headers,
            base_url,
            max_response_size=max_response_size,
        )
        message = f"HTTP {method} {url} - Status: {status_code}, Duration: {duration_ms}ms"
        await logger.debug(message, debug_context)

    except Exception:
        # Silently swallow all logging errors - never break HTTP requests
        pass
