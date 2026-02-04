"""
Unit tests for UnifiedLogger service.

This module contains comprehensive tests for UnifiedLogger including
all logging methods, context extraction, and error handling.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.models.config import ClientLoggingOptions
from miso_client.services.logger import LoggerService
from miso_client.services.unified_logger import UnifiedLogger
from miso_client.utils.logger_context_storage import LoggerContextStorage


class TestUnifiedLogger:
    """Test cases for UnifiedLogger class."""

    @pytest.fixture
    def mock_logger_service(self):
        """Mock LoggerService instance."""
        logger = MagicMock(spec=LoggerService)
        logger.info = AsyncMock()
        logger.debug = AsyncMock()
        logger.error = AsyncMock()
        logger.audit = AsyncMock()
        return logger

    @pytest.fixture
    def context_storage(self):
        """LoggerContextStorage instance."""
        return LoggerContextStorage()

    @pytest.fixture
    def unified_logger(self, mock_logger_service, context_storage):
        """UnifiedLogger instance."""
        return UnifiedLogger(mock_logger_service, context_storage)

    def test_unified_logger_init(self, mock_logger_service):
        """Test UnifiedLogger initialization."""
        logger = UnifiedLogger(mock_logger_service)

        assert logger.logger_service is mock_logger_service
        assert isinstance(logger.context_storage, LoggerContextStorage)

    def test_unified_logger_init_with_storage(self, mock_logger_service, context_storage):
        """Test UnifiedLogger initialization with custom storage."""
        logger = UnifiedLogger(mock_logger_service, context_storage)

        assert logger.logger_service is mock_logger_service
        assert logger.context_storage is context_storage

    @pytest.mark.asyncio
    async def test_info_with_context(self, unified_logger, mock_logger_service, context_storage):
        """Test info() method with context."""
        context_storage.set_context(
            {
                "userId": "user-123",
                "correlationId": "corr-456",
                "ipAddress": "127.0.0.1",
            }
        )

        await unified_logger.info("Test message")

        mock_logger_service.info.assert_called_once()
        call_args = mock_logger_service.info.call_args
        assert call_args[0][0] == "Test message"
        assert "context" in call_args[1]
        assert isinstance(call_args[1]["options"], ClientLoggingOptions)

    @pytest.mark.asyncio
    async def test_info_without_context(self, unified_logger, mock_logger_service, context_storage):
        """Test info() method without context."""
        context_storage.clear_context()

        await unified_logger.info("Test message")

        mock_logger_service.info.assert_called_once()
        call_args = mock_logger_service.info.call_args
        assert call_args[0][0] == "Test message"

    @pytest.mark.asyncio
    async def test_warn_with_context(self, unified_logger, mock_logger_service, context_storage):
        """Test warn() method with context."""
        context_storage.set_context({"userId": "user-123"})

        await unified_logger.warn("Warning message")

        mock_logger_service.info.assert_called_once()
        call_args = mock_logger_service.info.call_args
        assert call_args[0][0] == "WARNING: Warning message"

    @pytest.mark.asyncio
    async def test_debug_with_context(self, unified_logger, mock_logger_service, context_storage):
        """Test debug() method with context."""
        context_storage.set_context({"userId": "user-123"})

        await unified_logger.debug("Debug message")

        mock_logger_service.debug.assert_called_once()
        call_args = mock_logger_service.debug.call_args
        assert call_args[0][0] == "Debug message"

    @pytest.mark.asyncio
    async def test_error_without_exception(
        self, unified_logger, mock_logger_service, context_storage
    ):
        """Test error() method without exception."""
        context_storage.set_context({"userId": "user-123"})

        await unified_logger.error("Error message")

        mock_logger_service.error.assert_called_once()
        call_args = mock_logger_service.error.call_args
        assert call_args[0][0] == "Error message"
        assert call_args[1]["stack_trace"] is None

    @pytest.mark.asyncio
    async def test_error_with_exception(self, unified_logger, mock_logger_service, context_storage):
        """Test error() method with exception."""
        context_storage.set_context({"userId": "user-123"})

        exception = ValueError("Test error")
        await unified_logger.error("Error message", exception)

        mock_logger_service.error.assert_called_once()
        call_args = mock_logger_service.error.call_args
        assert call_args[0][0] == "Error message"
        assert call_args[1]["stack_trace"] is not None
        assert "ValueError" in call_args[1]["stack_trace"]
        assert "Test error" in call_args[1]["stack_trace"]

        # Check error context was added
        context = call_args[1]["context"]
        assert context["errorName"] == "ValueError"
        assert context["errorMessage"] == "Test error"

    @pytest.mark.asyncio
    async def test_audit_minimal(self, unified_logger, mock_logger_service, context_storage):
        """Test audit() method with minimal parameters."""
        context_storage.set_context({"userId": "user-123"})

        await unified_logger.audit("CREATE", "User")

        mock_logger_service.audit.assert_called_once()
        call_args = mock_logger_service.audit.call_args
        assert call_args[0][0] == "CREATE"
        assert call_args[0][1] == "User"

        context = call_args[1]["context"]
        assert context["entityId"] == "unknown"

    @pytest.mark.asyncio
    async def test_audit_with_entity_id(self, unified_logger, mock_logger_service, context_storage):
        """Test audit() method with entity ID."""
        context_storage.set_context({"userId": "user-123"})

        await unified_logger.audit("UPDATE", "User", entity_id="user-456")

        mock_logger_service.audit.assert_called_once()
        call_args = mock_logger_service.audit.call_args
        context = call_args[1]["context"]
        assert context["entityId"] == "user-456"

    @pytest.mark.asyncio
    async def test_audit_with_old_and_new_values(
        self, unified_logger, mock_logger_service, context_storage
    ):
        """Test audit() method with old and new values."""
        context_storage.set_context({"userId": "user-123"})

        old_values = {"name": "Old Name", "email": "old@example.com"}
        new_values = {"name": "New Name", "email": "new@example.com"}

        await unified_logger.audit(
            "UPDATE", "User", entity_id="user-456", old_values=old_values, new_values=new_values
        )

        mock_logger_service.audit.assert_called_once()
        call_args = mock_logger_service.audit.call_args
        context = call_args[1]["context"]
        assert context["entityId"] == "user-456"
        assert context["oldValues"] == old_values
        assert context["newValues"] == new_values

    @pytest.mark.asyncio
    async def test_error_handling_silent(
        self, unified_logger, mock_logger_service, context_storage
    ):
        """Test that errors in logger are silently caught."""
        # Make logger_service.info raise an exception
        mock_logger_service.info = AsyncMock(side_effect=Exception("Logger error"))

        # Should not raise exception
        await unified_logger.info("Test message")

        # Should have attempted to call
        mock_logger_service.info.assert_called_once()

    def test_build_context_and_options(self, unified_logger, context_storage):
        """Test _build_context_and_options() method."""
        context_storage.set_context(
            {
                "userId": "user-123",
                "applicationId": "app-456",
                "correlationId": "corr-789",
                "ipAddress": "127.0.0.1",
                "userAgent": "test-agent",
                "method": "GET",
                "path": "/api/test",
                "hostname": "example.com",
                "customField": "custom-value",
            }
        )

        context, options = unified_logger._build_context_and_options()

        # Check options (only non-auto fields)
        assert options.application is None
        assert options.environment is None

        # Check context (auto-computable fields remain in context)
        assert context["userId"] == "user-123"
        assert context["applicationId"] == "app-456"
        assert context["correlationId"] == "corr-789"
        assert context["ipAddress"] == "127.0.0.1"
        assert context["userAgent"] == "test-agent"
        assert context["method"] == "GET"
        assert context["path"] == "/api/test"
        assert context["hostname"] == "example.com"
        assert context["customField"] == "custom-value"

    def test_extract_error_context(self, unified_logger):
        """Test _extract_error_context() method."""
        exception = ValueError("Test error")

        error_context = unified_logger._extract_error_context(exception)

        assert error_context["errorName"] == "ValueError"
        assert error_context["errorMessage"] == "Test error"

    def test_extract_error_context_none(self, unified_logger):
        """Test _extract_error_context() with None."""
        error_context = unified_logger._extract_error_context(None)

        assert error_context == {}

    def test_extract_stack_trace(self, unified_logger):
        """Test _extract_stack_trace() method."""
        exception = ValueError("Test error")

        stack_trace = unified_logger._extract_stack_trace(exception)

        assert stack_trace is not None
        assert "ValueError" in stack_trace
        assert "Test error" in stack_trace

    def test_extract_stack_trace_none(self, unified_logger):
        """Test _extract_stack_trace() with None."""
        stack_trace = unified_logger._extract_stack_trace(None)

        assert stack_trace is None
