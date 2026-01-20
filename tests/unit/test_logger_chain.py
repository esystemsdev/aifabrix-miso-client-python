"""
Unit tests for LoggerChain fluent API.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from miso_client.models.config import ClientLoggingOptions
from miso_client.services.logger import LoggerChain, LoggerService


class TestLoggerChain:
    """Test cases for LoggerChain."""

    @pytest.fixture
    def logger_service(self, mock_http_client, mock_redis):
        """Test LoggerService instance."""
        return LoggerService(mock_http_client, mock_redis)

    @pytest.fixture
    def logger_chain(self, logger_service):
        """Test LoggerChain instance."""
        return LoggerChain(logger_service, {"initial": "context"}, ClientLoggingOptions())

    def test_chain_initialization(self, logger_service):
        """Test LoggerChain initialization."""
        chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())

        assert chain.logger is logger_service
        assert chain.context == {"key": "value"}
        assert isinstance(chain.options, ClientLoggingOptions)

    def test_add_context(self, logger_chain):
        """Test add_context method."""
        result = logger_chain.add_context("new_key", "new_value")

        assert result is logger_chain  # Should return self for chaining
        assert logger_chain.context["new_key"] == "new_value"
        assert logger_chain.context["initial"] == "context"  # Preserve existing

    def test_add_user(self, logger_chain):
        """Test add_user method."""
        result = logger_chain.add_user("user-123")

        assert result is logger_chain
        assert logger_chain.options.userId == "user-123"

    def test_add_application(self, logger_chain):
        """Test add_application method."""
        result = logger_chain.add_application("app-456")

        assert result is logger_chain
        assert logger_chain.options.applicationId == "app-456"

    def test_add_correlation(self, logger_chain):
        """Test add_correlation method."""
        result = logger_chain.add_correlation("corr-789")

        assert result is logger_chain
        assert logger_chain.options.correlationId == "corr-789"

    def test_with_token(self, logger_chain):
        """Test with_token method."""
        result = logger_chain.with_token("jwt-token-123")

        assert result is logger_chain
        assert logger_chain.options.token == "jwt-token-123"

    def test_without_masking(self, logger_chain):
        """Test without_masking method."""
        result = logger_chain.without_masking()

        assert result is logger_chain
        assert logger_chain.options.maskSensitiveData is False

    def test_chain_methods_composable(self, logger_chain):
        """Test that chain methods can be composed."""
        result = (
            logger_chain.add_context("key1", "value1").add_user("user-1").add_application("app-1")
        )

        assert result is logger_chain
        assert logger_chain.context["key1"] == "value1"
        assert logger_chain.options.userId == "user-1"
        assert logger_chain.options.applicationId == "app-1"

    @pytest.mark.asyncio
    async def test_error_method(self, logger_service):
        """Test chain error method."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(logger_service, "error", new_callable=AsyncMock) as mock_error:
            chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())
            await chain.error("Error message", "Stack trace")

            mock_error.assert_called_once_with(
                "Error message", {"key": "value"}, "Stack trace", chain.options
            )

    @pytest.mark.asyncio
    async def test_info_method(self, logger_service):
        """Test chain info method."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(logger_service, "info", new_callable=AsyncMock) as mock_info:
            chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())
            await chain.info("Info message")

            mock_info.assert_called_once_with("Info message", {"key": "value"}, chain.options)

    @pytest.mark.asyncio
    async def test_audit_method(self, logger_service):
        """Test chain audit method."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(logger_service, "audit", new_callable=AsyncMock) as mock_audit:
            chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())
            await chain.audit("action", "resource")

            mock_audit.assert_called_once_with(
                "action", "resource", {"key": "value"}, chain.options
            )

    @pytest.mark.asyncio
    async def test_chain_with_all_options(self, logger_service):
        """Test chain with all options set."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(logger_service, "info", new_callable=AsyncMock) as mock_info:
            chain = (
                LoggerChain(logger_service, {}, ClientLoggingOptions())
                .add_user("user-123")
                .add_application("app-456")
                .add_correlation("corr-789")
                .with_token("token-abc")
                .without_masking()
            )

            await chain.info("Test message")

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            options = call_args[0][2]  # Third argument is options
            assert options.userId == "user-123"
            assert options.applicationId == "app-456"
            assert options.correlationId == "corr-789"
            assert options.userId == "user-123"
            assert options.applicationId == "app-456"
            assert options.correlationId == "corr-789"
            assert options.token == "token-abc"
            assert options.maskSensitiveData is False

    def test_with_indexed_context(self, logger_chain):
        """Test with_indexed_context method."""
        result = logger_chain.with_indexed_context(
            source_key="source-key",
            source_display_name="Source Display",
            external_system_key="system-key",
            external_system_display_name="System Display",
            record_key="record-key",
            record_display_name="Record Display",
        )

        assert result is logger_chain
        assert logger_chain.options.sourceKey == "source-key"
        assert logger_chain.options.sourceDisplayName == "Source Display"
        assert logger_chain.options.externalSystemKey == "system-key"
        assert logger_chain.options.externalSystemDisplayName == "System Display"
        assert logger_chain.options.recordKey == "record-key"
        assert logger_chain.options.recordDisplayName == "Record Display"

    def test_with_indexed_context_partial(self, logger_chain):
        """Test with_indexed_context with partial parameters."""
        result = logger_chain.with_indexed_context(
            source_key="source-key", external_system_key="system-key"
        )

        assert result is logger_chain
        assert logger_chain.options.sourceKey == "source-key"
        assert logger_chain.options.externalSystemKey == "system-key"
        assert logger_chain.options.sourceDisplayName is None
        assert logger_chain.options.recordKey is None

    def test_with_credential_context(self, logger_chain):
        """Test with_credential_context method."""
        result = logger_chain.with_credential_context(
            credential_id="cred-123", credential_type="oauth2"
        )

        assert result is logger_chain
        assert logger_chain.options.credentialId == "cred-123"
        assert logger_chain.options.credentialType == "oauth2"

    def test_with_request_metrics(self, logger_chain):
        """Test with_request_metrics method."""
        result = logger_chain.with_request_metrics(
            request_size=1024,
            response_size=2048,
            duration_ms=150,
            duration_seconds=0.15,
            timeout=30.0,
            retry_count=2,
        )

        assert result is logger_chain
        assert logger_chain.options.requestSize == 1024
        assert logger_chain.options.responseSize == 2048
        assert logger_chain.options.durationMs == 150
        assert logger_chain.options.durationSeconds == 0.15
        assert logger_chain.options.timeout == 30.0
        assert logger_chain.options.retryCount == 2

    def test_with_request_metrics_zero_values(self, logger_chain):
        """Test with_request_metrics with zero values."""
        result = logger_chain.with_request_metrics(
            request_size=0, response_size=0, duration_ms=0, retry_count=0
        )

        assert result is logger_chain
        assert logger_chain.options.requestSize == 0
        assert logger_chain.options.responseSize == 0
        assert logger_chain.options.durationMs == 0
        assert logger_chain.options.retryCount == 0

    def test_with_error_context(self, logger_chain):
        """Test with_error_context method."""
        result = logger_chain.with_error_context(
            error_category="network", http_status_category="5xx"
        )

        assert result is logger_chain
        assert logger_chain.options.errorCategory == "network"
        assert logger_chain.options.httpStatusCategory == "5xx"

    def test_add_session(self, logger_chain):
        """Test add_session method."""
        result = logger_chain.add_session("session-123")

        assert result is logger_chain
        assert logger_chain.options.sessionId == "session-123"

    @pytest.mark.asyncio
    async def test_debug_method(self, logger_service):
        """Test chain debug method."""
        logger_service.config.log_level = "debug"
        logger_service.redis.is_connected.return_value = False

        with patch.object(logger_service, "debug", new_callable=AsyncMock) as mock_debug:
            chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())
            await chain.debug("Debug message")

            mock_debug.assert_called_once_with("Debug message", {"key": "value"}, chain.options)

    @pytest.mark.asyncio
    async def test_debug_method_not_logged_when_level_not_debug(self, logger_service):
        """Test that debug method doesn't log when log level is not debug."""
        logger_service.config.log_level = "info"
        logger_service.redis.is_connected.return_value = False

        with patch.object(logger_service, "debug", new_callable=AsyncMock) as mock_debug:
            chain = LoggerChain(logger_service, {"key": "value"}, ClientLoggingOptions())
            await chain.debug("Debug message")

            # debug() should still be called, but LoggerService.debug checks log_level
            mock_debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_chain_with_all_new_methods(self, logger_service):
        """Test chain with all new indexed context methods."""
        logger_service.config.log_level = "debug"
        logger_service.redis.is_connected.return_value = False

        with patch.object(logger_service, "info", new_callable=AsyncMock) as mock_info:
            chain = (
                LoggerChain(logger_service, {}, ClientLoggingOptions())
                .with_indexed_context(
                    source_key="source-key",
                    source_display_name="Source",
                    external_system_key="system-key",
                )
                .with_credential_context(credential_id="cred-123", credential_type="oauth2")
                .with_request_metrics(
                    request_size=1024, response_size=2048, duration_ms=150, retry_count=1
                )
                .with_error_context(error_category="network", http_status_category="5xx")
                .add_session("session-123")
                .add_user("user-456")
            )

            await chain.info("Test message")

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            options = call_args[0][2]  # Third argument is options
            assert options.sourceKey == "source-key"
            assert options.sourceDisplayName == "Source"
            assert options.externalSystemKey == "system-key"
            assert options.credentialId == "cred-123"
            assert options.credentialType == "oauth2"
            assert options.requestSize == 1024
            assert options.responseSize == 2048
            assert options.durationMs == 150
            assert options.retryCount == 1
            assert options.errorCategory == "network"
            assert options.httpStatusCategory == "5xx"
            assert options.sessionId == "session-123"
            assert options.userId == "user-456"

    def test_with_request(self, logger_chain):
        """Test with_request method extracts context from request."""
        # Create a mock request with all fields
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

        result = logger_chain.with_request(request)

        assert result is logger_chain
        # Top-level LogEntry fields
        assert logger_chain.options.userId == "user-123"
        assert logger_chain.options.sessionId == "session-456"
        assert logger_chain.options.correlationId == "corr-123"
        assert logger_chain.options.ipAddress == "192.168.1.1"
        assert logger_chain.options.userAgent == "Mozilla/5.0"
        # Context fields (not top-level)
        assert logger_chain.context["method"] == "POST"
        assert logger_chain.context["path"] == "/api/test"
        assert logger_chain.context["referer"] == "https://example.com"
        assert logger_chain.context["requestSize"] == 1024

    def test_with_request_minimal(self, logger_chain):
        """Test with_request with minimal request data."""
        request = MagicMock()
        request.method = "GET"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        result = logger_chain.with_request(request)

        assert result is logger_chain
        assert logger_chain.context["method"] == "GET"
        assert logger_chain.options.userId is None

    def test_with_request_composable(self, logger_chain):
        """Test with_request can be composed with other chain methods."""
        request = MagicMock()
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/test"
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "authorization": "Bearer token",
                "user-agent": "Mozilla/5.0",
            }.get(k, d)
        )

        result = logger_chain.with_request(request).add_application("app-123")

        assert result is logger_chain
        assert logger_chain.options.ipAddress == "192.168.1.1"
        assert logger_chain.options.userAgent == "Mozilla/5.0"
        assert logger_chain.options.applicationId == "app-123"

    @pytest.mark.asyncio
    async def test_for_request_shortcut(self, logger_service):
        """Test for_request shortcut method on LoggerService."""
        logger_service.redis.is_connected.return_value = False

        payload = {"sub": "user-789"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        request = MagicMock()
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/users"
        request.client = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "authorization": f"Bearer {token}",
                "user-agent": "TestAgent/1.0",
                "x-correlation-id": "corr-999",
            }.get(k, d)
        )

        with patch.object(logger_service, "info", new_callable=AsyncMock) as mock_info:
            chain = logger_service.for_request(request)
            await chain.info("Processing request")

            mock_info.assert_called_once()
            call_args = mock_info.call_args
            options = call_args[0][2]  # Third argument is options
            assert options.userId == "user-789"
            assert options.ipAddress == "10.0.0.1"
            assert options.userAgent == "TestAgent/1.0"
            assert options.correlationId == "corr-999"
            # Check context was also set
            context = call_args[0][1]  # Second argument is context
            assert context["method"] == "GET"
            assert context["path"] == "/api/users"

    def test_add_user_with_none_options(self, logger_service):
        """Test add_user when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.add_user("user-123")

        assert result is chain
        assert chain.options is not None
        assert chain.options.userId == "user-123"

    def test_add_application_with_none_options(self, logger_service):
        """Test add_application when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.add_application("app-456")

        assert result is chain
        assert chain.options is not None
        assert chain.options.applicationId == "app-456"

    def test_add_correlation_with_none_options(self, logger_service):
        """Test add_correlation when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.add_correlation("corr-789")

        assert result is chain
        assert chain.options is not None
        assert chain.options.correlationId == "corr-789"

    def test_with_token_with_none_options(self, logger_service):
        """Test with_token when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.with_token("jwt-token-123")

        assert result is chain
        assert chain.options is not None
        assert chain.options.token == "jwt-token-123"

    def test_without_masking_with_none_options(self, logger_service):
        """Test without_masking when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.without_masking()

        assert result is chain
        assert chain.options is not None
        assert chain.options.maskSensitiveData is False

    def test_with_request_with_none_options(self, logger_service):
        """Test with_request when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        request = MagicMock()
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/test"
        request.client = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        result = chain.with_request(request)

        assert result is chain
        assert chain.options is not None
        assert chain.context["method"] == "GET"

    def test_with_indexed_context_with_none_options(self, logger_service):
        """Test with_indexed_context when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.with_indexed_context(
            source_key="source-key", external_system_key="system-key"
        )

        assert result is chain
        assert chain.options is not None
        assert chain.options.sourceKey == "source-key"
        assert chain.options.externalSystemKey == "system-key"

    def test_with_credential_context_with_none_options(self, logger_service):
        """Test with_credential_context when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.with_credential_context(credential_id="cred-123", credential_type="oauth2")

        assert result is chain
        assert chain.options is not None
        assert chain.options.credentialId == "cred-123"
        assert chain.options.credentialType == "oauth2"

    def test_with_request_metrics_with_none_options(self, logger_service):
        """Test with_request_metrics when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.with_request_metrics(request_size=1024, response_size=2048, duration_ms=150)

        assert result is chain
        assert chain.options is not None
        assert chain.options.requestSize == 1024
        assert chain.options.responseSize == 2048
        assert chain.options.durationMs == 150

    def test_with_error_context_with_none_options(self, logger_service):
        """Test with_error_context when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.with_error_context(error_category="network", http_status_category="5xx")

        assert result is chain
        assert chain.options is not None
        assert chain.options.errorCategory == "network"
        assert chain.options.httpStatusCategory == "5xx"

    def test_add_session_with_none_options(self, logger_service):
        """Test add_session when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.add_session("session-123")

        assert result is chain
        assert chain.options is not None
        assert chain.options.sessionId == "session-123"

    def test_with_application_with_none_options(self, logger_service):
        """Test with_application when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.with_application("my-app")

        assert result is chain
        assert chain.options is not None
        assert chain.options.application == "my-app"

    def test_with_application_id_with_none_options(self, logger_service):
        """Test with_application_id when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.with_application_id("app-id-123")

        assert result is chain
        assert chain.options is not None
        assert chain.options.applicationId == "app-id-123"

    def test_with_environment_with_none_options(self, logger_service):
        """Test with_environment when options is None."""
        chain = LoggerChain(logger_service, {}, None)
        result = chain.with_environment("production")

        assert result is chain
        assert chain.options is not None
        assert chain.options.environment == "production"

    def test_with_request_with_request_id(self, logger_chain):
        """Test with_request when request_id exists in context."""
        from miso_client.utils.request_context import RequestContext

        request = MagicMock()
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/test"
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        # Mock extract_request_context to return a context with request_id
        with patch("miso_client.services.logger_chain.extract_request_context") as mock_extract:
            mock_context = RequestContext(
                user_id="user-123",
                session_id="session-456",
                correlation_id="corr-789",
                request_id="req-999",  # This should trigger line 131
                ip_address="192.168.1.1",
                user_agent="Mozilla/5.0",
                method="POST",
                path="/api/test",
                referer=None,
                request_size=None,
            )
            mock_extract.return_value = mock_context

            result = logger_chain.with_request(request)

            assert result is logger_chain
            assert logger_chain.options.requestId == "req-999"

    def test_chain_methods_with_empty_strings(self, logger_chain):
        """Test chain methods handle empty strings gracefully."""
        result = (
            logger_chain.add_user("")
            .add_application("")
            .add_correlation("")
            .add_session("")
            .with_token("")
        )

        assert result is logger_chain
        assert logger_chain.options.userId == ""
        assert logger_chain.options.applicationId == ""
        assert logger_chain.options.correlationId == ""
        assert logger_chain.options.sessionId == ""
        assert logger_chain.options.token == ""

    def test_add_context_with_none_value(self, logger_chain):
        """Test add_context with None value."""
        result = logger_chain.add_context("key", None)

        assert result is logger_chain
        assert logger_chain.context["key"] is None

    def test_method_chaining_returns_self(self, logger_chain):
        """Test that all chain methods return self for chaining."""
        result = (
            logger_chain.add_context("key", "value")
            .add_user("user-1")
            .add_application("app-1")
            .add_correlation("corr-1")
            .with_token("token-1")
            .without_masking()
            .with_indexed_context(source_key="source-1")
            .with_credential_context(credential_id="cred-1")
            .with_request_metrics(request_size=1024)
            .with_error_context(error_category="network")
            .add_session("session-1")
        )

        assert result is logger_chain
