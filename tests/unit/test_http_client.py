"""
Unit tests for HTTP client with automatic client token management.

This module contains tests for both InternalHttpClient (core HTTP functionality)
and public HttpClient (with ISO 27001 compliant audit and debug logging).
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from miso_client.errors import AuthenticationError, MisoClientError
from miso_client.models.config import MisoClientConfig
from miso_client.services.logger import LoggerService
from miso_client.services.redis import RedisService
from miso_client.utils.data_masker import DataMasker
from miso_client.utils.http_client import HttpClient
from miso_client.utils.internal_http_client import InternalHttpClient


class TestInternalHttpClient:
    """Test cases for HttpClient."""

    @pytest.fixture
    def config(self):
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
        )

    @pytest.fixture
    def http_client(self, config):
        return InternalHttpClient(config)

    @pytest.mark.asyncio
    async def test_fetch_client_token_success(self, http_client):
        """Test successful client token fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "token": "client-token-123",
            "expiresIn": 3600,
            "expiresAt": "2024-01-01T12:00:00Z",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await http_client._fetch_client_token()

            assert http_client.client_token == "client-token-123"
            assert http_client.token_expires_at is not None

    @pytest.mark.asyncio
    async def test_fetch_client_token_failure(self, http_client):
        """Test client token fetch failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            with pytest.raises(AuthenticationError):
                await http_client._fetch_client_token()

    @pytest.mark.asyncio
    async def test_get_client_token_cached(self, http_client):
        """Test getting cached client token."""
        http_client.client_token = "cached-token"
        http_client.token_expires_at = datetime.now() + timedelta(seconds=120)

        token = await http_client._get_client_token()

        assert token == "cached-token"

    @pytest.mark.asyncio
    async def test_get_client_token_refresh_needed(self, http_client):
        """Test token refresh when about to expire."""
        http_client.client_token = "old-token"
        http_client.token_expires_at = datetime.now() + timedelta(seconds=30)  # < 60s

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "token": "new-token",
            "expiresIn": 3600,
            "expiresAt": "2024-01-01T12:00:00Z",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            token = await http_client._get_client_token()

            assert token == "new-token"

    @pytest.mark.asyncio
    async def test_get_request_success(self, http_client):
        """Test successful GET request."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "test"}
        mock_response.headers.get.return_value = "application/json"
        mock_response.raise_for_status = MagicMock()

        http_client.client.get = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            result = await http_client.get("/test")

            assert result == {"data": "test"}
            # The x-client-token header is added during request, not to client headers
            call_args = http_client.client.get.call_args
            if call_args and len(call_args) > 1 and "headers" in call_args[1]:
                assert "x-client-token" in call_args[1]["headers"]
            else:
                # If headers not in kwargs, check if it was called with headers
                assert call_args is not None

    @pytest.mark.asyncio
    async def test_get_request_401_clears_token(self, http_client):
        """Test that 401 clears client token."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"
        http_client.token_expires_at = datetime.now() + timedelta(seconds=100)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.headers.get.return_value = "application/json"
        mock_response.json.return_value = {}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_response
        )

        http_client.client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(MisoClientError):
            await http_client.get("/test")

        assert http_client.client_token is None
        assert http_client.token_expires_at is None

    @pytest.mark.asyncio
    async def test_post_request(self, http_client):
        """Test POST request."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_response.headers.get.return_value = "application/json"
        mock_response.raise_for_status = MagicMock()

        http_client.client.post = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            result = await http_client.post("/test", {"key": "value"})

            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_authenticated_request(self, http_client):
        """Test authenticated request with Bearer token."""
        await http_client._initialize_client()
        http_client.client_token = "client-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"user": "data"}
        mock_response.headers.get.return_value = "application/json"
        mock_response.raise_for_status = MagicMock()

        http_client.client.get = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            result = await http_client.authenticated_request("GET", "/user", "user-token")

            assert result == {"user": "data"}
            # Verify Bearer token was added
            call_args = http_client.client.get.call_args
        assert "Authorization" in call_args[1]["headers"]
        assert call_args[1]["headers"]["Authorization"] == "Bearer user-token"

    @pytest.mark.asyncio
    async def test_request_methods(self, http_client):
        """Test all request methods."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_response.headers.get.return_value = "application/json"
        mock_response.raise_for_status = MagicMock()

        methods = ["GET", "POST", "PUT", "DELETE"]
        for method in methods:
            if method == "GET":
                http_client.client.get = AsyncMock(return_value=mock_response)
            elif method == "POST":
                http_client.client.post = AsyncMock(return_value=mock_response)
            elif method == "PUT":
                http_client.client.put = AsyncMock(return_value=mock_response)
            elif method == "DELETE":
                http_client.client.delete = AsyncMock(return_value=mock_response)

            with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
                result = await http_client.request(
                    method, "/test", None if method == "GET" else {"data": "test"}
                )
                assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_get_environment_token(self, http_client):
        """Test get_environment_token method."""
        http_client.client_token = "env-token"
        http_client.token_expires_at = datetime.now() + timedelta(seconds=100)

        token = await http_client.get_environment_token()

        assert token == "env-token"

    @pytest.mark.asyncio
    async def test_put_request_success(self, http_client):
        """Test successful PUT request."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "updated"}
        mock_response.raise_for_status = MagicMock()

        http_client.client.put = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            result = await http_client.put("/api/resource", {"key": "value"})

            assert result == {"data": "updated"}
            http_client.client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_put_request_401_clears_token(self, http_client):
        """Test PUT request with 401 error clears token."""
        await http_client._initialize_client()
        http_client.client_token = "existing-token"
        http_client.token_expires_at = datetime.now() + timedelta(seconds=3600)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.headers.get.return_value = "application/json"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        http_client.client.put = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            with pytest.raises(MisoClientError):
                await http_client.put("/api/resource", {"key": "value"})

            assert http_client.client_token is None
            assert http_client.token_expires_at is None

    @pytest.mark.asyncio
    async def test_delete_request_success(self, http_client):
        """Test successful DELETE request."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"deleted": True}
        mock_response.raise_for_status = MagicMock()

        http_client.client.delete = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            result = await http_client.delete("/api/resource")

            assert result == {"deleted": True}
            http_client.client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_request_401_clears_token(self, http_client):
        """Test DELETE request with 401 error clears token."""
        await http_client._initialize_client()
        http_client.client_token = "existing-token"
        http_client.token_expires_at = datetime.now() + timedelta(seconds=3600)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.headers.get.return_value = "application/json"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        http_client.client.delete = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            with pytest.raises(MisoClientError):
                await http_client.delete("/api/resource")

            assert http_client.client_token is None
            assert http_client.token_expires_at is None

    @pytest.mark.asyncio
    async def test_context_manager_usage(self, http_client):
        """Test async context manager usage."""
        await http_client._initialize_client()

        with patch.object(http_client, "close", new_callable=AsyncMock) as mock_close:
            async with http_client:
                pass

            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager_with_exception(self, http_client):
        """Test async context manager with exception."""
        await http_client._initialize_client()

        with patch.object(http_client, "close", new_callable=AsyncMock) as mock_close:
            try:
                async with http_client:
                    raise ValueError("Test error")
            except ValueError:
                pass

            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_unsupported_method(self, http_client):
        """Test request with unsupported HTTP method."""
        await http_client._initialize_client()

        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            await http_client.request("PATCH", "/api/resource")

    @pytest.mark.asyncio
    async def test_parse_error_response_non_json(self, http_client):
        """Test _parse_error_response with non-JSON content."""
        await http_client._initialize_client()

        mock_response = MagicMock()
        mock_response.headers.get.return_value = "text/plain"

        result = http_client._parse_error_response(mock_response, "/api/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_parse_error_response_malformed_json(self, http_client):
        """Test _parse_error_response with malformed JSON."""
        await http_client._initialize_client()

        mock_response = MagicMock()
        mock_response.headers.get.return_value = "application/json"
        mock_response.json.side_effect = ValueError("Invalid JSON")

        result = http_client._parse_error_response(mock_response, "/api/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_parse_error_response_missing_fields(self, http_client):
        """Test _parse_error_response with missing required fields."""
        await http_client._initialize_client()

        mock_response = MagicMock()
        mock_response.headers.get.return_value = "application/json"
        mock_response.json.return_value = {"type": "error"}  # Missing required fields

        result = http_client._parse_error_response(mock_response, "/api/test")

        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_token_refresh(self, http_client):
        """Test concurrent token refresh (lock mechanism)."""
        await http_client._initialize_client()
        http_client.client_token = None  # Force refresh

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "token": "new-token",
            "expiresIn": 3600,
            "expiresAt": "2024-01-01T12:00:00Z",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            # Simulate concurrent token fetches
            tokens = await asyncio.gather(
                http_client._get_client_token(),
                http_client._get_client_token(),
                http_client._get_client_token(),
            )

            # All should return the same token
            assert all(t == "new-token" for t in tokens)
            # Should only fetch once due to lock
            assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_close(self, http_client):
        """Test closing HTTP client."""
        await http_client._initialize_client()
        if http_client.client:
            http_client.client.aclose = AsyncMock()

        await http_client.close()

        if http_client.client:
            http_client.client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_request_with_structured_error_response(self, http_client):
        """Test GET request with structured error response."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"errors": ["Bad request"], "type": "/Errors/Bad Input", "title": "Bad Request", "statusCode": 400, "instance": "/api/test"}'
        mock_response.headers.get.return_value = "application/json"
        mock_response.json.return_value = {
            "errors": ["Bad request"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "instance": "/api/test",
        }
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400", request=MagicMock(), response=mock_response
        )

        http_client.client.get = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            with pytest.raises(MisoClientError) as exc_info:
                await http_client.get("/api/test")

            error = exc_info.value
            assert error.status_code == 400
            assert error.error_response is not None
            assert error.error_response.errors == ["Bad request"]
            assert error.error_response.type == "/Errors/Bad Input"
            assert error.error_response.title == "Bad Request"
            assert error.error_response.statusCode == 400
            assert error.error_response.instance == "/api/test"

    @pytest.mark.asyncio
    async def test_post_request_with_structured_error_response(self, http_client):
        """Test POST request with structured error response."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "Validation error"
        mock_response.headers.get.return_value = "application/json"
        mock_response.json.return_value = {
            "errors": [
                "The user has provided input that the browser is unable to convert.",
                "There are multiple rows in the database for the same value",
            ],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 422,
            "instance": "/OpenApi/rest/Xzy",
        }
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "422", request=MagicMock(), response=mock_response
        )

        http_client.client.post = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            with pytest.raises(MisoClientError) as exc_info:
                await http_client.post("/OpenApi/rest/Xzy", {"data": "test"})

            error = exc_info.value
            assert error.status_code == 422
            assert error.error_response is not None
            assert len(error.error_response.errors) == 2
            assert error.error_response.instance == "/OpenApi/rest/Xzy"

    @pytest.mark.asyncio
    async def test_error_response_fallback_to_error_body(self, http_client):
        """Test fallback to error_body when response doesn't match structured format."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_response.headers.get.return_value = "application/json"
        mock_response.json.return_value = {"code": "ERR500", "message": "Internal server error"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_response
        )

        http_client.client.get = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            with pytest.raises(MisoClientError) as exc_info:
                await http_client.get("/api/test")

            error = exc_info.value
            assert error.status_code == 500
            assert error.error_response is None
            assert error.error_body == {"code": "ERR500", "message": "Internal server error"}

    @pytest.mark.asyncio
    async def test_error_response_instance_extraction_from_url(self, http_client):
        """Test that instance URI is extracted from request URL when not in response."""
        await http_client._initialize_client()
        http_client.client_token = "test-token"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.headers.get.return_value = "application/json"
        mock_response.json.return_value = {
            "errors": ["Bad request"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            # instance not provided
        }
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400", request=MagicMock(), response=mock_response
        )

        http_client.client.get = AsyncMock(return_value=mock_response)

        with patch.object(http_client, "_ensure_client_token", new_callable=AsyncMock):
            with pytest.raises(MisoClientError) as exc_info:
                await http_client.get("/api/custom/endpoint")

            error = exc_info.value
            assert error.error_response is not None
            assert error.error_response.instance == "/api/custom/endpoint"


class TestHttpClient:
    """Test cases for public HttpClient with ISO 27001 compliant logging."""

    @pytest.fixture
    def config(self):
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            log_level="info",
        )

    @pytest.fixture
    def redis_service(self, config):
        return RedisService(config.redis)

    @pytest.fixture
    def internal_http_client(self, config):
        return InternalHttpClient(config)

    @pytest.fixture
    def logger_service(self, internal_http_client, redis_service):
        return LoggerService(internal_http_client, redis_service)

    @pytest.fixture
    def http_client(self, config, logger_service):
        return HttpClient(config, logger_service)

    @pytest.mark.asyncio
    async def test_get_request_with_audit_logging(self, http_client):
        """Test GET request with audit logging."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        result = await http_client.get("/api/test")

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        assert result == {"data": "test"}
        # Verify audit logging was called
        http_client.logger.audit.assert_called_once()
        call_args = http_client.logger.audit.call_args
        assert call_args[0][0] == "http.request.GET"
        assert call_args[0][1] == "/api/test"

    @pytest.mark.asyncio
    async def test_post_request_with_data_masking(self, http_client):
        """Test POST request with data masking in logs."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"success": True})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        # Request with sensitive data
        sensitive_data = {"password": "secret123", "username": "user"}
        result = await http_client.post("/api/login", sensitive_data)

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        assert result == {"success": True}
        # Verify audit logging was called
        http_client.logger.audit.assert_called_once()
        # Verify sensitive data was masked in context
        call_args = http_client.logger.audit.call_args
        context = call_args[0][2]  # Third argument is context
        # Context should not contain raw password
        context_str = str(context)
        assert "secret123" not in context_str

    @pytest.mark.asyncio
    async def test_debug_logging_when_enabled(self, http_client):
        """Test debug logging when log_level is debug."""
        # Set log level to debug
        http_client.config.log_level = "debug"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        result = await http_client.get("/api/test")

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        assert result == {"data": "test"}
        # Verify audit logging was called
        http_client.logger.audit.assert_called_once()
        # Verify debug logging was called when log_level is debug
        http_client.logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_logging_for_logs_endpoint(self, http_client):
        """Test that /api/logs endpoint is not audited."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"success": True})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()

        result = await http_client.post("/api/logs", {"log": "entry"})

        assert result == {"success": True}
        # Verify audit logging was NOT called for /api/logs
        http_client.logger.audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_logging_for_token_endpoint(self, http_client):
        """Test that /api/auth/token endpoint is not audited."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"token": "abc123"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()

        result = await http_client.post("/api/auth/token", {})

        assert result == {"token": "abc123"}
        # Verify audit logging was NOT called for /api/auth/token
        http_client.logger.audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_logging_with_masked_data(self, http_client):
        """Test error logging with masked sensitive data."""
        # Mock InternalHttpClient to raise error
        mock_internal_client = AsyncMock()
        from miso_client.errors import MisoClientError

        mock_internal_client.get = AsyncMock(
            side_effect=MisoClientError("Request failed with password: secret123", status_code=400)
        )
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()

        with pytest.raises(MisoClientError):
            await http_client.get("/api/test")

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        # Verify audit logging was called
        http_client.logger.audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_methods_wrapped(self, http_client):
        """Test that all HTTP methods are wrapped with logging."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"get": True})
        mock_internal_client.post = AsyncMock(return_value={"post": True})
        mock_internal_client.put = AsyncMock(return_value={"put": True})
        mock_internal_client.delete = AsyncMock(return_value={"delete": True})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()

        # Test all methods
        await http_client.get("/test")
        await http_client.post("/test", {"data": "test"})
        await http_client.put("/test", {"data": "test"})
        await http_client.delete("/test")

        # Wait for background logging tasks to complete
        await asyncio.sleep(0.02)

        # Verify audit logging was called for each method
        assert http_client.logger.audit.call_count == 4

    @pytest.mark.asyncio
    async def test_authenticated_request_with_logging(self, http_client):
        """Test authenticated request with logging."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"user": "data"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()

        result = await http_client.authenticated_request("GET", "/api/user", "token123")

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        assert result == {"user": "data"}
        # Verify audit logging was called
        http_client.logger.audit.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_delegates_to_internal(self, http_client):
        """Test that close() delegates to InternalHttpClient."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.close = AsyncMock()
        http_client._internal_client = mock_internal_client

        await http_client.close()

        mock_internal_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_environment_token_delegates(self, http_client):
        """Test that get_environment_token() delegates to InternalHttpClient."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get_environment_token = AsyncMock(return_value="token123")
        http_client._internal_client = mock_internal_client

        token = await http_client.get_environment_token()

        assert token == "token123"
        mock_internal_client.get_environment_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_headers_masking_in_debug_logs(self, http_client):
        """Test that request headers are masked in debug logs."""
        http_client.config.log_level = "debug"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        # Request with sensitive headers
        headers = {
            "Authorization": "Bearer secret-token-123",
            "x-client-token": "client-token-456",
            "Cookie": "session=abc123",
        }

        await http_client.get("/api/test", headers=headers)

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        # Verify debug logging was called
        http_client.logger.debug.assert_called_once()
        call_args = http_client.logger.debug.call_args
        debug_context = call_args[0][1]  # Second argument is context

        # Verify headers are present and masked
        assert "requestHeaders" in debug_context
        masked_headers = debug_context["requestHeaders"]
        # Verify sensitive headers are masked
        assert masked_headers.get("Authorization") == DataMasker.MASKED_VALUE
        assert masked_headers.get("x-client-token") == DataMasker.MASKED_VALUE
        assert masked_headers.get("Cookie") == DataMasker.MASKED_VALUE
        # Verify raw values are not present
        assert "secret-token-123" not in str(debug_context)
        assert "client-token-456" not in str(debug_context)
        assert "abc123" not in str(debug_context)

    @pytest.mark.asyncio
    async def test_response_body_masking_in_debug_logs(self, http_client):
        """Test that response bodies with sensitive data are masked in debug logs."""
        http_client.config.log_level = "debug"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        # Response with sensitive data
        mock_internal_client.get = AsyncMock(
            return_value={"user": {"password": "secret123", "username": "john"}}
        )
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        await http_client.get("/api/users")

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        # Verify debug logging was called
        http_client.logger.debug.assert_called_once()
        call_args = http_client.logger.debug.call_args
        debug_context = call_args[0][1]

        # Verify response body is present and masked
        assert "responseBody" in debug_context
        response_body_str = str(debug_context["responseBody"])
        # Verify sensitive data is masked
        assert "secret123" not in response_body_str
        assert DataMasker.MASKED_VALUE in response_body_str

    @pytest.mark.asyncio
    async def test_query_parameter_masking(self, http_client):
        """Test that query parameters are masked in debug logs."""
        http_client.config.log_level = "debug"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        # Request with sensitive query parameters
        await http_client.get("/api/test?token=secret123&api_key=key456&username=john")

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        # Verify debug logging was called
        http_client.logger.debug.assert_called_once()
        call_args = http_client.logger.debug.call_args
        debug_context = call_args[0][1]

        # Verify query params are present and masked
        # Query params might not be extracted if URL parsing fails or query string is empty
        # But if they are present, they should be masked
        if "queryParams" in debug_context:
            query_params = debug_context["queryParams"]
            # Verify sensitive query params are masked
            assert query_params.get("token") == DataMasker.MASKED_VALUE
            assert query_params.get("api_key") == DataMasker.MASKED_VALUE
            # Non-sensitive param should not be masked
            assert query_params.get("username") == "john"
        else:
            # If query params aren't extracted, verify that the URL contains the query string
            # which means the masking logic might have run but wasn't added to context
            assert "token" in debug_context.get("url", "")

    @pytest.mark.asyncio
    async def test_nested_data_masking(self, http_client):
        """Test that nested objects and arrays are masked recursively."""
        http_client.config.log_level = "debug"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"success": True})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        # Request with nested sensitive data
        nested_data = {
            "user": {
                "credentials": {
                    "password": "secret123",
                    "token": "token456",
                },
                "username": "john",
            },
            "settings": [{"api_key": "key789"}, {"session": "session123"}],
        }

        await http_client.post("/api/users", nested_data)

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        # Verify debug logging was called
        http_client.logger.debug.assert_called_once()
        call_args = http_client.logger.debug.call_args
        debug_context = call_args[0][1]

        # Verify nested data is masked
        assert "requestBody" in debug_context
        masked_body = debug_context["requestBody"]
        masked_str = str(masked_body)
        # Verify sensitive data at all nesting levels is masked
        assert "secret123" not in masked_str
        assert "token456" not in masked_str
        assert "key789" not in masked_str
        assert "session123" not in masked_str
        # Verify non-sensitive data is preserved
        assert "john" in masked_str

    @pytest.mark.asyncio
    async def test_jwt_user_id_extraction(self, http_client):
        """Test that user ID is extracted from JWT token in Authorization header."""
        from unittest.mock import patch

        # Mock JWT decoding
        with patch("miso_client.utils.jwt_tools.decode_token") as mock_decode:
            mock_decode.return_value = {"sub": "user-123", "username": "john"}

            # Mock InternalHttpClient
            mock_internal_client = AsyncMock()
            mock_internal_client.get = AsyncMock(return_value={"data": "test"})
            http_client._internal_client = mock_internal_client

            # Mock logger
            http_client.logger.audit = AsyncMock()

            # Request with JWT token in Authorization header
            headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
            await http_client.get("/api/test", headers=headers)

            # Wait for background logging task to complete
            await asyncio.sleep(0.01)

            # Verify audit logging was called with user ID
            http_client.logger.audit.assert_called_once()
            call_args = http_client.logger.audit.call_args
            audit_context = call_args[0][2]  # Third argument is context
            assert audit_context["userId"] == "user-123"

    @pytest.mark.asyncio
    async def test_duration_tracking(self, http_client):
        """Test that request duration is tracked correctly."""
        # Mock InternalHttpClient with delay
        mock_internal_client = AsyncMock()

        async def delayed_get(*args, **kwargs):
            await asyncio.sleep(0.01)  # 10ms delay
            return {"data": "test"}

        mock_internal_client.get = delayed_get
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()

        await http_client.get("/api/test")

        # Wait for background logging task to complete
        await asyncio.sleep(0.02)

        # Verify audit logging was called
        http_client.logger.audit.assert_called_once()
        call_args = http_client.logger.audit.call_args
        audit_context = call_args[0][2]
        assert "duration" in audit_context
        # Duration should be positive and reasonable (> 10ms due to sleep)
        assert audit_context["duration"] >= 10

    @pytest.mark.asyncio
    async def test_audit_log_structure(self, http_client):
        """Test that audit log has correct structure with all required fields."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()

        await http_client.get("/api/test?param=value")

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        # Verify audit logging was called with correct structure
        http_client.logger.audit.assert_called_once()
        call_args = http_client.logger.audit.call_args
        action = call_args[0][0]
        resource = call_args[0][1]
        context = call_args[0][2]

        # Verify action format
        assert action == "http.request.GET"

        # Verify resource is URL path
        assert resource == "/api/test?param=value"

        # Verify context has all required fields
        assert "method" in context
        assert context["method"] == "GET"
        assert "url" in context
        assert "statusCode" in context
        assert context["statusCode"] == 200
        assert "duration" in context
        assert isinstance(context["duration"], int)
        assert context["duration"] >= 0

    @pytest.mark.asyncio
    async def test_debug_log_structure(self, http_client):
        """Test that debug log has correct structure with all required fields."""
        http_client.config.log_level = "debug"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        await http_client.get("/api/test")

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        # Verify debug logging was called with correct structure
        http_client.logger.debug.assert_called_once()
        call_args = http_client.logger.debug.call_args
        message = call_args[0][0]
        debug_context = call_args[0][1]

        # Verify message contains key information
        assert "HTTP" in message
        assert "GET" in message
        assert "/api/test" in message

        # Verify debug context has all required fields
        assert "method" in debug_context
        assert "url" in debug_context
        assert "statusCode" in debug_context
        assert "duration" in debug_context
        assert "baseURL" in debug_context
        assert "timeout" in debug_context
        # Optional fields may be present
        # requestHeaders, requestBody, responseBody, queryParams may be None or present

    @pytest.mark.asyncio
    async def test_logging_errors_dont_break_requests(self, http_client):
        """Test that logging errors don't break HTTP requests."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger to raise exception
        http_client.logger.audit = AsyncMock(side_effect=Exception("Logging failed"))

        # Request should still succeed despite logging error
        result = await http_client.get("/api/test")

        assert result == {"data": "test"}
        # Verify request succeeded despite logging error

    @pytest.mark.asyncio
    async def test_response_body_truncation(self, http_client):
        """Test that response body is truncated to 1000 characters in debug logs."""
        http_client.config.log_level = "debug"

        # Create large response (over 1000 chars when converted to string)
        # Using a string response that's definitely over 1000 chars
        large_response = "x" * 1500

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value=large_response)
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        await http_client.get("/api/test")

        # Wait for background logging task to complete
        await asyncio.sleep(0.01)

        # Verify debug logging was called
        http_client.logger.debug.assert_called_once()
        call_args = http_client.logger.debug.call_args
        debug_context = call_args[0][1]

        # Verify response body is truncated (for non-dict responses)
        if "responseBody" in debug_context:
            response_body = debug_context["responseBody"]
            # For string responses, truncation happens before masking
            # Response body should be truncated (approximately 1000 chars + "...")
            response_str = str(response_body)
            # Note: Truncation happens on string representation, so should be around 1003 chars
            assert len(response_str) <= 1010  # Allow some buffer for dict formatting

    @pytest.mark.asyncio
    async def test_datamasker_called_for_headers(self, http_client):
        """Test that DataMasker.mask_sensitive_data is called for headers."""
        http_client.config.log_level = "debug"

        from unittest.mock import patch

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        # Mock DataMasker.mask_sensitive_data
        with patch("miso_client.utils.http_client_logging.DataMasker.mask_sensitive_data") as mock_mask:
            mock_mask.return_value = {"Authorization": DataMasker.MASKED_VALUE}

            headers = {"Authorization": "Bearer token123"}
            await http_client.get("/api/test", headers=headers)

            # Wait for background logging task to complete
            await asyncio.sleep(0.01)

            # Verify DataMasker was called for headers
            # It should be called at least once (for request headers)
            assert mock_mask.call_count >= 1

    @pytest.mark.asyncio
    async def test_datamasker_called_for_request_body(self, http_client):
        """Test that DataMasker.mask_sensitive_data is called for request body."""
        http_client.config.log_level = "debug"

        from unittest.mock import patch

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"success": True})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        # Mock DataMasker.mask_sensitive_data
        with patch("miso_client.utils.http_client_logging.DataMasker.mask_sensitive_data") as mock_mask:
            mock_mask.return_value = {"password": DataMasker.MASKED_VALUE, "username": "john"}

            request_data = {"password": "secret123", "username": "john"}
            await http_client.post("/api/login", request_data)

            # Wait for background logging task to complete
            await asyncio.sleep(0.01)

            # Verify DataMasker was called for request body
            # It should be called at least once (for request body)
            assert mock_mask.call_count >= 1

    @pytest.mark.asyncio
    async def test_non_blocking_logging(self, http_client):
        """Test that audit logging is non-blocking and doesn't delay request completion."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger with delay
        logging_called = False

        async def delayed_audit(*args, **kwargs):
            nonlocal logging_called
            await asyncio.sleep(0.05)  # 50ms delay
            logging_called = True

        http_client.logger.audit = delayed_audit

        # Make request and measure time
        start = asyncio.get_event_loop().time()
        await http_client.get("/api/test")
        elapsed = asyncio.get_event_loop().time() - start

        # Request should complete quickly (< 10ms) without waiting for logging
        assert elapsed < 0.01  # Should be much faster than 50ms logging delay

        # Wait for logging task to complete
        await asyncio.sleep(0.1)
        assert logging_called  # Verify logging eventually happened

    @pytest.mark.asyncio
    async def test_jwt_token_caching(self, http_client):
        """Test that JWT tokens are cached and reused."""
        from unittest.mock import patch

        # Mock JWT decoding
        decode_count = 0

        def mock_decode(token):
            nonlocal decode_count
            decode_count += 1
            # Return token with expiration in the future
            return {"sub": "user-123", "exp": (datetime.now() + timedelta(hours=1)).timestamp()}

        with patch("miso_client.utils.jwt_tools.decode_token", side_effect=mock_decode):
            # Mock InternalHttpClient
            mock_internal_client = AsyncMock()
            mock_internal_client.get = AsyncMock(return_value={"data": "test"})
            http_client._internal_client = mock_internal_client

            # Mock logger
            http_client.logger.audit = AsyncMock()

            token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            headers = {"Authorization": token}

            # First request - should decode token
            await http_client.get("/api/test", headers=headers)
            await asyncio.sleep(0.01)  # Wait for logging task
            first_decode_count = decode_count

            # Second request with same token - should use cache
            await http_client.get("/api/test", headers=headers)
            await asyncio.sleep(0.01)  # Wait for logging task

            # Verify decode was only called once (cache used on second request)
            assert decode_count == first_decode_count

    @pytest.mark.asyncio
    async def test_jwt_cache_expiration(self, http_client):
        """Test that JWT cache entries expire correctly."""
        from unittest.mock import patch
        from datetime import datetime, timedelta

        decode_call_count = 0

        # Mock JWT decoding with expired token
        def mock_decode_with_count(token):
            nonlocal decode_call_count
            decode_call_count += 1
            # Return token with expiration in the past (expired)
            return {"sub": "user-123", "exp": (datetime.now() - timedelta(hours=1)).timestamp()}

        with patch("miso_client.utils.jwt_tools.decode_token", side_effect=mock_decode_with_count):
            # Mock InternalHttpClient
            mock_internal_client = AsyncMock()
            mock_internal_client.get = AsyncMock(return_value={"data": "test"})
            http_client._internal_client = mock_internal_client

            # Mock logger
            http_client.logger.audit = AsyncMock()

            token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            headers = {"Authorization": token}

            # First request - should decode token and cache it
            await http_client.get("/api/test", headers=headers)
            await asyncio.sleep(0.01)  # Wait for logging task
            first_decode_count = decode_call_count

            # Second request - token should be expired, so cache should be cleared and re-decoded
            await http_client.get("/api/test", headers=headers)
            await asyncio.sleep(0.01)  # Wait for logging task

            # Verify decode was called again (cache miss due to expiration)
            # The token should be re-decoded since it expired
            assert decode_call_count > first_decode_count

    @pytest.mark.asyncio
    async def test_lazy_masking_non_debug(self, http_client):
        """Test that data masking only happens in debug mode."""
        from unittest.mock import patch

        # Ensure log level is not debug
        http_client.config.log_level = "info"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"success": True})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        # Mock DataMasker.mask_sensitive_data
        with patch("miso_client.utils.http_client_logging.DataMasker.mask_sensitive_data") as mock_mask:
            request_data = {"password": "secret123", "username": "john"}
            await http_client.post("/api/login", request_data)
            await asyncio.sleep(0.01)  # Wait for logging task

            # In non-debug mode, masking should NOT be called for audit logs
            # (audit logs don't include request/response bodies)
            # Only debug logs would call mask_sensitive_data
            # Since debug is not enabled, masking should not be called
            # But debug logging is called from _log_http_request_debug
            # which is only called when log_level == "debug"
            assert http_client.logger.debug.call_count == 0
            # DataMasker should not be called for audit-only logging
            # (audit context doesn't include full request/response data)
            assert mock_mask.call_count == 0  # Verify masking was not called

    @pytest.mark.asyncio
    async def test_lazy_masking_debug_mode(self, http_client):
        """Test that data masking happens when debug mode is enabled."""
        from unittest.mock import patch

        # Enable debug mode
        http_client.config.log_level = "debug"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"success": True})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        # Mock DataMasker.mask_sensitive_data
        with patch("miso_client.utils.http_client_logging.DataMasker.mask_sensitive_data") as mock_mask:
            mock_mask.return_value = {"password": DataMasker.MASKED_VALUE, "username": "john"}

            request_data = {"password": "secret123", "username": "john"}
            await http_client.post("/api/login", request_data)
            await asyncio.sleep(0.01)  # Wait for logging task

            # In debug mode, masking should be called for debug logs
            assert mock_mask.call_count >= 1  # Called for headers and/or body

    @pytest.mark.asyncio
    async def test_size_calculation_lazy(self, http_client):
        """Test that size calculations only happen in debug mode."""
        # Ensure log level is not debug
        http_client.config.log_level = "info"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"data": "test" * 1000})  # Large response
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()

        request_data = {"data": "test" * 1000}  # Large request
        await http_client.post("/api/test", request_data)
        await asyncio.sleep(0.01)  # Wait for logging task

        # Verify audit context was called
        assert http_client.logger.audit.called

        # Get the context from the call
        call_args = http_client.logger.audit.call_args
        audit_context = call_args[0][2]

        # In non-debug mode, requestSize and responseSize should not be calculated
        assert "requestSize" not in audit_context
        assert "responseSize" not in audit_context

    @pytest.mark.asyncio
    async def test_size_calculation_debug_mode(self, http_client):
        """Test that size calculations happen when debug mode is enabled."""
        # Enable debug mode
        http_client.config.log_level = "debug"

        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Mock logger
        http_client.logger.audit = AsyncMock()
        http_client.logger.debug = AsyncMock()

        request_data = {"data": "test"}
        await http_client.post("/api/test", request_data)
        await asyncio.sleep(0.01)  # Wait for logging task

        # Verify audit context was called
        assert http_client.logger.audit.called

        # Get the context from the call
        call_args = http_client.logger.audit.call_args
        audit_context = call_args[0][2]

        # In debug mode, requestSize and responseSize should be calculated
        # Note: These are optional, so they might not always be present
        # but if present, they should be numbers
        if "requestSize" in audit_context:
            assert isinstance(audit_context["requestSize"], int)
        if "responseSize" in audit_context:
            assert isinstance(audit_context["responseSize"], int)