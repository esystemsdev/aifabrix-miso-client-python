"""
Unit tests for config loader.
"""

import os
from unittest.mock import patch

import pytest

from miso_client.errors import ConfigurationError
from miso_client.utils.config_loader import load_config


class TestConfigLoader:
    """Test cases for config loader."""

    def test_load_config_minimal(self):
        """Test loading minimal config."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
            },
            clear=False,
        ):
            # Remove conflicting variables that might be set in .env
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.client_id == "test-client"
                assert config.client_secret == "test-secret"
                assert config.controller_url == "https://controller.aifabrix.ai"
                assert config.log_level == "info"
                assert config.redis is None

    def test_load_config_with_custom_url(self):
        """Test loading config with custom controller URL."""
        with patch.dict(
            os.environ,
            {
                "MISO_CONTROLLER_URL": "https://custom.controller.com",
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
            },
            clear=False,
        ):
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.controller_url == "https://custom.controller.com"

    def test_load_config_with_redis(self):
        """Test loading config with Redis."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "REDIS_HOST": "redis-host",
                "REDIS_PORT": "6380",
                "REDIS_PASSWORD": "redis-pass",
                "REDIS_DB": "1",
                "REDIS_KEY_PREFIX": "custom:",
            },
            clear=False,
        ):
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.redis is not None
                assert config.redis.host == "redis-host"
                assert config.redis.port == 6380
                assert config.redis.password == "redis-pass"
                assert config.redis.db == 1
                assert config.redis.key_prefix == "custom:"

    def test_load_config_with_log_level(self):
        """Test loading config with log level."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "MISO_LOG_LEVEL": "debug",
            },
            clear=False,
        ):
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.log_level == "debug"

    def test_load_config_alternative_env_names(self):
        """Test loading config with alternative environment variable names."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENT_ID": "test-client-alt",
                "MISO_CLIENT_SECRET": "test-secret-alt",
            },
            clear=False,
        ):
            # Remove primary names and conflicting variables
            os.environ.pop("MISO_CLIENTID", None)
            os.environ.pop("MISO_CLIENTSECRET", None)
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.client_id == "test-client-alt"
                assert config.client_secret == "test-secret-alt"

    def test_load_config_missing_client_id(self):
        """Test error when client ID is missing."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTSECRET": "test-secret",
            },
            clear=False,
        ):
            # Remove client ID variables and conflicting variables
            os.environ.pop("MISO_CLIENTID", None)
            os.environ.pop("MISO_CLIENT_ID", None)
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            with patch("dotenv.load_dotenv"):
                with pytest.raises(ConfigurationError, match="MISO_CLIENTID"):
                    load_config()

    def test_load_config_missing_client_secret(self):
        """Test error when client secret is missing."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
            },
            clear=False,
        ):
            # Remove client secret variables and conflicting variables
            os.environ.pop("MISO_CLIENTSECRET", None)
            os.environ.pop("MISO_CLIENT_SECRET", None)
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            with patch("dotenv.load_dotenv"):
                with pytest.raises(ConfigurationError, match="MISO_CLIENTSECRET"):
                    load_config()

    def test_load_config_redis_defaults(self):
        """Test Redis config with defaults."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "REDIS_HOST": "redis-host",
            },
            clear=False,
        ):
            # Remove Redis variables that should use defaults and conflicting variables
            os.environ.pop("REDIS_PORT", None)
            os.environ.pop("REDIS_DB", None)
            os.environ.pop("REDIS_KEY_PREFIX", None)
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.redis is not None
                assert config.redis.port == 6379  # Default
                assert config.redis.db == 0  # Default
                assert config.redis.key_prefix == "miso:"  # Default
                assert config.redis.password is None

    def test_load_config_dotenv_support(self):
        """Test that dotenv is supported if available."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
            },
            clear=False,
        ):
            with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                # Simulate dotenv available
                try:
                    load_config()
                    # If no ImportError, dotenv should be called
                except ImportError:
                    # dotenv not available, should still work
                    config = load_config()
                    assert config.client_id == "test-client"

    def test_load_config_with_api_key(self):
        """Test loading config with API_KEY."""
        # Remove API_KEY and MISO_API_KEY if they exist to ensure we use the patched value
        original_api_key = os.environ.pop("API_KEY", None)
        original_miso_api_key = os.environ.pop("MISO_API_KEY", None)
        try:
            with patch.dict(
                os.environ,
                {
                    "MISO_CLIENTID": "test-client",
                    "MISO_CLIENTSECRET": "test-secret",
                    "API_KEY": "test-api-key-123",
                },
                clear=False,
            ):
                with patch("dotenv.load_dotenv"):
                    config = load_config()

                    assert config.api_key == "test-api-key-123"
        finally:
            # Restore original values
            if original_api_key:
                os.environ["API_KEY"] = original_api_key
            if original_miso_api_key:
                os.environ["MISO_API_KEY"] = original_miso_api_key

    def test_load_config_without_api_key(self):
        """Test loading config without API_KEY (should be None)."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
            },
            clear=False,
        ):
            # Remove API_KEY variables and conflicting variables
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("REDIS_PORT", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.api_key is None

    def test_load_config_with_client_token_uri(self):
        """Test loading config with client token URI."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "MISO_CLIENT_TOKEN_URI": "/api/v1/auth/custom-token",
            },
            clear=False,
        ):
            # Remove conflicting variables
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.clientTokenUri == "/api/v1/auth/custom-token"

    def test_load_config_without_client_token_uri(self):
        """Test loading config without client token URI (should be None)."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
            },
            clear=False,
        ):
            # Remove conflicting variables
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            os.environ.pop("MISO_CLIENT_TOKEN_URI", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.clientTokenUri is None

    def test_load_config_with_allowed_origins(self):
        """Test loading config with allowed origins."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "MISO_ALLOWED_ORIGINS": "http://localhost:3000,https://example.com",
            },
            clear=False,
        ):
            # Remove conflicting variables
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.allowedOrigins == ["http://localhost:3000", "https://example.com"]

    def test_load_config_with_allowed_origins_wildcard(self):
        """Test loading config with allowed origins including wildcard."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "MISO_ALLOWED_ORIGINS": "http://localhost:*,https://example.com:443",
            },
            clear=False,
        ):
            # Remove conflicting variables
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.allowedOrigins == ["http://localhost:*", "https://example.com:443"]

    def test_load_config_with_allowed_origins_whitespace(self):
        """Test loading config with allowed origins containing whitespace."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "MISO_ALLOWED_ORIGINS": " http://localhost:3000 , https://example.com ",
            },
            clear=False,
        ):
            # Remove conflicting variables
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.allowedOrigins == ["http://localhost:3000", "https://example.com"]

    def test_load_config_without_allowed_origins(self):
        """Test loading config without allowed origins (should be None)."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
            },
            clear=False,
        ):
            # Remove conflicting variables
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            os.environ.pop("MISO_ALLOWED_ORIGINS", None)
            # Mock load_dotenv to prevent loading from .env file
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()

                assert config.allowedOrigins is None
