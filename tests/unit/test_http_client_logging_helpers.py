"""
Unit tests for HTTP client logging helpers.

Tests the extracted logging helper functions from http_client.py.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.models.config import MisoClientConfig
from miso_client.services.logger import LoggerService
from miso_client.utils.http_client_logging_helpers import (
    calculate_status_code,
    extract_user_id_from_headers,
    handle_logging_task_error,
    log_debug_if_enabled,
    log_http_request,
    wait_for_logging_tasks,
)
from miso_client.utils.jwt_tools import JwtTokenCache


class TestHandleLoggingTaskError:
    """Test cases for handle_logging_task_error function."""

    def test_handle_logging_task_error_no_exception(self):
        """Test handling task with no exception."""
        task = MagicMock()
        task.exception.return_value = None

        # Should not raise
        handle_logging_task_error(task)

    def test_handle_logging_task_error_with_exception(self):
        """Test handling task with exception (should swallow silently)."""
        task = MagicMock()
        task.exception.return_value = Exception("Test error")

        # Should not raise (silently swallows)
        handle_logging_task_error(task)

    def test_handle_logging_task_error_task_not_done(self):
        """Test handling task that's not done yet."""
        task = MagicMock()
        task.exception.side_effect = Exception("Task not done")

        # Should not raise (silently swallows)
        handle_logging_task_error(task)


class TestWaitForLoggingTasks:
    """Test cases for wait_for_logging_tasks function."""

    @pytest.mark.asyncio
    async def test_wait_for_logging_tasks_empty_set(self):
        """Test waiting with empty task set."""
        await wait_for_logging_tasks(set())

    @pytest.mark.asyncio
    async def test_wait_for_logging_tasks_completes(self):
        """Test waiting for tasks to complete."""
        task1 = asyncio.create_task(asyncio.sleep(0.01))
        task2 = asyncio.create_task(asyncio.sleep(0.01))
        tasks = {task1, task2}

        await wait_for_logging_tasks(tasks, timeout=0.1)

        assert task1.done()
        assert task2.done()

    @pytest.mark.asyncio
    async def test_wait_for_logging_tasks_timeout(self):
        """Test timeout when tasks take too long."""
        task = asyncio.create_task(asyncio.sleep(1.0))
        tasks = {task}

        # Should not raise even if timeout
        await wait_for_logging_tasks(tasks, timeout=0.01)

        # Task might still be running, that's okay
        task.cancel()


class TestCalculateStatusCode:
    """Test cases for calculate_status_code function."""

    def test_calculate_status_code_with_response(self):
        """Test status code calculation with successful response."""
        assert calculate_status_code({"data": "test"}, None) == 200

    def test_calculate_status_code_with_error_status_code(self):
        """Test status code calculation with error that has status_code."""
        error = MagicMock()
        error.status_code = 404
        assert calculate_status_code(None, error) == 404

    def test_calculate_status_code_with_error_no_status_code(self):
        """Test status code calculation with error without status_code."""
        error = Exception("Test error")
        assert calculate_status_code(None, error) == 500

    def test_calculate_status_code_none(self):
        """Test status code calculation with None values."""
        assert calculate_status_code(None, None) is None


class TestExtractUserIdFromHeaders:
    """Test cases for extract_user_id_from_headers function."""

    def test_extract_user_id_from_headers_with_token(self):
        """Test extracting user ID from headers with Bearer token."""
        jwt_cache = JwtTokenCache()
        headers = {
            "Authorization": (
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3OCJ9.test"
            )
        }

        # Mock the decode to return a user ID
        from unittest.mock import patch

        with patch.object(jwt_cache, "extract_user_id_from_headers", return_value="12345678"):
            result = extract_user_id_from_headers(headers, jwt_cache)
            assert result == "12345678"

    def test_extract_user_id_from_headers_no_headers(self):
        """Test extracting user ID with no headers."""
        jwt_cache = JwtTokenCache()
        assert extract_user_id_from_headers(None, jwt_cache) is None

    def test_extract_user_id_from_headers_no_auth_header(self):
        """Test extracting user ID with headers but no auth header."""
        jwt_cache = JwtTokenCache()
        headers = {"Content-Type": "application/json"}
        result = extract_user_id_from_headers(headers, jwt_cache)
        assert result is None


class TestLogDebugIfEnabled:
    """Test cases for log_debug_if_enabled function."""

    @pytest.fixture
    def config_debug(self):
        """Config with debug logging enabled."""
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            log_level="debug",
        )

    @pytest.fixture
    def config_info(self):
        """Config with info logging (debug disabled)."""
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            log_level="info",
        )

    @pytest.fixture
    def logger(self):
        """Mock logger service."""
        logger = MagicMock(spec=LoggerService)
        logger.debug = AsyncMock()
        return logger

    @pytest.mark.asyncio
    async def test_log_debug_if_enabled_debug_level(self, logger, config_debug):
        """Test debug logging when debug level is enabled."""
        import time

        start_time = time.perf_counter()
        await log_debug_if_enabled(
            logger,
            config_debug,
            "GET",
            "/api/test",
            {"data": "test"},
            None,
            start_time,
            "user-123",
            {"key": "value"},
            {"Authorization": "Bearer token"},
        )

        logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_debug_if_enabled_info_level(self, logger, config_info):
        """Test debug logging when debug level is disabled."""
        import time

        start_time = time.perf_counter()
        await log_debug_if_enabled(
            logger,
            config_info,
            "GET",
            "/api/test",
            {"data": "test"},
            None,
            start_time,
            "user-123",
            {"key": "value"},
            {"Authorization": "Bearer token"},
        )

        logger.debug.assert_not_called()


class TestLogHttpRequest:
    """Test cases for log_http_request function."""

    @pytest.fixture
    def config(self):
        """Test config."""
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            log_level="info",
        )

    @pytest.fixture
    def logger(self):
        """Mock logger service."""
        logger = MagicMock(spec=LoggerService)
        logger.audit = AsyncMock()
        logger.debug = AsyncMock()
        return logger

    @pytest.fixture
    def jwt_cache(self):
        """JWT token cache."""
        return JwtTokenCache()

    @pytest.mark.asyncio
    async def test_log_http_request_success(self, logger, config, jwt_cache):
        """Test logging successful HTTP request."""
        import time

        start_time = time.perf_counter()
        await log_http_request(
            logger,
            config,
            jwt_cache,
            "GET",
            "/api/test",
            {"data": "test"},
            None,
            start_time,
            {"key": "value"},
            {"Authorization": "Bearer token"},
        )

        logger.audit.assert_called_once()
        # Debug should not be called for info level
        logger.debug.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_http_request_error(self, logger, config, jwt_cache):
        """Test logging HTTP request with error."""
        import time

        start_time = time.perf_counter()
        error = Exception("Test error")
        await log_http_request(
            logger,
            config,
            jwt_cache,
            "GET",
            "/api/test",
            None,
            error,
            start_time,
            {"key": "value"},
            {"Authorization": "Bearer token"},
        )

        logger.audit.assert_called_once()
