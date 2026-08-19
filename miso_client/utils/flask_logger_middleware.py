"""Flask middleware helper for unified logging context.

This module provides Flask middleware to automatically set logger context
from request objects, enabling unified logging throughout the application.
"""

import importlib
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

from ..utils.logger_helpers import extract_jwt_context
from ..utils.request_context import extract_request_context
from .logger_context_storage import clear_logger_context, set_logger_context


class FlaskRequestLike(Protocol):
    """Minimal Flask request surface needed by this middleware."""

    headers: Mapping[str, str]
    host: str


class FlaskAppLike(Protocol):
    """Minimal Flask app surface needed by this middleware."""

    def before_request(self, func: Callable[[], None]) -> Any: ...

    def after_request(self, func: Callable[[Any], Any]) -> Any: ...


def _extract_bearer_token(auth_header: str) -> str:
    """Extract JWT token from Bearer authorization header."""
    return auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""


def _build_context_dict(
    request_context: Any, jwt_context: dict[str, Any], hostname: str | None, jwt_token: str
) -> dict[str, str | int | None]:
    """Build logger context dictionary from request and JWT context."""
    context_dict: dict[str, str | int | None] = {}
    _apply_request_context_fields(context_dict, request_context)
    _apply_jwt_context_fields(context_dict, jwt_context)
    if hostname:
        context_dict["hostname"] = hostname
    if jwt_token:
        context_dict["token"] = jwt_token
    return context_dict


def _apply_request_context_fields(
    context_dict: dict[str, str | int | None], request_context: Any
) -> None:
    """Populate context with values extracted from request object."""
    request_pairs = (
        ("ipAddress", request_context.ip_address),
        ("userAgent", request_context.user_agent),
        ("correlationId", request_context.correlation_id),
        ("method", request_context.method),
        ("path", request_context.path),
        ("userId", request_context.user_id),
        ("sessionId", request_context.session_id),
        ("requestId", request_context.request_id),
        ("referer", request_context.referer),
    )
    for key, value in request_pairs:
        if value:
            context_dict[key] = value
    if request_context.request_size is not None:
        context_dict["requestSize"] = request_context.request_size


def _apply_jwt_context_fields(
    context_dict: dict[str, str | int | None], jwt_context: dict[str, Any]
) -> None:
    """Populate context with values extracted from JWT token payload."""
    if jwt_context.get("userId"):
        context_dict["userId"] = jwt_context["userId"]
    if jwt_context.get("applicationId"):
        context_dict["applicationId"] = jwt_context["applicationId"]
    if jwt_context.get("sessionId"):
        context_dict["sessionId"] = jwt_context["sessionId"]


def _get_runtime_request() -> FlaskRequestLike | None:
    """Load Flask request object dynamically when Flask is installed."""
    try:
        flask_module = importlib.import_module("flask")
    except Exception:
        return None
    request_obj = getattr(flask_module, "request", None)
    return cast(FlaskRequestLike | None, request_obj)


def logger_context_middleware() -> None:
    """Flask middleware to set logger context from request.

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
    request = _get_runtime_request()
    if request is None:
        return
    request_context = extract_request_context(request)
    auth_header = request.headers.get("authorization", "")
    jwt_token = _extract_bearer_token(auth_header)
    jwt_context = extract_jwt_context(jwt_token) if jwt_token else {}
    hostname = request.host if hasattr(request, "host") else None
    context_dict = _build_context_dict(request_context, jwt_context, hostname, jwt_token)
    set_logger_context(context_dict)


def register_logger_context_middleware(app: FlaskAppLike) -> None:
    """Register logger context middleware with Flask app.

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

    def after_request_handler(response: Any) -> Any:
        """Clear per-request logger context after response is processed."""
        clear_logger_context()
        return response

    app.after_request(after_request_handler)
