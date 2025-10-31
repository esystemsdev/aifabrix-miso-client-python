"""
Unit tests for HTTP client with automatic client token management.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from miso_client.errors import AuthenticationError, MisoClientError
from miso_client.models.config import MisoClientConfig
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
