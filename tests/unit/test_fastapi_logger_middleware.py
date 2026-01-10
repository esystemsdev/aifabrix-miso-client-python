"""
Unit tests for FastAPI logger context middleware.

This module contains comprehensive tests for FastAPI middleware that
sets logger context from request objects.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.utils.fastapi_logger_middleware import logger_context_middleware
from miso_client.utils.logger_context_storage import clear_logger_context, get_logger_context


class TestFastAPILoggerContextMiddleware:
    """Test cases for FastAPI logger context middleware."""

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI Request object."""
        request = MagicMock()

        # Mock headers
        headers = MagicMock()
        headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "authorization": "Bearer test-token",
                "user-agent": "test-agent",
                "x-correlation-id": "corr-123",
            }.get(k.lower(), d)
        )
        request.headers = headers

        # Mock URL
        url = MagicMock()
        url.hostname = "example.com"
        request.url = url

        # Mock client
        client = MagicMock()
        client.host = "127.0.0.1"
        request.client = client

        return request

    @pytest.fixture
    def mock_response(self):
        """Mock FastAPI Response object."""
        response = MagicMock()
        return response

    @pytest.fixture
    def mock_call_next(self, mock_response):
        """Mock call_next function."""
        return AsyncMock(return_value=mock_response)

    @pytest.mark.asyncio
    async def test_middleware_sets_context(self, mock_request, mock_call_next, mock_response):
        """Test that middleware sets context from request."""
        # Capture context during middleware execution
        captured_context = None

        async def capture_context(request):
            nonlocal captured_context
            captured_context = get_logger_context()
            return mock_response

        mock_call_next.side_effect = capture_context

        try:
            await logger_context_middleware(mock_request, mock_call_next)

            # Check captured context
            assert captured_context is not None
            assert captured_context["ipAddress"] == "127.0.0.1"
            assert captured_context["userAgent"] == "test-agent"
            assert captured_context["correlationId"] == "corr-123"
            assert captured_context["hostname"] == "example.com"
            assert captured_context["token"] == "test-token"

            mock_call_next.assert_called_once_with(mock_request)
        finally:
            clear_logger_context()

    @pytest.mark.asyncio
    async def test_middleware_clears_context_after_request(self, mock_request, mock_call_next):
        """Test that middleware clears context after request completes."""
        await logger_context_middleware(mock_request, mock_call_next)

        # Context should be cleared after request
        context = get_logger_context()
        assert context is None

    @pytest.mark.asyncio
    async def test_middleware_without_auth_header(
        self, mock_request, mock_call_next, mock_response
    ):
        """Test middleware without Authorization header."""
        # Remove authorization header
        mock_request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "user-agent": "test-agent",
            }.get(k.lower(), d)
        )

        # Capture context during middleware execution
        captured_context = None

        async def capture_context(request):
            nonlocal captured_context
            captured_context = get_logger_context()
            return mock_response

        mock_call_next.side_effect = capture_context

        try:
            await logger_context_middleware(mock_request, mock_call_next)

            # Check captured context
            assert captured_context is not None
            assert "token" not in captured_context or captured_context["token"] == ""
        finally:
            clear_logger_context()

    @pytest.mark.asyncio
    async def test_middleware_calls_next(self, mock_request, mock_call_next):
        """Test that middleware calls next middleware/handler."""
        await logger_context_middleware(mock_request, mock_call_next)

        mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_middleware_returns_response(self, mock_request, mock_call_next, mock_response):
        """Test that middleware returns response from next."""
        response = await logger_context_middleware(mock_request, mock_call_next)

        assert response is mock_response

    @pytest.mark.asyncio
    async def test_middleware_handles_exception(self, mock_request, mock_call_next):
        """Test that middleware clears context even if next raises exception."""
        mock_call_next.side_effect = Exception("Handler error")

        try:
            with pytest.raises(Exception):
                await logger_context_middleware(mock_request, mock_call_next)
        finally:
            # Context should still be cleared
            context = get_logger_context()
            assert context is None
