"""
Unit tests for Flask endpoint utilities.
"""

import sys
from unittest.mock import MagicMock, patch

from miso_client.errors import AuthenticationError
from miso_client.models.config import (
    ClientTokenEndpointOptions,
    MisoClientConfig,
)
from miso_client.utils.flask_endpoints import create_flask_client_token_endpoint


class TestFlaskEndpoints:
    """Test cases for Flask endpoint utilities."""

    def test_create_flask_endpoint_success(self):
        """Test Flask endpoint returns token and config."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            controllerPublicUrl="https://controller-public.example.com",
            client_id="test-client",
            client_secret="secret",
        )

        mock_client = MagicMock()
        mock_client.is_initialized = MagicMock(return_value=True)
        mock_client.config = config

        # Mock Flask module
        mock_flask = MagicMock()
        mock_request = MagicMock()
        mock_request.headers = {"origin": "http://localhost:3000"}
        mock_request.scheme = "http"
        mock_request.host = "localhost:8000"
        mock_flask.request = mock_request
        flask_original = sys.modules.get("flask")
        sys.modules["flask"] = mock_flask

        try:
            # Mock asyncio.run to return the token directly
            with patch("miso_client.utils.flask_endpoints.asyncio.run") as mock_asyncio_run:
                mock_asyncio_run.return_value = "test-token-123"
                handler = create_flask_client_token_endpoint(mock_client)
                response, status_code = handler()
        finally:
            if flask_original:
                sys.modules["flask"] = flask_original
            elif "flask" in sys.modules:
                del sys.modules["flask"]

                assert status_code == 200
                assert response["token"] == "test-token-123"
                assert response["expiresIn"] == 1800
                assert response["config"]["baseUrl"] == "http://localhost:8000"
                assert (
                    response["config"]["controllerUrl"] == "https://controller-public.example.com"
                )
                assert (
                    response["config"]["controllerPublicUrl"]
                    == "https://controller-public.example.com"
                )
                assert response["config"]["clientId"] == "test-client"
                assert response["config"]["clientTokenUri"] == "/api/v1/auth/client-token"

    def test_create_flask_endpoint_not_initialized(self):
        """Test Flask endpoint returns 503 when client not initialized."""
        mock_client = MagicMock()
        mock_client.is_initialized = MagicMock(return_value=False)

        handler = create_flask_client_token_endpoint(mock_client)
        response, status_code = handler()

        assert status_code == 503
        assert response["error"] == "Service Unavailable"
        assert "not initialized" in response["message"]

    def test_create_flask_endpoint_origin_validation_failed(self):
        """Test Flask endpoint returns 403 on origin validation failure."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="secret",
            allowedOrigins=["http://localhost:3000"],
        )

        mock_client = MagicMock()
        mock_client.is_initialized = MagicMock(return_value=True)
        mock_client.config = config

        # Mock Flask module
        mock_flask = MagicMock()
        mock_request = MagicMock()
        mock_request.headers = {"origin": "http://evil.com"}
        mock_flask.request = mock_request
        flask_original = sys.modules.get("flask")
        sys.modules["flask"] = mock_flask

        try:
            # Mock asyncio.run to raise AuthenticationError
            with patch("miso_client.utils.flask_endpoints.asyncio.run") as mock_asyncio_run:
                mock_asyncio_run.side_effect = AuthenticationError(
                    "Origin validation failed: Invalid origin"
                )
                handler = create_flask_client_token_endpoint(mock_client)
                response, status_code = handler()
        finally:
            if flask_original:
                sys.modules["flask"] = flask_original
            elif "flask" in sys.modules:
                del sys.modules["flask"]

                assert status_code == 403
                assert response["error"] == "Forbidden"
                assert "Origin validation failed" in response["message"]

    def test_create_flask_endpoint_custom_options(self):
        """Test Flask endpoint with custom options."""
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

        # Mock Flask module
        mock_flask = MagicMock()
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_flask.request = mock_request
        flask_original = sys.modules.get("flask")
        sys.modules["flask"] = mock_flask

        try:
            with patch("miso_client.utils.flask_endpoints.asyncio.run") as mock_asyncio_run:
                mock_asyncio_run.return_value = "test-token"
                handler = create_flask_client_token_endpoint(mock_client, options)
                response, status_code = handler()
        finally:
            if flask_original:
                sys.modules["flask"] = flask_original
            elif "flask" in sys.modules:
                del sys.modules["flask"]

                assert status_code == 200
                assert response["token"] == "test-token"
                assert response["expiresIn"] == 3600
                assert "config" not in response

    def test_create_flask_endpoint_no_controller_url(self):
        """Test Flask endpoint returns 500 when controller URL not configured."""
        config = MisoClientConfig(
            controller_url="",  # Empty
            client_id="test-client",
            client_secret="secret",
        )

        mock_client = MagicMock()
        mock_client.is_initialized = MagicMock(return_value=True)
        mock_client.config = config

        # Mock Flask module
        mock_flask = MagicMock()
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.scheme = "http"
        mock_request.host = "localhost:8000"
        mock_flask.request = mock_request
        flask_original = sys.modules.get("flask")
        sys.modules["flask"] = mock_flask

        try:
            with patch("miso_client.utils.flask_endpoints.asyncio.run") as mock_asyncio_run:
                mock_asyncio_run.return_value = "test-token"
                handler = create_flask_client_token_endpoint(mock_client)
                response, status_code = handler()
        finally:
            if flask_original:
                sys.modules["flask"] = flask_original
            elif "flask" in sys.modules:
                del sys.modules["flask"]

                assert status_code == 500
                assert response["error"] == "Internal Server Error"
                assert "Controller URL not configured" in response["message"]
