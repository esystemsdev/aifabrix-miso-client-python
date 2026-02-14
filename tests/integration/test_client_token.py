"""
Integration tests for client ID and client token validation.

Validates that MISO_CLIENTID, MISO_CLIENTSECRET, and controller connectivity work:
get_environment_token() then log.info() with client credentials.

To run:
  pytest tests/integration/test_client_token.py -v
  Or: make test-integration
"""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from miso_client import MisoClient
from miso_client.errors import ConfigurationError
from miso_client.utils.config_loader import load_config

pytestmark = pytest.mark.integration

project_root = Path(__file__).resolve().parent.parent.parent
env_path = project_root / ".env"

if env_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        pass


@pytest.fixture(scope="module")
def config():
    """Load config from .env file."""
    try:
        return load_config()
    except ConfigurationError as e:
        pytest.skip(f"Failed to load config from .env: {e}")


@pytest.fixture
def client(config):
    """Initialize MisoClient instance (function-scoped to avoid event loop issues)."""
    try:
        client_instance = MisoClient(config)
        yield client_instance
    except Exception as e:
        pytest.skip(f"Failed to initialize MisoClient: {e}")
    finally:
        pass


@pytest.fixture(scope="module", autouse=True)
def patch_timeout():
    """Patch HTTP client timeout to 500ms for fast test failure."""
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
    """Check if tests should be skipped."""
    return (
        not config or not config.controller_url or not config.client_id or not config.client_secret
    )


async def wait_for_client_logging(client):
    """Wait for HTTP client logging tasks to complete."""
    try:
        if hasattr(client, "http_client") and hasattr(
            client.http_client, "_wait_for_logging_tasks"
        ):
            try:
                await asyncio.wait_for(
                    client.http_client._wait_for_logging_tasks(timeout=0.5), timeout=0.6
                )
            except (RuntimeError, asyncio.CancelledError, asyncio.TimeoutError):
                pass
    except (RuntimeError, asyncio.CancelledError):
        pass
    except Exception:
        pass


class TestClientToken:
    """Validate client ID and client token with the Miso Controller."""

    @pytest.mark.asyncio
    async def test_client_id_and_token_validation(self, client, config):
        """Obtain client token and send a log (client credentials accepted by controller)."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            token = await client.get_environment_token()
            assert token and isinstance(token, str), (
                "get_environment_token() must return a non-empty token"
            )
            await client.log.info(
                "Integration test: client token validation",
                context={"source": "test_client_token"},
            )
            await wait_for_client_logging(client)
        except Exception as e:
            pytest.fail(f"Client ID and token validation failed: {e}")
        finally:
            await client.disconnect()
