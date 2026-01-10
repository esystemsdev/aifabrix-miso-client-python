"""
Unit tests for unified logger factory functions.

This module contains comprehensive tests for get_logger() factory function
and related context management functions.
"""

from unittest.mock import MagicMock

import pytest

from miso_client.services.logger import LoggerService
from miso_client.services.unified_logger import UnifiedLogger
from miso_client.utils.unified_logger_factory import (
    clear_logger_context,
    get_logger,
    set_default_logger_service,
    set_logger_context,
)


class TestGetLogger:
    """Test cases for get_logger() factory function."""

    @pytest.fixture
    def mock_logger_service(self):
        """Mock LoggerService instance."""
        logger = MagicMock(spec=LoggerService)
        logger.info = MagicMock()
        logger.error = MagicMock()
        logger.audit = MagicMock()
        return logger

    def test_get_logger_with_provided_service(self, mock_logger_service):
        """Test get_logger() with provided logger service."""
        logger = get_logger(logger_service=mock_logger_service)

        assert isinstance(logger, UnifiedLogger)
        assert logger.logger_service is mock_logger_service

    def test_get_logger_with_default_service(self, mock_logger_service):
        """Test get_logger() with default logger service."""
        # Set default service
        set_default_logger_service(mock_logger_service)

        try:
            logger = get_logger()

            assert isinstance(logger, UnifiedLogger)
            assert logger.logger_service is mock_logger_service
        finally:
            # Clean up
            set_default_logger_service(None)

    def test_get_logger_no_service_raises_error(self):
        """Test get_logger() raises RuntimeError when no service available."""
        # Clear default service
        set_default_logger_service(None)

        with pytest.raises(RuntimeError) as exc_info:
            get_logger()

        assert "No logger service available" in str(exc_info.value)

    def test_get_logger_provided_overrides_default(self, mock_logger_service):
        """Test that provided service overrides default."""
        default_service = MagicMock(spec=LoggerService)
        provided_service = MagicMock(spec=LoggerService)

        set_default_logger_service(default_service)

        try:
            logger = get_logger(logger_service=provided_service)

            assert logger.logger_service is provided_service
            assert logger.logger_service is not default_service
        finally:
            set_default_logger_service(None)

    def test_get_logger_creates_new_storage_instance(self, mock_logger_service):
        """Test that get_logger() creates new storage instance each time."""
        logger1 = get_logger(logger_service=mock_logger_service)
        logger2 = get_logger(logger_service=mock_logger_service)

        # Each logger should have its own storage instance
        assert logger1.context_storage is not logger2.context_storage


class TestSetDefaultLoggerService:
    """Test cases for set_default_logger_service() function."""

    @pytest.fixture
    def mock_logger_service(self):
        """Mock LoggerService instance."""
        return MagicMock(spec=LoggerService)

    def test_set_default_logger_service(self, mock_logger_service):
        """Test setting default logger service."""
        try:
            set_default_logger_service(mock_logger_service)

            logger = get_logger()
            assert logger.logger_service is mock_logger_service
        finally:
            set_default_logger_service(None)

    def test_set_default_logger_service_none(self, mock_logger_service):
        """Test clearing default logger service."""
        set_default_logger_service(mock_logger_service)
        set_default_logger_service(None)

        with pytest.raises(RuntimeError):
            get_logger()


class TestContextManagementFunctions:
    """Test cases for context management helper functions."""

    def test_set_logger_context_function(self):
        """Test set_logger_context() helper function."""
        try:
            test_context = {
                "userId": "user-123",
                "correlationId": "corr-456",
            }

            set_logger_context(test_context)

            from miso_client.utils.logger_context_storage import get_logger_context

            context = get_logger_context()

            assert context == test_context
        finally:
            clear_logger_context()

    def test_clear_logger_context_function(self):
        """Test clear_logger_context() helper function."""
        set_logger_context({"userId": "user-123"})
        clear_logger_context()

        from miso_client.utils.logger_context_storage import get_logger_context

        context = get_logger_context()

        assert context is None
