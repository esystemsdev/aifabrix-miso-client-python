"""
Unit tests for MisoClient SDK.

This module contains comprehensive unit tests for the MisoClient SDK,
mirroring the test coverage from the TypeScript version.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from miso_client import MisoClient
from miso_client.services.auth import AuthService
from miso_client.services.role import RoleService
from miso_client.services.permission import PermissionService
from miso_client.services.logger import LoggerService, LoggerChain
from miso_client.models.config import UserInfo, AuthResult, RoleResult, PermissionResult


class TestMisoClient:
    """Test cases for MisoClient main class."""
    
    @pytest.mark.asyncio
    async def test_initialization_success(self, client, mock_redis):
        """Test successful client initialization."""
        with patch.object(client.redis, 'connect', new_callable=AsyncMock) as mock_connect:
            await client.initialize()
            assert client.is_initialized() is True
            mock_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialization_redis_failure(self, client):
        """Test initialization with Redis connection failure."""
        with patch.object(client.redis, 'connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            await client.initialize()
            assert client.is_initialized() is True  # Should still initialize for fallback mode
    
    @pytest.mark.asyncio
    async def test_disconnect(self, client):
        """Test client disconnection."""
        with patch.object(client.redis, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
            with patch.object(client.http_client, 'close', new_callable=AsyncMock) as mock_close:
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
        with patch.object(client.redis, 'is_connected', return_value=True):
            assert client.is_redis_connected() is True
        
        with patch.object(client.redis, 'is_connected', return_value=False):
            assert client.is_redis_connected() is False
    
    @pytest.mark.asyncio
    async def test_get_token_from_request(self, client):
        """Test extracting token from request."""
        req = {
            "headers": {
                "authorization": "Bearer test-token-123"
            }
        }
        
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
        with patch.object(client.auth, 'get_environment_token', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "env-token-123"
            
            token = await client.get_environment_token()
            
            assert token == "env-token-123"
            mock_get.assert_called_once()


class TestAuthService:
    """Test cases for AuthService."""
    
    @pytest.fixture
    def auth_service(self, mock_http_client, mock_redis):
        """Test AuthService instance."""
        return AuthService(mock_http_client, mock_redis)
    
    @pytest.mark.asyncio
    async def test_validate_token_success(self, auth_service):
        """Test successful token validation."""
        with patch.object(auth_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"authenticated": True, "user": {"id": "123", "username": "testuser"}}
            
            result = await auth_service.validate_token("valid-token")
            assert result is True
            mock_request.assert_called_once_with("POST", "/api/auth/validate", "valid-token")
    
    @pytest.mark.asyncio
    async def test_validate_token_failure(self, auth_service):
        """Test failed token validation."""
        with patch.object(auth_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"authenticated": False, "error": "Invalid token"}
            
            result = await auth_service.validate_token("invalid-token")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_token_exception(self, auth_service):
        """Test token validation with exception."""
        with patch.object(auth_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("Network error")
            
            result = await auth_service.validate_token("token")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_user_success(self, auth_service):
        """Test successful user retrieval."""
        user_info = UserInfo(id="123", username="testuser", email="test@example.com")
        with patch.object(auth_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"authenticated": True, "user": user_info.model_dump()}
            
            result = await auth_service.get_user("valid-token")
            assert result is not None
            assert result.id == "123"
            assert result.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_get_user_failure(self, auth_service):
        """Test failed user retrieval."""
        with patch.object(auth_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"authenticated": False, "error": "Invalid token"}
            
            result = await auth_service.get_user("invalid-token")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_info(self, auth_service):
        """Test getting user info from /api/auth/user endpoint."""
        user_info = UserInfo(id="123", username="testuser")
        with patch.object(auth_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = user_info.model_dump()
            
            result = await auth_service.get_user_info("valid-token")
            assert result is not None
            assert result.id == "123"
            mock_request.assert_called_once_with("GET", "/api/auth/user", "valid-token")
    
    @pytest.mark.asyncio
    async def test_get_environment_token(self, auth_service):
        """Test getting environment token."""
        with patch.object(auth_service.http_client, 'get_environment_token', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = "client-token-123"
            
            token = await auth_service.get_environment_token()
            
            assert token == "client-token-123"
            mock_get.assert_called_once()
    
    def test_login_returns_url(self, auth_service, config):
        """Test login returns URL string."""
        url = auth_service.login("/dashboard")
        
        assert isinstance(url, str)
        assert "/api/auth/login" in url
        assert "redirect=/dashboard" in url
    
    @pytest.mark.asyncio
    async def test_logout(self, auth_service):
        """Test logout functionality."""
        with patch.object(auth_service.http_client, 'request', new_callable=AsyncMock) as mock_request:
            await auth_service.logout()
            mock_request.assert_called_once_with("POST", "/api/auth/logout")
    
    @pytest.mark.asyncio
    async def test_logout_exception(self, auth_service):
        """Test logout with exception."""
        from miso_client.errors import MisoClientError
        
        with patch.object(auth_service.http_client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = Exception("Logout failed")
            
            with pytest.raises(MisoClientError, match="Logout failed"):
                await auth_service.logout()
    
    @pytest.mark.asyncio
    async def test_is_authenticated(self, auth_service):
        """Test is_authenticated method."""
        with patch.object(auth_service, 'validate_token', new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = True
            
            result = await auth_service.is_authenticated("token")
            
            assert result is True
            mock_validate.assert_called_once_with("token")


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
        
        with patch.object(role_service.cache, 'get', new_callable=AsyncMock) as mock_get:
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
        
        with patch.object(role_service.cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # Cache miss
            
            with patch.object(role_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
                mock_request.return_value = RoleResult(
                    userId="user-123",
                    roles=["admin"],
                    environment="dev",
                    application="test-app"
                ).model_dump()
                
                with patch.object(role_service.cache, 'set', new_callable=AsyncMock) as mock_set:
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
        
        with patch.object(role_service.cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None  # Cache miss
            
            with patch.object(role_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
                mock_request.side_effect = [
                    {"user": {"id": "user-123"}},  # From validate endpoint
                    RoleResult(userId="user-123", roles=["admin"], environment="dev", application="app").model_dump()
                ]
                
                with patch.object(role_service.cache, 'set', new_callable=AsyncMock):
                    roles = await role_service.get_roles(token)
                    assert "admin" in roles
    
    @pytest.mark.asyncio
    async def test_has_role(self, role_service):
        """Test role checking."""
        with patch.object(role_service, 'get_roles', new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["admin", "user"]
            
            result = await role_service.has_role("token", "admin")
            assert result is True
            
            result = await role_service.has_role("token", "guest")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_has_any_role(self, role_service):
        """Test checking for any role."""
        with patch.object(role_service, 'get_roles', new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["admin", "user"]
            
            result = await role_service.has_any_role("token", ["admin", "guest"])
            assert result is True
            
            result = await role_service.has_any_role("token", ["guest", "visitor"])
            assert result is False
    
    @pytest.mark.asyncio
    async def test_has_all_roles(self, role_service):
        """Test checking for all roles."""
        with patch.object(role_service, 'get_roles', new_callable=AsyncMock) as mock_get_roles:
            mock_get_roles.return_value = ["admin", "user"]
            
            result = await role_service.has_all_roles("token", ["admin", "user"])
            assert result is True
            
            result = await role_service.has_all_roles("token", ["admin", "guest"])
            assert result is False
    
    @pytest.mark.asyncio
    async def test_refresh_roles(self, role_service):
        """Test refreshing roles."""
        with patch.object(role_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                {"user": {"id": "user-123"}},
                RoleResult(userId="user-123", roles=["admin", "user"], environment="dev", application="app").model_dump()
            ]
            
            with patch.object(role_service.cache, 'set', new_callable=AsyncMock):
                roles = await role_service.refresh_roles("token")
                
                assert "admin" in roles
                assert "user" in roles
                # Should call refresh endpoint
                assert "/api/auth/roles/refresh" in str(mock_request.call_args_list[1])


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
        
        with patch.object(permission_service.cache, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"permissions": ["read", "write"], "timestamp": 1234567890}
            
            permissions = await permission_service.get_permissions(token)
            
            assert permissions == ["read", "write"]
            # Should use simplified cache key
            mock_get.assert_called_once_with("permissions:user-123")
    
    @pytest.mark.asyncio
    async def test_has_permission(self, permission_service):
        """Test permission checking."""
        with patch.object(permission_service, 'get_permissions', new_callable=AsyncMock) as mock_get_permissions:
            mock_get_permissions.return_value = ["read", "write"]
            
            result = await permission_service.has_permission("token", "read")
            assert result is True
            
            result = await permission_service.has_permission("token", "delete")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_has_any_permission(self, permission_service):
        """Test checking for any permission."""
        with patch.object(permission_service, 'get_permissions', new_callable=AsyncMock) as mock_get_permissions:
            mock_get_permissions.return_value = ["read", "write"]
            
            result = await permission_service.has_any_permission("token", ["read", "delete"])
            assert result is True
            
            result = await permission_service.has_any_permission("token", ["delete", "update"])
            assert result is False
    
    @pytest.mark.asyncio
    async def test_has_all_permissions(self, permission_service):
        """Test checking for all permissions."""
        with patch.object(permission_service, 'get_permissions', new_callable=AsyncMock) as mock_get_permissions:
            mock_get_permissions.return_value = ["read", "write"]
            
            result = await permission_service.has_all_permissions("token", ["read", "write"])
            assert result is True
            
            result = await permission_service.has_all_permissions("token", ["read", "delete"])
            assert result is False
    
    @pytest.mark.asyncio
    async def test_refresh_permissions(self, permission_service):
        """Test refreshing permissions."""
        with patch.object(permission_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                {"user": {"id": "user-123"}},
                PermissionResult(userId="user-123", permissions=["read", "write"], environment="dev", application="app").model_dump()
            ]
            
            with patch.object(permission_service.cache, 'set', new_callable=AsyncMock):
                permissions = await permission_service.refresh_permissions("token")
                
                assert "read" in permissions
                assert "write" in permissions
                # Should call refresh endpoint
                assert "/api/auth/permissions/refresh" in str(mock_request.call_args_list[1])
    
    @pytest.mark.asyncio
    async def test_clear_permissions_cache(self, permission_service):
        """Test clearing permissions cache."""
        with patch.object(permission_service.http_client, 'authenticated_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"user": {"id": "user-123"}}
            
            with patch.object(permission_service.cache, 'delete', new_callable=AsyncMock) as mock_delete:
                await permission_service.clear_permissions_cache("token")
                mock_delete.assert_called_once()
                assert mock_delete.call_args[0][0] == "permissions:user-123"


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
        
        with patch.object(logger_service.redis, 'rpush', new_callable=AsyncMock) as mock_rpush:
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
        
        with patch.object(logger_service.http_client, 'request', new_callable=AsyncMock) as mock_request:
            await logger_service.info("Test message", {"key": "value"})
            mock_request.assert_called_once()
            # Verify it's a POST to /api/logs
            assert mock_request.call_args[0][0] == "POST"
            assert mock_request.call_args[0][1] == "/api/logs"
    
    @pytest.mark.asyncio
    async def test_audit_log(self, logger_service):
        """Test audit logging."""
        logger_service.redis.is_connected.return_value = False
        
        with patch.object(logger_service.http_client, 'request', new_callable=AsyncMock) as mock_request:
            await logger_service.audit("user.login", "authentication", {"ip": "192.168.1.1"})
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_log_with_stack_trace(self, logger_service):
        """Test error logging with stack trace."""
        logger_service.redis.is_connected.return_value = False
        
        with patch.object(logger_service.http_client, 'request', new_callable=AsyncMock) as mock_request:
            await logger_service.error("Error occurred", {"error": "test"}, stack_trace="Traceback...")
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_debug_log_with_debug_level(self, logger_service):
        """Test debug logging when debug level is enabled."""
        logger_service.config.log_level = "debug"
        logger_service.redis.is_connected.return_value = False
        
        with patch.object(logger_service.http_client, 'request', new_callable=AsyncMock) as mock_request:
            await logger_service.debug("Debug message")
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_debug_log_without_debug_level(self, logger_service):
        """Test debug logging when debug level is disabled."""
        logger_service.config.log_level = "info"
        logger_service.redis.is_connected.return_value = False
        
        with patch.object(logger_service.http_client, 'request', new_callable=AsyncMock) as mock_request:
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
        
        with patch.object(logger_service.http_client, 'request', new_callable=AsyncMock) as mock_request:
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
    
    def test_with_performance(self, logger_service):
        """Test with_performance chain method."""
        chain = logger_service.with_performance()
        
        assert isinstance(chain, LoggerChain)
        assert chain.options.performanceMetrics is True
    
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
        
        with patch.object(logger_service, 'error', new_callable=AsyncMock) as mock_error:
            chain = logger_service.with_token("token")
            await chain.error("Error message", "stack trace")
            
            mock_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_chain_info(self, logger_service):
        """Test chain info logging."""
        logger_service.redis.is_connected.return_value = False
        
        with patch.object(logger_service, 'info', new_callable=AsyncMock) as mock_info:
            chain = logger_service.with_context({"key": "value"})
            await chain.info("Info message")
            
            mock_info.assert_called_once()


class TestRedisService:
    """Test cases for RedisService."""
    
    @pytest.mark.asyncio
    async def test_connect_success(self, redis_service):
        """Test successful Redis connection."""
        with patch('redis.asyncio.Redis') as mock_redis_class:
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
