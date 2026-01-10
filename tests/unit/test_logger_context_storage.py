"""
Unit tests for logger context storage using contextvars.

This module contains comprehensive tests for LoggerContextStorage including
context get/set/clear/merge operations and async context isolation.
"""

import asyncio

import pytest

from miso_client.utils.logger_context_storage import (
    LoggerContextStorage,
    clear_logger_context,
    get_logger_context,
    merge_logger_context,
    set_logger_context,
)


class TestLoggerContextStorage:
    """Test cases for LoggerContextStorage class."""

    def test_get_context_no_context(self):
        """Test getting context when none is set."""
        # Clear any existing context
        LoggerContextStorage.clear_context()

        context = LoggerContextStorage.get_context()

        assert context is None

    def test_set_context(self):
        """Test setting context."""
        LoggerContextStorage.clear_context()

        test_context = {
            "userId": "user-123",
            "correlationId": "corr-456",
            "ipAddress": "127.0.0.1",
        }

        LoggerContextStorage.set_context(test_context)
        context = LoggerContextStorage.get_context()

        assert context == test_context
        assert context["userId"] == "user-123"
        assert context["correlationId"] == "corr-456"
        assert context["ipAddress"] == "127.0.0.1"

    def test_clear_context(self):
        """Test clearing context."""
        test_context = {"userId": "user-123"}
        LoggerContextStorage.set_context(test_context)

        LoggerContextStorage.clear_context()
        context = LoggerContextStorage.get_context()

        assert context is None

    def test_merge_context_no_existing(self):
        """Test merging context when no existing context."""
        LoggerContextStorage.clear_context()

        additional = {"userId": "user-123", "correlationId": "corr-456"}
        LoggerContextStorage.merge_context(additional)

        context = LoggerContextStorage.get_context()
        assert context == additional

    def test_merge_context_with_existing(self):
        """Test merging context with existing context."""
        LoggerContextStorage.clear_context()

        existing = {"userId": "user-123", "ipAddress": "127.0.0.1"}
        LoggerContextStorage.set_context(existing)

        additional = {
            "correlationId": "corr-456",
            "userId": "user-789",
        }  # userId will be overwritten
        LoggerContextStorage.merge_context(additional)

        context = LoggerContextStorage.get_context()
        assert context["userId"] == "user-789"  # Overwritten
        assert context["ipAddress"] == "127.0.0.1"  # Preserved
        assert context["correlationId"] == "corr-456"  # Added

    @pytest.mark.asyncio
    async def test_context_isolation_across_async_tasks(self):
        """Test that context is isolated across different async tasks."""
        LoggerContextStorage.clear_context()

        async def task1():
            LoggerContextStorage.set_context({"task": "1", "value": "task1"})
            await asyncio.sleep(0.01)
            return LoggerContextStorage.get_context()

        async def task2():
            LoggerContextStorage.set_context({"task": "2", "value": "task2"})
            await asyncio.sleep(0.01)
            return LoggerContextStorage.get_context()

        # Run tasks concurrently
        results = await asyncio.gather(task1(), task2())

        # Each task should have its own context
        assert results[0]["task"] == "1"
        assert results[0]["value"] == "task1"
        assert results[1]["task"] == "2"
        assert results[1]["value"] == "task2"

    @pytest.mark.asyncio
    async def test_context_propagation_within_async_task(self):
        """Test that context propagates within the same async task."""
        LoggerContextStorage.clear_context()

        async def nested_function():
            return LoggerContextStorage.get_context()

        async def main_task():
            LoggerContextStorage.set_context({"task": "main", "value": "main-value"})
            # Context should be available in nested function
            return await nested_function()

        context = await main_task()
        assert context["task"] == "main"
        assert context["value"] == "main-value"


class TestLoggerContextStorageFunctions:
    """Test cases for module-level helper functions."""

    def test_get_logger_context_function(self):
        """Test get_logger_context() helper function."""
        LoggerContextStorage.clear_context()

        test_context = {"userId": "user-123"}
        LoggerContextStorage.set_context(test_context)

        context = get_logger_context()

        assert context == test_context

    def test_set_logger_context_function(self):
        """Test set_logger_context() helper function."""
        LoggerContextStorage.clear_context()

        test_context = {
            "userId": "user-123",
            "correlationId": "corr-456",
        }

        set_logger_context(test_context)
        context = get_logger_context()

        assert context == test_context

    def test_clear_logger_context_function(self):
        """Test clear_logger_context() helper function."""
        test_context = {"userId": "user-123"}
        set_logger_context(test_context)

        clear_logger_context()
        context = get_logger_context()

        assert context is None

    def test_merge_logger_context_function(self):
        """Test merge_logger_context() helper function."""
        LoggerContextStorage.clear_context()

        existing = {"userId": "user-123"}
        set_logger_context(existing)

        additional = {"correlationId": "corr-456"}
        merge_logger_context(additional)

        context = get_logger_context()
        assert context["userId"] == "user-123"
        assert context["correlationId"] == "corr-456"
