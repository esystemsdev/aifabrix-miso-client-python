"""
HTTP client logging helper functions.

Extracted from http_client.py to reduce file size and improve maintainability.
"""

import asyncio
import time
from typing import Any, Dict, Optional

from ..models.config import MisoClientConfig
from ..services.logger import LoggerService
from ..utils.jwt_tools import JwtTokenCache
from .http_client_logging import log_http_request_audit, log_http_request_debug


def handle_logging_task_error(task: asyncio.Task) -> None:
    """
    Handle errors in background logging tasks.

    Silently swallows all exceptions to prevent logging errors from breaking requests.

    Args:
        task: The completed logging task
    """
    try:
        exception = task.exception()
        if exception:
            # Silently swallow logging errors - never break HTTP requests
            pass
    except Exception:
        # Task might not be done yet or other error - ignore
        pass


async def wait_for_logging_tasks(logging_tasks: set[asyncio.Task], timeout: float = 0.5) -> None:
    """
    Wait for all pending logging tasks to complete.

    Useful for tests to ensure logging has finished before assertions.

    Args:
        logging_tasks: Set of logging tasks
        timeout: Maximum time to wait in seconds
    """
    if logging_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*logging_tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # Some tasks might still be running, that's okay
            pass


def calculate_status_code(response: Optional[Any], error: Optional[Exception]) -> Optional[int]:
    """
    Calculate HTTP status code from response or error.

    Args:
        response: Response data (if successful)
        error: Exception (if request failed)

    Returns:
        HTTP status code, or None if cannot determine
    """
    if response is not None:
        return 200
    if error is not None:
        if hasattr(error, "status_code"):
            status_code = getattr(error, "status_code", None)
            if isinstance(status_code, int):
                return status_code
        return 500
    return None


def extract_user_id_from_headers(
    request_headers: Optional[Dict[str, Any]], jwt_cache: JwtTokenCache
) -> Optional[str]:
    """
    Extract user ID from request headers.

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
) -> None:
    """
    Log debug details if debug logging is enabled.

    Args:
        logger: LoggerService instance
        config: MisoClientConfig instance
        method: HTTP method
        url: Request URL
        response: Response data (if successful)
        error: Exception (if request failed)
        start_time: Request start time
        user_id: User ID if available
        request_data: Request body data
        request_headers: Request headers
    """
    if config.log_level != "debug":
        return

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    status_code = calculate_status_code(response, error)
    await log_http_request_debug(
        logger=logger,
        method=method,
        url=url,
        response=response,
        duration_ms=duration_ms,
        status_code=status_code,
        user_id=user_id,
        request_data=request_data,
        request_headers=request_headers,
        base_url=config.controller_url,
        config=config,
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
    """
    Log HTTP request with audit and optional debug logging.

    Args:
        logger: LoggerService instance
        config: MisoClientConfig instance
        jwt_cache: JWT token cache instance
        method: HTTP method
        url: Request URL
        response: Response data (if successful)
        error: Exception (if request failed)
        start_time: Request start time
        request_data: Request body data
        request_headers: Request headers
    """
    user_id = extract_user_id_from_headers(request_headers, jwt_cache)

    await log_http_request_audit(
        logger=logger,
        method=method,
        url=url,
        response=response,
        error=error,
        start_time=start_time,
        request_data=request_data,
        user_id=user_id,
        log_level=config.log_level,
        config=config,
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
    )
