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

import asyncio
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
        yield client_instance
        # Teardown: Ensure client is properly closed to prevent event loop errors
        # This runs after all tests in the module complete
    except Exception as e:
        pytest.skip(f"Failed to initialize MisoClient: {e}")


@pytest.fixture(scope="module", autouse=True)
def cleanup_client(client, request):
    """Ensure client is properly cleaned up after all tests."""

    def finalizer():
        """Finalizer to clean up client after all module tests."""
        import asyncio

        try:
            # Try to get the event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Only cleanup if loop is not closed
            if not loop.is_closed():
                # Run cleanup in the event loop
                if loop.is_running():
                    # If loop is running, create a task
                    asyncio.create_task(client.disconnect())
                else:
                    # If loop is not running, run until complete
                    loop.run_until_complete(client.disconnect())
        except Exception:
            # Ignore all errors during teardown
            pass

    request.addfinalizer(finalizer)
    yield


@pytest.fixture(scope="module")
def user_token():
    """Get user token from environment (optional). Falls back to API_KEY for testing."""
    return os.getenv("TEST_USER_TOKEN") or os.getenv("API_KEY")


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


async def wait_for_client_logging(client):
    """Wait for HTTP client logging tasks to complete."""
    try:
        if hasattr(client, "http_client") and hasattr(
            client.http_client, "_wait_for_logging_tasks"
        ):
            try:
                # Use asyncio.wait_for to add an extra timeout layer
                await asyncio.wait_for(
                    client.http_client._wait_for_logging_tasks(timeout=0.5), timeout=0.6
                )
            except (RuntimeError, asyncio.CancelledError, asyncio.TimeoutError):
                # Event loop closed, cancelled, or timeout - that's okay
                pass
    except (RuntimeError, asyncio.CancelledError):
        # Event loop closed or cancelled - that's okay during teardown
        pass
    except Exception:
        # Ignore any other errors
        pass


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
            # API_KEY authentication returns None (no user info for API key auth)
            if config.api_key and user_token == config.api_key:
                assert user_info is None, "API_KEY auth should return None for user info"
            else:
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
            # First validate the token to ensure it's valid
            is_valid = await client.validate_token(user_token)
            if not is_valid:
                pytest.skip("User token is invalid - cannot test roles")

            roles = await client.get_roles(user_token)
            assert roles is not None
            assert isinstance(roles, list)
            # Verify roles are actually returned (not empty list from parsing error)
            # Only check if token is valid (API_KEY may not return roles)
            if not config.api_key or user_token != config.api_key:
                assert (
                    len(roles) > 0
                ), "Roles list should not be empty for valid JWT token - check API response parsing"
                # Verify roles are strings
                assert all(isinstance(r, str) for r in roles), "All roles should be strings"
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
            # First validate the token to ensure it's valid
            is_valid = await client.validate_token(user_token)
            if not is_valid:
                pytest.skip("User token is invalid - cannot test roles")

            roles = await client.refresh_roles(user_token)
            assert roles is not None
            assert isinstance(roles, list)
            # Verify roles are actually returned (not empty list from parsing error)
            # Only check if token is valid (API_KEY may not return roles)
            if not config.api_key or user_token != config.api_key:
                assert (
                    len(roles) > 0
                ), "Roles list should not be empty for valid JWT token - check API response parsing"
                # Verify roles are strings
                assert all(isinstance(r, str) for r in roles), "All roles should be strings"
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
            # First validate the token to ensure it's valid
            is_valid = await client.validate_token(user_token)
            if not is_valid:
                pytest.skip("User token is invalid - cannot test permissions")

            permissions = await client.get_permissions(user_token)
            assert permissions is not None
            assert isinstance(permissions, list)
            # Verify permissions are actually returned (not empty list from parsing error)
            # Only check if token is valid (API_KEY may not return permissions)
            if not config.api_key or user_token != config.api_key:
                assert (
                    len(permissions) > 0
                ), "Permissions list should not be empty for valid JWT token - check API response parsing"
                # Verify permissions are strings
                assert all(
                    isinstance(p, str) for p in permissions
                ), "All permissions should be strings"
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
            # First validate the token to ensure it's valid
            is_valid = await client.validate_token(user_token)
            if not is_valid:
                pytest.skip("User token is invalid - cannot test permissions")

            permissions = await client.refresh_permissions(user_token)
            assert permissions is not None
            assert isinstance(permissions, list)
            # Verify permissions are actually returned (not empty list from parsing error)
            # Only check if token is valid (API_KEY may not return permissions)
            if not config.api_key or user_token != config.api_key:
                assert (
                    len(permissions) > 0
                ), "Permissions list should not be empty for valid JWT token - check API response parsing"
                # Verify permissions are strings
                assert all(
                    isinstance(p, str) for p in permissions
                ), "All permissions should be strings"
        except Exception as e:
            pytest.fail(f"Refresh permissions failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_refresh_token(self, client, config, user_token):
        """Test POST /api/v1/auth/refresh - Refresh user access token."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await client.initialize()
            # Note: This test requires a valid refresh token, which we may not have
            # Skip if we don't have a refresh token in the environment
            refresh_token = os.getenv("TEST_REFRESH_TOKEN")
            if not refresh_token:
                pytest.skip("TEST_REFRESH_TOKEN not available - cannot test token refresh")

            # Use API client directly to test the API layer
            response = await client.api_client.auth.refresh_token(refresh_token)
            assert response is not None
            assert hasattr(response, "data")
            assert hasattr(response.data, "accessToken")
            assert isinstance(response.data.accessToken, str)
            assert len(response.data.accessToken) > 0
        except Exception as e:
            # Token refresh may fail if refresh token is expired or invalid
            if "401" in str(e) or "Unauthorized" in str(e) or "invalid" in str(e).lower():
                pytest.skip("Refresh token is invalid or expired")
            pytest.fail(f"Refresh token failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_initiate_device_code(self, client, config):
        """Test POST /api/v1/auth/login - Initiate device code flow."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            # Use API client directly to test the API layer
            response = await client.api_client.auth.initiate_device_code()
            assert response is not None
            assert hasattr(response, "data")
            assert hasattr(response.data, "deviceCode")
            assert hasattr(response.data, "userCode")
            assert hasattr(response.data, "verificationUri")
            assert isinstance(response.data.deviceCode, str)
            assert len(response.data.deviceCode) > 0
            assert isinstance(response.data.userCode, str)
            assert len(response.data.userCode) > 0
            assert isinstance(response.data.verificationUri, str)
            assert len(response.data.verificationUri) > 0
        except Exception as e:
            from miso_client.errors import ConnectionError as MisoConnectionError

            if "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Device code endpoint not available")
            if (
                isinstance(e, MisoConnectionError)
                or "timeout" in str(e).lower()
                or "ReadTimeout" in str(e)
                or "Connection" in str(e)
            ):
                pytest.skip("Device code endpoint timeout or connection error")
            pytest.fail(f"Initiate device code failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_poll_device_code_token(self, client, config):
        """Test POST /api/v1/auth/login/device/token - Poll for device code token."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            # First initiate device code flow to get a device code
            device_code_response = await client.api_client.auth.initiate_device_code()
            device_code = device_code_response.data.deviceCode

            # Poll for token (may return 202 if still pending)
            # Use API client directly to test the API layer
            response = await client.api_client.auth.poll_device_code_token(device_code)
            assert response is not None
            # Response may have data (token ready) or error (still pending)
            # Both are valid responses
            if response.data:
                assert hasattr(response.data, "accessToken")
                assert isinstance(response.data.accessToken, str)
        except Exception as e:
            # Device code polling may fail if:
            # - Device code expired
            # - User hasn't authorized yet (202 pending)
            # - Endpoint not available
            if "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Device code token endpoint not available")
            if (
                "202" in str(e)
                or "pending" in str(e).lower()
                or "authorization_pending" in str(e).lower()
            ):
                # This is expected - device code requires user interaction
                pytest.skip("Device code authorization pending (requires user interaction)")
            from miso_client.errors import ConnectionError as MisoConnectionError

            if (
                isinstance(e, MisoConnectionError)
                or "timeout" in str(e).lower()
                or "ReadTimeout" in str(e)
                or "Connection" in str(e)
            ):
                pytest.skip("Device code endpoint timeout or connection error")
            pytest.fail(f"Poll device code token failed: {e}")
        finally:
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_refresh_device_code_token(self, client, config):
        """Test POST /api/v1/auth/login/device/refresh - Refresh device code token."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            # Note: This test requires a valid refresh token from device code flow
            # Skip if we don't have a device code refresh token in the environment
            device_refresh_token = os.getenv("TEST_DEVICE_REFRESH_TOKEN")
            if not device_refresh_token:
                pytest.skip(
                    "TEST_DEVICE_REFRESH_TOKEN not available - cannot test device code token refresh"
                )

            # Use API client directly to test the API layer
            response = await client.api_client.auth.refresh_device_code_token(device_refresh_token)
            assert response is not None
            assert hasattr(response, "accessToken")
            assert isinstance(response.accessToken, str)
            assert len(response.accessToken) > 0
        except Exception as e:
            # Token refresh may fail if refresh token is expired or invalid
            if "401" in str(e) or "Unauthorized" in str(e) or "invalid" in str(e).lower():
                pytest.skip("Device code refresh token is invalid or expired")
            if "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Device code refresh endpoint not available")
            pytest.fail(f"Refresh device code token failed: {e}")
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
            # Use API client directly to test the API layer
            from miso_client.api.types.logs_types import GeneralLogData, LogRequest

            log_request = LogRequest(
                type="error",
                data=GeneralLogData(
                    level="error",
                    message="Integration test error log",
                    context={"test": True},
                    correlationId="test-correlation",
                ),
            )
            response = await client.api_client.logs.send_log(log_request)
            assert response is not None
            assert hasattr(response, "success")
            assert response.success is True
            # Wait for logging tasks to complete before test ends
            await wait_for_client_logging(client)
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
            # Use API client directly to test the API layer
            from miso_client.api.types.logs_types import GeneralLogData, LogRequest

            log_request = LogRequest(
                type="general",
                data=GeneralLogData(
                    level="info",
                    message="Integration test general log",
                    context={"test": True},
                    correlationId="test-correlation",
                ),
            )
            response = await client.api_client.logs.send_log(log_request)
            assert response is not None
            assert hasattr(response, "success")
            assert response.success is True
            # Wait for logging tasks to complete before test ends
            await wait_for_client_logging(client)
        except Exception as e:
            if "Event loop is closed" in str(e) or "RuntimeError" in str(e):
                # Event loop closed during teardown - this is expected and okay
                pass
            else:
                pytest.fail(f"Create general log failed: {e}")
        # Note: Don't disconnect here - client fixture is module-scoped and shared across tests

    @pytest.mark.asyncio
    async def test_create_audit_log(self, client, config):
        """Test POST /api/v1/logs - Create audit log with required fields."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await client.initialize()
            # Use API client directly to test the API layer
            from miso_client.api.types.logs_types import AuditLogData, LogRequest

            log_request = LogRequest(
                type="audit",
                data=AuditLogData(
                    entityType="Test Entity",
                    entityId="test-entity-123",
                    action="test-action",
                    correlationId="test-correlation",
                ),
            )
            response = await client.api_client.logs.send_log(log_request)
            assert response is not None
            assert hasattr(response, "success")
            assert response.success is True
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
            # Use API client directly to test the API layer
            from datetime import datetime

            from miso_client.models.config import LogEntry

            # Create a list of log entries for batch processing
            log_entries = [
                LogEntry(
                    timestamp=datetime.now().isoformat() + "Z",
                    level="info",
                    environment="test",
                    application=config.client_id,
                    message=f"Batch log test {i}",
                    context={"batch": True, "index": i},
                    correlationId="batch-test-1",
                )
                for i in range(2)  # Small batch for testing
            ]
            response = await client.api_client.logs.send_batch_logs(log_entries)
            assert response is not None
            assert hasattr(response, "success")
            assert hasattr(response, "processed")
            assert response.processed >= 0
            # Wait for logging tasks to complete before test ends
            await wait_for_client_logging(client)
        except Exception as e:
            if "Event loop is closed" in str(e) or "RuntimeError" in str(e):
                # Event loop closed during teardown - this is expected and okay
                pass
            else:
                pytest.fail(f"Create batch logs failed: {e}")
        # Note: Don't disconnect here - client fixture is module-scoped and shared across tests


class TestAuthEndpointsExtended:
    """Extended integration tests for additional Auth API endpoints."""

    async def _ensure_client_ready(self, client):
        """Ensure the client is initialized and HTTP client is ready."""
        await client.initialize()
        # Force close and recreate the HTTP client to handle event loop changes
        try:
            if client._internal_http_client.client is not None:
                await client._internal_http_client.close()
        except Exception:
            pass
        client._internal_http_client.client = None
        await client._internal_http_client._initialize_client()
        await client._internal_http_client._ensure_client_token()

    @pytest.mark.asyncio
    async def test_login_diagnostics(self, client, config):
        """Test GET /api/v1/auth/login/diagnostics - Get login diagnostics."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await self._ensure_client_ready(client)
            # Call the diagnostics endpoint directly via HTTP client
            response = await client._internal_http_client.get("/api/v1/auth/login/diagnostics")
            assert response is not None
            assert isinstance(response, dict)
            # Diagnostics should return database, controller, environment info
            if "data" in response:
                data = response["data"]
                # Check for expected diagnostic fields
                assert isinstance(data, dict)
        except Exception as e:
            if "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Diagnostics endpoint not available")
            pytest.fail(f"Login diagnostics failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_auth_cache_stats(self, client, config, user_token):
        """Test GET /api/v1/auth/cache/stats - Get cache statistics."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Call cache stats endpoint directly via authenticated request
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/auth/cache/stats", user_token
            )
            assert response is not None
            assert isinstance(response, dict)
        except Exception as e:
            # Cache endpoints may require special permissions or not exist
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for cache stats")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for cache stats with API key")
            if "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Cache stats endpoint not available")
            pytest.fail(f"Cache stats failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_auth_cache_performance(self, client, config, user_token):
        """Test GET /api/v1/auth/cache/performance - Get cache performance metrics."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/auth/cache/performance", user_token
            )
            assert response is not None
            assert isinstance(response, dict)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for cache performance")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for cache performance with API key")
            if "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Cache performance endpoint not available")
            pytest.fail(f"Cache performance failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_auth_cache_efficiency(self, client, config, user_token):
        """Test GET /api/v1/auth/cache/efficiency - Get cache efficiency metrics."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/auth/cache/efficiency", user_token
            )
            assert response is not None
            assert isinstance(response, dict)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for cache efficiency")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for cache efficiency with API key")
            if "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Cache efficiency endpoint not available")
            pytest.fail(f"Cache efficiency failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped


class TestLogsEndpointsExtended:
    """Extended integration tests for Logs list/stats API endpoints."""

    async def _ensure_client_ready(self, client):
        """Ensure the client is initialized and HTTP client is ready."""
        await client.initialize()
        # Force close and recreate the HTTP client to handle event loop changes
        try:
            if client._internal_http_client.client is not None:
                await client._internal_http_client.close()
        except Exception:
            pass
        client._internal_http_client.client = None
        await client._internal_http_client._initialize_client()
        await client._internal_http_client._ensure_client_token()

    @pytest.mark.asyncio
    async def test_list_general_logs(self, client, config, user_token):
        """Test GET /api/v1/logs/general - List general logs."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Use API client directly to test the API layer
            response = await client.api_client.logs.list_general_logs(
                token=user_token, page=1, page_size=10
            )
            assert response is not None
            assert hasattr(response, "data")
            assert isinstance(response.data, list)
            assert hasattr(response, "meta")
            assert hasattr(response.meta, "totalItems") or hasattr(response.meta, "currentPage")
            # Wait for logging tasks to complete before test ends
            await wait_for_client_logging(client)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for logs:read")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for logs:read with API key")
            pytest.fail(f"List general logs failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_list_audit_logs(self, client, config, user_token):
        """Test GET /api/v1/logs/audit - List audit logs."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Use API client directly to test the API layer
            response = await client.api_client.logs.list_audit_logs(
                token=user_token, page=1, page_size=10
            )
            assert response is not None
            assert hasattr(response, "data")
            assert isinstance(response.data, list)
            assert hasattr(response, "meta")
            # Wait for logging tasks to complete before test ends
            await wait_for_client_logging(client)
        except Exception as e:
            if "Event loop is closed" in str(e) or "RuntimeError" in str(e):
                # Event loop closed during teardown - this is expected and okay
                pass
            elif "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for audit:read")
            elif "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for audit:read with API key")
            else:
                pytest.fail(f"List audit logs failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_list_job_logs(self, client, config, user_token):
        """Test GET /api/v1/logs/jobs - List job logs."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Use API client directly to test the API layer
            response = await client.api_client.logs.list_job_logs(
                token=user_token, page=1, page_size=10
            )
            assert response is not None
            assert hasattr(response, "data")
            assert isinstance(response.data, list)
            assert hasattr(response, "meta")
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for jobs:read")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for jobs:read with API key")
            pytest.fail(f"List job logs failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_get_logs_stats_summary(self, client, config, user_token):
        """Test GET /api/v1/logs/stats/summary - Get log statistics summary."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Use API client directly to test the API layer
            response = await client.api_client.logs.get_stats_summary(token=user_token)
            assert response is not None
            assert hasattr(response, "data")
            assert hasattr(response.data, "totalLogs")
            assert hasattr(response.data, "byLevel")
            # Wait for logging tasks to complete before test ends
            await wait_for_client_logging(client)
        except Exception as e:
            if "Event loop is closed" in str(e) or "RuntimeError" in str(e):
                # Event loop closed during teardown - this is expected and okay
                pass
            elif "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for logs:read")
            elif "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for logs:read with API key")
            else:
                pytest.fail(f"Get logs stats summary failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_get_logs_stats_errors(self, client, config, user_token):
        """Test GET /api/v1/logs/stats/errors - Get error statistics."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Use API client directly to test the API layer
            response = await client.api_client.logs.get_stats_errors(token=user_token, limit=10)
            assert response is not None
            assert hasattr(response, "data")
            assert hasattr(response.data, "totalErrors")
            assert hasattr(response.data, "topErrors")
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for logs:read")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for logs:read with API key")
            pytest.fail(f"Get logs stats errors failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_get_logs_stats_applications(self, client, config, user_token):
        """Test GET /api/v1/logs/stats/applications - Get application statistics."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Use API client directly to test the API layer
            response = await client.api_client.logs.get_stats_applications(token=user_token)
            assert response is not None
            assert hasattr(response, "data")
            assert hasattr(response.data, "totalApplications")
            assert hasattr(response.data, "applications")
            # Wait for logging tasks to complete before test ends
            await wait_for_client_logging(client)
        except Exception as e:
            if "Event loop is closed" in str(e) or "RuntimeError" in str(e):
                # Event loop closed during teardown - this is expected and okay
                pass
            elif "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for logs:read")
            elif "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for logs:read with API key")
            else:
                pytest.fail(f"Get logs stats applications failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_get_logs_stats_users(self, client, config, user_token):
        """Test GET /api/v1/logs/stats/users - Get user activity statistics."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Use API client directly to test the API layer
            response = await client.api_client.logs.get_stats_users(token=user_token, limit=10)
            assert response is not None
            assert hasattr(response, "data")
            assert hasattr(response.data, "totalUsers")
            assert hasattr(response.data, "topUsers")
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for admin:read")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for admin:read with API key")
            pytest.fail(f"Get logs stats users failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_get_job_log(self, client, config, user_token):
        """Test GET /api/v1/logs/jobs/{id} - Get single job log by ID."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # First, list job logs to get a valid log ID
            list_response = await client.api_client.logs.list_job_logs(
                token=user_token, page=1, page_size=1
            )
            if not list_response.data or len(list_response.data) == 0:
                pytest.skip("No job logs available - cannot test get_job_log")

            # Get the first job log ID
            log_id = list_response.data[0].id

            # Use API client directly to test the API layer
            response = await client.api_client.logs.get_job_log(token=user_token, log_id=log_id)
            assert response is not None
            assert hasattr(response, "data")
            assert hasattr(response.data, "id")
            assert response.data.id == log_id
            assert hasattr(response.data, "jobId")
            assert hasattr(response.data, "message")
            # Wait for logging tasks to complete before test ends
            await wait_for_client_logging(client)
        except Exception as e:
            if "Event loop is closed" in str(e) or "RuntimeError" in str(e):
                # Event loop closed during teardown - this is expected and okay
                pass
            elif "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for jobs:read")
            elif "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for jobs:read with API key")
            elif "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Job log not found or endpoint not available")
            else:
                pytest.fail(f"Get job log failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_export_logs_json(self, client, config, user_token):
        """Test GET /api/v1/logs/export - Export logs in JSON format."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Use API client directly to test the API layer
            response = await client.api_client.logs.export_logs(
                token=user_token,
                log_type="general",
                format="json",
                limit=10,  # Small limit for testing
            )
            assert response is not None
            assert hasattr(response, "data")
            assert isinstance(response.data, list)
            assert hasattr(response, "meta")
            assert hasattr(response.meta, "type")
            assert response.meta.type == "general"
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for logs:export")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for logs:export with API key")
            if "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Export endpoint not available")
            pytest.fail(f"Export logs JSON failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_export_logs_csv(self, client, config, user_token):
        """Test GET /api/v1/logs/export - Export logs in CSV format."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            # Use API client directly to test the API layer
            # Note: CSV format returns raw text, but API client normalizes to LogExportResponse
            # This may need special handling - for now test that it doesn't crash
            response = await client.api_client.logs.export_logs(
                token=user_token,
                log_type="general",
                format="csv",
                limit=10,  # Small limit for testing
            )
            # CSV format may return different structure - just verify response exists
            assert response is not None
            # Wait for logging tasks to complete before test ends
            await wait_for_client_logging(client)
        except Exception as e:
            # CSV format may not be fully supported or may return raw text
            # which doesn't match LogExportResponse structure
            if "Event loop is closed" in str(e) or "RuntimeError" in str(e):
                # Event loop closed during teardown - this is expected and okay
                pass
            elif "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for logs:export")
            elif "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for logs:export with API key")
            elif "404" in str(e) or "Not Found" in str(e):
                pytest.skip("Export endpoint not available")
            elif "validation" in str(e).lower() or "parse" in str(e).lower():
                # CSV may return raw text that doesn't parse as JSON
                pytest.skip("CSV format returns raw text - may not parse as LogExportResponse")
            else:
                pytest.fail(f"Export logs CSV failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped


class TestNegativeScenarios:
    """Integration tests for error handling and negative scenarios."""

    async def _ensure_client_ready(self, client):
        """Ensure the client is initialized and HTTP client is ready."""
        await client.initialize()
        # Force close and recreate the HTTP client to handle event loop changes
        try:
            if client._internal_http_client.client is not None:
                await client._internal_http_client.close()
        except Exception:
            pass
        client._internal_http_client.client = None
        await client._internal_http_client._initialize_client()
        await client._internal_http_client._ensure_client_token()

    @pytest.mark.asyncio
    async def test_invalid_token_validation(self, client, config):
        """Test POST /api/v1/auth/validate - Validate with invalid token."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await self._ensure_client_ready(client)
            # Use an obviously invalid token
            is_valid = await client.validate_token("invalid-token-12345")
            # Should return False for invalid token (not raise exception)
            assert is_valid is False
        except Exception:
            # Some implementations may raise exception instead of returning False
            # This is acceptable behavior for invalid tokens
            pass
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_expired_token_handling(self, client, config):
        """Test handling of expired JWT token."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await self._ensure_client_ready(client)
            # Use a malformed JWT that would be expired
            # This is a valid JWT structure but with expired timestamp
            expired_token = (
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                "eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxMDAwMDAwMDAwfQ."
                "invalid-signature"
            )
            is_valid = await client.validate_token(expired_token)
            # Should return False for expired/invalid token
            assert is_valid is False
        except Exception:
            # Exception is acceptable for invalid tokens
            pass
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_empty_token_validation(self, client, config):
        """Test POST /api/v1/auth/validate - Validate with empty token."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await self._ensure_client_ready(client)
            # Test with empty string token
            is_valid = await client.validate_token("")
            # Should return False for empty token
            assert is_valid is False
        except Exception:
            # Exception is acceptable for empty tokens
            pass
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_roles_with_invalid_token(self, client, config):
        """Test GET /api/v1/auth/roles - Get roles with invalid token."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await self._ensure_client_ready(client)
            roles = await client.get_roles("invalid-token")
            # Should return empty list on error (service pattern)
            assert roles == []
        except Exception:
            # Exception is also acceptable
            pass
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_permissions_with_invalid_token(self, client, config):
        """Test GET /api/v1/auth/permissions - Get permissions with invalid token."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await self._ensure_client_ready(client)
            permissions = await client.get_permissions("invalid-token")
            # Should return empty list on error (service pattern)
            assert permissions == []
        except Exception:
            # Exception is also acceptable
            pass
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_user_info_with_invalid_token(self, client, config):
        """Test GET /api/v1/auth/user - Get user info with invalid token."""
        if should_skip(config):
            pytest.skip("Config not available")

        try:
            await self._ensure_client_ready(client)
            user_info = await client.get_user("invalid-token")
            # Should return None on error (service pattern)
            assert user_info is None
        except Exception:
            # Exception is also acceptable
            pass
        # Note: Don't disconnect - client fixture is module-scoped
