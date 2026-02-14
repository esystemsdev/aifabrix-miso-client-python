"""
Manual tests for config loader encryption key (ENCRYPTION_KEY / MISO_ENCRYPTION_KEY).

Not run by make test. Run manually: pytest tests/manual/ -v
"""

import os
from unittest.mock import patch

from miso_client.utils.config_loader import load_config


class TestEncryptionKeyEnvFallback:
    """ENCRYPTION_KEY fallback when MISO_ENCRYPTION_KEY is not set."""

    def test_load_config_with_encryption_key_env_fallback(self):
        """Test loading config with ENCRYPTION_KEY when MISO_ENCRYPTION_KEY is not set."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "ENCRYPTION_KEY": "fallback-encryption-key",
            },
            clear=False,
        ):
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            os.environ.pop("MISO_API_KEY", None)
            os.environ.pop("MISO_ENCRYPTION_KEY", None)
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()
            assert config.encryption_key == "fallback-encryption-key"

    def test_load_config_miso_encryption_key_overrides_encryption_key(self):
        """Test that MISO_ENCRYPTION_KEY takes precedence over ENCRYPTION_KEY."""
        with patch.dict(
            os.environ,
            {
                "MISO_CLIENTID": "test-client",
                "MISO_CLIENTSECRET": "test-secret",
                "MISO_ENCRYPTION_KEY": "miso-key",
                "ENCRYPTION_KEY": "plain-key",
            },
            clear=False,
        ):
            os.environ.pop("MISO_CONTROLLER_URL", None)
            os.environ.pop("REDIS_HOST", None)
            os.environ.pop("API_KEY", None)
            with patch("dotenv.load_dotenv"):
                with patch("miso_client.utils.config_loader.load_dotenv", create=True):
                    config = load_config()
            assert config.encryption_key == "miso-key"
