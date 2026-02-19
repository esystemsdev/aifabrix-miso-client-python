"""
Unit tests for logger_request_helpers warn-level support.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.services.application_context import ApplicationContext
from miso_client.services.logger import LoggerService
from miso_client.utils.logger_request_helpers import (
    get_for_request,
    get_log_with_request,
    get_with_context,
)


@pytest.fixture
def logger_service(config, mock_redis):
    """Create logger service with mocked application context."""
    from miso_client.utils.internal_http_client import InternalHttpClient

    internal_client = InternalHttpClient(config)
    logger = LoggerService(internal_client, mock_redis)
    mock_app_context = ApplicationContext(
        application=config.client_id,
        application_id=None,
        environment="unknown",
    )
    logger.application_context_service.get_application_context = AsyncMock(
        return_value=mock_app_context
    )
    return logger


@pytest.mark.asyncio
async def test_get_with_context_supports_warn_level(logger_service):
    """Ensure get_with_context keeps warn level."""
    log_entry = await get_with_context(
        logger_service=logger_service,
        context={"customField": "value"},
        message="Warn helper message",
        level="warn",
    )

    assert log_entry.level == "warn"
    assert log_entry.message == "Warn helper message"


@pytest.mark.asyncio
async def test_get_log_with_request_supports_warn_level(logger_service):
    """Ensure get_log_with_request keeps warn level."""
    request = MagicMock()
    request.method = "GET"
    request.url = MagicMock()
    request.url.path = "/api/test"
    request.client = MagicMock()
    request.client.host = "10.0.0.1"
    request.headers = MagicMock()
    request.headers.get = MagicMock(return_value=None)

    log_entry = await get_log_with_request(
        logger_service=logger_service,
        request=request,
        message="Warn request helper message",
        level="warn",
    )

    assert log_entry.level == "warn"
    assert log_entry.message == "Warn request helper message"


@pytest.mark.asyncio
async def test_get_for_request_supports_warn_level(logger_service):
    """Ensure get_for_request alias keeps warn level."""
    request = MagicMock()
    request.method = "POST"
    request.url = MagicMock()
    request.url.path = "/api/alias-test"
    request.client = MagicMock()
    request.client.host = "10.0.0.2"
    request.headers = MagicMock()
    request.headers.get = MagicMock(return_value=None)

    log_entry = await get_for_request(
        logger_service=logger_service,
        request=request,
        message="Warn alias helper message",
        level="warn",
    )

    assert log_entry.level == "warn"
    assert log_entry.message == "Warn alias helper message"
