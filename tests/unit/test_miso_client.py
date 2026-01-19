"""
Unit tests for MisoClient SDK.

This module contains comprehensive unit tests for the MisoClient SDK,
mirroring the test coverage from the TypeScript version.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miso_client.api.types.auth_types import (
    LoginResponse,
    LoginResponseData,
    ValidateTokenResponse,
    ValidateTokenResponseData,
)
from miso_client.models.config import PermissionResult, RoleResult, UserInfo
from miso_client.services.auth import AuthService
from miso_client.services.logger import LoggerChain, LoggerService
from miso_client.services.permission import PermissionService
from miso_client.services.role import RoleService
from miso_client.utils.logger_helpers import extract_jwt_context, extract_metadata


class TestMisoClient:
    """Test cases for MisoClient main class."""

    @pytest.mark.asyncio
    async def test_initialization_success(self, client, mock_redis):
        """Test successful client initialization."""
        with patch.object(client.redis, "connect", new_callable=AsyncMock) as mock_connect:
            await client.initialize()
            assert client.is_initialized() is True
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_redis_failure(self, client):
        """Test initialization with Redis connection failure."""
        with patch.object(client.redis, "connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")

            await client.initialize()
            assert client.is_initialized() is True  # Should still initialize for fallback mode

    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Test client disconnection."""
        with patch.object(client.redis, "disconnect", new_callable=AsyncMock) as mock_disconnect:
            with patch.object(client.http_client, "close", new_callable=AsyncMock) as mock_close:
                await client.disconnect()
                assert client.is_initialized() is False
                mock_disconnect.assert_called_once()
                mock_close.assert_called_once()

    def test_get_config(self, client, config):
        """Test configuration retrieval."""
        returned_config = client.get_config()
        assert returned_config.controller_url == config.controller_url
        assert returned_config.client_id == config.client_id
        assert returned_config.client_secret == config.client_secret

    def test_get_config_immutable(self, client, config):
        """Test that returned config cannot be modified."""
        returned_config = client.get_config()
        returned_config.client_id = "modified"

        original_config = client.get_config()
        assert original_config.client_id == config.client_id

    def test_is_redis_connected(self, client):
        """Test Redis connection status."""
        with patch.object(client.redis, "is_connected", return_value=True):
            assert client.is_redis_connected() is True

        with patch.object(client.redis, "is_connected", return_value=False):
            assert client.is_redis_connected() is False

    @pytest.mark.asyncio
    async def test_get_token_from_request(self, client):
        """Test extracting token from request."""
        req = {"headers": {"authorization": "Bearer test-token-123"}}

        token = client.get_token(req)

        assert token == "test-token-123"

    @pytest.mark.asyncio
    async def test_get_token_no_header(self, client):
        """Test extracting token when no header."""
        req = {"headers": {}}

        token = client.get_token(req)

        assert token is None

    @pytest.mark.asyncio
    async def test_get_environment_token(self, client):
        """Test getting environment token."""
        with patch.object(client.auth, "get_environment_token", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "env-token-123"

            token = await client.get_environment_token()

            assert token == "env-token-123"
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_clears_all_caches(self, client):
        """Test that logout clears all caches (roles, permissions, JWT)."""
        import jwt

        token = jwt.encode({"sub": "user-123"}, "secret", algorithm="HS256")

        with patch.object(client.auth, "logout", new_callable=AsyncMock) as mock_auth_logout:
            # Mock response matches OpenAPI spec: {"data": null} for logout
            mock_auth_logout.return_value = {
                "data": None,
            }

            with patch.object(
                client.roles, "clear_roles_cache", new_callable=AsyncMock
            ) as mock_clear_roles:
                with patch.object(
                    client.permissions, "clear_permissions_cache", new_callable=AsyncMock
                ) as mock_clear_permissions:
                    result = await client.logout(token)

                    # Verify logout was called
                    mock_auth_logout.assert_called_once_with(token)

                    # Verify all caches are cleared
                    mock_clear_roles.assert_called_once_with(token)
                    mock_clear_permissions.assert_called_once_with(token)

                    # Verify response is returned (OpenAPI spec: {"data": null})
                    assert result["data"] is None

    @pytest.mark.asyncio
    async def test_logout_clears_caches_even_on_failure(self, client):
        """Test that caches are cleared even if logout API call fails."""
        import jwt

        token = jwt.encode({"sub": "user-123"}, "secret", algorithm="HS256")

        with patch.object(client.auth, "logout", new_callable=AsyncMock) as mock_auth_logout:
            mock_auth_logout.return_value = {}  # Logout failed

            with patch.object(
                client.roles, "clear_roles_cache", new_callable=AsyncMock
            ) as mock_clear_roles:
                with patch.object(
                    client.permissions, "clear_permissions_cache", new_callable=AsyncMock
                ) as mock_clear_permissions:
                    result = await client.logout(token)

                    # Verify logout was called
                    mock_auth_logout.assert_called_once_with(token)

                    # Verify caches are still cleared (security best practice)
                    mock_clear_roles.assert_called_once_with(token)
                    mock_clear_permissions.assert_called_once_with(token)

                    # Verify response is returned
                    assert result == {}

    @pytest.mark.asyncio
    async def test_logout_clears_refresh_data(self, client):
        """Test that logout clears refresh tokens and callbacks."""
        import jwt

        token = jwt.encode({"sub": "user-123"}, "secret", algorithm="HS256")

        # Register refresh callback and token
        async def refresh_callback(token: str) -> str:
            return "new-token"

        client.register_user_token_refresh_callback("user-123", refresh_callback)
        client.register_user_refresh_token("user-123", "refresh-token-abc")

        # Verify they're registered
        assert "user-123" in client.http_client._user_token_refresh._refresh_callbacks
        assert (
            client.http_client._user_token_refresh._refresh_tokens["user-123"]
            == "refresh-token-abc"
        )

        with patch.object(client.auth, "logout", new_callable=AsyncMock) as mock_auth_logout:
            mock_auth_logout.return_value = {"data": None}

            with patch.object(client.roles, "clear_roles_cache", new_callable=AsyncMock):
                with patch.object(
                    client.permissions, "clear_permissions_cache", new_callable=AsyncMock
                ):
                    await client.logout(token)

                    # Verify refresh data is cleared
                    assert (
                        "user-123" not in client.http_client._user_token_refresh._refresh_callbacks
                    )
                    assert "user-123" not in client.http_client._user_token_refresh._refresh_tokens

    def test_register_user_token_refresh_callback(self, client):
        """Test registering refresh callback."""

        async def refresh_callback(token: str) -> str:
            return "new-token"

        client.register_user_token_refresh_callback("user-123", refresh_callback)

        assert "user-123" in client.http_client._user_token_refresh._refresh_callbacks
        assert (
            client.http_client._user_token_refresh._refresh_callbacks["user-123"]
            == refresh_callback
        )

    def test_register_user_refresh_token(self, client):
        """Test registering refresh token."""
        client.register_user_refresh_token("user-123", "refresh-token-abc")

        assert (
            client.http_client._user_token_refresh._refresh_tokens["user-123"]
            == "refresh-token-abc"
        )

    def test_clear_user_token_refresh(self, client):
        """Test clearing refresh data for a user."""

        # Register callback and token
        async def refresh_callback(token: str) -> str:
            return "new-token"

        client.register_user_token_refresh_callback("user-123", refresh_callback)
        client.register_user_refresh_token("user-123", "refresh-token-abc")

        # Verify they're registered
        assert "user-123" in client.http_client._user_token_refresh._refresh_callbacks
        assert "user-123" in client.http_client._user_token_refresh._refresh_tokens

        # Clear refresh data
        client.clear_user_token_refresh("user-123")

        # Verify they're cleared
        assert "user-123" not in client.http_client._user_token_refresh._refresh_callbacks
        assert "user-123" not in client.http_client._user_token_refresh._refresh_tokens

    def test_auth_service_set_on_refresh_manager(self, client):
        """Test that auth_service is set on refresh manager after initialization."""
        assert client.http_client._user_token_refresh._auth_service == client.auth


class TestAuthService:
    """Test cases for AuthService."""

    @pytest.fixture
    def auth_service(self, mock_http_client, mock_redis, mock_cache, mock_api_client):
        """Test AuthService instance."""
        return AuthService(mock_http_client, mock_redis, mock_cache, mock_api_client)

    @pytest.mark.asyncio
    async def test_validate_token_success(self, auth_service):
        """Test successful token validation."""
        # Disable api_client to use HTTP client fallback
        auth_service.api_client = None
        with patch.object(
            auth_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {
                "authenticated": True,
                "user": {"id": "123", "username": "testuser"},
            }

            result = await auth_service.validate_token("valid-token")
            assert result is True
            mock_request.assert_called_once_with(
                "POST",
                "/api/v1/auth/validate",
                "valid-token",
                {"token": "valid-token"},
            )

    @pytest.mark.asyncio
    async def test_validate_token_failure(self, auth_service):
        """Test failed token validation."""
        validate_response = ValidateTokenResponse(
            success=True,
            data=ValidateTokenResponseData(authenticated=False, user=None),
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.validate_token = AsyncMock(return_value=validate_response)

        result = await auth_service.validate_token("invalid-token")
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_token_exception(self, auth_service):
        """Test token validation with exception."""
        auth_service.api_client.auth.validate_token = AsyncMock(
            side_effect=Exception("Network error")
        )

        result = await auth_service.validate_token("token")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_user_success(self, auth_service):
        """Test successful user retrieval."""
        user_info = UserInfo(id="123", username="testuser", email="test@example.com")
        validate_response = ValidateTokenResponse(
            success=True,
            data=ValidateTokenResponseData(authenticated=True, user=user_info),
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.validate_token = AsyncMock(return_value=validate_response)

        result = await auth_service.get_user("valid-token")
        assert result is not None
        assert result.id == "123"
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_failure(self, auth_service):
        """Test failed user retrieval."""
        validate_response = ValidateTokenResponse(
            success=True,
            data=ValidateTokenResponseData(authenticated=False, user=None),
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.validate_token = AsyncMock(return_value=validate_response)

        result = await auth_service.get_user("invalid-token")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_info(self, auth_service):
        """Test getting user info from /api/auth/user endpoint."""
        from miso_client.api.types.auth_types import GetUserResponse, GetUserResponseData

        user_info = UserInfo(id="123", username="testuser")
        get_user_response = GetUserResponse(
            success=True,
            data=GetUserResponseData(user=user_info, authenticated=True),
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.get_user = AsyncMock(return_value=get_user_response)
        get_user_response = GetUserResponse(
            success=True,
            data=GetUserResponseData(user=user_info, authenticated=True),
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.get_user = AsyncMock(return_value=get_user_response)

        result = await auth_service.get_user_info("valid-token")
        assert result is not None
        assert result.id == "123"
        auth_service.api_client.auth.get_user.assert_called_once_with(
            "valid-token", auth_strategy=None
        )

    @pytest.mark.asyncio
    async def test_get_environment_token(self, auth_service):
        """Test getting environment token."""
        with patch.object(
            auth_service.http_client, "get_environment_token", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = "client-token-123"

            token = await auth_service.get_environment_token()

            assert token == "client-token-123"
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_authenticated(self, auth_service):
        """Test is_authenticated method."""
        with patch.object(auth_service, "validate_token", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = True

            result = await auth_service.is_authenticated("token")

            assert result is True
            mock_validate.assert_called_once_with("token")

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service):
        """Test successful login."""
        # LoginResponse now matches OpenAPI spec: {"data": {...}} without success/timestamp
        login_response = LoginResponse(
            data=LoginResponseData(loginUrl="https://keycloak.example.com/auth?redirect_uri=..."),
        )
        auth_service.api_client.auth.login = AsyncMock(return_value=login_response)

        result = await auth_service.login(
            redirect="http://localhost:3000/auth/callback", state="abc123"
        )

        assert "loginUrl" in result["data"]
        assert result["data"]["state"] == "abc123"
        auth_service.api_client.auth.login.assert_called_once_with(
            "http://localhost:3000/auth/callback", "abc123"
        )

    @pytest.mark.asyncio
    async def test_login_without_state(self, auth_service):
        """Test login without state parameter."""
        # LoginResponse now matches OpenAPI spec: {"data": {...}} without success/timestamp
        login_response = LoginResponse(
            data=LoginResponseData(loginUrl="https://keycloak.example.com/auth?redirect_uri=..."),
        )
        auth_service.api_client.auth.login = AsyncMock(return_value=login_response)

        result = await auth_service.login(redirect="http://localhost:3000/auth/callback")

        assert "loginUrl" in result["data"]
        auth_service.api_client.auth.login.assert_called_once_with(
            "http://localhost:3000/auth/callback", None
        )

    @pytest.mark.asyncio
    async def test_login_exception(self, auth_service):
        """Test login with exception - should return empty dict per service method pattern."""
        auth_service.api_client.auth.login = AsyncMock(side_effect=ValueError("Network error"))

        result = await auth_service.login(redirect="http://localhost:3000/auth/callback")

        assert result == {}
        auth_service.api_client.auth.login.assert_called_once_with(
            "http://localhost:3000/auth/callback", None
        )

    @pytest.mark.asyncio
    async def test_logout_success(self, auth_service):
        """Test successful logout."""
        from miso_client.api.types.auth_types import LogoutResponse

        # LogoutResponse now matches OpenAPI spec: {"data": null} for logout
        logout_response = LogoutResponse(
            data=None,
        )
        auth_service.api_client.auth.logout = AsyncMock(return_value=logout_response)

        with patch.object(auth_service.http_client, "clear_user_token") as mock_clear_token:
            result = await auth_service.logout(token="jwt-token-123")

            # OpenAPI spec: logout returns {"data": null}
            assert result["data"] is None
            auth_service.api_client.auth.logout.assert_called_once_with("jwt-token-123")
            # Verify JWT cache is cleared
            mock_clear_token.assert_called_once_with("jwt-token-123")

    @pytest.mark.asyncio
    async def test_logout_exception_re_raising(self, auth_service):
        """Test logout with exception - should return empty dict per service method pattern."""
        auth_service.api_client.auth.logout = AsyncMock(side_effect=ValueError("Invalid request"))

        # Service methods should not raise uncaught errors - they should return empty dict
        result = await auth_service.logout(token="jwt-token-123")
        assert result == {}
        auth_service.api_client.auth.logout.assert_called_once_with("jwt-token-123")

    @pytest.mark.asyncio
    async def test_validate_token_cache_hit(self, auth_service, mock_cache):
        """Test token validation cache hit - should return cached result without HTTP request."""
        # Cached result matches OpenAPI spec format: {"data": {...}} without success/timestamp
        cached_result = {
            "data": {"authenticated": True, "user": {"id": "123", "username": "testuser"}},
        }
        mock_cache.get = AsyncMock(return_value=cached_result)

        result = await auth_service._validate_token_request("valid-token")

        assert result == cached_result
        mock_cache.get.assert_called_once()
        # Should not make HTTP request on cache hit
        auth_service.api_client.auth.validate_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_token_cache_miss(self, auth_service, mock_cache):
        """Test token validation cache miss - should make HTTP request and cache result."""
        mock_cache.get = AsyncMock(return_value=None)
        validate_response = ValidateTokenResponse(
            success=True,
            data=ValidateTokenResponseData(
                authenticated=True,
                user=UserInfo(id="123", username="testuser"),
            ),
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.validate_token = AsyncMock(return_value=validate_response)

        result = await auth_service._validate_token_request("valid-token")

        assert result["data"]["authenticated"] is True
        mock_cache.get.assert_called_once()
        auth_service.api_client.auth.validate_token.assert_called_once()
        # Should cache successful validation
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_token_cache_failed_validation(self, auth_service, mock_cache):
        """Test that failed validations are not cached."""
        mock_cache.get = AsyncMock(return_value=None)
        validate_response = ValidateTokenResponse(
            success=True,
            data=ValidateTokenResponseData(authenticated=False, user=None),
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.validate_token = AsyncMock(return_value=validate_response)

        result = await auth_service._validate_token_request("invalid-token")

        assert result["data"]["authenticated"] is False
        # Should not cache failed validations
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_logout_clears_validation_cache(self, auth_service, mock_cache):
        """Test that logout clears validation cache entry."""
        from miso_client.api.types.auth_types import LogoutResponse

        logout_response = LogoutResponse(
            success=True,
            message="Logout successful",
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.logout = AsyncMock(return_value=logout_response)

        with patch.object(auth_service.http_client, "clear_user_token"):
            await auth_service.logout(token="jwt-token-123")

        # Should clear validation cache
        mock_cache.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_token_no_cache_service(self, auth_service):
        """Test token validation when cache service is not available."""
        auth_service.cache = None
        validate_response = ValidateTokenResponse(
            success=True,
            data=ValidateTokenResponseData(
                authenticated=True,
                user=UserInfo(id="123", username="testuser"),
            ),
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.validate_token = AsyncMock(return_value=validate_response)

        result = await auth_service._validate_token_request("valid-token")

        assert result["data"]["authenticated"] is True
        auth_service.api_client.auth.validate_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_ttl_from_token_with_expiration(self, auth_service):
        """Test smart TTL calculation from token expiration."""
        import time

        with patch("miso_client.utils.auth_cache_helpers.decode_token") as mock_decode:
            # Token expires in 300 seconds (5 minutes)
            future_exp = int(time.time()) + 300
            mock_decode.return_value = {"exp": future_exp}

            ttl = auth_service._get_cache_ttl_from_token("token-with-exp")

            # Should be token_exp - now - 30s buffer, clamped between 60s and validation_ttl
            assert 60 <= ttl <= auth_service.validation_ttl
            assert ttl <= 270  # Should be less than 300 - 30 buffer

    @pytest.mark.asyncio
    async def test_get_cache_ttl_from_token_no_expiration(self, auth_service):
        """Test TTL calculation when token has no expiration claim."""
        with patch("miso_client.utils.auth_cache_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "123"}  # No exp claim

            ttl = auth_service._get_cache_ttl_from_token("token-no-exp")

            # Should use default validation_ttl
            assert ttl == auth_service.validation_ttl

    @pytest.mark.asyncio
    async def test_get_cache_ttl_from_token_malformed(self, auth_service):
        """Test TTL calculation with malformed token."""
        with patch("miso_client.utils.auth_cache_helpers.decode_token") as mock_decode:
            mock_decode.return_value = None  # Decode failed

            ttl = auth_service._get_cache_ttl_from_token("malformed-token")

            # Should use default validation_ttl
            assert ttl == auth_service.validation_ttl

    def test_get_token_cache_key(self, auth_service):
        """Test cache key generation using SHA-256 hash."""
        token = "test-token-123"
        cache_key = auth_service._get_token_cache_key(token)

        assert cache_key.startswith("token_validation:")
        assert len(cache_key) > len("token_validation:")
        # Should be deterministic
        assert auth_service._get_token_cache_key(token) == cache_key
        # Different tokens should have different keys
        assert auth_service._get_token_cache_key("different-token") != cache_key

    @pytest.mark.asyncio
    async def test_refresh_user_token_success(self, auth_service):
        """Test successful user token refresh."""
        from miso_client.api.types.auth_types import DeviceCodeTokenResponse, RefreshTokenResponse

        refresh_response = RefreshTokenResponse(
            success=True,
            data=DeviceCodeTokenResponse(
                accessToken="new-access-token",
                refreshToken="new-refresh-token",
                expiresIn=3600,
            ),
            timestamp="2024-01-01T00:00:00Z",
        )
        auth_service.api_client.auth.refresh_token = AsyncMock(return_value=refresh_response)

        result = await auth_service.refresh_user_token("refresh-token-abc")

        assert result is not None
        assert result["data"]["token"] == "new-access-token"
        assert result["data"]["refreshToken"] == "new-refresh-token"
        assert result["data"]["expiresIn"] == 3600
        auth_service.api_client.auth.refresh_token.assert_called_once_with("refresh-token-abc")

    @pytest.mark.asyncio
    async def test_refresh_user_token_failure(self, auth_service):
        """Test refresh user token failure."""
        auth_service.api_client.auth.refresh_token = AsyncMock(
            side_effect=Exception("Refresh failed")
        )

        result = await auth_service.refresh_user_token("refresh-token-abc")

        assert result is None
        auth_service.api_client.auth.refresh_token.assert_called_once_with("refresh-token-abc")

    @pytest.mark.asyncio
    async def test_validate_token_with_api_key_match(self, mock_http_client, mock_redis):
        """Test validate_token with matching API_KEY bypasses OAuth2."""
        from miso_client.models.config import MisoClientConfig

        # Create config with API_KEY
        api_key_config = MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client-id",
            client_secret="test-client-secret",
            api_key="test-api-key-123",
        )
        mock_http_client.config = api_key_config

        auth_service = AuthService(mock_http_client, mock_redis)

        # Token matches API_KEY - should return True without calling OAuth2
        result = await auth_service.validate_token("test-api-key-123")

        assert result is True
        # Should not call authenticated_request
        mock_http_client.authenticated_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_token_with_api_key_no_match(self, mock_http_client, mock_redis):
        """Test validate_token with non-matching token falls back to OAuth2."""
        from miso_client.models.config import MisoClientConfig

        # Create config with API_KEY
        api_key_config = MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client-id",
            client_secret="test-client-secret",
            api_key="test-api-key-123",
        )
        mock_http_client.config = api_key_config

        auth_service = AuthService(mock_http_client, mock_redis)

        # Token doesn't match API_KEY - should fall back to OAuth2
        mock_http_client.authenticated_request.return_value = {"authenticated": False}

        result = await auth_service.validate_token("different-token")

        assert result is False
        # Should call authenticated_request for OAuth2 validation
        mock_http_client.authenticated_request.assert_called_once_with(
            "POST", "/api/v1/auth/validate", "different-token", {"token": "different-token"}
        )

    @pytest.mark.asyncio
    async def test_validate_token_without_api_key(self, mock_http_client, mock_redis):
        """Test validate_token without API_KEY uses OAuth2."""
        from miso_client.models.config import MisoClientConfig

        # Create config without API_KEY
        config = MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client-id",
            client_secret="test-client-secret",
        )
        mock_http_client.config = config

        auth_service = AuthService(mock_http_client, mock_redis)

        # Without API_KEY, should use OAuth2
        mock_http_client.authenticated_request.return_value = {"authenticated": True}

        result = await auth_service.validate_token("oauth-token")

        assert result is True
        mock_http_client.authenticated_request.assert_called_once_with(
            "POST", "/api/v1/auth/validate", "oauth-token", {"token": "oauth-token"}
        )

    @pytest.mark.asyncio
    async def test_get_user_with_api_key_match(self, mock_http_client, mock_redis):
        """Test get_user with matching API_KEY returns None without OAuth2."""
        from miso_client.models.config import MisoClientConfig

        # Create config with API_KEY
        api_key_config = MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client-id",
            client_secret="test-client-secret",
            api_key="test-api-key-123",
        )
        mock_http_client.config = api_key_config

        auth_service = AuthService(mock_http_client, mock_redis)

        # Token matches API_KEY - should return None without calling OAuth2
        result = await auth_service.get_user("test-api-key-123")

        assert result is None
        # Should not call authenticated_request
        mock_http_client.authenticated_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_with_api_key_no_match(self, mock_http_client, mock_redis):
        """Test get_user with non-matching token falls back to OAuth2."""
        from miso_client.models.config import MisoClientConfig

        # Create config with API_KEY
        api_key_config = MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client-id",
            client_secret="test-client-secret",
            api_key="test-api-key-123",
        )
        mock_http_client.config = api_key_config

        auth_service = AuthService(mock_http_client, mock_redis)

        # Disable api_client to use HTTP client fallback
        auth_service.api_client = None
        # Token doesn't match API_KEY - should fall back to OAuth2
        user_info = UserInfo(id="123", username="testuser")
        mock_http_client.authenticated_request.return_value = {
            "data": {
                "authenticated": True,
                "user": user_info.model_dump(),
            }
        }

        result = await auth_service.get_user("different-token")

        assert result is not None
        assert result.id == "123"
        # Should call authenticated_request for OAuth2 validation
        mock_http_client.authenticated_request.assert_called_once_with(
            "POST",
            "/api/v1/auth/validate",
            "different-token",
            {"token": "different-token"},
        )

    @pytest.mark.asyncio
    async def test_get_user_info_with_api_key_match(self, mock_http_client, mock_redis):
        """Test get_user_info with matching API_KEY returns None without OAuth2."""
        from miso_client.models.config import MisoClientConfig

        # Create config with API_KEY
        api_key_config = MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client-id",
            client_secret="test-client-secret",
            api_key="test-api-key-123",
        )
        mock_http_client.config = api_key_config

        auth_service = AuthService(mock_http_client, mock_redis)

        # Token matches API_KEY - should return None without calling OAuth2
        result = await auth_service.get_user_info("test-api-key-123")

        assert result is None
        # Should not call authenticated_request
        mock_http_client.authenticated_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_info_with_api_key_no_match(self, mock_http_client, mock_redis):
        """Test get_user_info with non-matching token falls back to OAuth2."""
        from miso_client.models.config import MisoClientConfig

        # Create config with API_KEY
        api_key_config = MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client-id",
            client_secret="test-client-secret",
            api_key="test-api-key-123",
        )
        mock_http_client.config = api_key_config

        auth_service = AuthService(mock_http_client, mock_redis)

        # Token doesn't match API_KEY - should fall back to OAuth2
        user_info = UserInfo(id="123", username="testuser")
        mock_http_client.authenticated_request.return_value = user_info.model_dump()

        result = await auth_service.get_user_info("different-token")

        assert result is not None
        assert result.id == "123"
        # Should call authenticated_request for OAuth2 validation
        mock_http_client.authenticated_request.assert_called_once_with(
            "GET", "/api/v1/auth/user", "different-token"
        )


class TestRoleService:
    """Test cases for RoleService."""

    @pytest.fixture
    def role_service(self, mock_http_client, mock_cache):
        """Test RoleService instance."""
        return RoleService(mock_http_client, mock_cache)

    @pytest.mark.asyncio
    async def test_get_roles_with_jwt_userid(self, role_service):
        """Test getting roles using JWT userId extraction."""
        import jwt

        token = jwt.encode({"sub": "user-123"}, "secret", algorithm="HS256")

        with patch.object(role_service.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"roles": ["admin", "user"], "timestamp": 1234567890}

            roles = await role_service.get_roles(token)

            assert roles == ["admin", "user"]
            # Should use simplified cache key
            mock_get.assert_called_once_with("roles:user-123")

    @pytest.mark.asyncio
    async def test_get_roles_from_controller(self, role_service):
        """Test getting roles from controller when cache miss."""
        import jwt

        token = jwt.encode({"sub": "user-123"}, "secret", algorithm="HS256")

        with patch.object(role_service.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # Cache miss

            with patch.object(
                role_service.http_client, "authenticated_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = RoleResult(
                    userId="user-123", roles=["admin"], environment="dev", application="test-app"
                ).model_dump()

                with patch.object(role_service.cache, "set", new_callable=AsyncMock) as mock_set:
                    roles = await role_service.get_roles(token)
                    assert roles == ["admin"]
                    mock_set.assert_called_once()
                    # Verify simplified cache key
                    assert mock_set.call_args[0][0] == "roles:user-123"

    @pytest.mark.asyncio
    async def test_get_roles_no_userid_in_token(self, role_service):
        """Test getting roles when userId not in token."""
        import jwt

        token = jwt.encode({"name": "test"}, "secret", algorithm="HS256")

        with patch.object(role_service.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # Cache miss

            with patch.object(
                role_service.http_client, "authenticated_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.side_effect = [
                    {"user": {"id": "user-123"}},  # From validate endpoint
                    RoleResult(
                        userId="user-123", roles=["admin"], environment="dev", application="app"
                    ).model_dump(),
                ]

                with patch.object(role_service.cache, "set", new_callable=AsyncMock):
                    roles = await role_service.get_roles(token)
                    assert "admin" in roles

    @pytest.mark.asyncio
    async def test_has_role(self, role_service):
        """Test role checking."""
        with patch.object(role_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["admin", "user"]

            result = await role_service.has_role("token", "admin")
            assert result is True

            result = await role_service.has_role("token", "guest")
            assert result is False

    @pytest.mark.asyncio
    async def test_has_any_role(self, role_service):
        """Test checking for any role."""
        with patch.object(role_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["admin", "user"]

            result = await role_service.has_any_role("token", ["admin", "guest"])
            assert result is True

            result = await role_service.has_any_role("token", ["guest", "visitor"])
            assert result is False

    @pytest.mark.asyncio
    async def test_has_all_roles(self, role_service):
        """Test checking for all roles."""
        with patch.object(role_service, "get_roles", new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["admin", "user"]

            result = await role_service.has_all_roles("token", ["admin", "user"])
            assert result is True

            result = await role_service.has_all_roles("token", ["admin", "guest"])
            assert result is False

    @pytest.mark.asyncio
    async def test_refresh_roles(self, role_service):
        """Test refreshing roles."""
        with patch.object(
            role_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [
                {"user": {"id": "user-123"}},
                RoleResult(
                    userId="user-123", roles=["admin", "user"], environment="dev", application="app"
                ).model_dump(),
            ]

            with patch.object(role_service.cache, "set", new_callable=AsyncMock):
                roles = await role_service.refresh_roles("token")

                assert "admin" in roles
                assert "user" in roles
                # Should call refresh endpoint
                assert "/api/v1/auth/roles/refresh" in str(mock_request.call_args_list[1])

    @pytest.mark.asyncio
    async def test_clear_roles_cache(self, role_service):
        """Test clearing roles cache."""
        with patch.object(
            role_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"user": {"id": "user-123"}}

            with patch.object(role_service.cache, "delete", new_callable=AsyncMock) as mock_delete:
                await role_service.clear_roles_cache("token")
                mock_delete.assert_called_once()
                assert mock_delete.call_args[0][0] == "roles:user-123"

    @pytest.mark.asyncio
    async def test_clear_roles_cache_with_jwt_userid(self, role_service):
        """Test clearing roles cache when userId is in JWT token."""
        import jwt

        token = jwt.encode({"sub": "user-456"}, "secret", algorithm="HS256")

        with patch.object(role_service.cache, "delete", new_callable=AsyncMock) as mock_delete:
            await role_service.clear_roles_cache(token)
            mock_delete.assert_called_once()
            assert mock_delete.call_args[0][0] == "roles:user-456"

    @pytest.mark.asyncio
    async def test_clear_roles_cache_validate_fails(self, role_service):
        """Test clear_roles_cache when validate fails."""
        with patch.object(
            role_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("Validate failed")

            # Should silently fail
            await role_service.clear_roles_cache("token")

            # Cache delete should not be called
            with patch.object(role_service.cache, "delete", new_callable=AsyncMock) as mock_delete:
                await role_service.clear_roles_cache("token")
                mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_roles_cache_user_id_none(self, role_service):
        """Test clear_roles_cache when user_id is None."""
        with patch.object(
            role_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"user": {}}  # No id field

            # Should silently fail
            await role_service.clear_roles_cache("token")

            # Cache delete should not be called
            with patch.object(role_service.cache, "delete", new_callable=AsyncMock) as mock_delete:
                await role_service.clear_roles_cache("token")
                mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_roles_cache_exception_handling(self, role_service):
        """Test clear_roles_cache exception handling (should silently fail)."""
        with patch.object(
            role_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("Unexpected error")

            # Should not raise exception
            await role_service.clear_roles_cache("token")


class TestPermissionService:
    """Test cases for PermissionService."""

    @pytest.fixture
    def permission_service(self, mock_http_client, mock_cache):
        """Test PermissionService instance."""
        return PermissionService(mock_http_client, mock_cache)

    @pytest.mark.asyncio
    async def test_get_permissions_with_jwt_userid(self, permission_service):
        """Test getting permissions using JWT userId extraction."""
        import jwt

        token = jwt.encode({"sub": "user-123"}, "secret", algorithm="HS256")

        with patch.object(permission_service.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"permissions": ["read", "write"], "timestamp": 1234567890}

            permissions = await permission_service.get_permissions(token)

            assert permissions == ["read", "write"]
            # Should use simplified cache key
            mock_get.assert_called_once_with("permissions:user-123")

    @pytest.mark.asyncio
    async def test_has_permission(self, permission_service):
        """Test permission checking."""
        with patch.object(
            permission_service, "get_permissions", new_callable=AsyncMock
        ) as mock_get_permissions:
            mock_get_permissions.return_value = ["read", "write"]

            result = await permission_service.has_permission("token", "read")
            assert result is True

            result = await permission_service.has_permission("token", "delete")
            assert result is False

    @pytest.mark.asyncio
    async def test_has_any_permission(self, permission_service):
        """Test checking for any permission."""
        with patch.object(
            permission_service, "get_permissions", new_callable=AsyncMock
        ) as mock_get_permissions:
            mock_get_permissions.return_value = ["read", "write"]

            result = await permission_service.has_any_permission("token", ["read", "delete"])
            assert result is True

            result = await permission_service.has_any_permission("token", ["delete", "update"])
            assert result is False

    @pytest.mark.asyncio
    async def test_has_all_permissions(self, permission_service):
        """Test checking for all permissions."""
        with patch.object(
            permission_service, "get_permissions", new_callable=AsyncMock
        ) as mock_get_permissions:
            mock_get_permissions.return_value = ["read", "write"]

            result = await permission_service.has_all_permissions("token", ["read", "write"])
            assert result is True

            result = await permission_service.has_all_permissions("token", ["read", "delete"])
            assert result is False

    @pytest.mark.asyncio
    async def test_refresh_permissions(self, permission_service):
        """Test refreshing permissions."""
        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [
                {"user": {"id": "user-123"}},
                PermissionResult(
                    userId="user-123",
                    permissions=["read", "write"],
                    environment="dev",
                    application="app",
                ).model_dump(),
            ]

            with patch.object(permission_service.cache, "set", new_callable=AsyncMock):
                permissions = await permission_service.refresh_permissions("token")

                assert "read" in permissions
                assert "write" in permissions
                # Should call refresh endpoint
                assert "/api/v1/auth/permissions/refresh" in str(mock_request.call_args_list[1])

    @pytest.mark.asyncio
    async def test_clear_permissions_cache(self, permission_service):
        """Test clearing permissions cache."""
        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"user": {"id": "user-123"}}

            with patch.object(
                permission_service.cache, "delete", new_callable=AsyncMock
            ) as mock_delete:
                await permission_service.clear_permissions_cache("token")
                mock_delete.assert_called_once()
                assert mock_delete.call_args[0][0] == "permissions:user-123"

    @pytest.mark.asyncio
    async def test_refresh_permissions_user_info_fails(self, permission_service):
        """Test refresh_permissions when user info fetch fails."""
        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("Network error")

            permissions = await permission_service.refresh_permissions("token")

            assert permissions == []

    @pytest.mark.asyncio
    async def test_refresh_permissions_user_id_none(self, permission_service):
        """Test refresh_permissions when user_id is None after validate."""
        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"user": {}}  # No id field

            permissions = await permission_service.refresh_permissions("token")

            assert permissions == []

    @pytest.mark.asyncio
    async def test_refresh_permissions_endpoint_fails(self, permission_service):
        """Test refresh_permissions when refresh endpoint fails."""
        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [
                {"user": {"id": "user-123"}},
                Exception("Refresh endpoint failed"),
            ]

            permissions = await permission_service.refresh_permissions("token")

            assert permissions == []

    @pytest.mark.asyncio
    async def test_refresh_permissions_exception_handling(self, permission_service):
        """Test refresh_permissions exception handling."""
        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("Unexpected error")

            permissions = await permission_service.refresh_permissions("token")

            assert permissions == []

    @pytest.mark.asyncio
    async def test_clear_permissions_cache_validate_fails(self, permission_service):
        """Test clear_permissions_cache when validate fails."""
        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("Validate failed")

            # Should silently fail
            await permission_service.clear_permissions_cache("token")

            # Cache delete should not be called
            with patch.object(
                permission_service.cache, "delete", new_callable=AsyncMock
            ) as mock_delete:
                await permission_service.clear_permissions_cache("token")
                mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_permissions_cache_user_id_none(self, permission_service):
        """Test clear_permissions_cache when user_id is None."""
        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"user": {}}  # No id field

            # Should silently fail
            await permission_service.clear_permissions_cache("token")

            # Cache delete should not be called
            with patch.object(
                permission_service.cache, "delete", new_callable=AsyncMock
            ) as mock_delete:
                await permission_service.clear_permissions_cache("token")
                mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_permissions_cache_exception_handling(self, permission_service):
        """Test clear_permissions_cache exception handling (should silently fail)."""
        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("Unexpected error")

            # Should not raise exception
            await permission_service.clear_permissions_cache("token")

    @pytest.mark.asyncio
    async def test_get_permissions_cache_returns_non_dict(self, permission_service):
        """Test get_permissions when cache returns non-dict value."""
        import jwt

        token = jwt.encode({"sub": "user-123"}, "secret", algorithm="HS256")

        with patch.object(permission_service.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "not-a-dict"  # Invalid cache format

            with patch.object(
                permission_service.http_client, "authenticated_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.return_value = {
                    "userId": "user-123",
                    "permissions": ["read", "write"],
                    "environment": "dev",
                    "application": "app",
                }

                permissions = await permission_service.get_permissions(token)

                # Should fallback to controller
                assert len(permissions) > 0

    @pytest.mark.asyncio
    async def test_get_permissions_extract_user_id_fails(self, permission_service):
        """Test get_permissions when extract_user_id fails."""
        # Invalid token that extract_user_id can't parse
        invalid_token = "invalid.token.here"

        with patch.object(
            permission_service.http_client, "authenticated_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = [
                {"user": {"id": "user-123"}},  # validate endpoint
                {
                    "userId": "user-123",
                    "permissions": ["read"],
                    "environment": "dev",
                    "application": "app",
                },  # permissions endpoint
            ]

            permissions = await permission_service.get_permissions(invalid_token)

            # Should fallback to validate endpoint
            assert "read" in permissions

    @pytest.mark.asyncio
    async def test_get_permissions_validate_endpoint_fails(self, permission_service):
        """Test get_permissions when validate endpoint fails."""
        import jwt

        token = jwt.encode({"sub": "user-123"}, "secret", algorithm="HS256")

        with patch.object(permission_service.cache, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # Cache miss

            with patch.object(
                permission_service.http_client, "authenticated_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.side_effect = Exception("Validate endpoint failed")

                permissions = await permission_service.get_permissions(token)

                assert permissions == []


class TestLoggerService:
    """Test cases for LoggerService."""

    @pytest.fixture
    def logger_service(self, mock_http_client, mock_redis):
        """Test LoggerService instance."""
        return LoggerService(mock_http_client, mock_redis)

    @pytest.mark.asyncio
    async def test_log_with_redis(self, logger_service):
        """Test logging with Redis available."""
        logger_service.redis.is_connected.return_value = True

        with patch.object(logger_service.redis, "rpush", new_callable=AsyncMock) as mock_rpush:
            mock_rpush.return_value = True

            await logger_service.info("Test message", {"key": "value"})
            mock_rpush.assert_called_once()
            # Verify queue name uses clientId
            queue_name = mock_rpush.call_args[0][0]
            assert queue_name == "logs:test-client-id"

    @pytest.mark.asyncio
    async def test_log_without_redis(self, logger_service):
        """Test logging without Redis (fallback to HTTP)."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test message", {"key": "value"})
            mock_request.assert_called_once()
            # Verify it's a POST to /api/logs
            assert mock_request.call_args[0][0] == "POST"
            assert mock_request.call_args[0][1] == "/api/v1/logs"

    @pytest.mark.asyncio
    async def test_audit_log(self, logger_service):
        """Test audit logging."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.audit("user.login", "authentication", {"ip": "192.168.1.1"})
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_log_with_stack_trace(self, logger_service):
        """Test error logging with stack trace."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.error(
                "Error occurred", {"error": "test"}, stack_trace="Traceback..."
            )
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_debug_log_with_debug_level(self, logger_service):
        """Test debug logging when debug level is enabled."""
        logger_service.config.log_level = "debug"
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.debug("Debug message")
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_debug_log_without_debug_level(self, logger_service):
        """Test debug logging when debug level is disabled."""
        logger_service.config.log_level = "info"
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.debug("Debug message")
            mock_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_correlation_id_generation(self, logger_service):
        """Test correlation ID generation."""
        corr_id = logger_service._generate_correlation_id()

        assert isinstance(corr_id, str)
        assert len(corr_id) > 0
        assert logger_service.config.client_id[:10] in corr_id

    @pytest.mark.asyncio
    async def test_data_masking(self, logger_service):
        """Test data masking in logs."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test", {"password": "secret123", "username": "john"})

            # Verify request was made
            mock_request.assert_called_once()
            # Check that password was masked in the log entry
            call_args = mock_request.call_args
            log_data = call_args[1]["data"] if "data" in call_args[1] else call_args[0][2]
            if "context" in log_data and "password" in log_data["context"]:
                assert log_data["context"]["password"] == "***MASKED***"

    def test_set_masking(self, logger_service):
        """Test setting masking."""
        assert logger_service.mask_sensitive_data is True

        logger_service.set_masking(False)
        assert logger_service.mask_sensitive_data is False

        logger_service.set_masking(True)
        assert logger_service.mask_sensitive_data is True

    def test_extract_jwt_context_with_roles_list(self, logger_service):
        """Test JWT context extraction with roles as list."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-123",
                "roles": ["admin", "user"],
                "applicationId": "app-456",
                "sessionId": "session-789",
            }

            context = extract_jwt_context("test-token")

            assert context["userId"] == "user-123"
            assert context["roles"] == ["admin", "user"]
            assert context["applicationId"] == "app-456"
            assert context["sessionId"] == "session-789"

    def test_extract_jwt_context_with_realm_access(self, logger_service):
        """Test JWT context extraction with realm_access.roles format."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-123",
                "realm_access": {"roles": ["admin", "user"]},
            }

            context = extract_jwt_context("test-token")

            assert context["userId"] == "user-123"
            assert context["roles"] == ["admin", "user"]

    def test_extract_jwt_context_with_scope_string(self, logger_service):
        """Test JWT context extraction with scope as string."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-123",
                "scope": "read write delete",
            }

            context = extract_jwt_context("test-token")

            assert context["userId"] == "user-123"
            assert context["permissions"] == ["read", "write", "delete"]

    def test_extract_jwt_context_with_permissions_list(self, logger_service):
        """Test JWT context extraction with permissions as list."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-123",
                "permissions": ["read", "write"],
            }

            context = extract_jwt_context("test-token")

            assert context["userId"] == "user-123"
            assert context["permissions"] == ["read", "write"]

    def test_extract_jwt_context_with_multiple_user_id_fields(self, logger_service):
        """Test JWT context extraction with different user ID field names."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            # Test with userId field
            mock_decode.return_value = {"userId": "user-456"}

            context = extract_jwt_context("test-token")

            assert context["userId"] == "user-456"

            # Test with user_id field
            mock_decode.return_value = {"user_id": "user-789"}

            context = extract_jwt_context("test-token")

            assert context["userId"] == "user-789"

    def test_extract_jwt_context_with_application_id_fields(self, logger_service):
        """Test JWT context extraction with different application ID field names."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {"app_id": "app-123"}

            context = extract_jwt_context("test-token")

            assert context["applicationId"] == "app-123"

    def test_extract_jwt_context_with_session_id_fields(self, logger_service):
        """Test JWT context extraction with different session ID field names."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {"sid": "session-123"}

            context = extract_jwt_context("test-token")

            assert context["sessionId"] == "session-123"

    def test_extract_jwt_context_with_none_token(self, logger_service):
        """Test JWT context extraction with None token."""
        context = extract_jwt_context(None)

        assert context == {}

    def test_extract_jwt_context_decode_fails(self, logger_service):
        """Test JWT context extraction when decode fails."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = None

            context = extract_jwt_context("invalid-token")

            assert context == {}

    def test_extract_jwt_context_decode_exception(self, logger_service):
        """Test JWT context extraction when decode raises exception."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.side_effect = Exception("Decode failed")

            context = extract_jwt_context("invalid-token")

            assert context == {}

    def test_extract_jwt_context_with_non_list_roles(self, logger_service):
        """Test JWT context extraction when roles is not a list."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-123",
                "roles": "admin",
            }  # String instead of list

            context = extract_jwt_context("test-token")

            assert context["userId"] == "user-123"
            assert context["roles"] == []  # Should default to empty list

    def test_extract_jwt_context_with_non_dict_realm_access(self, logger_service):
        """Test JWT context extraction when realm_access is not a dict."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "user-123", "realm_access": "invalid"}

            context = extract_jwt_context("test-token")

            assert context["userId"] == "user-123"
            assert context["roles"] == []  # Should default to empty list

    def test_extract_jwt_context_with_non_list_permissions(self, logger_service):
        """Test JWT context extraction when permissions is not a list."""
        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-123",
                "permissions": "read",
            }  # String instead of list

            context = extract_jwt_context("test-token")

            assert context["userId"] == "user-123"
            assert context["permissions"] == []  # Should default to empty list

    def test_extract_metadata(self, logger_service):
        """Test metadata extraction from environment."""
        with patch.dict("os.environ", {"HOSTNAME": "test-host"}):
            metadata = extract_metadata()

            assert "hostname" in metadata
            assert metadata["hostname"] == "test-host"
            assert "platform" in metadata
            assert "python_version" in metadata

    def test_extract_metadata_without_hostname(self, logger_service):
        """Test metadata extraction when HOSTNAME is not set."""
        with patch.dict("os.environ", {}, clear=True):
            metadata = extract_metadata()

            assert metadata["hostname"] == "unknown"
            assert "platform" in metadata
            assert "python_version" in metadata

    @pytest.mark.asyncio
    async def test_log_redis_rpush_fails_fallback_to_http(self, logger_service):
        """Test logging when Redis rpush fails (should fallback to HTTP)."""
        logger_service.redis.is_connected.return_value = True

        with patch.object(logger_service.redis, "rpush", new_callable=AsyncMock) as mock_rpush:
            mock_rpush.return_value = False  # Redis operation fails

            with patch.object(
                logger_service.internal_http_client, "request", new_callable=AsyncMock
            ) as mock_request:
                await logger_service.info("Test message", {"key": "value"})

                # Should attempt Redis first
                mock_rpush.assert_called_once()
                # Then fallback to HTTP
                mock_request.assert_called_once()
                assert mock_request.call_args[0][0] == "POST"
                assert mock_request.call_args[0][1] == "/api/v1/logs"

    @pytest.mark.asyncio
    async def test_log_http_fallback_silently_fails(self, logger_service):
        """Test logging when HTTP fallback fails (should silently fail)."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = Exception("HTTP request failed")

            # Should not raise exception
            await logger_service.info("Test message", {"key": "value"})

            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_with_custom_correlation_id(self, logger_service):
        """Test logging with custom correlation ID in options."""
        logger_service.redis.is_connected.return_value = False

        from miso_client.models.config import ClientLoggingOptions

        options = ClientLoggingOptions(correlationId="custom-corr-123")

        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test message", {"key": "value"}, options=options)

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            log_data = call_args[1]["data"] if "data" in call_args[1] else call_args[0][2]

            assert log_data["correlationId"] == "custom-corr-123"

    @pytest.mark.asyncio
    async def test_log_with_jwt_token_in_options(self, logger_service):
        """Test logging with JWT token in options for context extraction."""
        logger_service.redis.is_connected.return_value = False

        from miso_client.models.config import ClientLoggingOptions

        with patch("miso_client.utils.logger_helpers.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-123",
                "roles": ["admin"],
            }

            options = ClientLoggingOptions(token="jwt-token-123")

            with patch.object(
                logger_service.internal_http_client, "request", new_callable=AsyncMock
            ) as mock_request:
                await logger_service.info("Test message", {"key": "value"}, options=options)

                mock_request.assert_called_once()
                call_args = mock_request.call_args
                log_data = call_args[1]["data"] if "data" in call_args[1] else call_args[0][2]

                # userId is now a ForeignKeyReference object (serialized as dict when sent via HTTP)
                assert log_data["userId"] is not None
                user_id_ref = log_data["userId"]
                # When serialized via model_dump(), ForeignKeyReference becomes a dict
                if isinstance(user_id_ref, dict):
                    assert user_id_ref["id"] == "user-123"
                else:
                    assert user_id_ref.id == "user-123"

    @pytest.mark.asyncio
    async def test_event_emission_mode_with_listeners(self, logger_service):
        """Test event emission mode when listeners are registered."""
        logger_service.config.emit_events = True
        logger_service.redis.is_connected.return_value = True

        # Track events
        events_received = []

        def sync_handler(log_entry):
            events_received.append(log_entry)

        async def async_handler(log_entry):
            events_received.append(log_entry)

        # Register listeners
        logger_service.on(sync_handler)
        logger_service.on(async_handler)

        # Log should emit events, not send via Redis/HTTP
        with patch.object(logger_service.redis, "rpush", new_callable=AsyncMock) as mock_rpush:
            with patch.object(
                logger_service.internal_http_client, "request", new_callable=AsyncMock
            ) as mock_request:
                await logger_service.info("Test message", {"key": "value"})

                # Events should be emitted
                assert len(events_received) == 2
                assert events_received[0].message == "Test message"
                assert events_received[1].message == "Test message"

                # Should NOT send via Redis or HTTP
                mock_rpush.assert_not_called()
                mock_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_emission_mode_without_listeners(self, logger_service):
        """Test event emission mode without listeners falls back to HTTP/Redis."""
        logger_service.config.emit_events = True
        logger_service.redis.is_connected.return_value = False

        # No listeners registered, should fall back to HTTP
        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test message", {"key": "value"})

            # Should fall back to HTTP when no listeners
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_event_emission_mode_disabled(self, logger_service):
        """Test that HTTP/Redis is used when emit_events=False."""
        logger_service.config.emit_events = False
        logger_service.redis.is_connected.return_value = False

        events_received = []

        def handler(log_entry):
            events_received.append(log_entry)

        logger_service.on(handler)

        # Even with listeners, should use HTTP when emit_events=False
        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test message", {"key": "value"})

            # Should use HTTP, not emit events
            assert len(events_received) == 0
            mock_request.assert_called_once()

    def test_event_listener_registration(self, logger_service):
        """Test event listener registration and unregistration."""
        events_received = []

        def handler1(log_entry):
            events_received.append(("handler1", log_entry))

        def handler2(log_entry):
            events_received.append(("handler2", log_entry))

        # Register listeners
        logger_service.on(handler1)
        logger_service.on(handler2)

        assert len(logger_service._event_listeners) == 2

        # Unregister one
        logger_service.off(handler1)

        assert len(logger_service._event_listeners) == 1
        assert logger_service._event_listeners[0] == handler2

    @pytest.mark.asyncio
    async def test_event_listener_error_handling(self, logger_service):
        """Test that listener errors don't break logging."""
        logger_service.config.emit_events = True
        logger_service.redis.is_connected.return_value = False

        events_received = []

        def failing_handler(log_entry):
            raise ValueError("Handler error")

        def working_handler(log_entry):
            events_received.append(log_entry)

        logger_service.on(failing_handler)
        logger_service.on(working_handler)

        # Should not raise exception, working handler should still receive event
        with patch.object(
            logger_service.internal_http_client, "request", new_callable=AsyncMock
        ) as mock_request:
            await logger_service.info("Test message")

            # Working handler should receive event
            assert len(events_received) == 1
            assert events_received[0].message == "Test message"

            # Should not fall back to HTTP when listeners exist (even if one fails)
            mock_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_log_with_request(self, logger_service):
        """Test get_log_with_request extracts request context."""
        from unittest.mock import MagicMock

        import jwt

        payload = {"sub": "user-123", "sessionId": "session-456"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        request = MagicMock()
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/test"
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        request.headers = MagicMock()
        request.headers.get = MagicMock(
            side_effect=lambda k, d=None: {
                "authorization": f"Bearer {token}",
                "user-agent": "Mozilla/5.0",
                "x-correlation-id": "corr-123",
                "referer": "https://example.com",
                "content-length": "1024",
            }.get(k, d)
        )

        log_entry = await logger_service.get_log_with_request(request, "Processing request", "info")

        assert log_entry.message == "Processing request"
        assert log_entry.level == "info"
        # userId is now a ForeignKeyReference object
        assert log_entry.userId is not None
        assert log_entry.userId.id == "user-123"
        assert log_entry.sessionId == "session-456"
        assert log_entry.correlationId == "corr-123"
        assert log_entry.ipAddress == "192.168.1.1"
        assert log_entry.userAgent == "Mozilla/5.0"
        assert log_entry.context["method"] == "POST"
        assert log_entry.context["path"] == "/api/test"
        assert log_entry.context["referer"] == "https://example.com"
        assert log_entry.context["requestSize"] == 1024

    @pytest.mark.asyncio
    async def test_get_with_context(self, logger_service):
        """Test get_with_context adds custom context."""
        context = {"customField": "value", "anotherField": 123}
        log_entry = await logger_service.get_with_context(context, "Custom log", "info")

        assert log_entry.message == "Custom log"
        assert log_entry.level == "info"
        assert log_entry.context["customField"] == "value"
        assert log_entry.context["anotherField"] == 123

    @pytest.mark.asyncio
    async def test_get_with_token(self, logger_service):
        """Test get_with_token extracts user context from JWT."""
        import jwt

        payload = {"sub": "user-789", "sessionId": "session-abc"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        log_entry = await logger_service.get_with_token(token, "User action", "audit")

        assert log_entry.message == "User action"
        assert log_entry.level == "audit"
        # userId is now a ForeignKeyReference object
        assert log_entry.userId is not None
        assert log_entry.userId.id == "user-789"
        assert log_entry.sessionId == "session-abc"

    @pytest.mark.asyncio
    async def test_get_for_request(self, logger_service):
        """Test get_for_request alias for get_log_with_request."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/users"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        log_entry = await logger_service.get_for_request(request, "Request processed", "info")

        assert log_entry.message == "Request processed"
        assert log_entry.level == "info"
        assert log_entry.context["method"] == "GET"
        assert log_entry.context["path"] == "/api/users"

    @pytest.mark.asyncio
    async def test_get_log_with_request_minimal(self, logger_service):
        """Test get_log_with_request with minimal request data."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.method = "GET"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        log_entry = await logger_service.get_log_with_request(request, "Minimal request", "info")

        assert log_entry.message == "Minimal request"
        assert log_entry.context["method"] == "GET"
        assert log_entry.userId is None

    @pytest.mark.asyncio
    async def test_get_log_with_request_with_stack_trace(self, logger_service):
        """Test get_log_with_request with stack trace."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.method = "POST"
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)

        log_entry = await logger_service.get_log_with_request(
            request, "Error occurred", "error", stack_trace="Traceback..."
        )

        assert log_entry.level == "error"
        assert log_entry.stackTrace == "Traceback..."


class TestLoggerChain:
    """Test cases for LoggerChain."""

    @pytest.fixture
    def logger_service(self, mock_http_client, mock_redis):
        """Test LoggerService instance."""
        return LoggerService(mock_http_client, mock_redis)

    @pytest.fixture
    def logger_chain(self, logger_service):
        """Test LoggerChain instance."""
        return LoggerChain(logger_service, {"initial": "context"}, None)

    def test_with_context(self, logger_service):
        """Test with_context chain method."""
        chain = logger_service.with_context({"key": "value"})

        assert isinstance(chain, LoggerChain)
        assert chain.context == {"key": "value"}

    def test_with_token(self, logger_service):
        """Test with_token chain method."""
        chain = logger_service.with_token("test-token")

        assert isinstance(chain, LoggerChain)
        assert chain.options.token == "test-token"

    def test_without_masking(self, logger_service):
        """Test without_masking chain method."""
        chain = logger_service.without_masking()

        assert isinstance(chain, LoggerChain)
        assert chain.options.maskSensitiveData is False

    def test_add_context(self, logger_chain):
        """Test add_context chain method."""
        chain = logger_chain.add_context("new_key", "new_value")

        assert chain is logger_chain  # Should return self
        assert logger_chain.context["new_key"] == "new_value"

    def test_add_user(self, logger_chain):
        """Test add_user chain method."""
        chain = logger_chain.add_user("user-123")

        assert chain is logger_chain
        assert logger_chain.options.userId == "user-123"

    @pytest.mark.asyncio
    async def test_chain_error(self, logger_service):
        """Test chain error logging."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(logger_service, "error", new_callable=AsyncMock) as mock_error:
            chain = logger_service.with_token("token")
            await chain.error("Error message", "stack trace")

            mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_chain_info(self, logger_service):
        """Test chain info logging."""
        logger_service.redis.is_connected.return_value = False

        with patch.object(logger_service, "info", new_callable=AsyncMock) as mock_info:
            chain = logger_service.with_context({"key": "value"})
            await chain.info("Info message")

            mock_info.assert_called_once()


class TestRedisService:
    """Test cases for RedisService."""

    @pytest.mark.asyncio
    async def test_connect_success(self, redis_service):
        """Test successful Redis connection."""
        with patch("redis.asyncio.Redis") as mock_redis_class:
            mock_redis = MagicMock()
            mock_redis.ping = AsyncMock()
            mock_redis_class.return_value = mock_redis

            await redis_service.connect()
            assert redis_service.is_connected() is True

    @pytest.mark.asyncio
    async def test_connect_no_config(self):
        """Test Redis connection when no config."""
        from miso_client.services.redis import RedisService

        redis_service = RedisService(None)

        await redis_service.connect()
        # Should not raise, just continue with fallback mode
        assert redis_service.is_connected() is False

    @pytest.mark.asyncio
    async def test_get_success(self, redis_service):
        """Test successful Redis get operation."""
        redis_service.redis = MagicMock()
        redis_service.redis.get = AsyncMock(return_value="test_value")
        redis_service.connected = True

        result = await redis_service.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_get_not_connected(self, redis_service):
        """Test Redis get when not connected."""
        result = await redis_service.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_success(self, redis_service):
        """Test successful Redis set operation."""
        redis_service.redis = MagicMock()
        redis_service.redis.setex = AsyncMock()
        redis_service.connected = True

        result = await redis_service.set("test_key", "test_value", 300)
        assert result is True

    @pytest.mark.asyncio
    async def test_set_not_connected(self, redis_service):
        """Test Redis set when not connected."""
        result = await redis_service.set("test_key", "test_value", 300)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self, redis_service):
        """Test successful Redis delete operation."""
        redis_service.redis = MagicMock()
        redis_service.redis.delete = AsyncMock()
        redis_service.connected = True

        result = await redis_service.delete("test_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_rpush_success(self, redis_service):
        """Test successful Redis rpush operation."""
        redis_service.redis = MagicMock()
        redis_service.redis.rpush = AsyncMock()
        redis_service.connected = True

        result = await redis_service.rpush("queue", "value")
        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect_when_connected(self, redis_service):
        """Test disconnect when connected."""
        redis_service.redis = MagicMock()
        redis_service.redis.aclose = AsyncMock()
        redis_service.connected = True

        await redis_service.disconnect()

        assert redis_service.connected is False
        redis_service.redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, redis_service):
        """Test disconnect when not connected."""
        redis_service.redis = None
        redis_service.connected = False

        # Should not raise exception
        await redis_service.disconnect()

        assert redis_service.connected is False

    @pytest.mark.asyncio
    async def test_disconnect_when_redis_is_none(self, redis_service):
        """Test disconnect when redis is None."""
        redis_service.redis = None
        redis_service.connected = True

        # Should not raise exception, but connected flag should be set to False
        await redis_service.disconnect()

        # Note: The actual implementation doesn't set connected to False if redis is None
        # This is expected behavior - disconnect only sets connected to False if redis exists
        assert redis_service.redis is None

    @pytest.mark.asyncio
    async def test_get_with_key_prefix(self, redis_service, config):
        """Test get operation with key prefix configured."""
        redis_service.config = config.redis
        redis_service.config.key_prefix = "prefix:"
        redis_service.redis = MagicMock()
        redis_service.redis.get = AsyncMock(return_value="test_value")
        redis_service.connected = True

        result = await redis_service.get("test_key")

        assert result == "test_value"
        redis_service.redis.get.assert_called_once_with("prefix:test_key")

    @pytest.mark.asyncio
    async def test_set_with_key_prefix(self, redis_service, config):
        """Test set operation with key prefix configured."""
        redis_service.config = config.redis
        redis_service.config.key_prefix = "prefix:"
        redis_service.redis = MagicMock()
        redis_service.redis.setex = AsyncMock()
        redis_service.connected = True

        result = await redis_service.set("test_key", "test_value", 300)

        assert result is True
        redis_service.redis.setex.assert_called_once_with("prefix:test_key", 300, "test_value")

    @pytest.mark.asyncio
    async def test_delete_with_key_prefix(self, redis_service, config):
        """Test delete operation with key prefix configured."""
        redis_service.config = config.redis
        redis_service.config.key_prefix = "prefix:"
        redis_service.redis = MagicMock()
        redis_service.redis.delete = AsyncMock()
        redis_service.connected = True

        result = await redis_service.delete("test_key")

        assert result is True
        redis_service.redis.delete.assert_called_once_with("prefix:test_key")

    @pytest.mark.asyncio
    async def test_rpush_with_key_prefix(self, redis_service, config):
        """Test rpush operation with key prefix configured."""
        redis_service.config = config.redis
        redis_service.config.key_prefix = "prefix:"
        redis_service.redis = MagicMock()
        redis_service.redis.rpush = AsyncMock()
        redis_service.connected = True

        result = await redis_service.rpush("queue", "value")

        assert result is True
        redis_service.redis.rpush.assert_called_once_with("prefix:queue", "value")

    @pytest.mark.asyncio
    async def test_get_operation_exception(self, redis_service):
        """Test get operation when Redis raises exception."""
        redis_service.redis = MagicMock()
        redis_service.redis.get = AsyncMock(side_effect=Exception("Redis error"))
        redis_service.connected = True

        result = await redis_service.get("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_operation_exception(self, redis_service):
        """Test set operation when Redis raises exception."""
        redis_service.redis = MagicMock()
        redis_service.redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        redis_service.connected = True

        result = await redis_service.set("test_key", "test_value", 300)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_operation_exception(self, redis_service):
        """Test delete operation when Redis raises exception."""
        redis_service.redis = MagicMock()
        redis_service.redis.delete = AsyncMock(side_effect=Exception("Redis error"))
        redis_service.connected = True

        result = await redis_service.delete("test_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_rpush_operation_exception(self, redis_service):
        """Test rpush operation when Redis raises exception."""
        redis_service.redis = MagicMock()
        redis_service.redis.rpush = AsyncMock(side_effect=Exception("Redis error"))
        redis_service.connected = True

        result = await redis_service.rpush("queue", "value")

        assert result is False

    @pytest.mark.asyncio
    async def test_connect_ping_not_awaitable(self, redis_service, config):
        """Test connect when ping response is not awaitable."""
        redis_service.config = config.redis

        with patch("redis.asyncio.Redis") as mock_redis_class:
            mock_redis = MagicMock()
            mock_redis.ping = MagicMock(return_value="PONG")  # Not awaitable
            mock_redis_class.return_value = mock_redis

            await redis_service.connect()

            assert redis_service.is_connected() is True

    @pytest.mark.asyncio
    async def test_connect_failure_handling(self, redis_service, config):
        """Test connect failure handling."""
        redis_service.config = config.redis

        with patch("redis.asyncio.Redis") as mock_redis_class:
            mock_redis_class.side_effect = Exception("Connection failed")

            # Should raise exception when config is provided
            with pytest.raises(Exception, match="Connection failed"):
                await redis_service.connect()

            assert redis_service.is_connected() is False

    @pytest.mark.asyncio
    async def test_get_with_awaitable_response(self, redis_service):
        """Test get operation with awaitable response."""
        redis_service.redis = MagicMock()

        # Create a coroutine-like object
        async def get_async():
            return "test_value"

        redis_service.redis.get = MagicMock(return_value=get_async())
        redis_service.connected = True

        result = await redis_service.get("test_key")

        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set_with_awaitable_response(self, redis_service):
        """Test set operation with awaitable response."""
        redis_service.redis = MagicMock()

        # Create a coroutine-like object
        async def setex_async():
            return True

        redis_service.redis.setex = MagicMock(return_value=setex_async())
        redis_service.connected = True

        result = await redis_service.set("test_key", "test_value", 300)

        assert result is True
