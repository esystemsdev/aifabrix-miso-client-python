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
            # Remove MISO_CLIENTID if it exists
            os.environ.pop("MISO_CLIENTID", None)
            os.environ.pop("MISO_CLIENT_ID", None)

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
            # Remove MISO_CLIENTSECRET if it exists
            os.environ.pop("MISO_CLIENTSECRET", None)
            os.environ.pop("MISO_CLIENT_SECRET", None)

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
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "API_KEY": "test-api-key-123",
            },
            clear=False,
        ):
            config = load_config()

            assert config.api_key == "test-api-key-123"

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
            # Ensure API_KEY is not set
            os.environ.pop("API_KEY", None)

            config = load_config()

            assert config.api_key is None
