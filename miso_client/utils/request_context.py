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
    """
    Protocol for HTTP request objects.

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
    """
    Extract logging context from HTTP request object.

    Supports multiple Python web frameworks:
    - FastAPI/Starlette Request
    - Flask Request
    - Generic dict-like request objects

    Args:
        request: HTTP request object

    Returns:
        RequestContext with extracted fields

    Example:
        >>> from fastapi import Request
        >>> ctx = extract_request_context(request)
        >>> await logger.with_request(request).info("Processing")
    """
    # Extract IP address (handle proxies)
    ip_address = _extract_ip_address(request)

    # Extract correlation ID from common headers
    correlation_id = _extract_correlation_id(request)

    # Extract user from JWT if available
    user_id, session_id = _extract_user_from_auth_header(request)

    # Extract method
    method = _extract_method(request)

    # Extract path
    path = _extract_path(request)

    # Extract other headers
    headers = _get_headers(request)
    user_agent = headers.get("user-agent")
    referer = headers.get("referer")
    request_id = headers.get("x-request-id")

    # Extract request size
    content_length = headers.get("content-length")
    request_size = int(content_length) if content_length else None

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

    # FastAPI/Starlette: request.client.host
    # Check if client exists and has host attribute with actual value
    if hasattr(request, "client") and request.client:
        try:
            host = getattr(request.client, "host", None)
            # Check if host is a real value (string) and not a MagicMock
            if isinstance(host, str):
                return host
        except Exception:
            pass

    # Flask: request.remote_addr
    if hasattr(request, "remote_addr"):
        try:
            remote_addr = getattr(request, "remote_addr", None)
            # Check if remote_addr is a real value (string) and not a MagicMock
            if isinstance(remote_addr, str):
                return remote_addr
        except Exception:
            pass

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
    if hasattr(request, "method"):
        try:
            method = getattr(request, "method", None)
            # Check if method is a real value (string) and not a MagicMock
            if isinstance(method, str):
                return method
        except Exception:
            pass
    return None


def _extract_path(request: Any) -> Optional[str]:
    """Extract request path from request."""
    # FastAPI/Starlette: request.url.path
    if hasattr(request, "url") and request.url:
        try:
            url_path = getattr(request.url, "path", None)
            # Check if path is a real value (string) and not a MagicMock
            if isinstance(url_path, str):
                return url_path
        except Exception:
            pass

    # Flask: request.path
    if hasattr(request, "path"):
        try:
            path = getattr(request, "path", None)
            # Check if path is a real value (string) and not a MagicMock
            if isinstance(path, str):
                return path
        except Exception:
            pass

    # Try original_url (some frameworks)
    if hasattr(request, "original_url"):
        try:
            original_url = getattr(request, "original_url", None)
            # Check if original_url is a real value (string) and not a MagicMock
            if isinstance(original_url, str):
                return original_url
        except Exception:
            pass

    return None


def _extract_user_from_auth_header(request: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract user ID and session ID from Authorization header JWT.

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

        user_id = (
            decoded.get("sub")
            or decoded.get("userId")
            or decoded.get("user_id")
            or decoded.get("id")
        )
        session_id = decoded.get("sessionId") or decoded.get("sid")

        return user_id, session_id
    except Exception:
        return None, None
