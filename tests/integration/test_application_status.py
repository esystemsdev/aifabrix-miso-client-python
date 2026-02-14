"""
Integration tests for Application Status API (logger + get/update application status).

Uses the same client-credentials authentication as other integration tests.
Requires MISO_CLIENTID in format miso-controller-{env}-{app} (e.g. miso-controller-dev-dataplane).

To run:
  pytest tests/integration/test_application_status.py -v
  Or: make validate-api (runs all integration tests)

Tests will skip if config is missing or client_id is not parseable as miso-controller-{env}-{app}.
"""

import asyncio
from pathlib import Path
from typing import Optional, Tuple
from unittest.mock import patch

import pytest

from miso_client import ApplicationStatus, MisoClient, UpdateSelfStatusRequest
from miso_client.errors import ConfigurationError
from miso_client.utils.config_loader import load_config

pytestmark = pytest.mark.integration

project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"

if env_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        pass


def get_env_key_app_key(client_id: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Parse env_key and app_key from clientId format: miso-controller-{env}-{app}."""
    if not client_id or not client_id.startswith("miso-controller-"):
        return None, None
    parts = client_id.split("-", 3)
    if len(parts) < 4:
        return None, None
    return parts[2], parts[3]


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
    finally:
        # Disconnect is async; fixture teardown runs sync - tests disconnect in finally
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


class TestApplicationStatus:
    """Integration tests for Application Status API (same auth as logger)."""

    @pytest.mark.asyncio
    async def test_logger_send_log(self, client, config):
        """Send log via client.log (client credentials / x-client-token)."""
        if should_skip(config):
            pytest.fail("Config not available")

        env_key, app_key = get_env_key_app_key(config.client_id)
        if not env_key or not app_key:
            pytest.fail("MISO_CLIENTID must be miso-controller-{env}-{app}")

        try:
            await client.initialize()
            await client.log.info(
                "Integration test log from test_application_status",
                context={"source": "test_application_status", "env": env_key, "app": app_key},
            )
            await wait_for_client_logging(client)
        except Exception as e:
            pytest.fail(f"Logger send log failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_get_application_status(self, client, config):
        """GET application status (client credentials / x-client-token, same as logger)."""
        if should_skip(config):
            pytest.fail("Config not available")

        env_key, app_key = get_env_key_app_key(config.client_id)
        if not env_key or not app_key:
            pytest.fail("MISO_CLIENTID must be miso-controller-{env}-{app}")

        try:
            await client.initialize()
            status = await client.get_application_status(env_key=env_key, app_key=app_key)
            assert status is not None
            assert hasattr(status, "status") or hasattr(status, "model_dump")
        except Exception as e:
            pytest.fail(f"Get application status failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_update_my_application_status(self, client, config):
        """UPDATE my application status (client credentials / x-client-token)."""
        if should_skip(config):
            pytest.fail("Config not available")

        env_key, app_key = get_env_key_app_key(config.client_id)
        if not env_key or not app_key:
            pytest.fail("MISO_CLIENTID must be miso-controller-{env}-{app}")

        try:
            await client.initialize()
            body = UpdateSelfStatusRequest(status=ApplicationStatus.HEALTHY)
            result = await client.update_my_application_status(body, env_key=env_key)
            assert result is not None
            assert hasattr(result, "success") or hasattr(result, "model_dump")
        except Exception as e:
            pytest.fail(f"Update my application status failed: {e}")
        finally:
            await client.disconnect()
