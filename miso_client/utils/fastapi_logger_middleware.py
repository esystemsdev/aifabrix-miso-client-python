"""FastAPI middleware helper for unified logging context.

This module provides FastAPI middleware to automatically set logger context
from request objects, enabling unified logging throughout the application.
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol

from ..utils.logger_helpers import extract_jwt_context
from ..utils.request_context import extract_request_context
from .logger_context_storage import set_logger_context


class URLLike(Protocol):
    """Minimal URL interface used by logger middleware."""

    @property
    def hostname(self) -> str | None:
        """Return URL hostname when available."""
        ...


class RequestLike(Protocol):
    """Minimal request interface used by logger middleware."""

    headers: Mapping[str, str]
    url: URLLike | None


class ResponseLike(Protocol):
    """Protocol marker for middleware response objects."""

    ...


def _extract_bearer_token(auth_header: str) -> str:
    """Extract JWT token from Bearer authorization header."""
    return auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""


def _extract_hostname(request: RequestLike) -> str | None:
    """Extract request hostname if available."""
    if request.url:
        return request.url.hostname
    return None


def _build_context_dict(
    request_context: object, jwt_context: dict[str, Any], hostname: str | None, jwt_token: str
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
    context_dict: dict[str, str | int | None], request_context: object
) -> None:
    """Populate context with values extracted from request object."""
    request_pairs = (
        ("ipAddress", getattr(request_context, "ip_address", None)),
        ("userAgent", getattr(request_context, "user_agent", None)),
        ("correlationId", getattr(request_context, "correlation_id", None)),
        ("method", getattr(request_context, "method", None)),
        ("path", getattr(request_context, "path", None)),
        ("userId", getattr(request_context, "user_id", None)),
        ("sessionId", getattr(request_context, "session_id", None)),
        ("requestId", getattr(request_context, "request_id", None)),
        ("referer", getattr(request_context, "referer", None)),
    )
    for key, value in request_pairs:
        if value:
            context_dict[key] = value
    request_size = getattr(request_context, "request_size", None)
    if request_size is not None:
        context_dict["requestSize"] = request_size


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


def _prepare_logger_context(request: RequestLike) -> dict[str, str | int | None]:
    """Prepare complete logger context dictionary from incoming request."""
    request_context = extract_request_context(request)
    headers = request.headers
    auth_header = headers.get("authorization", "")
    jwt_token = _extract_bearer_token(auth_header)
    jwt_context = extract_jwt_context(jwt_token) if jwt_token else {}
    hostname = _extract_hostname(request)
    return _build_context_dict(request_context, jwt_context, hostname, jwt_token)


async def logger_context_middleware(
    request: RequestLike, call_next: Callable[[RequestLike], Awaitable[ResponseLike]]
) -> ResponseLike:
    """Set logger context for request lifetime in FastAPI middleware."""
    set_logger_context(_prepare_logger_context(request))

    try:
        response = await call_next(request)
        return response
    finally:
        # Clear context after request completes
        from .logger_context_storage import clear_logger_context

        clear_logger_context()
