"""
Flask middleware helper for unified logging context.

This module provides Flask middleware to automatically set logger context
from request objects, enabling unified logging throughout the application.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

from ..utils.logger_helpers import extract_jwt_context
from ..utils.request_context import extract_request_context
from .logger_context_storage import clear_logger_context, set_logger_context


def logger_context_middleware() -> None:
    """
    Flask middleware to set logger context from request.

    Use with @app.before_request decorator to enable automatic context
    extraction for unified logging.

    Example:
        >>> from flask import Flask
        >>> from miso_client.utils.flask_logger_middleware import logger_context_middleware
        >>> app = Flask(__name__)
        >>> @app.before_request
        ... def before_request():
        ...     logger_context_middleware()
    """
    from flask import request

    # Extract request context
    request_context = extract_request_context(request)

    # Extract JWT context from Authorization header
    auth_header = request.headers.get("authorization", "")
    jwt_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    jwt_context = extract_jwt_context(jwt_token) if jwt_token else {}

    # Extract hostname from request
    hostname = request.host if hasattr(request, "host") else None

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


def register_logger_context_middleware(app: "Flask") -> None:
    """
    Register logger context middleware with Flask app.

    Convenience function to register the middleware automatically.

    Args:
        app: Flask application instance

    Example:
        >>> from flask import Flask
        >>> from miso_client.utils.flask_logger_middleware import register_logger_context_middleware
        >>> app = Flask(__name__)
        >>> register_logger_context_middleware(app)
    """
    app.before_request(logger_context_middleware)

    def after_request_handler(response):
        clear_logger_context()
        return response

    app.after_request(after_request_handler)
