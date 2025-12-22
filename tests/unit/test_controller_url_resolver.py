"""
Unit tests for controller URL resolver.
"""

import pytest

from miso_client.errors import ConfigurationError
from miso_client.models.config import MisoClientConfig
from miso_client.utils.controller_url_resolver import is_browser, resolve_controller_url


class TestControllerUrlResolver:
    """Test cases for controller URL resolver."""

    def test_is_browser_always_false(self):
        """Test is_browser always returns False for Python SDK."""
        assert is_browser() is False

    def test_resolve_controller_url_private_url(self):
        """Test resolution prefers controllerPrivateUrl."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            controllerPrivateUrl="https://controller-private.example.com",
            client_id="test",
            client_secret="secret",
        )
        url = resolve_controller_url(config)
        assert url == "https://controller-private.example.com"

    def test_resolve_controller_url_fallback_to_controller_url(self):
        """Test resolution falls back to controller_url when private URL not set."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test",
            client_secret="secret",
        )
        url = resolve_controller_url(config)
        assert url == "https://controller.example.com"

    def test_resolve_controller_url_no_url_configured(self):
        """Test error when no URL is configured."""
        config = MisoClientConfig(
            controller_url="",  # Empty string
            client_id="test",
            client_secret="secret",
        )
        with pytest.raises(ConfigurationError, match="No controller URL configured"):
            resolve_controller_url(config)

    def test_resolve_controller_url_invalid_url(self):
        """Test error when URL is invalid."""
        config = MisoClientConfig(
            controller_url="javascript:alert('xss')",
            client_id="test",
            client_secret="secret",
        )
        with pytest.raises(ConfigurationError, match="Invalid controller URL format"):
            resolve_controller_url(config)

    def test_resolve_controller_url_validates_url(self):
        """Test URL validation in resolver."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            client_id="test",
            client_secret="secret",
        )
        url = resolve_controller_url(config)
        assert url.startswith("https://")

    def test_resolve_controller_url_with_public_url(self):
        """Test public URL is available but not used in server environment."""
        config = MisoClientConfig(
            controller_url="https://controller.example.com",
            controllerPrivateUrl="https://controller-private.example.com",
            controllerPublicUrl="https://controller-public.example.com",
            client_id="test",
            client_secret="secret",
        )
        # Server environment should use private URL
        url = resolve_controller_url(config)
        assert url == "https://controller-private.example.com"
