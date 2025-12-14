"""
Unit tests for origin validator.
"""

from miso_client.utils.origin_validator import validate_origin


class TestOriginValidator:
    """Test cases for origin validator."""

    def test_validate_origin_exact_match(self):
        """Test exact origin match."""
        headers = {"origin": "http://localhost:3000"}
        allowed = ["http://localhost:3000"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True
        assert result["error"] is None

    def test_validate_origin_case_insensitive(self):
        """Test case-insensitive origin matching."""
        headers = {"Origin": "HTTP://LOCALHOST:3000"}
        allowed = ["http://localhost:3000"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True
        assert result["error"] is None

    def test_validate_origin_wildcard_port(self):
        """Test wildcard port matching."""
        headers = {"origin": "http://localhost:3000"}
        allowed = ["http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True
        assert result["error"] is None

    def test_validate_origin_wildcard_port_different_port(self):
        """Test wildcard port matching with different port."""
        headers = {"origin": "http://localhost:8080"}
        allowed = ["http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True
        assert result["error"] is None

    def test_validate_origin_wildcard_port_https(self):
        """Test wildcard port matching with HTTPS."""
        headers = {"origin": "https://example.com:443"}
        allowed = ["https://example.com:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True
        assert result["error"] is None

    def test_validate_origin_multiple_allowed(self):
        """Test with multiple allowed origins."""
        headers = {"origin": "http://localhost:3000"}
        allowed = ["http://localhost:*", "https://example.com"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True
        assert result["error"] is None

    def test_validate_origin_not_in_list(self):
        """Test origin not in allowed list."""
        headers = {"origin": "http://evil.com:3000"}
        allowed = ["http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is False
        assert "not in allowed origins" in result["error"]

    def test_validate_origin_fallback_to_referer(self):
        """Test fallback to referer header when origin missing."""
        headers = {"referer": "http://localhost:3000/page"}
        allowed = ["http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True
        assert result["error"] is None

    def test_validate_origin_no_origin_or_referer(self):
        """Test when neither origin nor referer present."""
        headers = {}
        allowed = ["http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is False
        assert "No origin or referer header" in result["error"]

    def test_validate_origin_empty_allowed_list(self):
        """Test with empty allowed origins list (should allow all)."""
        headers = {"origin": "http://any-origin.com"}
        allowed = []

        result = validate_origin(headers, allowed)

        assert result["valid"] is True
        assert result["error"] is None

    def test_validate_origin_none_allowed(self):
        """Test with None allowed origins (should allow all for backward compatibility)."""
        headers = {"origin": "http://any-origin.com"}

        result = validate_origin(headers, None)

        assert result["valid"] is True
        assert result["error"] is None

    def test_validate_origin_dict_headers(self):
        """Test with dict headers."""
        headers = {"origin": "http://localhost:3000"}
        allowed = ["http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True

    def test_validate_origin_object_with_headers(self):
        """Test with object that has headers attribute."""

        class MockRequest:
            def __init__(self):
                self.headers = {"origin": "http://localhost:3000"}

        request = MockRequest()
        allowed = ["http://localhost:*"]

        result = validate_origin(request, allowed)

        assert result["valid"] is True

    def test_validate_origin_invalid_format(self):
        """Test with invalid origin format."""
        headers = {"origin": "not-a-valid-url"}
        allowed = ["http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is False
        assert "Invalid origin format" in result["error"]

    def test_validate_origin_scheme_mismatch(self):
        """Test scheme mismatch."""
        headers = {"origin": "http://localhost:3000"}
        allowed = ["https://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is False

    def test_validate_origin_host_mismatch(self):
        """Test host mismatch."""
        headers = {"origin": "http://localhost:3000"}
        allowed = ["http://example.com:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is False

    def test_validate_origin_referer_with_path(self):
        """Test referer header with path."""
        headers = {"referer": "http://localhost:3000/api/users?page=1"}
        allowed = ["http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True

    def test_validate_origin_referer_case_variations(self):
        """Test referer header with different case variations."""
        headers = {"Referer": "http://localhost:3000/page"}
        allowed = ["http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True

    def test_validate_origin_empty_string_allowed(self):
        """Test with empty string in allowed origins (should be skipped)."""
        headers = {"origin": "http://localhost:3000"}
        allowed = ["", "http://localhost:*"]

        result = validate_origin(headers, allowed)

        assert result["valid"] is True
