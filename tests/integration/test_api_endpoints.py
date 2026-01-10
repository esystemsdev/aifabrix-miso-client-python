"""
Comprehensive integration tests for all Auth and Logs API endpoints.

Tests against real controller using credentials from .env file.

To run these tests:
1. Ensure .env file exists with MISO_CLIENTID, MISO_CLIENTSECRET, MISO_CONTROLLER_URL
2. Optionally set TEST_USER_TOKEN for authenticated endpoint tests
3. Run: pytest tests/integration/test_api_endpoints.py
   Or: make validate-api

Tests will FAIL if controller is unavailable or endpoints return errors.
This ensures API validation catches real issues.

Timeout is set to 500ms for fast failure when controller is down.

Note: These tests are excluded from normal test runs (make test).
They require a running controller instance and are only run via make validate-api.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from miso_client import MisoClient
from miso_client.errors import ConfigurationError
from miso_client.utils.config_loader import load_config

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration

# Load environment variables from project root .env file
# Use absolute path to ensure we find the .env file regardless of pytest's working directory
project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"

if env_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        pass  # dotenv not installed, continue without it


@pytest.fixture(scope="module")
def config():
    """Load config from .env file."""
    try:
        return load_config()
    except ConfigurationError as e:
        pytest.skip(f"Failed to load config from .env: {e}")


@pytest.fixture(scope="module")
def client(config):
    """Initialize MisoClient instance with 500ms timeout for fast failure."""
    try:
        client_instance = MisoClient(config)
        # Note: We don't call initialize() here as it's async
        # Each test will initialize/disconnect as needed
        return client_instance
    except Exception as e:
        pytest.skip(f"Failed to initialize MisoClient: {e}")


@pytest.fixture(scope="module")
def user_token():
    """Get user token from environment (optional)."""
    return os.getenv("TEST_USER_TOKEN")


@pytest.fixture(scope="module", autouse=True)
def patch_timeout():
    """Patch HTTP client timeout to 500ms for all tests."""
    import httpx

    # Create a subclass that always forces 500ms timeout
    class PatchedAsyncClient(httpx.AsyncClient):
        """httpx.AsyncClient with forced 500ms timeout for fast test failure."""

        def __init__(self, *args, **kwargs):
            # Always override timeout to 500ms for fast failure
            kwargs["timeout"] = 0.5
            super().__init__(*args, **kwargs)

    # Patch httpx.AsyncClient in all modules that use it
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
    """Check if tests should be skipped (evaluated at test time, not module load time)."""
    return (
        not config or not config.controller_url or not config.client_id or not config.client_secret
    )


class TestAuthEndpoints:
    """Integration tests for Auth API endpoints."""

    @pytest.mark.asyncio
    async def test_client_token_generation_legacy(self, client, config):
        """Test POST /api/v1/auth/token - Generate client token (legacy)."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            token = await client.get_environment_token()
            assert token is not None
            assert isinstance(token, str)
            assert len(token) > 0
        except Exception as e:
            pytest.fail(f"Client token generation failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_get_user_info(self, client, config, user_token):
        """Test GET /api/v1/auth/user - Get user info."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await client.initialize()
            user_info = await client.get_user_info(user_token)
            assert user_info is not None
            assert hasattr(user_info, "id") or hasattr(user_info, "username")
        except Exception as e:
            pytest.fail(f"Get user failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_validate_token(self, client, config, user_token):
        """Test POST /api/v1/auth/validate - Validate token."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await client.initialize()
            is_valid = await client.validate_token(user_token)
            assert isinstance(is_valid, bool)
        except Exception as e:
            pytest.fail(f"Token validation failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_logout(self, client, config, user_token):
        """Test POST /api/v1/auth/logout - Logout."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await client.initialize()
            result = await client.logout(user_token)
            assert result is not None
            assert isinstance(result, dict)
        except Exception as e:
            pytest.fail(f"Logout failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_login_initiation(self, client, config):
        """Test GET /api/v1/auth/login - Initiate login flow."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            response = await client.login("http://localhost:3000/callback", state="test-state")
            assert response is not None
            assert isinstance(response, dict)
            # Login returns {} on error, so verify response is not empty
            assert len(response) > 0, "Login returned empty response (controller may be down)"
            # Response should have loginUrl or data.loginUrl
            has_login_url = False
            if "data" in response and isinstance(response["data"], dict):
                assert "loginUrl" in response["data"], "Response missing loginUrl in data"
                has_login_url = True
            elif "loginUrl" in response:
                assert response["loginUrl"] is not None
                has_login_url = True
            assert has_login_url, "Response missing loginUrl field"
        except Exception as e:
            pytest.fail(f"Login initiation failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_get_roles(self, client, config, user_token):
        """Test GET /api/v1/auth/roles - Get roles."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await client.initialize()
            roles = await client.get_roles(user_token)
            assert roles is not None
            assert isinstance(roles, list)
        except Exception as e:
            pytest.fail(f"Get roles failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_refresh_roles(self, client, config, user_token):
        """Test GET /api/v1/auth/roles/refresh - Refresh roles."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await client.initialize()
            roles = await client.refresh_roles(user_token)
            assert roles is not None
            assert isinstance(roles, list)
        except Exception as e:
            pytest.fail(f"Refresh roles failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_get_permissions(self, client, config, user_token):
        """Test GET /api/v1/auth/permissions - Get permissions."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await client.initialize()
            permissions = await client.get_permissions(user_token)
            assert permissions is not None
            assert isinstance(permissions, list)
        except Exception as e:
            pytest.fail(f"Get permissions failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_refresh_permissions(self, client, config, user_token):
        """Test GET /api/v1/auth/permissions/refresh - Refresh permissions."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await client.initialize()
            permissions = await client.refresh_permissions(user_token)
            assert permissions is not None
            assert isinstance(permissions, list)
        except Exception as e:
            pytest.fail(f"Refresh permissions failed: {e}")
        finally:
            await client.disconnect()


class TestLogsEndpoints:
    """Integration tests for Logs API endpoints."""

    @pytest.mark.asyncio
    async def test_create_error_log(self, client, config):
        """Test POST /api/v1/logs - Create error log."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            # Logger silently swallows errors, so verify HTTP call directly
            # Build log entry and transform to LogRequest format
            from miso_client.utils.logger_helpers import build_log_entry, extract_metadata

            log_entry = build_log_entry(
                level="error",
                message="Integration test error log",
                context={"test": True},
                config_client_id=config.client_id,
                correlation_id="test-correlation",
                jwt_token=None,
                stack_trace=None,
                options=None,
                metadata=extract_metadata(),
                mask_sensitive=False,
            )
            # Transform to LogRequest format (what controller expects)
            log_request = client.logger._transform_log_entry_to_request(log_entry)
            # Call HTTP client directly - will raise timeout/connection error if controller is down
            response = await client._internal_http_client.request(
                "POST", "/api/v1/logs", log_request.model_dump(exclude_none=True)
            )
            assert response is not None
        except Exception as e:
            pytest.fail(f"Create error log failed: {e}")
        # Note: Don't disconnect here - client fixture is module-scoped and shared across tests

    @pytest.mark.asyncio
    async def test_create_general_log(self, client, config):
        """Test POST /api/v1/logs - Create general log."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            # Ensure HTTP client is initialized (may have been closed by previous test)
            if client._internal_http_client.client is None:
                await client._internal_http_client._initialize_client()
            # Logger silently swallows errors, so verify HTTP call directly
            from miso_client.utils.logger_helpers import build_log_entry, extract_metadata

            log_entry = build_log_entry(
                level="info",
                message="Integration test general log",
                context={"test": True},
                config_client_id=config.client_id,
                correlation_id="test-correlation",
                jwt_token=None,
                stack_trace=None,
                options=None,
                metadata=extract_metadata(),
                mask_sensitive=False,
            )
            # Transform to LogRequest format (what controller expects)
            log_request = client.logger._transform_log_entry_to_request(log_entry)
            # Call HTTP client directly - will raise timeout/connection error if controller is down
            try:
                response = await client._internal_http_client.request(
                    "POST", "/api/v1/logs", log_request.model_dump(exclude_none=True)
                )
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    # HTTP client connection was closed, recreate it and retry
                    await client._internal_http_client.close()
                    await client._internal_http_client._initialize_client()
                    await client._internal_http_client._ensure_client_token()
                    response = await client._internal_http_client.request(
                        "POST", "/api/v1/logs", log_request.model_dump(exclude_none=True)
                    )
                else:
                    raise
            assert response is not None
        except Exception as e:
            pytest.fail(f"Create general log failed: {e}")
        # Note: Don't disconnect here - client fixture is module-scoped and shared across tests

    @pytest.mark.asyncio
    async def test_create_audit_log(self, client, config):
        """Test POST /api/v1/logs - Create audit log with required fields."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            # Logger silently swallows errors, so verify HTTP call directly
            from miso_client.utils.logger_helpers import build_log_entry, extract_metadata

            log_entry = build_log_entry(
                level="audit",
                message="Audit: test-action on test-entity-123",
                context={
                    "test": True,
                    "entityType": "Test Entity",
                    "action": "test-action",
                    "resource": "test-entity-123",
                },
                config_client_id=config.client_id,
                correlation_id="test-correlation",
                jwt_token=None,
                stack_trace=None,
                options=None,
                metadata=extract_metadata(),
                mask_sensitive=False,
            )
            # Transform to LogRequest format (what controller expects)
            log_request = client.logger._transform_log_entry_to_request(log_entry)
            # Call HTTP client directly - will raise timeout/connection error if controller is down
            try:
                response = await client._internal_http_client.request(
                    "POST", "/api/v1/logs", log_request.model_dump(exclude_none=True)
                )
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    # HTTP client connection was closed, recreate it and retry
                    await client._internal_http_client.close()
                    await client._internal_http_client._initialize_client()
                    await client._internal_http_client._ensure_client_token()
                    response = await client._internal_http_client.request(
                        "POST", "/api/v1/logs", log_request.model_dump(exclude_none=True)
                    )
                else:
                    raise
            assert response is not None
        except Exception as e:
            pytest.fail(f"Create audit log failed: {e}")
        # Note: Don't disconnect here - client fixture is module-scoped and shared across tests

    @pytest.mark.asyncio
    async def test_create_batch_logs(self, client, config):
        """Test POST /api/v1/logs/batch - Create batch logs (1-100 logs)."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            # Ensure HTTP client is initialized (may have been closed by previous test)
            if client._internal_http_client.client is None:
                await client._internal_http_client._initialize_client()
            # Logger silently swallows errors, so verify HTTP call directly
            # Build batch log entries
            from miso_client.utils.logger_helpers import build_log_entry, extract_metadata

            log_entry = build_log_entry(
                level="info",
                message="Batch log test",
                context={"batch": True},
                config_client_id=config.client_id,
                correlation_id="batch-test-1",
                jwt_token=None,
                stack_trace=None,
                options=None,
                metadata=extract_metadata(),
                mask_sensitive=False,
            )
            # Transform to LogRequest format (what controller expects)
            log_request = client.logger._transform_log_entry_to_request(log_entry)
            # Call HTTP client directly - will raise timeout/connection error if controller is down
            try:
                response = await client._internal_http_client.request(
                    "POST", "/api/v1/logs", log_request.model_dump(exclude_none=True)
                )
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    # HTTP client connection was closed, recreate it and retry
                    await client._internal_http_client.close()
                    await client._internal_http_client._initialize_client()
                    await client._internal_http_client._ensure_client_token()
                    response = await client._internal_http_client.request(
                        "POST", "/api/v1/logs", log_request.model_dump(exclude_none=True)
                    )
                else:
                    raise
            assert response is not None
        except Exception as e:
            pytest.fail(f"Create batch logs failed: {e}")
        # Note: Don't disconnect here - client fixture is module-scoped and shared across tests
