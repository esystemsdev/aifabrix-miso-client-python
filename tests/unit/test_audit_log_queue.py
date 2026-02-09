"""
Unit tests for audit log queue.

This module contains comprehensive tests for AuditLogQueue including
batching, Redis queuing, HTTP fallback, and signal handling.
"""

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miso_client.models.config import AuditConfig, ForeignKeyReference, LogEntry, MisoClientConfig
from miso_client.services.redis import RedisService
from miso_client.utils.audit_log_queue import AuditLogQueue, QueuedLogEntry


class TestQueuedLogEntry:
    """Test cases for QueuedLogEntry class."""

    def test_queued_log_entry_initialization(self):
        """Test QueuedLogEntry initialization."""
        entry = LogEntry(
            timestamp="2024-01-01T12:00:00Z",
            level="audit",
            environment="test",
            application="test-app",
            message="Test message",
        )
        timestamp = 1704110400000

        queued_entry = QueuedLogEntry(entry, timestamp)

        assert queued_entry.entry == entry
        assert queued_entry.timestamp == timestamp


class TestAuditLogQueue:
    """Test cases for AuditLogQueue class."""

    @pytest.fixture
    def config(self):
        """Test configuration."""
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            audit=AuditConfig(batchSize=5, batchInterval=200),
        )

    @pytest.fixture
    def mock_http_client(self):
        """Mock HttpClient."""
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value={"success": True})
        return mock_client

    @pytest.fixture
    def mock_redis(self):
        """Mock RedisService."""
        mock_redis = MagicMock(spec=RedisService)
        mock_redis.is_connected = MagicMock(return_value=False)
        mock_redis.rpush = AsyncMock(return_value=True)
        return mock_redis

    @pytest.fixture
    def audit_queue(self, config, mock_http_client, mock_redis):
        """Test AuditLogQueue instance."""
        return AuditLogQueue(mock_http_client, mock_redis, config)

    @pytest.fixture
    def log_entry(self):
        """Test log entry."""
        return LogEntry(
            timestamp="2024-01-01T12:00:00Z",
            level="audit",
            environment="test",
            application="test-app",
            message="Test message",
        )

    @pytest.mark.asyncio
    async def test_add_single_entry(self, audit_queue, log_entry):
        """Test adding single entry to queue."""
        await audit_queue.add(log_entry)

        assert audit_queue.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_add_triggers_flush_at_batch_size(self, audit_queue, log_entry, mock_http_client):
        """Test that adding entries triggers flush when batch size is reached."""
        audit_queue.batch_size = 3

        # Add entries up to batch size
        for i in range(3):
            entry = LogEntry(
                timestamp="2024-01-01T12:00:00Z",
                level="audit",
                environment="test",
                application="test-app",
                message=f"Message {i}",
            )
            await audit_queue.add(entry)

        # Wait for flush to complete
        await asyncio.sleep(0.1)

        # Verify flush was called
        mock_http_client.request.assert_called_once()
        # Queue should be empty after flush
        assert audit_queue.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_flush_with_redis(self, audit_queue, log_entry, mock_redis):
        """Test flush with Redis available."""
        mock_redis.is_connected.return_value = True
        mock_redis.rpush = AsyncMock(return_value=True)

        # Add entries
        for i in range(2):
            entry = LogEntry(
                timestamp="2024-01-01T12:00:00Z",
                level="audit",
                environment="test",
                application="test-app",
                message=f"Message {i}",
            )
            await audit_queue.add(entry)

        # Flush manually
        await audit_queue.flush()

        # Verify Redis was used
        mock_redis.rpush.assert_called_once()
        queue_name = mock_redis.rpush.call_args[0][0]
        assert queue_name == "audit-logs:test-client"

        # Verify HTTP was not called
        audit_queue.http_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_without_redis_fallback_to_http(
        self, audit_queue, log_entry, mock_http_client
    ):
        """Test flush without Redis falls back to HTTP."""
        audit_queue.redis.is_connected.return_value = False

        # Add entries
        for i in range(2):
            entry = LogEntry(
                timestamp="2024-01-01T12:00:00Z",
                level="audit",
                environment="test",
                application="test-app",
                message=f"Message {i}",
            )
            await audit_queue.add(entry)

        # Flush manually
        await audit_queue.flush()

        # Verify HTTP was called
        mock_http_client.request.assert_called_once()
        call_args = mock_http_client.request.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/api/v1/logs/batch"
        assert "logs" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_flush_with_redis_failure_fallback_to_http(
        self, audit_queue, log_entry, mock_http_client, mock_redis
    ):
        """Test flush with Redis failure falls back to HTTP."""
        mock_redis.is_connected.return_value = True
        mock_redis.rpush = AsyncMock(return_value=False)  # Redis push fails

        # Add entries
        for i in range(2):
            entry = LogEntry(
                timestamp="2024-01-01T12:00:00Z",
                level="audit",
                environment="test",
                application="test-app",
                message=f"Message {i}",
            )
            await audit_queue.add(entry)

        # Flush manually
        await audit_queue.flush()

        # Verify HTTP fallback was called
        mock_http_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_empty_queue(self, audit_queue):
        """Test flush with empty queue does nothing."""
        await audit_queue.flush()

        assert audit_queue.get_queue_size() == 0
        audit_queue.http_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_flush_while_flushing(self, audit_queue, log_entry):
        """Test that flush returns early if already flushing."""
        audit_queue.is_flushing = True

        await audit_queue.add(log_entry)
        await audit_queue.flush()

        # Queue should still have entry since flush was skipped
        assert audit_queue.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_schedule_flush_timer(self, audit_queue, log_entry, mock_http_client):
        """Test automatic flush after batch interval."""
        audit_queue.batch_size = 10  # Large batch size
        audit_queue.batch_interval = 50  # 50ms

        # Add single entry (should trigger timer)
        await audit_queue.add(log_entry)

        # Wait for timer to trigger
        await asyncio.sleep(0.1)

        # Verify flush was called
        mock_http_client.request.assert_called_once()
        assert audit_queue.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_schedule_flush_timer_cancelled(self, audit_queue, log_entry):
        """Test that flush timer is cancelled when flush is triggered early."""
        audit_queue.batch_size = 10
        audit_queue.batch_interval = 1000  # Long interval

        # Add entry (starts timer)
        await audit_queue.add(log_entry)

        # Wait a bit for timer to start
        await asyncio.sleep(0.01)

        # Manually flush (should cancel timer)
        await audit_queue.flush()

        # Wait a bit more
        await asyncio.sleep(0.1)

        # Timer should be None (cancelled)
        assert audit_queue.flush_timer is None

    @pytest.mark.asyncio
    async def test_get_queue_size(self, audit_queue, log_entry):
        """Test get_queue_size method."""
        assert audit_queue.get_queue_size() == 0

        await audit_queue.add(log_entry)
        assert audit_queue.get_queue_size() == 1

        await audit_queue.add(log_entry)
        assert audit_queue.get_queue_size() == 2

    @pytest.mark.asyncio
    async def test_clear(self, audit_queue, log_entry):
        """Test clear method."""
        # Add entries
        for i in range(3):
            await audit_queue.add(log_entry)

        assert audit_queue.get_queue_size() == 3

        # Clear queue
        audit_queue.clear()

        assert audit_queue.get_queue_size() == 0
        assert audit_queue.flush_timer is None

    @pytest.mark.asyncio
    async def test_flush_excludes_environment_and_application(self, audit_queue, mock_http_client):
        """Test that flush excludes environment and application from log entries."""
        audit_queue.redis.is_connected.return_value = False

        entry = LogEntry(
            timestamp="2024-01-01T12:00:00Z",
            level="audit",
            environment="test-env",
            application="test-app",
            message="Test message",
            context={"key": "value"},
        )

        await audit_queue.add(entry)
        await audit_queue.flush()

        # Verify HTTP request was made
        mock_http_client.request.assert_called_once()
        call_args = mock_http_client.request.call_args
        logs = call_args[0][2]["logs"]

        # Verify environment and application are excluded
        assert len(logs) == 1
        assert "environment" not in logs[0]
        assert "application" not in logs[0]
        assert logs[0]["message"] == "Test message"
        assert logs[0]["context"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_batch_payload_preserves_entry_fields(
        self, audit_queue, mock_http_client, mock_redis
    ):
        """Test that batch payload keeps per-entry fields intact."""
        audit_queue.redis.is_connected.return_value = False

        entry_one = LogEntry(
            timestamp="2024-01-01T12:00:00Z",
            level="audit",
            environment="test-env",
            application="test-app",
            message="Entry one",
            correlationId="corr-1",
            requestId="req-1",
            sessionId="session-1",
            ipAddress="203.0.113.10",
            userAgent="agent-1",
            requestSize=123,
            userId=ForeignKeyReference(id="user-1", key="user-1", name="user-1", type="User"),
            applicationId=ForeignKeyReference(
                id="app-1", key="app-1", name="app-1", type="Application"
            ),
            context={"method": "POST", "path": "/api/one"},
        )
        entry_two = LogEntry(
            timestamp="2024-01-01T12:00:01Z",
            level="audit",
            environment="test-env",
            application="test-app",
            message="Entry two",
            correlationId="corr-2",
            requestId="req-2",
            sessionId="session-2",
            ipAddress="203.0.113.11",
            userAgent="agent-2",
            requestSize=456,
            userId=ForeignKeyReference(id="user-2", key="user-2", name="user-2", type="User"),
            applicationId=ForeignKeyReference(
                id="app-2", key="app-2", name="app-2", type="Application"
            ),
            context={"method": "PUT", "path": "/api/two"},
        )

        await audit_queue.add(entry_one)
        await audit_queue.add(entry_two)
        await audit_queue.flush()

        mock_http_client.request.assert_called_once()
        payload_logs = mock_http_client.request.call_args[0][2]["logs"]

        assert len(payload_logs) == 2
        assert payload_logs[0]["correlationId"] == "corr-1"
        assert payload_logs[0]["requestId"] == "req-1"
        assert payload_logs[0]["sessionId"] == "session-1"
        assert payload_logs[0]["ipAddress"] == "203.0.113.10"
        assert payload_logs[0]["userAgent"] == "agent-1"
        assert payload_logs[0]["requestSize"] == 123
        assert payload_logs[0]["userId"]["id"] == "user-1"
        assert payload_logs[0]["applicationId"]["id"] == "app-1"
        assert payload_logs[0]["context"]["method"] == "POST"
        assert payload_logs[0]["context"]["path"] == "/api/one"
        assert "environment" not in payload_logs[0]
        assert "application" not in payload_logs[0]

        assert payload_logs[1]["correlationId"] == "corr-2"
        assert payload_logs[1]["requestId"] == "req-2"
        assert payload_logs[1]["sessionId"] == "session-2"
        assert payload_logs[1]["ipAddress"] == "203.0.113.11"
        assert payload_logs[1]["userAgent"] == "agent-2"
        assert payload_logs[1]["requestSize"] == 456
        assert payload_logs[1]["userId"]["id"] == "user-2"
        assert payload_logs[1]["applicationId"]["id"] == "app-2"
        assert payload_logs[1]["context"]["method"] == "PUT"
        assert payload_logs[1]["context"]["path"] == "/api/two"
        assert "environment" not in payload_logs[1]
        assert "application" not in payload_logs[1]

    @pytest.mark.asyncio
    async def test_flush_handles_http_error_silently(
        self, audit_queue, log_entry, mock_http_client
    ):
        """Test that flush handles HTTP errors silently."""
        audit_queue.redis.is_connected.return_value = False
        mock_http_client.request = AsyncMock(side_effect=Exception("HTTP error"))

        # Add entry
        await audit_queue.add(log_entry)

        # Flush should not raise exception
        await audit_queue.flush()

        # Queue should be empty (entry was removed even if HTTP failed)
        assert audit_queue.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_flush_handles_redis_error_silently(
        self, audit_queue, log_entry, mock_redis, mock_http_client
    ):
        """Test that flush handles Redis errors silently."""
        mock_redis.is_connected.return_value = True
        mock_redis.rpush = AsyncMock(side_effect=Exception("Redis error"))

        # Add entry
        await audit_queue.add(log_entry)

        # Flush should not raise exception (errors are silently swallowed)
        await audit_queue.flush()

        # Verify no exception was raised and queue is empty
        assert audit_queue.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_flush_with_sync_flag(self, audit_queue, log_entry, mock_http_client):
        """Test flush with sync flag."""
        audit_queue.redis.is_connected.return_value = False

        await audit_queue.add(log_entry)
        await audit_queue.flush(sync=True)

        # Verify flush completed
        mock_http_client.request.assert_called_once()
        assert audit_queue.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_signal_handler(self, audit_queue, log_entry, mock_http_client):
        """Test signal handler triggers flush."""
        # Add entry
        await audit_queue.add(log_entry)

        # Simulate signal handler
        # Note: We can't actually send signals in tests, so we test the handler directly
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = True

            def _capture_task(coro):
                coro.close()
                return MagicMock()

            with patch("asyncio.create_task", side_effect=_capture_task) as mock_create_task:
                audit_queue._signal_handler(signal.SIGTERM, None)

                # Verify create_task was called
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_signal_handler_event_loop_not_running(self, audit_queue, log_entry):
        """Test signal handler when event loop is not running."""
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.is_running.return_value = False
            with patch("asyncio.create_task") as mock_create_task:
                audit_queue._signal_handler(signal.SIGTERM, None)

                # create_task should not be called
                mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialization_with_signal_handlers(self, config, mock_http_client, mock_redis):
        """Test initialization with signal handlers."""
        with patch("signal.signal") as mock_signal:
            AuditLogQueue(mock_http_client, mock_redis, config)

            # Verify signal handlers were set up
            assert mock_signal.call_count == 2
            assert mock_signal.call_args_list[0][0][0] == signal.SIGINT
            assert mock_signal.call_args_list[1][0][0] == signal.SIGTERM

    @pytest.mark.asyncio
    async def test_initialization_without_signal_handlers(
        self, config, mock_http_client, mock_redis
    ):
        """Test initialization when signal handlers are not available."""
        with patch("signal.signal", side_effect=ValueError("Signal not available")):
            # Should not raise exception
            queue = AuditLogQueue(mock_http_client, mock_redis, config)

            assert queue.batch_size == 5
            assert queue.batch_interval == 200

    @pytest.mark.asyncio
    async def test_default_batch_config(self, mock_http_client, mock_redis):
        """Test default batch configuration when audit config is None."""
        # When audit is None, the code uses {} which doesn't have batchSize attribute
        # So we need to provide an AuditConfig with None values to get defaults
        config = MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            audit=AuditConfig(batchSize=None, batchInterval=None),
        )

        queue = AuditLogQueue(mock_http_client, mock_redis, config)

        assert queue.batch_size == 10  # Default
        assert queue.batch_interval == 100  # Default

    @pytest.mark.asyncio
    async def test_flush_cancels_timer(self, audit_queue, log_entry):
        """Test that flush cancels existing timer."""
        audit_queue.batch_size = 10
        audit_queue.batch_interval = 1000

        # Add entry (starts timer)
        await audit_queue.add(log_entry)

        # Verify timer is set
        assert audit_queue.flush_timer is not None

        # Flush manually
        await audit_queue.flush()

        # Timer should be cancelled
        assert audit_queue.flush_timer is None

    @pytest.mark.asyncio
    async def test_flush_with_empty_entries_after_copy(
        self, audit_queue, log_entry, mock_http_client
    ):
        """Test flush when entries list becomes empty after copy."""
        audit_queue.redis.is_connected.return_value = False

        # Add entry
        await audit_queue.add(log_entry)

        # Manually clear queue before flush completes (simulating race condition)
        # This tests the check for empty entries after copy
        async def delayed_flush():
            await asyncio.sleep(0.01)
            await audit_queue.flush()

        # Start flush
        task = asyncio.create_task(delayed_flush())

        # Clear queue immediately
        audit_queue.queue.clear()

        # Wait for flush
        await task

        # Should not raise exception
        assert audit_queue.get_queue_size() == 0
