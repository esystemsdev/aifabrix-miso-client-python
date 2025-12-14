"""
Unit tests for environment token wrapper.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.errors import AuthenticationError
from miso_client.models.config import MisoClientConfig
from miso_client.utils.environment_token import get_environment_token


class TestEnvironmentToken:
    """Test cases for environment token wrapper."""

    @pytest.mark.asyncio
    async def test_get_environment_token_valid_origin(self):
        """Test getting environment token with valid origin."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="test-secret",
            allowedOrigins=["http://localhost:*"],
        )

        mock_client = MagicMock()
        mock_client.config = config
        mock_client.auth = MagicMock()
        mock_client.auth.get_environment_token = AsyncMock(return_value="test-token")
        mock_client.logger = MagicMock()
        mock_client.logger.error = AsyncMock()
        mock_client.logger.audit = AsyncMock()

        headers = {"origin": "http://localhost:3000"}

        token = await get_environment_token(mock_client, headers)

        assert token == "test-token"
        mock_client.auth.get_environment_token.assert_called_once()
        mock_client.logger.audit.assert_called()

    @pytest.mark.asyncio
    async def test_get_environment_token_invalid_origin(self):
        """Test getting environment token with invalid origin."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="test-secret",
            allowedOrigins=["http://localhost:*"],
        )

        mock_client = MagicMock()
        mock_client.config = config
        mock_client.auth = MagicMock()
        mock_client.logger = MagicMock()
        mock_client.logger.error = AsyncMock()
        mock_client.logger.audit = AsyncMock()

        headers = {"origin": "http://evil.com:3000"}

        with pytest.raises(AuthenticationError, match="Origin validation failed"):
            await get_environment_token(mock_client, headers)

        mock_client.auth.get_environment_token.assert_not_called()
        mock_client.logger.error.assert_called()
        mock_client.logger.audit.assert_called()

    @pytest.mark.asyncio
    async def test_get_environment_token_no_allowed_origins(self):
        """Test getting environment token when no allowed origins configured."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="test-secret",
            allowedOrigins=None,
        )

        mock_client = MagicMock()
        mock_client.config = config
        mock_client.auth = MagicMock()
        mock_client.auth.get_environment_token = AsyncMock(return_value="test-token")
        mock_client.logger = MagicMock()
        mock_client.logger.error = AsyncMock()
        mock_client.logger.audit = AsyncMock()

        headers = {"origin": "http://any-origin.com"}

        token = await get_environment_token(mock_client, headers)

        assert token == "test-token"
        mock_client.auth.get_environment_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_environment_token_empty_allowed_origins(self):
        """Test getting environment token when allowed origins is empty list."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="test-secret",
            allowedOrigins=[],
        )

        mock_client = MagicMock()
        mock_client.config = config
        mock_client.auth = MagicMock()
        mock_client.auth.get_environment_token = AsyncMock(return_value="test-token")
        mock_client.logger = MagicMock()
        mock_client.logger.error = AsyncMock()
        mock_client.logger.audit = AsyncMock()

        headers = {"origin": "http://any-origin.com"}

        token = await get_environment_token(mock_client, headers)

        assert token == "test-token"
        mock_client.auth.get_environment_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_environment_token_controller_failure(self):
        """Test getting environment token when controller call fails."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="test-secret",
            allowedOrigins=["http://localhost:*"],
        )

        mock_client = MagicMock()
        mock_client.config = config
        mock_client.auth = MagicMock()
        mock_client.auth.get_environment_token = AsyncMock(
            side_effect=Exception("Controller error")
        )
        mock_client.logger = MagicMock()
        mock_client.logger.error = AsyncMock()
        mock_client.logger.audit = AsyncMock()

        headers = {"origin": "http://localhost:3000"}

        with pytest.raises(AuthenticationError, match="Failed to get environment token"):
            await get_environment_token(mock_client, headers)

        mock_client.logger.error.assert_called()
        mock_client.logger.audit.assert_called()

    @pytest.mark.asyncio
    async def test_get_environment_token_with_custom_uri(self):
        """Test getting environment token with custom client token URI."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="test-secret",
            allowedOrigins=["http://localhost:*"],
            clientTokenUri="/api/v1/auth/custom-token",
        )

        mock_client = MagicMock()
        mock_client.config = config
        mock_client.auth = MagicMock()
        mock_client.auth.get_environment_token = AsyncMock(return_value="test-token")
        mock_client.logger = MagicMock()
        mock_client.logger.error = AsyncMock()
        mock_client.logger.audit = AsyncMock()

        headers = {"origin": "http://localhost:3000"}

        token = await get_environment_token(mock_client, headers)

        assert token == "test-token"
        # Verify audit log uses custom URI
        audit_calls = [call for call in mock_client.logger.audit.call_args_list]
        assert any("/api/v1/auth/custom-token" in str(call) for call in audit_calls)

    @pytest.mark.asyncio
    async def test_get_environment_token_audit_logging(self):
        """Test that audit logging is called with masked credentials."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test-client",
            client_secret="test-secret",
            allowedOrigins=["http://localhost:*"],
        )

        mock_client = MagicMock()
        mock_client.config = config
        mock_client.auth = MagicMock()
        mock_client.auth.get_environment_token = AsyncMock(return_value="test-token")
        mock_client.logger = MagicMock()
        mock_client.logger.error = AsyncMock()
        mock_client.logger.audit = AsyncMock()

        headers = {"origin": "http://localhost:3000"}

        await get_environment_token(mock_client, headers)

        # Verify audit was called
        assert mock_client.logger.audit.call_count >= 1
        # Verify credentials are masked in audit context
        audit_calls = mock_client.logger.audit.call_args_list
        for call in audit_calls:
            if call[0] and len(call[0]) > 2:  # Check if context is provided
                context = call[0][2] if len(call[0]) > 2 else call[1].get("context", {})
                if isinstance(context, dict) and "clientSecret" in context:
                    assert context["clientSecret"] != "test-secret"
                    assert "***MASKED***" in str(context["clientSecret"])
