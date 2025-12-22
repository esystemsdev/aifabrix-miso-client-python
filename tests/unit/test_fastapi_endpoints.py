"""
Unit tests for FastAPI endpoint utilities.
"""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miso_client.errors import AuthenticationError
from miso_client.models.config import (
    ClientTokenEndpointOptions,
    MisoClientConfig,
)
from miso_client.utils.fastapi_endpoints import create_fastapi_client_token_endpoint


class MockHTTPException(Exception):
    """Mock HTTPException for testing."""

    def __init__(self, status_code: int, detail: dict):
        """Initialize mock HTTPException."""
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code} {detail.get('error', 'Error')}")


class TestFastApiEndpoints:
    """Test cases for FastAPI endpoint utilities."""

    @pytest.mark.asyncio
    async def test_create_fastapi_endpoint_success(self):
        """Test FastAPI endpoint returns token and config."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            controllerPublicUrl="https://controller-public.example.com",
            client_id="test-client",
            client_secret="secret",
        )

        mock_client = MagicMock()
        mock_client.is_initialized = MagicMock(return_value=True)
        mock_client.config = config

        # Mock get_environment_token
        with patch(
            "miso_client.utils.fastapi_endpoints.get_environment_token",
            new_callable=AsyncMock,
            return_value="test-token-123",
        ):
            # Mock FastAPI request
            mock_request = MagicMock()
            mock_request.headers = {"origin": "http://localhost:3000"}
            mock_request.base_url = "http://localhost:8000/"

            handler = create_fastapi_client_token_endpoint(mock_client)
            response = await handler(mock_request)

            assert response.token == "test-token-123"
            assert response.expiresIn == 1800
            assert response.config is not None
            assert response.config.baseUrl == "http://localhost:8000"
            assert response.config.controllerUrl == "https://controller-public.example.com"
            assert response.config.controllerPublicUrl == "https://controller-public.example.com"
            assert response.config.clientId == "test-client"
            assert response.config.clientTokenUri == "/api/v1/auth/client-token"

    # TODO: Fix FastAPI import mocking - Python's import system doesn't recognize
    # mocked modules when imports happen inside handler functions at runtime
    # @pytest.mark.asyncio
    # async def test_create_fastapi_endpoint_not_initialized(self):
    #     """Test FastAPI endpoint raises 503 when client not initialized."""
    #     mock_client = MagicMock()
    #     mock_client.is_initialized = MagicMock(return_value=False)
    #
    #     mock_request = MagicMock()
    #
    #     # Mock FastAPI HTTPException import at the point of use
    #     # Patch the import inside the handler function
    #     with patch.dict("sys.modules", {"fastapi": ModuleType("fastapi")}):
    #         mock_fastapi = sys.modules["fastapi"]
    #         mock_fastapi.HTTPException = MockHTTPException
    #
    #         handler = create_fastapi_client_token_endpoint(mock_client)
    #
    #         with pytest.raises(MockHTTPException) as exc_info:
    #             await handler(mock_request)
    #
    #         # Should raise HTTPException with 503 status
    #         assert exc_info.value.status_code == 503
    #         assert "Service Unavailable" in str(exc_info.value.detail.get("error", ""))

    @pytest.mark.asyncio
    async def test_create_fastapi_endpoint_origin_validation_failed(self):
        """Test FastAPI endpoint raises 403 on origin validation failure."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="secret",
            allowedOrigins=["http://localhost:3000"],
        )

        mock_client = MagicMock()
        mock_client.is_initialized = MagicMock(return_value=True)
        mock_client.config = config

        # Mock FastAPI module - use ModuleType so imports work correctly
        mock_fastapi = ModuleType("fastapi")
        mock_fastapi.HTTPException = MockHTTPException
        fastapi_original = sys.modules.get("fastapi")
        sys.modules["fastapi"] = mock_fastapi

        try:
            # Mock get_environment_token to raise AuthenticationError
            with patch(
                "miso_client.utils.fastapi_endpoints.get_environment_token",
                new_callable=AsyncMock,
                side_effect=AuthenticationError("Origin validation failed: Invalid origin"),
            ):
                mock_request = MagicMock()
                mock_request.headers = {"origin": "http://evil.com"}

                handler = create_fastapi_client_token_endpoint(mock_client)

                with pytest.raises(MockHTTPException) as exc_info:
                    await handler(mock_request)

                # Should raise HTTPException with 403 status
                assert exc_info.value.status_code == 403
                assert "Forbidden" in str(exc_info.value.detail.get("error", ""))
        finally:
            if fastapi_original:
                sys.modules["fastapi"] = fastapi_original
            elif "fastapi" in sys.modules:
                del sys.modules["fastapi"]

    @pytest.mark.asyncio
    async def test_create_fastapi_endpoint_custom_options(self):
        """Test FastAPI endpoint with custom options."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="secret",
        )

        mock_client = MagicMock()
        mock_client.is_initialized = MagicMock(return_value=True)
        mock_client.config = config

        options = ClientTokenEndpointOptions(
            clientTokenUri="/api/custom/token",
            expiresIn=3600,
            includeConfig=False,
        )

        with patch(
            "miso_client.utils.fastapi_endpoints.get_environment_token",
            new_callable=AsyncMock,
            return_value="test-token",
        ):
            mock_request = MagicMock()
            mock_request.headers = {}

            handler = create_fastapi_client_token_endpoint(mock_client, options)
            response = await handler(mock_request)

            assert response.token == "test-token"
            assert response.expiresIn == 3600
            assert response.config is None

    @pytest.mark.asyncio
    async def test_create_fastapi_endpoint_no_controller_url(self):
        """Test FastAPI endpoint raises 500 when controller URL not configured."""
        config = MisoClientConfig(
            controller_url="",  # Empty
            client_id="test-client",
            client_secret="secret",
        )

        mock_client = MagicMock()
        mock_client.is_initialized = MagicMock(return_value=True)
        mock_client.config = config

        # Mock FastAPI module - use ModuleType so imports work correctly
        mock_fastapi = ModuleType("fastapi")
        mock_fastapi.HTTPException = MockHTTPException
        fastapi_original = sys.modules.get("fastapi")
        sys.modules["fastapi"] = mock_fastapi

        try:
            with patch(
                "miso_client.utils.fastapi_endpoints.get_environment_token",
                new_callable=AsyncMock,
                return_value="test-token",
            ):
                mock_request = MagicMock()
                mock_request.headers = {}
                mock_request.base_url = "http://localhost:8000/"

                handler = create_fastapi_client_token_endpoint(mock_client)

                with pytest.raises(MockHTTPException) as exc_info:
                    await handler(mock_request)

                # Should raise HTTPException with 500 status
                assert exc_info.value.status_code == 500
                assert "Internal Server Error" in str(exc_info.value.detail.get("error", ""))
        finally:
            if fastapi_original:
                sys.modules["fastapi"] = fastapi_original
            elif "fastapi" in sys.modules:
                del sys.modules["fastapi"]
