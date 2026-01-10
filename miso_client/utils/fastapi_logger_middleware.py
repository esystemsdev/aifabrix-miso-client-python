"""
FastAPI middleware helper for unified logging context.

This module provides FastAPI middleware to automatically set logger context
from request objects, enabling unified logging throughout the application.
"""

from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from fastapi import Request, Response

from ..utils.logger_helpers import extract_jwt_context
from ..utils.request_context import extract_request_context
from .logger_context_storage import set_logger_context


async def logger_context_middleware(
    request: "Request", call_next: Callable[["Request"], Awaitable["Response"]]
) -> "Response":
    """
    FastAPI middleware to set logger context from request.

    Call this early in middleware chain (after auth middleware) to enable
    automatic context extraction for unified logging.

    Args:
        request: FastAPI Request object
        call_next: Next middleware/handler in chain

    Returns:
        Response object

    Example:
        >>> from fastapi import FastAPI
        >>> from miso_client.utils.fastapi_logger_middleware import logger_context_middleware
        >>> app = FastAPI()
        >>> app.middleware("http")(logger_context_middleware)
    """
    # Extract request context
    request_context = extract_request_context(request)

    # Extract JWT context from Authorization header
    headers = request.headers if hasattr(request, "headers") else {}
    auth_header = headers.get("authorization", "") if hasattr(headers, "get") else ""
    jwt_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    jwt_context = extract_jwt_context(jwt_token) if jwt_token else {}

    # Extract hostname from request
    hostname = None
    if hasattr(request, "url") and request.url:
        hostname = getattr(request.url, "hostname", None)

    # Build context dictionary
    context_dict: dict[str, str | None] = {}

    # Add request context fields
    if request_context.ip_address:
        context_dict["ipAddress"] = request_context.ip_address
    if request_context.user_agent:
        context_dict["userAgent"] = request_context.user_agent
    if request_context.correlation_id:
        context_dict["correlationId"] = request_context.correlation_id
    if request_context.method:
        context_dict["method"] = request_context.method
    if request_context.path:
        context_dict["path"] = request_context.path
    if request_context.user_id:
        context_dict["userId"] = request_context.user_id
    if request_context.session_id:
        context_dict["sessionId"] = request_context.session_id
    if request_context.request_id:
        context_dict["requestId"] = request_context.request_id

    # Add JWT context fields
    if jwt_context.get("userId"):
        context_dict["userId"] = jwt_context["userId"]
    if jwt_context.get("applicationId"):
        context_dict["applicationId"] = jwt_context["applicationId"]
    if jwt_context.get("sessionId"):
        context_dict["sessionId"] = jwt_context["sessionId"]

    # Add hostname
    if hostname:
        context_dict["hostname"] = hostname

    # Add token for potential future extraction
    if jwt_token:
        context_dict["token"] = jwt_token

    # Set context for this async execution context
    set_logger_context(context_dict)

    try:
        # Call next middleware/handler
        response = await call_next(request)
        return response
    finally:
        # Clear context after request completes
        from .logger_context_storage import clear_logger_context

        clear_logger_context()
