"""
Integration tests for Encryption Service (encrypt/decrypt) against miso-controller.

Tests require .env with MISO_CLIENTID, MISO_CLIENTSECRET, MISO_CONTROLLER_URL,
and MISO_ENCRYPTION_KEY or ENCRYPTION_KEY. Tests that need the controller
are skipped when encryption_key is not set.

Run: pytest tests/integration/test_encryption.py -v
Or: make test-integration
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from miso_client import EncryptionError, MisoClient
from miso_client.errors import ConfigurationError
from miso_client.utils.config_loader import load_config

pytestmark = pytest.mark.integration

project_root = Path(__file__).resolve().parent.parent.parent
env_path = project_root / ".env"

if env_path.exists():
    try:
        from dotenv import load_dotenv

        # Override so .env wins over tests/conftest.py ENCRYPTION_KEY (controller must match .env)
        load_dotenv(env_path, override=True)
    except ImportError:
        pass


@pytest.fixture(scope="module")
def config():
    """Load config from .env file."""
    try:
        return load_config()
    except ConfigurationError as e:
        pytest.fail(f"Failed to load config from .env: {e}")


@pytest.fixture
def client(config):
    """Initialize MisoClient instance (function-scoped to avoid event loop issues)."""
    try:
        client_instance = MisoClient(config)
        yield client_instance
    except Exception as e:
        pytest.fail(f"Failed to initialize MisoClient: {e}")


@pytest.fixture(scope="module", autouse=True)
def patch_timeout():
    """Patch HTTP client timeout for fast failure when controller is down."""
    import httpx

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["timeout"] = 0.5
            super().__init__(*args, **kwargs)

    with patch("httpx.AsyncClient", new=PatchedAsyncClient):
        with patch(
            "miso_client.utils.internal_http_client.httpx.AsyncClient",
            new=PatchedAsyncClient,
        ):
            with patch(
                "miso_client.utils.client_token_manager.httpx.AsyncClient",
                new=PatchedAsyncClient,
            ):
                yield


def should_skip(config) -> bool:
    """Skip when config or controller credentials are missing."""
    return (
        not config
        or not config.controller_url
        or not config.client_id
        or not config.client_secret
    )


def should_skip_encryption(config) -> bool:
    """Skip when encryption key is not set (required for encrypt/decrypt)."""
    return should_skip(config) or not config.encryption_key


class TestEncryptionIntegration:
    """Integration tests for encrypt/decrypt against miso-controller."""

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_round_trip(self, client, config):
        """Encrypt then decrypt and verify plaintext matches."""
        if should_skip_encryption(config):
            pytest.skip("Encryption key not set (MISO_ENCRYPTION_KEY or ENCRYPTION_KEY)")

        parameter_name = "integration-test-encryption-param"
        plaintext = "integration-test-secret-value"

        try:
            await client.initialize()
            result = await client.encrypt(plaintext, parameter_name)
            assert result is not None
            assert hasattr(result, "value")
            assert hasattr(result, "storage")
            assert result.value
            assert result.storage in ("keyvault", "local")

            decrypted = await client.decrypt(result.value, parameter_name)
            assert decrypted == plaintext
        except Exception as e:
            pytest.fail(f"Encrypt/decrypt round-trip failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_encrypt_returns_value_and_storage(self, client, config):
        """Encrypt returns EncryptResult with value and storage."""
        if should_skip_encryption(config):
            pytest.skip("Encryption key not set (MISO_ENCRYPTION_KEY or ENCRYPTION_KEY)")

        try:
            await client.initialize()
            result = await client.encrypt("test-secret", "integration-test-param-storage")
            assert result is not None
            assert isinstance(result.value, str)
            assert len(result.value) > 0
            assert result.storage in ("keyvault", "local")
            assert result.value.startswith(("kv://", "enc://"))
        except Exception as e:
            pytest.fail(f"Encrypt failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_decrypt_nonexistent_parameter_raises(self, client, config):
        """Decrypt with nonexistent parameter reference raises EncryptionError."""
        if should_skip_encryption(config):
            pytest.skip("Encryption key not set (MISO_ENCRYPTION_KEY or ENCRYPTION_KEY)")

        try:
            await client.initialize()
            with pytest.raises(EncryptionError) as exc_info:
                await client.decrypt(
                    "kv://nonexistent-integration-test-param",
                    "nonexistent-integration-test-param",
                )
            assert exc_info.value.code in (
                "PARAMETER_NOT_FOUND",
                "DECRYPTION_FAILED",
                "ACCESS_DENIED",
            )
        except pytest.raises.Exception:
            raise
        except Exception as e:
            pytest.fail(f"Decrypt nonexistent param test failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_encrypt_invalid_parameter_name_raises(self, client, config):
        """Encrypt with invalid parameter name raises INVALID_PARAMETER_NAME."""
        if should_skip_encryption(config):
            pytest.skip("Encryption key not set (MISO_ENCRYPTION_KEY or ENCRYPTION_KEY)")

        try:
            await client.initialize()
            with pytest.raises(EncryptionError) as exc_info:
                await client.encrypt("secret", "invalid name!")
            assert exc_info.value.code == "INVALID_PARAMETER_NAME"
        except pytest.raises.Exception:
            raise
        except Exception as e:
            pytest.fail(f"Encrypt invalid parameter name test failed: {e}")
        finally:
            await client.disconnect()
