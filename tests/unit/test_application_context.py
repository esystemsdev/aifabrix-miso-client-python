"""
Unit tests for ApplicationContextService.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from miso_client.models.config import MisoClientConfig
from miso_client.services.application_context import (
    ApplicationContext,
    ApplicationContextService,
)
from miso_client.utils.internal_http_client import InternalHttpClient


@pytest.fixture
def mock_config():
    """Create mock MisoClientConfig."""
    return MisoClientConfig(
        controller_url="https://controller.example.com",
        client_id="miso-controller-miso-test-app",
        client_secret="secret",
    )


@pytest.fixture
def mock_internal_http_client(mock_config):
    """Create mock InternalHttpClient."""
    mock_client = Mock(spec=InternalHttpClient)
    mock_client.config = mock_config
    mock_client.token_manager = Mock()
    mock_client.token_manager.get_client_token = AsyncMock(return_value="client-token")
    return mock_client


@pytest.mark.asyncio
async def test_get_application_context_from_client_id_format(mock_internal_http_client):
    """Test extracting application context from clientId format."""
    service = ApplicationContextService(mock_internal_http_client)

    # Mock token extraction to return None (fallback to clientId parsing)
    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        return_value={"application": None, "environment": None, "applicationId": None},
    ):
        context = await service.get_application_context()

    assert context.application == "test-app"
    assert context.environment == "miso"
    assert context.application_id is None


@pytest.mark.asyncio
async def test_get_application_context_from_token(mock_internal_http_client):
    """Test extracting application context from client token."""
    service = ApplicationContextService(mock_internal_http_client)

    # Mock token extraction to return values
    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        return_value={
            "application": "token-app",
            "environment": "production",
            "applicationId": "app-123",
        },
    ):
        context = await service.get_application_context()

    assert context.application == "token-app"
    assert context.environment == "production"
    assert context.application_id == "app-123"


@pytest.mark.asyncio
async def test_get_application_context_with_overwrites(mock_internal_http_client):
    """Test overwriting application context values."""
    service = ApplicationContextService(mock_internal_http_client)

    # First call to populate cache
    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        return_value={"application": None, "environment": None, "applicationId": None},
    ):
        await service.get_application_context()

    # Second call with overwrites
    context = await service.get_application_context(
        overwrite_application="overwrite-app",
        overwrite_application_id="overwrite-id",
        overwrite_environment="overwrite-env",
    )

    assert context.application == "overwrite-app"
    assert context.application_id == "overwrite-id"
    assert context.environment == "overwrite-env"


@pytest.mark.asyncio
async def test_get_application_context_fallback_to_client_id(mock_internal_http_client):
    """Test fallback to clientId when token and parsing fail."""
    service = ApplicationContextService(mock_internal_http_client)

    # Mock token extraction to fail
    mock_internal_http_client.token_manager.get_client_token = AsyncMock(
        side_effect=Exception("Token fetch failed")
    )

    # Use non-standard clientId format
    mock_internal_http_client.config.client_id = "non-standard-client-id"

    context = await service.get_application_context()

    assert context.application == "non-standard-client-id"
    assert context.environment == "unknown"
    assert context.application_id is None


@pytest.mark.asyncio
async def test_get_application_context_caching(mock_internal_http_client):
    """Test that application context is cached."""
    service = ApplicationContextService(mock_internal_http_client)

    # Mock token extraction
    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        return_value={
            "application": "cached-app",
            "environment": "cached-env",
            "applicationId": "cached-id",
        },
    ):
        context1 = await service.get_application_context()
        context2 = await service.get_application_context()

    # Should return same cached context
    assert context1.application == context2.application
    assert context1.environment == context2.environment
    assert context1.application_id == context2.application_id


def test_parse_client_id_format_valid():
    """Test parsing valid clientId format."""
    service = ApplicationContextService(Mock())
    parsed = service._parse_client_id_format("miso-controller-miso-test-app")

    assert parsed["application"] == "test-app"
    assert parsed["environment"] == "miso"


def test_parse_client_id_format_invalid():
    """Test parsing invalid clientId format."""
    service = ApplicationContextService(Mock())
    parsed = service._parse_client_id_format("invalid-format")

    assert parsed["application"] is None
    assert parsed["environment"] is None


def test_parse_client_id_format_multi_part_application():
    """Test parsing clientId with multi-part application name."""
    service = ApplicationContextService(Mock())
    parsed = service._parse_client_id_format("miso-controller-miso-test-app-v2")

    assert parsed["application"] == "test-app-v2"
    assert parsed["environment"] == "miso"


def test_application_context_to_dict():
    """Test ApplicationContext.to_dict() method."""
    context = ApplicationContext(
        application="test-app",
        application_id="app-123",
        environment="production",
    )

    result = context.to_dict()

    assert result == {
        "application": "test-app",
        "applicationId": "app-123",
        "environment": "production",
    }


def test_clear_cache(mock_internal_http_client):
    """Test clearing cached context."""
    service = ApplicationContextService(mock_internal_http_client)
    service._cached_context = ApplicationContext("test", "id", "env")

    service.clear_cache()

    assert service._cached_context is None


def test_get_application_context_sync_from_cached_token(mock_internal_http_client):
    """Test synchronous method uses cached client token without async calls."""
    service = ApplicationContextService(mock_internal_http_client)
    # Set cached token directly (synchronous access)
    mock_internal_http_client.token_manager.client_token = "cached-client-token"

    # Mock token extraction to return values
    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        return_value={
            "application": "sync-app",
            "environment": "sync-env",
            "applicationId": "sync-id",
        },
    ):
        context = service.get_application_context_sync()

    # Verify result
    assert context.application == "sync-app"
    assert context.environment == "sync-env"
    assert context.application_id == "sync-id"
    # Verify get_client_token was NOT called (no async call)
    mock_internal_http_client.token_manager.get_client_token.assert_not_called()


def test_get_application_context_sync_from_client_id_format(mock_internal_http_client):
    """Test synchronous method falls back to clientId parsing when no token."""
    service = ApplicationContextService(mock_internal_http_client)
    # No cached token
    mock_internal_http_client.token_manager.client_token = None

    # Mock token extraction to return None (fallback to clientId parsing)
    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        return_value={"application": None, "environment": None, "applicationId": None},
    ):
        context = service.get_application_context_sync()

    # Should parse from clientId format
    assert context.application == "test-app"
    assert context.environment == "miso"
    assert context.application_id is None
    # Verify get_client_token was NOT called (no async call)
    mock_internal_http_client.token_manager.get_client_token.assert_not_called()


def test_get_application_context_sync_caching(mock_internal_http_client):
    """Test synchronous method caches result."""
    service = ApplicationContextService(mock_internal_http_client)
    mock_internal_http_client.token_manager.client_token = "cached-token"

    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        return_value={
            "application": "cached-app",
            "environment": "cached-env",
            "applicationId": "cached-id",
        },
    ) as mock_extract:
        context1 = service.get_application_context_sync()
        context2 = service.get_application_context_sync()

    # Should return same cached context
    assert context1 is context2
    assert context1.application == "cached-app"
    # extract_client_token_info should only be called once (cached on second call)
    assert mock_extract.call_count == 1


def test_get_application_context_sync_no_controller_calls(mock_internal_http_client):
    """Test synchronous method does not trigger controller calls."""
    service = ApplicationContextService(mock_internal_http_client)
    mock_internal_http_client.token_manager.client_token = "cached-token"

    # Verify get_client_token is never called (would trigger controller call)
    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        return_value={
            "application": "test-app",
            "environment": "test-env",
            "applicationId": None,
        },
    ):
        context = service.get_application_context_sync()

    # Verify no async token fetch was attempted
    assert not mock_internal_http_client.token_manager.get_client_token.called
    assert context.application == "test-app"


@pytest.mark.asyncio
async def test_get_application_context_exception_handling(mock_internal_http_client):
    """Test get_application_context exception handling (lines 205-206)."""
    service = ApplicationContextService(mock_internal_http_client)

    # Mock get_client_token to raise exception
    mock_internal_http_client.token_manager.get_client_token = AsyncMock(
        side_effect=Exception("Token fetch failed")
    )

    # Should fall back to clientId parsing
    context = await service.get_application_context()

    assert context.application == "test-app"
    assert context.environment == "miso"


def test_get_application_context_sync_token_extraction_exception(mock_internal_http_client):
    """Test synchronous method handles token extraction exception (lines 137-139)."""
    service = ApplicationContextService(mock_internal_http_client)
    mock_internal_http_client.token_manager.client_token = "cached-token"

    # Mock token extraction to raise exception
    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        side_effect=Exception("Token extraction failed"),
    ):
        context = service.get_application_context_sync()

    # Should fall back to clientId parsing
    assert context.application == "test-app"
    assert context.environment == "miso"


def test_get_application_context_sync_final_fallback(mock_internal_http_client):
    """Test synchronous method final fallback when parsing fails (lines 157-163)."""
    service = ApplicationContextService(mock_internal_http_client)
    mock_internal_http_client.token_manager.client_token = None

    # Use non-standard clientId format that won't parse
    mock_internal_http_client.config.client_id = "non-standard-client-id"

    # Mock token extraction to return None
    with patch(
        "miso_client.services.application_context.extract_client_token_info",
        return_value={"application": None, "environment": None, "applicationId": None},
    ):
        context = service.get_application_context_sync()

    # Should use clientId as application name with "unknown" environment
    assert context.application == "non-standard-client-id"
    assert context.environment == "unknown"
    assert context.application_id is None


def test_build_context_with_overwrites_exception_handling(mock_internal_http_client):
    """Test _build_context_with_overwrites exception handling (lines 267-276)."""
    service = ApplicationContextService(mock_internal_http_client)
    service._cached_context = None  # No cached context

    # Mock _parse_client_id_format to raise exception
    with patch.object(service, "_parse_client_id_format", side_effect=Exception("Parse failed")):
        context = service._build_context_with_overwrites(
            overwrite_application="overwrite-app",
            overwrite_application_id=None,
            overwrite_environment="overwrite-env",
        )

    # Should use clientId as fallback for non-overwritten values
    assert context.application == "overwrite-app"
    assert context.environment == "overwrite-env"
    assert context.application_id is None
