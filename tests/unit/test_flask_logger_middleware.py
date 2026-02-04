"""
Unit tests for Flask logger context middleware.

This module contains comprehensive tests for Flask middleware that
sets logger context from request objects.
"""

import sys
from unittest.mock import MagicMock

import pytest

from miso_client.utils.flask_logger_middleware import (
    logger_context_middleware,
    register_logger_context_middleware,
)
from miso_client.utils.logger_context_storage import clear_logger_context, get_logger_context


class TestFlaskLoggerContextMiddleware:
    """Test cases for Flask logger context middleware."""

    @pytest.fixture
    def mock_flask_request(self):
        """Mock Flask request object."""
        request = MagicMock()

        # Mock headers
        headers = MagicMock()
        headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "authorization": "Bearer test-token",
                "user-agent": "test-agent",
                "x-correlation-id": "corr-123",
                "x-request-id": "req-456",
                "referer": "https://example.com",
                "content-length": "1024",
            }.get(k.lower(), d)
        )
        request.headers = headers

        # Mock host
        request.host = "example.com"

        # Mock remote_addr
        request.remote_addr = "127.0.0.1"

        return request

    def test_middleware_sets_context(self, mock_flask_request):
        """Test that middleware sets context from request."""
        mock_flask_module = MagicMock()
        mock_flask_module.request = mock_flask_request
        sys.modules["flask"] = mock_flask_module
        try:
            logger_context_middleware()

            context = get_logger_context()

            assert context is not None
            assert context["ipAddress"] == "127.0.0.1"
            assert context["userAgent"] == "test-agent"
            assert context["correlationId"] == "corr-123"
            assert context["requestId"] == "req-456"
            assert context["hostname"] == "example.com"
            assert context["referer"] == "https://example.com"
            assert context["requestSize"] == 1024
            assert context["token"] == "test-token"
        finally:
            clear_logger_context()
            if "flask" in sys.modules and isinstance(sys.modules["flask"], MagicMock):
                del sys.modules["flask"]

    def test_middleware_without_auth_header(self, mock_flask_request):
        """Test middleware without Authorization header."""
        # Remove authorization header
        mock_flask_request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "user-agent": "test-agent",
            }.get(k.lower(), d)
        )

        mock_flask_module = MagicMock()
        mock_flask_module.request = mock_flask_request
        sys.modules["flask"] = mock_flask_module
        try:
            logger_context_middleware()

            context = get_logger_context()
            # Should still set context but without token
            assert context is not None
            assert "token" not in context or context["token"] == ""
        finally:
            clear_logger_context()
            if "flask" in sys.modules and isinstance(sys.modules["flask"], MagicMock):
                del sys.modules["flask"]

    def test_middleware_extracts_jwt_context(self, mock_flask_request):
        """Test that middleware extracts JWT context."""
        mock_flask_module = MagicMock()
        mock_flask_module.request = mock_flask_request
        sys.modules["flask"] = mock_flask_module
        try:
            logger_context_middleware()

            context = get_logger_context()
            # JWT context extraction is tested in test_logger_helpers.py
            # Here we just verify context is set
            assert context is not None
        finally:
            clear_logger_context()
            if "flask" in sys.modules and isinstance(sys.modules["flask"], MagicMock):
                del sys.modules["flask"]


class TestRegisterLoggerContextMiddleware:
    """Test cases for register_logger_context_middleware() function."""

    @pytest.fixture
    def mock_flask_app(self):
        """Mock Flask application."""
        app = MagicMock()
        app.before_request = MagicMock()
        app.after_request = MagicMock()
        return app

    def test_register_middleware(self, mock_flask_app):
        """Test registering middleware with Flask app."""
        register_logger_context_middleware(mock_flask_app)

        # Should register before_request handler
        mock_flask_app.before_request.assert_called_once()

        # Should register after_request handler
        mock_flask_app.after_request.assert_called_once()

    def test_before_request_handler(self, mock_flask_app):
        """Test that before_request handler calls middleware."""
        register_logger_context_middleware(mock_flask_app)

        # Get the registered handler
        before_handler = mock_flask_app.before_request.call_args[0][0]

        # Mock request with all required attributes
        mock_request = MagicMock()
        headers = MagicMock()
        headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "authorization": "Bearer test-token",
                "user-agent": "test-agent",
                "x-correlation-id": "corr-123",
            }.get(k.lower(), d)
        )
        mock_request.headers = headers
        mock_request.host = "example.com"
        mock_request.remote_addr = "127.0.0.1"
        mock_request.method = "GET"
        mock_request.path = "/test"

        mock_flask_module = MagicMock()
        mock_flask_module.request = mock_request
        sys.modules["flask"] = mock_flask_module
        try:
            before_handler()

            context = get_logger_context()
            assert context is not None
        finally:
            clear_logger_context()
            if "flask" in sys.modules and isinstance(sys.modules["flask"], MagicMock):
                del sys.modules["flask"]

    def test_after_request_handler(self, mock_flask_app):
        """Test that after_request handler clears context."""
        register_logger_context_middleware(mock_flask_app)

        # Set some context first
        from miso_client.utils.logger_context_storage import set_logger_context

        set_logger_context({"userId": "user-123"})

        # Get the registered handler
        after_handler = mock_flask_app.after_request.call_args[0][0]

        # Mock response
        mock_response = MagicMock()

        # Call handler
        result = after_handler(mock_response)

        # Context should be cleared
        context = get_logger_context()
        assert context is None

        # Handler should return response
        assert result is mock_response
