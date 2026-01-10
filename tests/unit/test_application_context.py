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
