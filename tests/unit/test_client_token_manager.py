"""Unit tests for client token manager internals."""

from unittest.mock import patch

from miso_client.models.config import MisoClientConfig
from miso_client.utils.client_token_manager import ClientTokenManager


def _build_config() -> MisoClientConfig:
    """Create a minimal config for token manager tests."""
    return MisoClientConfig(
        controller_url="https://controller.example.com",
        client_id="test-client",
        client_secret="test-secret",
    )


class TestClientTokenManager:
    """Focused tests for fallback behavior in token manager."""

    def test_expires_in_uses_default_when_decoded_payload_is_not_dict(self):
        """Return default TTL when decode_token returns unsupported payload type."""
        token_manager = ClientTokenManager(_build_config())

        with patch("miso_client.utils.client_token_manager.decode_token", return_value="invalid"):
            expires_in = token_manager._expires_in_from_token_claims("fake-token")

        assert expires_in == 1800
