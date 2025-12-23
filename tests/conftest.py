"""
Shared pytest fixtures for MisoClient tests.
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client import MisoClient, MisoClientConfig, RedisConfig
from miso_client.api import ApiClient
from miso_client.services.cache import CacheService
from miso_client.services.redis import RedisService
from miso_client.utils.http_client import HttpClient

# Set test environment variables
os.environ["ENCRYPTION_KEY"] = "_-aheB8oQwob2XxUyN1JK2RLOs_Hpi3WSkKluxLZzmE="


@pytest.fixture
def config():
    """Test configuration with new API (client_id/client_secret)."""
    return MisoClientConfig(
        controller_url="https://controller.aifabrix.ai",
        client_id="test-client-id",
        client_secret="test-client-secret",
        redis=RedisConfig(
            host="localhost",
            port=6379,
            key_prefix="miso:",
        ),
        log_level="debug",
        cache={
            "roleTTL": 900,
            "permissionTTL": 900,
        },
    )


@pytest.fixture
def config_no_redis():
    """Test configuration without Redis."""
    return MisoClientConfig(
        controller_url="https://controller.aifabrix.ai",
        client_id="test-client-id",
        client_secret="test-client-secret",
        log_level="info",
    )


@pytest.fixture
def http_client(config):
    """HTTP client fixture."""
    return HttpClient(config)


@pytest.fixture
def redis_service(config):
    """Redis service fixture."""
    return RedisService(config.redis)


@pytest.fixture
def mock_redis():
    """Mock Redis service."""
    redis = MagicMock(spec=RedisService)
    redis.is_connected = MagicMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.rpush = AsyncMock(return_value=True)
    redis.connect = AsyncMock()
    redis.disconnect = AsyncMock()
    return redis


@pytest.fixture
def mock_cache():
    """Mock Cache service."""
    cache = MagicMock(spec=CacheService)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.clear = AsyncMock()
    return cache


@pytest.fixture
def mock_http_client(config):
    """Mock HTTP client."""
    http_client = MagicMock(spec=HttpClient)
    http_client.config = config
    http_client.get = AsyncMock(return_value={})
    http_client.post = AsyncMock(return_value={})
    http_client.put = AsyncMock(return_value={})
    http_client.delete = AsyncMock(return_value={})
    http_client.request = AsyncMock(return_value={})
    http_client.authenticated_request = AsyncMock(return_value={})
    http_client.get_environment_token = AsyncMock(return_value="mock-client-token")
    http_client.close = AsyncMock()
    return http_client


@pytest.fixture
def mock_api_client(mock_http_client):
    """Mock API client."""
    from miso_client.api.auth_api import AuthApi
    from miso_client.api.logs_api import LogsApi
    from miso_client.api.permissions_api import PermissionsApi
    from miso_client.api.roles_api import RolesApi

    api_client = MagicMock(spec=ApiClient)
    api_client.http_client = mock_http_client

    # Mock API sub-clients
    api_client.auth = MagicMock(spec=AuthApi)
    api_client.roles = MagicMock(spec=RolesApi)
    api_client.permissions = MagicMock(spec=PermissionsApi)
    api_client.logs = MagicMock(spec=LogsApi)

    return api_client


@pytest.fixture
def client(config):
    """Test MisoClient instance."""
    return MisoClient(config)
