"""
Unit tests for LoggerService.

This module contains comprehensive tests for LoggerService including
event emission mode, log transformation, and get_* methods.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from miso_client.models.config import ClientLoggingOptions, LogEntry
from miso_client.services.logger import LoggerService
from miso_client.utils.audit_log_queue import AuditLogQueue


class TestLoggerServiceEventEmission:
    """Test cases for LoggerService event emission mode."""

    @pytest.fixture
    def config_with_emit_events(self, config):
        """Config with emit_events enabled."""
        config.emit_events = True
        return config

    @pytest.fixture
    def logger_service(self, config_with_emit_events, mock_redis):
        """LoggerService with emit_events enabled."""
        from miso_client.utils.internal_http_client import InternalHttpClient

        internal_client = InternalHttpClient(config_with_emit_events)
        return LoggerService(internal_client, mock_redis)

    @pytest.mark.asyncio
    async def test_event_emission_with_async_callback(self, logger_service):
        """Test event emission mode with async callback."""
        callback_called = []

        async def async_callback(log_entry: LogEntry):
            callback_called.append(log_entry)

        logger_service.on(async_callback)

        await logger_service.info("Test message", {"key": "value"})

        assert len(callback_called) == 1
        assert callback_called[0].message == "Test message"
        assert callback_called[0].level == "info"

    @pytest.mark.asyncio
    async def test_event_emission_with_sync_callback(self, logger_service):
        """Test event emission mode with sync callback."""
        callback_called = []

        def sync_callback(log_entry: LogEntry):
            callback_called.append(log_entry)

        logger_service.on(sync_callback)

        await logger_service.info("Test message", {"key": "value"})

        assert len(callback_called) == 1
        assert callback_called[0].message == "Test message"

    @pytest.mark.asyncio
    async def test_event_emission_with_multiple_callbacks(self, logger_service):
        """Test event emission mode with multiple callbacks."""
        callback1_called = []
        callback2_called = []

        def callback1(log_entry: LogEntry):
            callback1_called.append(log_entry)

        async def callback2(log_entry: LogEntry):
            callback2_called.append(log_entry)

        logger_service.on(callback1)
        logger_service.on(callback2)

        await logger_service.info("Test message")

        assert len(callback1_called) == 1
        assert len(callback2_called) == 1

    @pytest.mark.asyncio
    async def test_event_listener_exception_handling(self, logger_service):
        """Test that event listener exceptions are silently caught."""
        callback_called = []

        def failing_callback(log_entry: LogEntry):
            raise ValueError("Callback error")

        def working_callback(log_entry: LogEntry):
            callback_called.append(log_entry)

        logger_service.on(failing_callback)
        logger_service.on(working_callback)

        # Should not raise exception
        await logger_service.info("Test message")

        # Working callback should still be called
        assert len(callback_called) == 1

    @pytest.mark.asyncio
    async def test_event_emission_skips_http_redis(self, logger_service):
        """Test that event emission mode skips HTTP/Redis sending."""
        callback_called = []

        def callback(log_entry: LogEntry):
            callback_called.append(log_entry)

        logger_service.on(callback)
        logger_service.redis.is_connected.return_value = True

        # Mock HTTP client to verify it's not called
        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test message")

            # Callback should be called
            assert len(callback_called) == 1
            # HTTP should not be called
            mock_request.assert_not_called()
            # Redis should not be called
            logger_service.redis.rpush.assert_not_called()

    def test_on_off_methods(self, logger_service):
        """Test on() and off() methods for event listeners."""
        callback1 = MagicMock()
        callback2 = MagicMock()

        logger_service.on(callback1)
        logger_service.on(callback2)
        assert len(logger_service._event_listeners) == 2

        logger_service.off(callback1)
        assert len(logger_service._event_listeners) == 1
        assert callback1 not in logger_service._event_listeners
        assert callback2 in logger_service._event_listeners

        # Removing non-existent callback should not raise error
        logger_service.off(callback1)
        assert len(logger_service._event_listeners) == 1

    def test_on_prevents_duplicate_callbacks(self, logger_service):
        """Test that on() prevents adding duplicate callbacks."""
        callback = MagicMock()

        logger_service.on(callback)
        logger_service.on(callback)  # Try to add again

        assert len(logger_service._event_listeners) == 1


class TestLoggerServiceTransformLogEntry:
    """Test cases for _transform_log_entry_to_request method."""

    @pytest.fixture
    def logger_service(self, config, mock_redis):
        """Test LoggerService instance."""
        from miso_client.utils.internal_http_client import InternalHttpClient

        internal_client = InternalHttpClient(config)
        return LoggerService(internal_client, mock_redis)

    def test_transform_audit_log_entry(self, logger_service, config):
        """Test transforming audit log entry to AuditLogData."""
        from miso_client.api.types.logs_types import AuditLogData, LogRequest

        log_entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level="audit",
            environment="test",
            application=config.client_id,
            message="Audit message",
            correlationId="corr-123",
            context={
                "action": "user.login",
                "resource": "authentication",
                "entityType": "user",
                "entityId": "user-123",
                "oldValues": {"lastLogin": None},
                "newValues": {"lastLogin": "2024-01-01"},
            },
        )

        log_request = logger_service._transform_log_entry_to_request(log_entry)

        assert isinstance(log_request, LogRequest)
        assert log_request.type == "audit"
        assert isinstance(log_request.data, AuditLogData)
        assert log_request.data.action == "user.login"
        assert log_request.data.entityType == "user"
        assert log_request.data.entityId == "user-123"
        assert log_request.data.correlationId == "corr-123"

    def test_transform_audit_log_entry_with_defaults(self, logger_service, config):
        """Test transforming audit log entry with missing context fields."""
        from miso_client.api.types.logs_types import AuditLogData, LogRequest

        log_entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level="audit",
            environment="test",
            application=config.client_id,
            message="Audit message",
            correlationId="corr-123",
            context={"action": "user.login"},  # Missing entityType, entityId
        )

        log_request = logger_service._transform_log_entry_to_request(log_entry)

        assert isinstance(log_request, LogRequest)
        assert log_request.type == "audit"
        assert isinstance(log_request.data, AuditLogData)
        assert log_request.data.action == "user.login"
        assert log_request.data.entityType == "unknown"  # Default
        assert log_request.data.entityId == "unknown"  # Default

    def test_transform_error_log_entry(self, logger_service, config):
        """Test transforming error log entry to GeneralLogData."""
        from miso_client.api.types.logs_types import GeneralLogData, LogRequest

        log_entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level="error",
            environment="test",
            application=config.client_id,
            message="Error occurred",
            correlationId="corr-123",
            context={"error": "test"},
        )

        log_request = logger_service._transform_log_entry_to_request(log_entry)

        assert isinstance(log_request, LogRequest)
        assert log_request.type == "error"
        assert isinstance(log_request.data, GeneralLogData)
        assert log_request.data.level == "error"
        assert log_request.data.message == "Error occurred"
        assert log_request.data.correlationId == "corr-123"

    def test_transform_info_log_entry(self, logger_service, config):
        """Test transforming info log entry to GeneralLogData."""
        from miso_client.api.types.logs_types import GeneralLogData, LogRequest

        log_entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level="info",
            environment="test",
            application=config.client_id,
            message="Info message",
            correlationId="corr-123",
            context={"key": "value"},
        )

        log_request = logger_service._transform_log_entry_to_request(log_entry)

        assert isinstance(log_request, LogRequest)
        assert log_request.type == "general"
        assert isinstance(log_request.data, GeneralLogData)
        assert log_request.data.level == "info"
        assert log_request.data.message == "Info message"

    def test_transform_debug_log_entry(self, logger_service, config):
        """Test transforming debug log entry to GeneralLogData."""
        from miso_client.api.types.logs_types import GeneralLogData, LogRequest

        log_entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level="debug",
            environment="test",
            application=config.client_id,
            message="Debug message",
            correlationId="corr-123",
        )

        log_request = logger_service._transform_log_entry_to_request(log_entry)

        assert isinstance(log_request, LogRequest)
        assert log_request.type == "general"
        assert isinstance(log_request.data, GeneralLogData)
        assert log_request.data.level == "debug"


class TestLoggerServiceGetMethods:
    """Test cases for LoggerService get_* methods."""

    @pytest.fixture
    def logger_service(self, config, mock_redis):
        """Test LoggerService instance."""
        from miso_client.utils.internal_http_client import InternalHttpClient

        internal_client = InternalHttpClient(config)
        return LoggerService(internal_client, mock_redis)

    def test_get_log_with_request_fastapi(self, logger_service):
        """Test get_log_with_request with FastAPI request."""
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

        log_entry = logger_service.get_log_with_request(request, "Test message", "info")

        assert isinstance(log_entry, LogEntry)
        assert log_entry.message == "Test message"
        assert log_entry.level == "info"
        assert log_entry.userId is not None
        assert log_entry.userId.id == "user-123"
        assert log_entry.sessionId == "session-456"
        assert log_entry.correlationId == "corr-123"
        assert log_entry.ipAddress == "192.168.1.1"
        assert log_entry.userAgent == "Mozilla/5.0"
        assert log_entry.context["method"] == "POST"
        assert log_entry.context["path"] == "/api/test"
        assert log_entry.context["referer"] == "https://example.com"
        assert log_entry.context["requestSize"] == 1024

    def test_get_log_with_request_minimal(self, logger_service):
        """Test get_log_with_request with minimal request data."""
        request = MagicMock()
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/test"
        request.client = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        log_entry = logger_service.get_log_with_request(request, "Test message")

        assert isinstance(log_entry, LogEntry)
        assert log_entry.message == "Test message"
        assert log_entry.context["method"] == "GET"
        assert log_entry.context["path"] == "/api/test"
        assert log_entry.userId is None  # No token

    def test_get_log_with_request_with_stack_trace(self, logger_service):
        """Test get_log_with_request with stack trace."""
        request = MagicMock()
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/test"
        request.client = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        log_entry = logger_service.get_log_with_request(
            request, "Error message", "error", stack_trace="Traceback..."
        )

        assert log_entry.level == "error"
        assert log_entry.stackTrace == "Traceback..."

    def test_get_with_context(self, logger_service):
        """Test get_with_context method."""
        context = {"customField": "value", "anotherField": 123}

        log_entry = logger_service.get_with_context(context, "Custom log", "info")

        assert isinstance(log_entry, LogEntry)
        assert log_entry.message == "Custom log"
        assert log_entry.level == "info"
        assert log_entry.context == context

    def test_get_with_context_with_options(self, logger_service):
        """Test get_with_context with custom options."""
        context = {"customField": "value"}
        options = ClientLoggingOptions()
        options.userId = "user-123"
        options.correlationId = "corr-456"

        log_entry = logger_service.get_with_context(context, "Custom log", "info", options=options)

        assert log_entry.userId is not None
        assert log_entry.userId.id == "user-123"
        assert log_entry.correlationId == "corr-456"

    def test_get_with_token(self, logger_service):
        """Test get_with_token method."""
        payload = {"sub": "user-123", "sessionId": "session-456"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        log_entry = logger_service.get_with_token(token, "User action", "audit")

        assert isinstance(log_entry, LogEntry)
        assert log_entry.message == "User action"
        assert log_entry.level == "audit"
        assert log_entry.userId is not None
        assert log_entry.userId.id == "user-123"
        assert log_entry.sessionId == "session-456"

    def test_get_for_request(self, logger_service):
        """Test get_for_request method (alias for get_log_with_request)."""
        request = MagicMock()
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/users"
        request.client = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        log_entry = logger_service.get_for_request(request, "Request processed")

        assert isinstance(log_entry, LogEntry)
        assert log_entry.message == "Request processed"
        assert log_entry.context["method"] == "POST"
        assert log_entry.context["path"] == "/api/users"


class TestLoggerServiceEdgeCases:
    """Test cases for LoggerService edge cases."""

    @pytest.fixture
    def logger_service(self, config, mock_redis):
        """Test LoggerService instance."""
        from miso_client.utils.internal_http_client import InternalHttpClient

        internal_client = InternalHttpClient(config)
        return LoggerService(internal_client, mock_redis)

    @pytest.mark.asyncio
    async def test_audit_log_queue_path(self, logger_service):
        """Test audit log uses audit_log_queue when available."""
        # Create mock audit log queue
        mock_queue = MagicMock(spec=AuditLogQueue)
        mock_queue.add = AsyncMock()
        logger_service.audit_log_queue = mock_queue

        await logger_service.audit("action", "resource", {"key": "value"})

        # Should use audit log queue
        mock_queue.add.assert_called_once()
        # Should not use Redis or HTTP
        logger_service.redis.rpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_skips_http(self, logger_service):
        """Test that circuit breaker open skips HTTP logging."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.circuit_breaker, "is_open", return_value=True
        ), patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test message")

            # HTTP should not be called when circuit breaker is open
            mock_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_failure_fallback_to_http(self, logger_service):
        """Test Redis failure falls back to HTTP."""
        logger_service.redis.is_connected.return_value = True
        logger_service.redis.rpush = AsyncMock(return_value=False)  # Redis fails

        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test message")

            # Should fallback to HTTP
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_failure_with_circuit_breaker(self, logger_service):
        """Test HTTP failure records in circuit breaker."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.circuit_breaker, "is_open", return_value=False
        ), patch.object(
            logger_service.circuit_breaker, "record_failure", return_value=None
        ) as mock_record_failure, patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("HTTP error")

            await logger_service.info("Test message")

            # Should record failure in circuit breaker
            mock_record_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_client_path(self, logger_service, mock_api_client):
        """Test using api_client when available."""
        logger_service.api_client = mock_api_client
        logger_service.redis.is_connected.return_value = False

        mock_api_client.logs.send_log = AsyncMock()

        with patch.object(logger_service.circuit_breaker, "is_open", return_value=False):
            await logger_service.info("Test message", {"key": "value"})

            # Should use api_client
            mock_api_client.logs.send_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_internal_http_client_path(self, logger_service):
        """Test using internal_http_client when api_client not available."""
        logger_service.api_client = None
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.circuit_breaker, "is_open", return_value=False
        ), patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test message")

            # Should use internal_http_client
            mock_request.assert_called_once()
            assert mock_request.call_args[0][0] == "POST"
            assert mock_request.call_args[0][1] == "/api/v1/logs"
