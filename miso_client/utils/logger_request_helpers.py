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


async def get_log_with_request(
    logger_service: "LoggerService",
    request: Any,
    message: str,
    level: LogLevel = "info",
    context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None,
) -> "LogEntry":
    """Get LogEntry object with auto-extracted request context.

    Extracts IP, method, path, userAgent, correlationId, userId from request.
    Returns LogEntry object ready for use in other projects' logger tables.

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
        >>> log_entry = await get_log_with_request(logger, request, "Processing request")
        >>> # Use log_entry in your own logger table

    """
    # Extract request context
    ctx = extract_request_context(request)

    # Merge request info into context
    request_context = context or {}
    if ctx.user_id:
        request_context["userId"] = ctx.user_id
    if ctx.session_id:
        request_context["sessionId"] = ctx.session_id
    if ctx.correlation_id:
        request_context["correlationId"] = ctx.correlation_id
    if ctx.request_id:
        request_context["requestId"] = ctx.request_id
    if ctx.ip_address:
        request_context["ipAddress"] = ctx.ip_address
    if ctx.user_agent:
        request_context["userAgent"] = ctx.user_agent
    if ctx.method:
        request_context["method"] = ctx.method
    if ctx.path:
        request_context["path"] = ctx.path
    if ctx.referer:
        request_context["referer"] = ctx.referer
    if ctx.request_size:
        request_context["requestSize"] = ctx.request_size

    # Create log entry using helper function
    context_data, auto_fields = split_log_context(request_context)
    correlation_id = auto_fields.get("correlationId") or logger_service._generate_correlation_id()

    app_context = await logger_service.application_context_service.get_application_context(
        overwrite_application=None,
        overwrite_application_id=None,
        overwrite_environment=None,
    )

    return build_log_entry(
        level=level,
        message=message,
        context=context_data,
        config_client_id=logger_service.config.client_id,
        correlation_id=correlation_id,
        jwt_token=auto_fields.get("token"),
        stack_trace=stack_trace,
        options=ClientLoggingOptions(),
        auto_fields=auto_fields,
        metadata=extract_metadata(),
        mask_sensitive=logger_service.mask_sensitive_data,
        application_context=app_context.to_dict(),
    )


async def get_with_context(
    logger_service: "LoggerService",
    context: Dict[str, Any],
    message: str,
    level: LogLevel = "info",
    stack_trace: Optional[str] = None,
    options: Optional[ClientLoggingOptions] = None,
) -> "LogEntry":
    """Get LogEntry object with custom context.

    Adds custom context and returns LogEntry object.
    Allows projects to add their own context while leveraging MisoClient defaults.

    Args:
        logger_service: LoggerService instance
        context: Custom context data
        message: Log message
        level: Log level (default: "info")
        stack_trace: Stack trace for errors (optional)
        options: Optional logging options (optional)

    Returns:
        LogEntry object with custom context

    Example:
        >>> log_entry = await get_with_context(
        ...     logger,
        ...     {"customField": "value"},
        ...     "Custom log",
        ...     level="info"
        ... )

    """
    final_options = options or ClientLoggingOptions()
    context_data, auto_fields = split_log_context(context)
    correlation_id = auto_fields.get("correlationId") or logger_service._generate_correlation_id()

    app_context = await logger_service.application_context_service.get_application_context(
        overwrite_application=final_options.application if final_options else None,
        overwrite_application_id=None,
        overwrite_environment=final_options.environment if final_options else None,
    )

    return build_log_entry(
        level=level,
        message=message,
        context=context_data,
        config_client_id=logger_service.config.client_id,
        correlation_id=correlation_id,
        jwt_token=auto_fields.get("token"),
        stack_trace=stack_trace,
        options=final_options,
        auto_fields=auto_fields,
        metadata=extract_metadata(),
        mask_sensitive=logger_service.mask_sensitive_data,
        application_context=app_context.to_dict(),
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
