"""
Unit tests for logger helper functions.
"""

from unittest.mock import patch

from miso_client.models.config import ClientLoggingOptions
from miso_client.utils.logger_helpers import build_log_entry, transform_log_entry_to_request


def test_build_log_entry_includes_request_metadata_and_app_context(config):
    """Ensure request metadata and app context fields are preserved."""
    context = {"method": "POST", "path": "/api/test", "referer": "https://example.com"}
    auto_fields = {
        "correlationId": "corr-123",
        "requestId": "req-456",
        "sessionId": "session-789",
        "ipAddress": "203.0.113.10",
        "userAgent": "Mozilla/5.0",
        "requestSize": 512,
    }
    metadata = {"hostname": "unit-test-host"}
    application_context = {
        "application": "test-app",
        "applicationId": "app-001",
        "environment": "test",
    }

    with patch("miso_client.utils.logger_helpers.decode_token", return_value={}):
        log_entry = build_log_entry(
            level="audit",
            message="Audit entry",
            context=context,
            config_client_id=config.client_id,
            correlation_id=None,
            jwt_token=None,
            stack_trace=None,
            options=None,
            auto_fields=auto_fields,
            metadata=metadata,
            mask_sensitive=True,
            application_context=application_context,
        )

    assert log_entry.correlationId == "corr-123"
    assert log_entry.requestId == "req-456"
    assert log_entry.sessionId == "session-789"
    assert log_entry.ipAddress == "203.0.113.10"
    assert log_entry.userAgent == "Mozilla/5.0"
    assert log_entry.requestSize == 512
    assert log_entry.hostname == "unit-test-host"
    assert log_entry.application == "test-app"
    assert log_entry.environment == "test"
    assert log_entry.applicationId is not None
    assert log_entry.applicationId.id == "app-001"
    assert log_entry.userId is None
    assert log_entry.context["method"] == "POST"
    assert log_entry.context["path"] == "/api/test"
    assert log_entry.context["referer"] == "https://example.com"


def test_build_log_entry_uses_jwt_context_for_user_and_application(config):
    """Ensure JWT context populates user and application references."""
    with patch(
        "miso_client.utils.logger_helpers.decode_token",
        return_value={"sub": "user-123", "sessionId": "session-abc", "applicationId": "app-900"},
    ):
        log_entry = build_log_entry(
            level="info",
            message="Info entry",
            context={"action": "read"},
            config_client_id=config.client_id,
            jwt_token="jwt-token",
        )

    assert log_entry.userId is not None
    assert log_entry.userId.id == "user-123"
    assert log_entry.sessionId == "session-abc"
    assert log_entry.applicationId is not None
    assert log_entry.applicationId.id == "app-900"


def test_build_log_entry_application_only_auth_has_no_user(config):
    """Ensure application-only log entries omit user context."""
    log_entry = build_log_entry(
        level="error",
        message="Error entry",
        context={"action": "process"},
        config_client_id=config.client_id,
        stack_trace="Traceback: boom",
        application_context={"application": "app-only", "environment": "prod"},
    )

    assert log_entry.userId is None
    assert log_entry.application == "app-only"
    assert log_entry.environment == "prod"
    assert log_entry.stackTrace == "Traceback: boom"


def test_build_log_entry_context_overrides_token_user(config):
    """Ensure explicit context userId takes precedence over token userId."""
    auto_fields = {"userId": "user-context"}

    with patch(
        "miso_client.utils.logger_helpers.decode_token",
        return_value={"sub": "user-token"},
    ):
        log_entry = build_log_entry(
            level="info",
            message="Override test",
            context={"action": "test"},
            config_client_id=config.client_id,
            auto_fields=auto_fields,
            jwt_token="jwt-token",
        )

    assert log_entry.userId is not None
    assert log_entry.userId.id == "user-context"


def test_build_log_entry_warn_level_preserved(config):
    """Ensure warn level is supported and preserved in transformed request payload."""
    log_entry = build_log_entry(
        level="warn",
        message="Warn message",
        context={"action": "warn-test"},
        config_client_id=config.client_id,
    )

    assert log_entry.level == "warn"
    log_request = transform_log_entry_to_request(log_entry)
    assert log_request.type == "general"
    assert log_request.data.level == "warn"


def test_build_log_entry_options_override_context_and_application_context(config):
    """Ensure option-level application/environment takes precedence over other sources."""
    log_entry = build_log_entry(
        level="info",
        message="Override app/env",
        context={"application": "ctx-app", "environment": "ctx-env"},
        config_client_id=config.client_id,
        options=ClientLoggingOptions(application="opt-app", environment="opt-env"),
        application_context={"application": "app-ctx", "environment": "env-ctx"},
    )

    assert log_entry.application == "opt-app"
    assert log_entry.environment == "opt-env"


def test_build_log_entry_mirrors_application_id_into_context(config):
    """Ensure context.applicationId is preserved in final serialized payload."""
    log_entry = build_log_entry(
        level="info",
        message="Mirror applicationId",
        context={"operation": "test"},
        config_client_id=config.client_id,
        auto_fields={"applicationId": "app-top-1"},
    )

    assert log_entry.applicationId is not None
    assert log_entry.applicationId.id == "app-top-1"
    assert log_entry.context is not None
    assert log_entry.context["applicationId"] == "app-top-1"


def test_build_log_entry_does_not_clobber_with_empty_trace_values(config):
    """Ensure empty values do not overwrite non-empty resolved traceability values."""
    with patch(
        "miso_client.utils.logger_helpers.decode_token",
        return_value={
            "sub": "jwt-user",
            "applicationId": "jwt-app",
            "sessionId": "jwt-session",
        },
    ):
        log_entry = build_log_entry(
            level="info",
            message="No empty clobber",
            context={"application": "  ", "environment": "   ", "customTag": "value"},
            config_client_id=config.client_id,
            correlation_id="",
            jwt_token="jwt-token",
            auto_fields={
                "applicationId": " ",
                "userId": "",
                "requestId": "   ",
                "correlationId": "corr-non-empty",
                "sessionId": "",
                "ipAddress": "   ",
                "userAgent": "",
            },
            application_context={
                "application": "app-from-context",
                "applicationId": "app-from-context-id",
                "environment": "dev",
            },
        )

    assert log_entry.correlationId == "corr-non-empty"
    assert log_entry.application == "app-from-context"
    assert log_entry.environment == "dev"
    assert log_entry.applicationId is not None
    assert log_entry.applicationId.id == "app-from-context-id"
    assert log_entry.userId is not None
    assert log_entry.userId.id == "jwt-user"
    assert log_entry.requestId is None
    assert log_entry.sessionId == "jwt-session"
    assert log_entry.ipAddress is None
    assert log_entry.userAgent is None
    assert log_entry.context is not None
    assert log_entry.context["customTag"] == "value"


def test_transform_log_entry_to_request_keeps_traceability_fields(config):
    """Ensure transformed API payload preserves top-level and nested traceability fields."""
    log_entry = build_log_entry(
        level="audit",
        message="Audit transform",
        context={"action": "create", "resource": "item", "applicationId": ""},
        config_client_id=config.client_id,
        auto_fields={
            "applicationId": "app-serialized",
            "userId": "user-serialized",
            "requestId": "req-serialized",
            "sessionId": "session-serialized",
            "ipAddress": "203.0.113.1",
            "userAgent": "pytest-agent",
            "correlationId": "corr-serialized",
        },
    )

    log_request = transform_log_entry_to_request(log_entry)
    payload = log_request.model_dump(exclude_none=True)

    assert payload["data"]["applicationId"]["id"] == "app-serialized"
    assert payload["data"]["context"]["applicationId"] == "app-serialized"
    assert payload["data"]["userId"]["id"] == "user-serialized"
    assert payload["data"]["requestId"] == "req-serialized"
    assert payload["data"]["sessionId"] == "session-serialized"
    assert payload["data"]["ipAddress"] == "203.0.113.1"
    assert payload["data"]["userAgent"] == "pytest-agent"
