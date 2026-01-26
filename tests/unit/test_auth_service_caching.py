"""
Unit tests for AuthService user info caching.

Tests caching functionality for get_user_info() method including cache hits,
cache misses, error handling, and cache clearing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miso_client.models.config import MisoClientConfig
from miso_client.services.auth import AuthService
from miso_client.services.cache import CacheService
from miso_client.services.redis import RedisService
from miso_client.utils.http_client import HttpClient


class TestAuthServiceUserInfoCaching:
    """Test cases for AuthService user info caching."""

    @pytest.fixture
    def config(self):
        """Test configuration."""
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            cache={
                "userTTL": 300,  # 5 minutes
            },
        )

    @pytest.fixture
    def config_custom_ttl(self):
        """Test configuration with custom user TTL."""
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            cache={
                "user_ttl": 600,  # 10 minutes (using snake_case)
            },
        )

    @pytest.fixture
    def mock_http_client(self, config):
        """Mock HTTP client."""
        http_client = MagicMock(spec=HttpClient)
        http_client.config = config
        http_client.authenticated_request = AsyncMock()
        http_client.clear_user_token = MagicMock()
        return http_client

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis service."""
        redis = MagicMock(spec=RedisService)
        redis.is_connected = MagicMock(return_value=True)
        return redis

    @pytest.fixture
    def mock_cache(self):
        """Mock Cache service."""
        cache = MagicMock(spec=CacheService)
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=True)
        cache.delete = AsyncMock(return_value=True)
        return cache

    @pytest.fixture
    def auth_service(self, mock_http_client, mock_redis, mock_cache):
        """Create AuthService instance with mocks."""
        return AuthService(
            http_client=mock_http_client,
            redis=mock_redis,
            cache=mock_cache,
        )

    @pytest.fixture
    def auth_service_no_cache(self, mock_http_client, mock_redis):
        """Create AuthService instance without cache."""
        return AuthService(
            http_client=mock_http_client,
            redis=mock_redis,
            cache=None,
        )

    @pytest.fixture
    def sample_user_info(self):
        """Sample user info for testing."""
        return {
            "id": "user-123",
            "username": "testuser",
            "email": "test@example.com",
            "firstName": "Test",
            "lastName": "User",
            "roles": ["user", "admin"],
        }

    @pytest.fixture
    def sample_token(self):
        """Sample JWT token with user ID in 'sub' claim."""
        # This is a mock token - in real tests we'd use jwt_tools.extract_user_id
        return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLTEyMyIsIm5hbWUiOiJUZXN0IFVzZXIifQ.signature"

    # ========== Cache Hit Tests ==========

    @pytest.mark.asyncio
    async def test_get_user_info_cache_hit(
        self, auth_service, mock_cache, sample_user_info, sample_token
    ):
        """Test get_user_info returns cached user info on cache hit."""
        # Setup cache to return cached data
        cached_data = {
            "user": sample_user_info,
            "timestamp": 1234567890000,
        }
        mock_cache.get = AsyncMock(return_value=cached_data)

        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value="user-123"):
            result = await auth_service.get_user_info(sample_token)

        assert result is not None
        assert result.id == "user-123"
        assert result.username == "testuser"
        assert result.email == "test@example.com"
        # Cache should have been checked
        mock_cache.get.assert_called_once_with("user:user-123")
        # HTTP client should NOT have been called (cache hit)
        auth_service.http_client.authenticated_request.assert_not_called()

    # ========== Cache Miss Tests ==========

    @pytest.mark.asyncio
    async def test_get_user_info_cache_miss_fetches_from_api(
        self, auth_service, mock_cache, mock_http_client, sample_user_info, sample_token
    ):
        """Test get_user_info fetches from API on cache miss and caches result."""
        # Setup cache miss
        mock_cache.get = AsyncMock(return_value=None)
        # Setup API response
        mock_http_client.authenticated_request = AsyncMock(return_value=sample_user_info)

        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value="user-123"):
            result = await auth_service.get_user_info(sample_token)

        assert result is not None
        assert result.id == "user-123"
        assert result.username == "testuser"
        # API should have been called
        mock_http_client.authenticated_request.assert_called_once()
        # Result should have been cached
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "user:user-123"
        assert call_args[0][1]["user"]["id"] == "user-123"
        assert "timestamp" in call_args[0][1]
        assert call_args[0][2] == 300  # Default TTL

    @pytest.mark.asyncio
    async def test_get_user_info_no_caching_without_user_id(
        self, auth_service, mock_cache, mock_http_client, sample_user_info, sample_token
    ):
        """Test get_user_info doesn't cache when userId cannot be extracted."""
        # Setup cache miss
        mock_cache.get = AsyncMock(return_value=None)
        # Setup API response
        mock_http_client.authenticated_request = AsyncMock(return_value=sample_user_info)

        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value=None):
            result = await auth_service.get_user_info(sample_token)

        assert result is not None
        assert result.id == "user-123"
        # API should have been called
        mock_http_client.authenticated_request.assert_called_once()
        # Result should NOT have been cached (no user ID)
        mock_cache.set.assert_not_called()

    # ========== Custom TTL Tests ==========

    @pytest.mark.asyncio
    async def test_get_user_info_custom_ttl_from_config(
        self, config_custom_ttl, mock_redis, mock_cache, sample_user_info, sample_token
    ):
        """Test get_user_info uses custom TTL from config."""
        # Create service with custom TTL config
        mock_http_client = MagicMock(spec=HttpClient)
        mock_http_client.config = config_custom_ttl
        mock_http_client.authenticated_request = AsyncMock(return_value=sample_user_info)

        auth_service = AuthService(
            http_client=mock_http_client,
            redis=mock_redis,
            cache=mock_cache,
        )

        # Setup cache miss
        mock_cache.get = AsyncMock(return_value=None)

        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value="user-123"):
            await auth_service.get_user_info(sample_token)

        # Verify custom TTL was used
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert call_args[0][2] == 600  # Custom TTL from config

    # ========== Error Handling Tests ==========

    @pytest.mark.asyncio
    async def test_get_user_info_returns_none_on_api_error(
        self, auth_service, mock_cache, mock_http_client, sample_token
    ):
        """Test get_user_info returns None on API error."""
        # Setup cache miss and API error
        mock_cache.get = AsyncMock(return_value=None)
        mock_http_client.authenticated_request = AsyncMock(side_effect=Exception("API error"))

        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value="user-123"):
            result = await auth_service.get_user_info(sample_token)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_info_returns_none_for_api_key(self, auth_service):
        """Test get_user_info returns None when token is API key."""
        auth_service.config.api_key = "test-api-key"

        result = await auth_service.get_user_info("test-api-key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_info_no_cache_service(
        self, auth_service_no_cache, mock_http_client, sample_user_info, sample_token
    ):
        """Test get_user_info works without cache service."""
        mock_http_client.authenticated_request = AsyncMock(return_value=sample_user_info)

        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value="user-123"):
            result = await auth_service_no_cache.get_user_info(sample_token)

        assert result is not None
        assert result.id == "user-123"
        # API should have been called
        mock_http_client.authenticated_request.assert_called_once()

    # ========== Clear User Cache Tests ==========

    @pytest.mark.asyncio
    async def test_clear_user_cache_success(self, auth_service, mock_cache, sample_token):
        """Test clear_user_cache deletes cache entry."""
        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value="user-123"):
            await auth_service.clear_user_cache(sample_token)

        mock_cache.delete.assert_called_once_with("user:user-123")

    @pytest.mark.asyncio
    async def test_clear_user_cache_no_user_id(self, auth_service, mock_cache, sample_token):
        """Test clear_user_cache does nothing when userId cannot be extracted."""
        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value=None):
            await auth_service.clear_user_cache(sample_token)

        mock_cache.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_user_cache_no_cache_service(self, auth_service_no_cache, sample_token):
        """Test clear_user_cache handles missing cache service."""
        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value="user-123"):
            # Should not raise exception
            await auth_service_no_cache.clear_user_cache(sample_token)

    @pytest.mark.asyncio
    async def test_clear_user_cache_handles_error(self, auth_service, mock_cache, sample_token):
        """Test clear_user_cache handles cache delete error gracefully."""
        mock_cache.delete = AsyncMock(side_effect=Exception("Cache error"))

        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value="user-123"):
            # Should not raise exception
            await auth_service.clear_user_cache(sample_token)

    # ========== Logout Clears User Cache Tests ==========

    @pytest.mark.asyncio
    async def test_logout_clears_user_cache(
        self, auth_service, mock_cache, mock_http_client, sample_token
    ):
        """Test logout clears both token validation and user info caches."""
        mock_http_client.authenticated_request = AsyncMock(return_value={"data": None})

        with patch("miso_client.services.auth_user_cache.extract_user_id", return_value="user-123"):
            await auth_service.logout(sample_token)

        # Verify both caches were cleared
        delete_calls = mock_cache.delete.call_args_list
        assert len(delete_calls) == 2
        # First call clears token validation cache
        assert "token_validation:" in delete_calls[0][0][0]
        # Second call clears user info cache
        assert delete_calls[1][0][0] == "user:user-123"

    # ========== Cache Key Format Tests ==========

    def test_get_user_cache_key_format(self, auth_service):
        """Test user cache key follows expected format."""
        cache_key = auth_service._get_user_cache_key("user-123")
        assert cache_key == "user:user-123"

    # ========== Config TTL Property Tests ==========

    def test_user_ttl_default_value(self, config):
        """Test user_ttl returns default when not configured."""
        config_no_user_ttl = MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
        )
        assert config_no_user_ttl.user_ttl == 300  # Default 5 minutes

    def test_user_ttl_snake_case_config(self, config_custom_ttl):
        """Test user_ttl reads snake_case config."""
        assert config_custom_ttl.user_ttl == 600

    def test_user_ttl_camel_case_config(self, config):
        """Test user_ttl reads camelCase config."""
        assert config.user_ttl == 300
