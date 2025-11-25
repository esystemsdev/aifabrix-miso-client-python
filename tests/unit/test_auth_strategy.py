"""
Unit tests for authentication strategy functionality.

This module contains tests for AuthStrategyHandler and authentication strategy
support in HTTP clients and services.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miso_client.errors import MisoClientError
from miso_client.models.config import AuthStrategy, MisoClientConfig
from miso_client.utils.auth_strategy import AuthStrategyHandler


class TestAuthStrategyHandler:
    """Test cases for AuthStrategyHandler."""

    def test_build_auth_headers_bearer(self):
        """Test building headers for bearer authentication."""
        strategy = AuthStrategy(methods=["bearer"], bearerToken="test-token-123")
        headers = AuthStrategyHandler.build_auth_headers("bearer", strategy, None)
        assert headers == {"Authorization": "Bearer test-token-123"}

    def test_build_auth_headers_bearer_missing_token(self):
        """Test building headers for bearer without token raises error."""
        strategy = AuthStrategy(methods=["bearer"])
        with pytest.raises(ValueError, match="bearerToken is required"):
            AuthStrategyHandler.build_auth_headers("bearer", strategy, None)

    def test_build_auth_headers_client_token(self):
        """Test building headers for client-token authentication."""
        strategy = AuthStrategy(methods=["client-token"])
        headers = AuthStrategyHandler.build_auth_headers(
            "client-token", strategy, "client-token-123"
        )
        assert headers == {"x-client-token": "client-token-123"}

    def test_build_auth_headers_client_token_missing(self):
        """Test building headers for client-token without token raises error."""
        strategy = AuthStrategy(methods=["client-token"])
        with pytest.raises(ValueError, match="client_token is required"):
            AuthStrategyHandler.build_auth_headers("client-token", strategy, None)

    def test_build_auth_headers_client_credentials(self):
        """Test building headers for client-credentials authentication."""
        strategy = AuthStrategy(methods=["client-credentials"])
        headers = AuthStrategyHandler.build_auth_headers(
            "client-credentials", strategy, "client-token-123"
        )
        assert headers == {"x-client-token": "client-token-123"}

    def test_build_auth_headers_api_key(self):
        """Test building headers for api-key authentication."""
        strategy = AuthStrategy(methods=["api-key"], apiKey="test-api-key-123")
        headers = AuthStrategyHandler.build_auth_headers("api-key", strategy, None)
        assert headers == {"Authorization": "Bearer test-api-key-123"}

    def test_build_auth_headers_api_key_missing(self):
        """Test building headers for api-key without key raises error."""
        strategy = AuthStrategy(methods=["api-key"])
        with pytest.raises(ValueError, match="apiKey is required"):
            AuthStrategyHandler.build_auth_headers("api-key", strategy, None)

    def test_should_try_method(self):
        """Test should_try_method returns True for methods in strategy."""
        strategy = AuthStrategy(methods=["bearer", "api-key"])
        assert AuthStrategyHandler.should_try_method("bearer", strategy) is True
        assert AuthStrategyHandler.should_try_method("api-key", strategy) is True
        assert AuthStrategyHandler.should_try_method("client-token", strategy) is False

    def test_get_default_strategy(self):
        """Test get_default_strategy returns default strategy."""
        strategy = AuthStrategyHandler.get_default_strategy()
        assert strategy.methods == ["bearer", "client-token"]
        assert strategy.bearerToken is None
        assert strategy.apiKey is None


class TestInternalHttpClientAuthStrategy:
    """Test cases for InternalHttpClient with auth strategy."""

    @pytest.fixture
    def config(self):
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
        )

    @pytest.fixture
    def http_client(self, config):
        from miso_client.utils.internal_http_client import InternalHttpClient

        return InternalHttpClient(config)

    @pytest.mark.asyncio
    async def test_authenticated_request_with_strategy(self, http_client):
        """Test authenticated_request with auth strategy."""
        strategy = AuthStrategy(methods=["bearer"], bearerToken="test-token")

        with patch.object(
            http_client, "request_with_auth_strategy", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"data": "test"}
            result = await http_client.authenticated_request(
                "GET", "/api/test", "test-token", auth_strategy=strategy
            )
            assert result == {"data": "test"}
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticated_request_backward_compatibility(self, http_client):
        """Test authenticated_request without strategy (backward compatibility)."""
        with patch.object(
            http_client, "request_with_auth_strategy", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"data": "test"}
            result = await http_client.authenticated_request("GET", "/api/test", "test-token")
            assert result == {"data": "test"}
            # Should create default strategy with bearer token
            call_args = mock_request.call_args
            strategy = call_args[0][2]  # Third positional arg is auth_strategy
            assert strategy.methods == ["bearer", "client-token"]
            assert strategy.bearerToken == "test-token"

    @pytest.mark.asyncio
    async def test_request_with_auth_strategy_success(self, http_client):
        """Test request_with_auth_strategy with successful request."""
        strategy = AuthStrategy(methods=["bearer"], bearerToken="test-token")

        with patch.object(http_client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"data": "test"}
            result = await http_client.request_with_auth_strategy("GET", "/api/test", strategy)
            assert result == {"data": "test"}
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_with_auth_strategy_401_fallback(self, http_client):
        """Test request_with_auth_strategy falls back on 401."""
        strategy = AuthStrategy(
            methods=["bearer", "api-key"], bearerToken="test-token", apiKey="test-key"
        )

        import httpx

        error_401 = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )

        with patch.object(http_client, "request", new_callable=AsyncMock) as mock_request:
            # First call returns 401, second succeeds
            mock_request.side_effect = [error_401, {"data": "success"}]
            result = await http_client.request_with_auth_strategy("GET", "/api/test", strategy)
            assert result == {"data": "success"}
            # Should have tried twice (bearer failed, api-key succeeded)
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_request_with_auth_strategy_all_methods_fail(self, http_client):
        """Test request_with_auth_strategy when all methods fail."""
        strategy = AuthStrategy(
            methods=["bearer", "api-key"], bearerToken="test-token", apiKey="test-key"
        )

        import httpx

        error_401 = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )

        with patch.object(http_client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = error_401
            with pytest.raises(MisoClientError, match="All authentication methods failed"):
                await http_client.request_with_auth_strategy("GET", "/api/test", strategy)


class TestHttpClientAuthStrategy:
    """Test cases for HttpClient with auth strategy."""

    @pytest.fixture
    def config(self):
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
        )

    @pytest.fixture
    def mock_logger(self):
        logger = MagicMock()
        logger.log = AsyncMock()
        return logger

    @pytest.fixture
    def http_client(self, config, mock_logger):
        from miso_client.services.logger import LoggerService

        logger_service = LoggerService(MagicMock(), MagicMock())
        from miso_client.utils.http_client import HttpClient

        return HttpClient(config, logger_service)

    @pytest.mark.asyncio
    async def test_request_with_auth_strategy(self, http_client):
        """Test HttpClient request_with_auth_strategy."""
        strategy = AuthStrategy(methods=["bearer"], bearerToken="test-token")

        with patch.object(
            http_client._internal_client, "request_with_auth_strategy", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"data": "test"}
            result = await http_client.request_with_auth_strategy("GET", "/api/test", strategy)
            assert result == {"data": "test"}
            mock_request.assert_called_once()


class TestConfigLoaderAuthStrategy:
    """Test cases for config loader with auth strategy."""

    @pytest.mark.asyncio
    async def test_load_config_with_auth_strategy(self):
        """Test loading config with MISO_AUTH_STRATEGY environment variable."""
        import os
        from unittest.mock import patch

        from miso_client.utils.config_loader import load_config

        # Set required environment variables
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client-id",
                "MISO_CLIENTSECRET": "test-client-secret",
                "MISO_AUTH_STRATEGY": "bearer,api-key",
                "MISO_API_KEY": "test-api-key",
            },
            clear=False,
        ):
            # Remove conflicting API_KEY and other variables
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()
                assert config.authStrategy is not None
                assert config.authStrategy.methods == ["bearer", "api-key"]
                assert config.authStrategy.apiKey == "test-api-key"

    @pytest.mark.asyncio
    async def test_load_config_with_invalid_auth_strategy(self):
        """Test loading config with invalid auth strategy raises error."""
        import os
        from unittest.mock import patch

        from miso_client.errors import ConfigurationError
        from miso_client.utils.config_loader import load_config

        # Set required environment variables and invalid auth strategy
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client-id",
                "MISO_CLIENTSECRET": "test-client-secret",
                "MISO_AUTH_STRATEGY": "invalid-method",
            },
            clear=False,
        ):
            with pytest.raises(ConfigurationError, match="Invalid auth method"):
                load_config()


class TestMisoClientAuthStrategy:
    """Test cases for MisoClient with auth strategy."""

    @pytest.fixture
    def config(self):
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
        )

    @pytest.fixture
    def client(self, config):
        from miso_client import MisoClient

        return MisoClient(config)

    def test_create_auth_strategy(self, client):
        """Test create_auth_strategy helper method."""
        strategy = client.create_auth_strategy(["api-key"], bearer_token=None, api_key="test-key")
        assert strategy.methods == ["api-key"]
        assert strategy.apiKey == "test-key"
        assert strategy.bearerToken is None

    @pytest.mark.asyncio
    async def test_request_with_auth_strategy(self, client):
        """Test MisoClient request_with_auth_strategy."""
        strategy = AuthStrategy(methods=["bearer"], bearerToken="test-token")

        with patch.object(
            client.http_client, "request_with_auth_strategy", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"data": "test"}
            result = await client.request_with_auth_strategy("GET", "/api/test", strategy)
            assert result == {"data": "test"}
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_roles_with_auth_strategy(self, client):
        """Test get_roles with auth strategy."""
        strategy = AuthStrategy(methods=["bearer"], bearerToken="test-token")

        with patch.object(client.roles, "get_roles", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["admin", "user"]
            result = await client.get_roles("test-token", auth_strategy=strategy)
            assert result == ["admin", "user"]
            mock_get_roles.assert_called_once_with("test-token", auth_strategy=strategy)
