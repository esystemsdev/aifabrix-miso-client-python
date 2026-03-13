"""Runtime helpers for HttpClient logging and correlation handling."""

import asyncio
from typing import Any, Dict, Optional, Set
from uuid import uuid4

from ..models.config import MisoClientConfig
from ..services.logger import LoggerService
from ..utils.jwt_tools import JwtTokenCache
from .http_client_logging_helpers import (
    handle_logging_task_error,
    log_http_request,
    wait_for_logging_tasks,
)
from .logger_context_storage import get_logger_context


def resolve_correlation_id(request_headers: Dict[str, Any]) -> Optional[str]:
    """Resolve correlation ID from request headers or logger context."""
    header_candidates = (
        request_headers.get("x-correlation-id"),
        request_headers.get("X-Correlation-Id"),
        request_headers.get("correlation-id"),
        request_headers.get("x-request-id"),
        request_headers.get("X-Request-Id"),
        request_headers.get("request-id"),
    )
    for candidate in header_candidates:
        if candidate:
            return str(candidate)

    stored_context = get_logger_context()
    if not stored_context:
        return None

    context_candidate = stored_context.get("correlationId") or stored_context.get("requestId")
    if context_candidate:
        return str(context_candidate)

    return None


def ensure_correlation_headers(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure outbound request kwargs include x-correlation-id header."""
    headers = dict(kwargs.get("headers", {}) or {})
    correlation_id = resolve_correlation_id(headers) or str(uuid4())
    headers.setdefault("x-correlation-id", correlation_id)
    kwargs["headers"] = headers
    return headers


def create_logging_task(
    logging_tasks: Set[asyncio.Task[Any]],
    logger: LoggerService,
    config: MisoClientConfig,
    jwt_cache: JwtTokenCache,
    method: str,
    url: str,
    response: Any,
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    request_headers: Dict[str, Any],
) -> None:
    task = asyncio.create_task(
        _build_log_http_request_coroutine(
            logger,
            config,
            jwt_cache,
            method,
            url,
            response,
            error,
            start_time,
            request_data,
            request_headers,
        )
    )
    task.add_done_callback(handle_logging_task_error)
    logging_tasks.add(task)
    task.add_done_callback(logging_tasks.discard)


async def _build_log_http_request_coroutine(
    logger: LoggerService,
    config: MisoClientConfig,
    jwt_cache: JwtTokenCache,
    method: str,
    url: str,
    response: Any,
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    request_headers: Dict[str, Any],
) -> None:
    """Build coroutine for HTTP request logging execution."""
    await log_http_request(
        logger,
        config,
        jwt_cache,
        method,
        url,
        response,
        error,
        start_time,
        request_data,
        request_headers,
    )


async def wait_pending_logging_tasks(logging_tasks: Set[asyncio.Task[Any]], timeout: float) -> None:
    """Wait for pending logging tasks to complete."""
    if logging_tasks:
        await wait_for_logging_tasks(logging_tasks, timeout)


def cancel_pending_logging_tasks(logging_tasks: Set[asyncio.Task[Any]]) -> None:
    """Cancel pending logging tasks safely."""
    for task in list(logging_tasks):
        if not task.done():
            try:
                task.cancel()
            except Exception:
                continue
