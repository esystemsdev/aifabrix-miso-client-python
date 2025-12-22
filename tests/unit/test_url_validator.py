"""
Unit tests for URL validator.
"""

from miso_client.utils.url_validator import validate_url


class TestUrlValidator:
    """Test cases for URL validator."""

    def test_validate_url_valid_http(self):
        """Test valid HTTP URL."""
        assert validate_url("http://example.com") is True

    def test_validate_url_valid_https(self):
        """Test valid HTTPS URL."""
        assert validate_url("https://example.com") is True

    def test_validate_url_with_port(self):
        """Test URL with port."""
        assert validate_url("http://localhost:3000") is True
        assert validate_url("https://example.com:8080") is True

    def test_validate_url_with_path(self):
        """Test URL with path."""
        assert validate_url("https://example.com/api/v1") is True

    def test_validate_url_javascript_protocol(self):
        """Test dangerous javascript: protocol."""
        assert validate_url("javascript:alert('xss')") is False

    def test_validate_url_data_protocol(self):
        """Test dangerous data: protocol."""
        assert validate_url("data:text/html,<script>alert('xss')</script>") is False

    def test_validate_url_file_protocol(self):
        """Test dangerous file: protocol."""
        assert validate_url("file:///etc/passwd") is False

    def test_validate_url_empty_string(self):
        """Test empty string."""
        assert validate_url("") is False

    def test_validate_url_none(self):
        """Test None value."""
        assert validate_url(None) is False  # type: ignore

    def test_validate_url_no_protocol(self):
        """Test URL without protocol."""
        assert validate_url("example.com") is False

    def test_validate_url_invalid_format(self):
        """Test invalid URL format."""
        assert validate_url("not a url") is False

    def test_validate_url_no_hostname(self):
        """Test URL without hostname."""
        assert validate_url("http://") is False

    def test_validate_url_controller_url(self):
        """Test controller URL format."""
        assert validate_url("https://controller.example.com") is True
        assert validate_url("http://controller.example.com/api/v1") is True
