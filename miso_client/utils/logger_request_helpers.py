"""Logger request helper functions for extracting request context.

This module provides helper functions for extracting logging context from HTTP requests
and building LogEntry objects with request context.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from ..models.config import ClientLoggingOptions, LogEntry
    from ..services.logger import LoggerService

from ..models.config import ClientLoggingOptions, LogLevel
from ..utils.logger_helpers import build_log_entry, extract_metadata, split_log_context
from ..utils.request_context import extract_request_context


def _merge_request_context(base_context: Dict[str, Any], request: Any) -> Dict[str, Any]:
    """Merge extracted HTTP request context into provided context dictionary."""
    ctx = extract_request_context(request)
    context_pairs = (
        ("userId", ctx.user_id),
        ("sessionId", ctx.session_id),
        ("correlationId", ctx.correlation_id),
        ("requestId", ctx.request_id),
        ("ipAddress", ctx.ip_address),
        ("userAgent", ctx.user_agent),
        ("method", ctx.method),
        ("path", ctx.path),
        ("referer", ctx.referer),
        ("requestSize", ctx.request_size),
    )
    for key, value in context_pairs:
        if value:
            base_context[key] = value
    return base_context


def _resolve_correlation_id(logger_service: "LoggerService", auto_fields: Dict[str, Any]) -> str:
    """Resolve correlation id from context auto fields with fallback generation."""
    return str(auto_fields.get("correlationId") or logger_service._generate_correlation_id())


async def _resolve_application_context(
    logger_service: "LoggerService", options: Optional[ClientLoggingOptions]
) -> Dict[str, Any]:
    """Resolve application context dictionary for log entry construction."""
    app_context = await logger_service.application_context_service.get_application_context(
        overwrite_application=options.application if options else None,
        overwrite_application_id=None,
        overwrite_environment=options.environment if options else None,
    )
    return app_context.to_dict()


async def _build_entry(
    logger_service: "LoggerService",
    *,
    message: str,
    level: LogLevel,
    context: Dict[str, Any],
    stack_trace: Optional[str],
    options: Optional[ClientLoggingOptions],
) -> "LogEntry":
    """Build a log entry from prepared inputs."""
    final_options = options or ClientLoggingOptions()
    context_data, auto_fields = split_log_context(context)
    return build_log_entry(
        level=level,
        message=message,
        context=context_data,
        config_client_id=logger_service.config.client_id,
        correlation_id=_resolve_correlation_id(logger_service, auto_fields),
        jwt_token=auto_fields.get("token"),
        stack_trace=stack_trace,
        options=final_options,
        auto_fields=auto_fields,
        metadata=extract_metadata(),
        mask_sensitive=logger_service.mask_sensitive_data,
        application_context=await _resolve_application_context(logger_service, final_options),
    )


async def get_log_with_request(
    logger_service: "LoggerService",
    request: Any,
    message: str,
    level: LogLevel = "info",
    context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None,
) -> "LogEntry":
    """Get LogEntry object with auto-extracted request context."""
    request_context = _merge_request_context(context or {}, request)
    return await _build_entry(
        logger_service,
        message=message,
        level=level,
        context=request_context,
        stack_trace=stack_trace,
        options=ClientLoggingOptions(),
    )


async def get_with_context(
    logger_service: "LoggerService",
    context: Dict[str, Any],
    message: str,
    level: LogLevel = "info",
    stack_trace: Optional[str] = None,
    options: Optional[ClientLoggingOptions] = None,
) -> "LogEntry":
    """Get LogEntry object with custom context."""
    return await _build_entry(
        logger_service,
        message=message,
        level=level,
        context=context,
        stack_trace=stack_trace,
        options=options,
    )


async def get_for_request(
    logger_service: "LoggerService",
    request: Any,
    message: str,
    level: LogLevel = "info",
    context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None,
) -> "LogEntry":
    """Get LogEntry object with request context (alias for get_log_with_request).

    Same functionality as get_log_with_request() for convenience.

    Args:
        logger_service: LoggerService instance
        request: HTTP request object (FastAPI, Flask, Starlette)
        message: Log message
        level: Log level (default: "info")
        context: Additional context data (optional)
        stack_trace: Stack trace for errors (optional)

    Returns:
        LogEntry object with request context extracted

    Example:
        >>> log_entry = await get_for_request(logger, request, "Request processed")

    """
    return await get_log_with_request(logger_service, request, message, level, context, stack_trace)
