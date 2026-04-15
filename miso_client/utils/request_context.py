"""Request context extraction utilities for HTTP requests."""

from typing import Any, Dict, Optional, Protocol, Tuple, runtime_checkable

from ..utils.jwt_tools import decode_token


@runtime_checkable
class RequestHeaders(Protocol):
    """Protocol for request headers access."""

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get header value by key."""
        ...


@runtime_checkable
class RequestClient(Protocol):
    """Protocol for request client info."""

    host: Optional[str]


@runtime_checkable
class RequestURL(Protocol):
    """Protocol for request URL."""

    path: str


@runtime_checkable
class HttpRequest(Protocol):
    """Protocol for HTTP request objects.

    Supports:
    - FastAPI/Starlette Request
    - Flask Request
    - Generic dict-like request objects
    """

    method: str
    headers: RequestHeaders
    client: Optional[RequestClient]
    url: Optional[RequestURL]


class RequestContext:
    """Container for extracted request context."""

    def __init__(
        self,
        ip_address: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[str] = None,
        referer: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        request_size: Optional[int] = None,
    ):
        """Initialize request context."""
        self.ip_address = ip_address
        self.method = method
        self.path = path
        self.user_agent = user_agent
        self.correlation_id = correlation_id
        self.referer = referer
        self.user_id = user_id
        self.session_id = session_id
        self.request_id = request_id
        self.request_size = request_size

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


def extract_request_context(request: Any) -> RequestContext:
    """Extract logging context from an HTTP request object."""
    values = _extract_context_values(request)
    return _build_request_context(
        ip_address=values["ip_address"],
        method=values["method"],
        path=values["path"],
        user_agent=values["user_agent"],
        correlation_id=values["correlation_id"],
        referer=values["referer"],
        user_id=values["user_id"],
        session_id=values["session_id"],
        request_id=values["request_id"],
        request_size=values["request_size"],
    )


def _extract_context_values(request: Any) -> Dict[str, Any]:
    """Extract primitive request context values for RequestContext creation."""
    headers = _get_headers(request)
    user_id, session_id = _extract_user_from_auth_header(request)
    user_agent, referer, request_id = _extract_header_fields(headers)
    return {
        "ip_address": _extract_ip_address(request),
        "method": _extract_method(request),
        "path": _extract_path(request),
        "user_agent": user_agent,
        "correlation_id": _extract_correlation_id(request),
        "referer": referer,
        "user_id": user_id,
        "session_id": session_id,
        "request_id": request_id,
        "request_size": _extract_request_size(headers),
    }


def _build_request_context(
    *,
    ip_address: Optional[str],
    method: Optional[str],
    path: Optional[str],
    user_agent: Optional[str],
    correlation_id: Optional[str],
    referer: Optional[str],
    user_id: Optional[str],
    session_id: Optional[str],
    request_id: Optional[str],
    request_size: Optional[int],
) -> RequestContext:
    """Create RequestContext instance from extracted primitive values."""
    return RequestContext(
        ip_address=ip_address,
        method=method,
        path=path,
        user_agent=user_agent,
        correlation_id=correlation_id,
        referer=referer,
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        request_size=request_size,
    )


def _get_headers(request: Any) -> Dict[str, Optional[str]]:
    """Get headers from request object."""
    # FastAPI/Starlette
    if hasattr(request, "headers"):
        headers = request.headers
        if hasattr(headers, "get"):
            # Type cast to satisfy type checker - headers.get() returns Optional[str]
            return headers  # type: ignore[no-any-return]
        # Convert to dict if needed
        if hasattr(headers, "items"):
            return dict(headers.items())
    return {}


def _extract_header_fields(
    headers: Dict[str, Optional[str]],
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract common logger-related header fields."""
    return headers.get("user-agent"), headers.get("referer"), headers.get("x-request-id")


def _extract_request_size(headers: Dict[str, Optional[str]]) -> Optional[int]:
    """Extract request body size from content-length header."""
    content_length = headers.get("content-length")
    if not content_length:
        return None
    try:
        return int(content_length)
    except (TypeError, ValueError):
        return None


def _extract_attr_str(source: Any, attr_name: str) -> Optional[str]:
    """Return a string attribute if available and valid."""
    try:
        value = getattr(source, attr_name, None)
        return value if isinstance(value, str) else None
    except Exception:
        return None


def _extract_ip_address(request: Any) -> Optional[str]:
    """Extract client IP address, handling proxies."""
    headers = _get_headers(request)

    # Check x-forwarded-for first (proxy/load balancer)
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        # Take first IP in chain
        return forwarded_for.split(",")[0].strip()

    # Check x-real-ip
    real_ip = headers.get("x-real-ip")
    if real_ip:
        return real_ip

    if hasattr(request, "client") and request.client:
        host = _extract_attr_str(request.client, "host")
        if host:
            return host

    if hasattr(request, "remote_addr"):
        remote_addr = _extract_attr_str(request, "remote_addr")
        if remote_addr:
            return remote_addr

    return None


def _extract_correlation_id(request: Any) -> Optional[str]:
    """Extract correlation ID from common headers."""
    headers = _get_headers(request)

    return (
        headers.get("x-correlation-id")
        or headers.get("x-request-id")
        or headers.get("request-id")
        or headers.get("traceparent")  # W3C Trace Context
    )


def _extract_method(request: Any) -> Optional[str]:
    """Extract HTTP method from request."""
    return _extract_attr_str(request, "method") if hasattr(request, "method") else None


def _extract_first_path_candidate(request: Any, attr_name: str) -> Optional[str]:
    """Extract first available path string from request or nested URL object."""
    if attr_name == "path" and hasattr(request, "url") and request.url:
        path_value = _extract_attr_str(request.url, "path")
        if path_value:
            return path_value
    if hasattr(request, attr_name):
        return _extract_attr_str(request, attr_name)
    return None


def _extract_path(request: Any) -> Optional[str]:
    """Extract request path from request."""
    for candidate in ("path", "original_url"):
        value = _extract_first_path_candidate(request, candidate)
        if value:
            return value
    return None


def _extract_user_from_auth_header(request: Any) -> Tuple[Optional[str], Optional[str]]:
    """Extract user ID and session ID from Authorization header JWT.

    Args:
        request: HTTP request object

    Returns:
        Tuple of (user_id, session_id)

    """
    headers = _get_headers(request)
    auth_header = headers.get("authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None, None

    try:
        token = auth_header[7:]  # Remove "Bearer " prefix
        decoded = decode_token(token)
        if not decoded:
            return None, None

        return _extract_identity_fields(decoded)
    except Exception:
        return None, None


def _extract_identity_fields(decoded: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Extract user and session identifiers from decoded JWT payload."""
    user_id = (
        decoded.get("sub") or decoded.get("userId") or decoded.get("user_id") or decoded.get("id")
    )
    session_id = decoded.get("sessionId") or decoded.get("sid")
    return user_id, session_id
