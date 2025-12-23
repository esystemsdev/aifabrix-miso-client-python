"""
Unit tests for request context extraction utilities.
"""

from unittest.mock import MagicMock

import jwt

from miso_client.utils.request_context import (
    RequestContext,
    _extract_correlation_id,
    _extract_ip_address,
    _extract_method,
    _extract_path,
    _extract_user_from_auth_header,
    _get_headers,
    extract_request_context,
)


class TestRequestContext:
    """Test cases for RequestContext class."""

    def test_request_context_init(self):
        """Test RequestContext initialization."""
        ctx = RequestContext(
            ip_address="192.168.1.1",
            method="GET",
            path="/api/test",
            user_agent="Mozilla/5.0",
            correlation_id="corr-123",
            user_id="user-456",
        )

        assert ctx.ip_address == "192.168.1.1"
        assert ctx.method == "GET"
        assert ctx.path == "/api/test"
        assert ctx.user_agent == "Mozilla/5.0"
        assert ctx.correlation_id == "corr-123"
        assert ctx.user_id == "user-456"

    def test_request_context_to_dict(self):
        """Test RequestContext.to_dict() excludes None values."""
        ctx = RequestContext(
            ip_address="192.168.1.1",
            method="GET",
            path=None,  # None value
            user_agent="Mozilla/5.0",
        )

        result = ctx.to_dict()

        assert "ip_address" in result
        assert "method" in result
        assert "path" not in result  # None excluded
        assert "user_agent" in result


class TestGetHeaders:
    """Test cases for _get_headers function."""

    def test_get_headers_fastapi_style(self):
        """Test headers extraction from FastAPI/Starlette request."""
        mock_headers = MagicMock()
        mock_headers.get = MagicMock(side_effect=lambda k, d=None: {"user-agent": "test"}.get(k, d))

        request = MagicMock()
        request.headers = mock_headers

        headers = _get_headers(request)

        assert headers.get("user-agent") == "test"

    def test_get_headers_dict_like(self):
        """Test headers extraction from dict-like object."""
        request = MagicMock()
        request.headers = {"user-agent": "test", "authorization": "Bearer token"}

        headers = _get_headers(request)

        assert headers.get("user-agent") == "test"
        assert headers.get("authorization") == "Bearer token"

    def test_get_headers_no_headers(self):
        """Test headers extraction when request has no headers."""
        request = MagicMock()
        del request.headers

        headers = _get_headers(request)

        assert headers == {}


class TestExtractIPAddress:
    """Test cases for _extract_ip_address function."""

    def test_extract_ip_from_x_forwarded_for(self):
        """Test IP extraction from x-forwarded-for header."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}.get(k, d)
        )

        ip = _extract_ip_address(request)

        assert ip == "192.168.1.1"  # First IP in chain

    def test_extract_ip_from_x_real_ip(self):
        """Test IP extraction from x-real-ip header."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {"x-real-ip": "192.168.1.2"}.get(k, d)
        )

        ip = _extract_ip_address(request)

        assert ip == "192.168.1.2"

    def test_extract_ip_from_client_host(self):
        """Test IP extraction from request.client.host (FastAPI/Starlette)."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)
        request.client = MagicMock()
        request.client.host = "192.168.1.3"

        ip = _extract_ip_address(request)

        assert ip == "192.168.1.3"

    def test_extract_ip_from_remote_addr(self):
        """Test IP extraction from request.remote_addr (Flask)."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)
        request.remote_addr = "192.168.1.4"

        ip = _extract_ip_address(request)

        assert ip == "192.168.1.4"

    def test_extract_ip_none(self):
        """Test IP extraction when no IP available."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        ip = _extract_ip_address(request)

        assert ip is None


class TestExtractCorrelationId:
    """Test cases for _extract_correlation_id function."""

    def test_extract_correlation_from_x_correlation_id(self):
        """Test correlation ID extraction from x-correlation-id header."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {"x-correlation-id": "corr-123"}.get(k, d)
        )

        corr_id = _extract_correlation_id(request)

        assert corr_id == "corr-123"

    def test_extract_correlation_from_x_request_id(self):
        """Test correlation ID extraction from x-request-id header."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {"x-request-id": "req-456"}.get(k, d)
        )

        corr_id = _extract_correlation_id(request)

        assert corr_id == "req-456"

    def test_extract_correlation_from_traceparent(self):
        """Test correlation ID extraction from traceparent header (W3C Trace Context)."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
            }.get(k, d)
        )

        corr_id = _extract_correlation_id(request)

        assert corr_id == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    def test_extract_correlation_none(self):
        """Test correlation ID extraction when not available."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        corr_id = _extract_correlation_id(request)

        assert corr_id is None


class TestExtractMethod:
    """Test cases for _extract_method function."""

    def test_extract_method_get(self):
        """Test method extraction."""
        request = MagicMock()
        request.method = "GET"

        method = _extract_method(request)

        assert method == "GET"

    def test_extract_method_post(self):
        """Test POST method extraction."""
        request = MagicMock()
        request.method = "POST"

        method = _extract_method(request)

        assert method == "POST"

    def test_extract_method_none(self):
        """Test method extraction when not available."""
        request = MagicMock()
        del request.method

        method = _extract_method(request)

        assert method is None


class TestExtractPath:
    """Test cases for _extract_path function."""

    def test_extract_path_from_url_path(self):
        """Test path extraction from request.url.path (FastAPI/Starlette)."""
        request = MagicMock()
        request.url = MagicMock()
        request.url.path = "/api/test"

        path = _extract_path(request)

        assert path == "/api/test"

    def test_extract_path_from_path(self):
        """Test path extraction from request.path (Flask)."""
        request = MagicMock()
        request.path = "/api/flask"

        path = _extract_path(request)

        assert path == "/api/flask"

    def test_extract_path_none(self):
        """Test path extraction when not available."""
        request = MagicMock()

        path = _extract_path(request)

        assert path is None


class TestExtractUserFromAuthHeader:
    """Test cases for _extract_user_from_auth_header function."""

    def test_extract_user_from_bearer_token(self):
        """Test user extraction from Bearer token."""
        payload = {"sub": "user-123", "sessionId": "session-456"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {"authorization": f"Bearer {token}"}.get(k, d)
        )

        user_id, session_id = _extract_user_from_auth_header(request)

        assert user_id == "user-123"
        assert session_id == "session-456"

    def test_extract_user_from_user_id_claim(self):
        """Test user extraction from userId claim."""
        payload = {"userId": "user-789"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {"authorization": f"Bearer {token}"}.get(k, d)
        )

        user_id, session_id = _extract_user_from_auth_header(request)

        assert user_id == "user-789"
        assert session_id is None

    def test_extract_user_no_auth_header(self):
        """Test user extraction when no authorization header."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        user_id, session_id = _extract_user_from_auth_header(request)

        assert user_id is None
        assert session_id is None

    def test_extract_user_invalid_token(self):
        """Test user extraction with invalid token."""
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {"authorization": "Bearer invalid.token"}.get(k, d)
        )

        user_id, session_id = _extract_user_from_auth_header(request)

        assert user_id is None
        assert session_id is None


class TestExtractRequestContext:
    """Test cases for extract_request_context function."""

    def test_extract_full_context(self):
        """Test full context extraction from request."""
        payload = {"sub": "user-123", "sessionId": "session-456"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        request = MagicMock()
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/test"
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "authorization": f"Bearer {token}",
                "user-agent": "Mozilla/5.0",
                "x-correlation-id": "corr-123",
                "referer": "https://example.com",
                "content-length": "1024",
            }.get(k, d)
        )

        ctx = extract_request_context(request)

        assert ctx.ip_address == "192.168.1.1"
        assert ctx.method == "POST"
        assert ctx.path == "/api/test"
        assert ctx.user_agent == "Mozilla/5.0"
        assert ctx.correlation_id == "corr-123"
        assert ctx.referer == "https://example.com"
        assert ctx.user_id == "user-123"
        assert ctx.session_id == "session-456"
        assert ctx.request_size == 1024

    def test_extract_minimal_context(self):
        """Test context extraction with minimal request data."""
        request = MagicMock()
        request.method = "GET"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        ctx = extract_request_context(request)

        assert ctx.method == "GET"
        assert ctx.ip_address is None
        assert ctx.user_id is None

    def test_extract_context_with_x_forwarded_for(self):
        """Test context extraction with proxy headers."""
        request = MagicMock()
        request.method = "GET"
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {"x-forwarded-for": "10.0.0.1, 192.168.1.1"}.get(k, d)
        )

        ctx = extract_request_context(request)

        assert ctx.ip_address == "10.0.0.1"  # First IP in chain
