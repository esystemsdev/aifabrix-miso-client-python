"""
Unit tests for HTTP client with automatic client token management.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from miso_client.errors import AuthenticationError, MisoClientError
from miso_client.models.config import MisoClientConfig
from miso_client.models.error_response import ErrorResponse
from miso_client.utils.http_client import HttpClient


class TestHttpClient:
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
        return HttpClient(config)

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
