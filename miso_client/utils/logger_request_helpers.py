"""Logger request helper functions for extracting request context.

This module provides helper functions for extracting logging context from HTTP requests
and building LogEntry objects with request context.
"""

from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

if TYPE_CHECKING:
    from ..models.config import ClientLoggingOptions, ForeignKeyReference, LogEntry
    from ..services.logger import LoggerService

from ..models.config import ClientLoggingOptions, ForeignKeyReference
from ..utils.logger_helpers import build_log_entry, extract_metadata
from ..utils.request_context import extract_request_context


async def get_log_with_request(
    logger_service: "LoggerService",
    request: Any,
    message: str,
    level: Literal["error", "audit", "info", "debug"] = "info",
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

    # Build options from extracted context
    options = ClientLoggingOptions()
    if ctx.user_id:
        options.userId = ctx.user_id
    if ctx.session_id:
        options.sessionId = ctx.session_id
    if ctx.correlation_id:
        options.correlationId = ctx.correlation_id
    if ctx.request_id:
        options.requestId = ctx.request_id
    if ctx.ip_address:
        options.ipAddress = ctx.ip_address
    if ctx.user_agent:
        options.userAgent = ctx.user_agent

    # Merge request info into context
    request_context = context or {}
    if ctx.method:
        request_context["method"] = ctx.method
    if ctx.path:
        request_context["path"] = ctx.path
    if ctx.referer:
        request_context["referer"] = ctx.referer
    if ctx.request_size:
        request_context["requestSize"] = ctx.request_size

    # Create log entry using helper function
    correlation_id = (
        options.correlationId if options else None
    ) or logger_service._generate_correlation_id()

    # Get application context (with overwrites from options)
    application_id_str: Optional[str] = None
    if options and options.applicationId:
        if isinstance(options.applicationId, ForeignKeyReference):
            application_id_str = options.applicationId.id
        else:
            application_id_str = options.applicationId
    app_context = await logger_service.application_context_service.get_application_context(
        overwrite_application=options.application if options else None,
        overwrite_application_id=application_id_str,
        overwrite_environment=options.environment if options else None,
    )

    return build_log_entry(
        level=level,
        message=message,
        context=request_context,
        config_client_id=logger_service.config.client_id,
        correlation_id=correlation_id,
        jwt_token=options.token if options else None,
        stack_trace=stack_trace,
        options=options,
        metadata=extract_metadata(),
        mask_sensitive=logger_service.mask_sensitive_data,
        application_context=app_context.to_dict(),
    )


async def get_with_context(
    logger_service: "LoggerService",
    context: Dict[str, Any],
    message: str,
    level: Literal["error", "audit", "info", "debug"] = "info",
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
    correlation_id = (
        final_options.correlationId if final_options else None
    ) or logger_service._generate_correlation_id()

    # Get application context (with overwrites from options)
    application_id_str: Optional[str] = None
    if final_options and final_options.applicationId:
        if isinstance(final_options.applicationId, ForeignKeyReference):
            application_id_str = final_options.applicationId.id
        else:
            application_id_str = final_options.applicationId
    app_context = await logger_service.application_context_service.get_application_context(
        overwrite_application=final_options.application if final_options else None,
        overwrite_application_id=application_id_str,
        overwrite_environment=final_options.environment if final_options else None,
    )

    return build_log_entry(
        level=level,
        message=message,
        context=context,
        config_client_id=logger_service.config.client_id,
        correlation_id=correlation_id,
        jwt_token=final_options.token if final_options else None,
        stack_trace=stack_trace,
        options=final_options,
        metadata=extract_metadata(),
        mask_sensitive=logger_service.mask_sensitive_data,
        application_context=app_context.to_dict(),
    )


async def get_with_token(
    logger_service: "LoggerService",
    token: str,
    message: str,
    level: Literal["error", "audit", "info", "debug"] = "info",
    context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None,
) -> "LogEntry":
    """Get LogEntry object with JWT token context extracted.

    Extracts userId, sessionId from JWT token.
    Returns LogEntry with user context extracted.

    Args:
        logger_service: LoggerService instance
        token: JWT token string
        message: Log message
        level: Log level (default: "info")
        context: Additional context data (optional)
        stack_trace: Stack trace for errors (optional)

    Returns:
        LogEntry object with user context extracted

    Example:
        >>> log_entry = await get_with_token(
        ...     logger,
        ...     "jwt-token",
        ...     "User action",
        ...     level="audit"
        ... )

    """
    options = ClientLoggingOptions(token=token)
    correlation_id = (
        options.correlationId if options else None
    ) or logger_service._generate_correlation_id()

    # Get application context (with overwrites from options)
    application_id_str: Optional[str] = None
    if options and options.applicationId:
        if isinstance(options.applicationId, ForeignKeyReference):
            application_id_str = options.applicationId.id
        else:
            application_id_str = options.applicationId
    app_context = await logger_service.application_context_service.get_application_context(
        overwrite_application=options.application if options else None,
        overwrite_application_id=application_id_str,
        overwrite_environment=options.environment if options else None,
    )

    return build_log_entry(
        level=level,
        message=message,
        context=context,
        config_client_id=logger_service.config.client_id,
        correlation_id=correlation_id,
        jwt_token=token,
        stack_trace=stack_trace,
        options=options,
        metadata=extract_metadata(),
        mask_sensitive=logger_service.mask_sensitive_data,
        application_context=app_context.to_dict(),
    )


async def get_for_request(
    logger_service: "LoggerService",
    request: Any,
    message: str,
    level: Literal["error", "audit", "info", "debug"] = "info",
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
