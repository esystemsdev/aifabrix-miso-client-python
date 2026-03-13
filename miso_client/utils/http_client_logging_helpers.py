"""HTTP client logging helper functions.

Extracted from http_client.py to reduce file size and improve maintainability.
"""

import asyncio
import time
from typing import Any, Dict, Optional

from ..models.config import MisoClientConfig
from ..services.logger import LoggerService
from ..utils.jwt_tools import JwtTokenCache
from .http_client_logging import log_http_request_audit, log_http_request_debug
from .http_error_handler import extract_correlation_id_from_response


def handle_logging_task_error(task: asyncio.Task) -> None:
    """Handle errors in background logging tasks.

    Silently swallows all exceptions to prevent logging errors from breaking requests.
    Handles closed event loops gracefully during test teardown.

    Args:
        task: The completed logging task

    """
    try:
        exception = task.exception()
        if exception:
            # Silently swallow logging errors - never break HTTP requests
            # This includes RuntimeError("Event loop is closed") during teardown
            pass
    except (RuntimeError, asyncio.CancelledError):
        # Event loop closed or task cancelled during teardown - this is expected
        pass
    except Exception:
        # Task might not be done yet or other error - ignore
        pass


async def wait_for_logging_tasks(logging_tasks: set[asyncio.Task], timeout: float = 0.5) -> None:
    """Wait for active logging tasks to complete."""
    if not logging_tasks:
        return

    active_tasks = [task for task in logging_tasks if not task.done()]
    if not active_tasks:
        return

    try:
        await asyncio.wait_for(
            asyncio.gather(*active_tasks, return_exceptions=True),
            timeout=timeout,
        )
    except (asyncio.TimeoutError, RuntimeError):
        for task in active_tasks:
            if not task.done():
                try:
                    task.cancel()
                except Exception:
                    pass


def calculate_status_code(response: Optional[Any], error: Optional[Exception]) -> Optional[int]:
    """Calculate HTTP status code from response or error.

    Args:
        response: Response data (if successful)
        error: Exception (if request failed)

    Returns:
        HTTP status code, or None if cannot determine

    """
    if response is not None:
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        return 200
    if error is not None:
        response_obj = getattr(error, "response", None)
        response_status = getattr(response_obj, "status_code", None)
        if isinstance(response_status, int):
            return response_status
        if hasattr(error, "status_code"):
            status_code = getattr(error, "status_code", None)
            if isinstance(status_code, int):
                return status_code
        return 500
    return None


def extract_user_id_from_headers(
    request_headers: Optional[Dict[str, Any]], jwt_cache: JwtTokenCache
) -> Optional[str]:
    """Extract user ID from request headers.

    Args:
        request_headers: Request headers dictionary
        jwt_cache: JWT token cache instance

    Returns:
        User ID if found, None otherwise

    """
    if request_headers:
        return jwt_cache.extract_user_id_from_headers(request_headers)
    return None


async def log_debug_if_enabled(
    logger: LoggerService,
    config: MisoClientConfig,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
    correlation_id: Optional[str] = None,
) -> None:
    if config.log_level != "debug":
        return
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    status_code = calculate_status_code(response, error)
    await _log_debug_request(
        logger,
        config,
        method,
        url,
        response,
        duration_ms,
        status_code,
        user_id,
        request_data,
        request_headers,
        correlation_id,
    )


async def _log_debug_request(
    logger: LoggerService,
    config: MisoClientConfig,
    method: str,
    url: str,
    response: Optional[Any],
    duration_ms: int,
    status_code: Optional[int],
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
    correlation_id: Optional[str],
) -> None:
    """Delegate debug-request logging call to shared formatter function."""
    await log_http_request_debug(
        logger,
        method,
        url,
        response,
        duration_ms,
        status_code,
        user_id,
        request_data,
        request_headers,
        config.controller_url,
        config,
        correlation_id,
    )


def _resolve_correlation_id(
    response: Optional[Any], request_headers: Optional[Dict[str, Any]]
) -> Optional[str]:
    """Resolve correlation id from response headers or request headers."""
    correlation_id = (
        extract_correlation_id_from_response(response)
        if response is not None and hasattr(response, "headers")
        else None
    )
    if correlation_id is not None or not request_headers:
        return correlation_id
    return (
        request_headers.get("x-correlation-id")
        or request_headers.get("X-Correlation-Id")
        or request_headers.get("correlation-id")
        or request_headers.get("x-request-id")
        or request_headers.get("X-Request-Id")
        or request_headers.get("request-id")
    )


async def _log_audit_and_debug(
    logger: LoggerService,
    config: MisoClientConfig,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
    user_id: Optional[str],
    correlation_id: Optional[str],
) -> None:
    """Log audit event first, then optional debug event."""
    await _log_audit_only(
        logger,
        config,
        method,
        url,
        response,
        error,
        start_time,
        request_data,
        user_id,
        correlation_id,
    )
    await log_debug_if_enabled(
        logger,
        config,
        method,
        url,
        response,
        error,
        start_time,
        user_id,
        request_data,
        request_headers,
        correlation_id=correlation_id,
    )


async def _log_audit_only(
    logger: LoggerService,
    config: MisoClientConfig,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    correlation_id: Optional[str],
) -> None:
    """Log audit-only event."""
    await log_http_request_audit(
        logger,
        method,
        url,
        response,
        error,
        start_time,
        request_data,
        user_id,
        config.log_level,
        config,
        correlation_id,
    )


async def log_http_request(
    logger: LoggerService,
    config: MisoClientConfig,
    jwt_cache: JwtTokenCache,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
) -> None:
    """Log HTTP request with audit and optional debug details."""
    user_id = extract_user_id_from_headers(request_headers, jwt_cache)
    correlation_id = _resolve_correlation_id(response, request_headers)
    await _log_audit_and_debug(
        logger,
        config,
        method,
        url,
        response,
        error,
        start_time,
        request_data,
        request_headers,
        user_id,
        correlation_id,
    )
