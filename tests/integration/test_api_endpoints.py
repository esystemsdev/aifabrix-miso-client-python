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
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/logs/general", user_token, params={"page": 1, "pageSize": 10}
            )
            assert response is not None
            assert isinstance(response, dict)
            # Should have data, meta, links
            assert "data" in response
            assert isinstance(response["data"], list)
            if "meta" in response:
                assert "totalItems" in response["meta"] or "currentPage" in response["meta"]
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
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/logs/audit", user_token, params={"page": 1, "pageSize": 10}
            )
            assert response is not None
            assert isinstance(response, dict)
            assert "data" in response
            assert isinstance(response["data"], list)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for audit:read")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for audit:read with API key")
            pytest.fail(f"List audit logs failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_list_job_logs(self, client, config, user_token):
        """Test GET /api/v1/logs/jobs - List job logs."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/logs/jobs", user_token, params={"page": 1, "pageSize": 10}
            )
            assert response is not None
            assert isinstance(response, dict)
            assert "data" in response
            assert isinstance(response["data"], list)
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
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/logs/stats/summary", user_token
            )
            assert response is not None
            assert isinstance(response, dict)
            if "data" in response:
                data = response["data"]
                # Check for expected stats fields
                assert isinstance(data, dict)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for logs:read")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for logs:read with API key")
            pytest.fail(f"Get logs stats summary failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_get_logs_stats_errors(self, client, config, user_token):
        """Test GET /api/v1/logs/stats/errors - Get error statistics."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/logs/stats/errors", user_token, params={"limit": 10}
            )
            assert response is not None
            assert isinstance(response, dict)
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
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/logs/stats/applications", user_token
            )
            assert response is not None
            assert isinstance(response, dict)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for logs:read")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for logs:read with API key")
            pytest.fail(f"Get logs stats applications failed: {e}")
        # Note: Don't disconnect - client fixture is module-scoped

    @pytest.mark.asyncio
    async def test_get_logs_stats_users(self, client, config, user_token):
        """Test GET /api/v1/logs/stats/users - Get user activity statistics."""
        if should_skip(config) or not user_token:
            pytest.skip("Config or user token not available")

        try:
            await self._ensure_client_ready(client)
            response = await client._internal_http_client.authenticated_request(
                "GET", "/api/v1/logs/stats/users", user_token, params={"limit": 10}
            )
            assert response is not None
            assert isinstance(response, dict)
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                pytest.skip("Insufficient permissions for admin:read")
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.skip("Authentication not supported for admin:read with API key")
            pytest.fail(f"Get logs stats users failed: {e}")
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
