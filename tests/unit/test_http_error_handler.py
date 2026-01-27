"""
Unit tests for HTTP error handler utilities.
"""

from unittest.mock import Mock

import httpx

from miso_client.utils.http_error_handler import (
    detect_auth_method_from_headers,
    extract_correlation_id_from_response,
    parse_error_response,
)


class TestDetectAuthMethodFromHeaders:
    """Test cases for detect_auth_method_from_headers function."""

    def test_detect_bearer_from_authorization_header(self):
        """Test detection of bearer auth from Authorization header."""
        headers = {"Authorization": "Bearer token123"}
        result = detect_auth_method_from_headers(headers)
        assert result == "bearer"

    def test_detect_bearer_from_lowercase_authorization_header(self):
        """Test detection of bearer auth from lowercase authorization header."""
        headers = {"authorization": "Bearer token123"}
        result = detect_auth_method_from_headers(headers)
        assert result == "bearer"

    def test_detect_client_token(self):
        """Test detection of client-token auth from x-client-token header."""
        headers = {"x-client-token": "token123"}
        result = detect_auth_method_from_headers(headers)
        assert result == "client-token"

    def test_detect_client_token_capitalized(self):
        """Test detection of client-token auth from X-Client-Token header."""
        headers = {"X-Client-Token": "token123"}
        result = detect_auth_method_from_headers(headers)
        assert result == "client-token"

    def test_detect_client_credentials(self):
        """Test detection of client-credentials auth from x-client-id header."""
        headers = {"x-client-id": "client123"}
        result = detect_auth_method_from_headers(headers)
        assert result == "client-credentials"

    def test_detect_client_credentials_capitalized(self):
        """Test detection of client-credentials auth from X-Client-Id header."""
        headers = {"X-Client-Id": "client123"}
        result = detect_auth_method_from_headers(headers)
        assert result == "client-credentials"

    def test_detect_api_key(self):
        """Test detection of api-key auth from x-api-key header."""
        headers = {"x-api-key": "key123"}
        result = detect_auth_method_from_headers(headers)
        assert result == "api-key"

    def test_detect_api_key_capitalized(self):
        """Test detection of api-key auth from X-Api-Key header."""
        headers = {"X-Api-Key": "key123"}
        result = detect_auth_method_from_headers(headers)
        assert result == "api-key"

    def test_returns_none_for_empty_headers(self):
        """Test returns None for empty headers dict."""
        headers: dict = {}
        result = detect_auth_method_from_headers(headers)
        assert result is None

    def test_returns_none_for_none_headers(self):
        """Test returns None for None headers."""
        result = detect_auth_method_from_headers(None)
        assert result is None

    def test_returns_none_for_no_auth_headers(self):
        """Test returns None when no auth headers present."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        result = detect_auth_method_from_headers(headers)
        assert result is None

    def test_priority_bearer_over_client_token(self):
        """Test bearer takes priority when both Authorization and x-client-token present."""
        headers = {
            "Authorization": "Bearer token123",
            "x-client-token": "client-token123",
        }
        result = detect_auth_method_from_headers(headers)
        assert result == "bearer"

    def test_priority_client_token_over_client_id(self):
        """Test client-token takes priority over client-credentials."""
        headers = {
            "x-client-token": "token123",
            "x-client-id": "client123",
        }
        result = detect_auth_method_from_headers(headers)
        assert result == "client-token"


class TestExtractCorrelationIdFromResponse:
    """Test cases for extract_correlation_id_from_response function."""

    def test_extract_from_x_correlation_id(self):
        """Test extraction from x-correlation-id header."""
        response = Mock(spec=httpx.Response)
        response.headers = {"x-correlation-id": "corr-123"}
        result = extract_correlation_id_from_response(response)
        assert result == "corr-123"

    def test_extract_from_x_request_id(self):
        """Test extraction from x-request-id header."""
        response = Mock(spec=httpx.Response)
        response.headers = {"x-request-id": "req-456"}
        result = extract_correlation_id_from_response(response)
        assert result == "req-456"

    def test_extract_from_correlation_id(self):
        """Test extraction from correlation-id header."""
        response = Mock(spec=httpx.Response)
        response.headers = {"correlation-id": "corr-789"}
        result = extract_correlation_id_from_response(response)
        assert result == "corr-789"

    def test_returns_none_for_none_response(self):
        """Test returns None for None response."""
        result = extract_correlation_id_from_response(None)
        assert result is None

    def test_returns_none_when_no_correlation_header(self):
        """Test returns None when no correlation headers present."""
        response = Mock(spec=httpx.Response)
        # Use a Mock for headers that returns None for any get() call
        mock_headers = Mock()
        mock_headers.get.return_value = None
        response.headers = mock_headers
        result = extract_correlation_id_from_response(response)
        assert result is None


class TestParseErrorResponse:
    """Test cases for parse_error_response function."""

    def test_parse_valid_error_response(self):
        """Test parsing a valid error response."""
        response = Mock(spec=httpx.Response)
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {
            "errors": ["Error message"],
            "type": "/Errors/BadRequest",
            "title": "Bad Request",
            "statusCode": 400,
        }
        result = parse_error_response(response, "/api/test")
        assert result is not None
        assert result.errors == ["Error message"]
        assert result.type == "/Errors/BadRequest"
        assert result.statusCode == 400
        assert result.instance == "/api/test"  # Filled from URL

    def test_parse_error_response_with_auth_method(self):
        """Test parsing error response that includes authMethod."""
        response = Mock(spec=httpx.Response)
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {
            "errors": ["Token expired"],
            "type": "/Errors/Unauthorized",
            "title": "Unauthorized",
            "statusCode": 401,
            "authMethod": "bearer",
        }
        result = parse_error_response(response, "/api/auth/validate")
        assert result is not None
        assert result.authMethod == "bearer"
        assert result.statusCode == 401

    def test_parse_error_response_preserves_instance(self):
        """Test that instance from response is preserved."""
        response = Mock(spec=httpx.Response)
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {
            "errors": ["Error"],
            "type": "/Errors/BadRequest",
            "title": "Bad Request",
            "statusCode": 400,
            "instance": "/api/original-endpoint",
        }
        result = parse_error_response(response, "/api/test")
        assert result is not None
        assert result.instance == "/api/original-endpoint"  # Preserved from response

    def test_parse_error_response_extracts_correlation_id(self):
        """Test that correlation ID is extracted from headers when not in body."""
        response = Mock(spec=httpx.Response)
        # Create a dict-like mock for headers
        headers_dict = {
            "content-type": "application/json",
            "x-correlation-id": "corr-123",
        }
        mock_headers = Mock()
        mock_headers.get.side_effect = lambda key, default="": headers_dict.get(key, default)
        mock_headers.__contains__ = lambda self, key: key in headers_dict
        response.headers = mock_headers
        response.json.return_value = {
            "errors": ["Error"],
            "type": "/Errors/BadRequest",
            "title": "Bad Request",
            "statusCode": 400,
        }
        result = parse_error_response(response, "/api/test")
        assert result is not None
        assert result.correlationId == "corr-123"

    def test_returns_none_for_non_json_response(self):
        """Test returns None for non-JSON response."""
        response = Mock(spec=httpx.Response)
        response.headers = {"content-type": "text/html"}
        result = parse_error_response(response, "/api/test")
        assert result is None

    def test_returns_none_for_invalid_structure(self):
        """Test returns None when JSON doesn't match ErrorResponse structure."""
        response = Mock(spec=httpx.Response)
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"message": "Just a message"}
        result = parse_error_response(response, "/api/test")
        assert result is None

    def test_returns_none_for_missing_required_fields(self):
        """Test returns None when required fields are missing."""
        response = Mock(spec=httpx.Response)
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {
            "errors": ["Error"],
            "type": "/Errors/BadRequest",
            # Missing title and statusCode
        }
        result = parse_error_response(response, "/api/test")
        assert result is None

    def test_returns_none_on_json_parse_error(self):
        """Test returns None when JSON parsing fails."""
        response = Mock(spec=httpx.Response)
        response.headers = {"content-type": "application/json"}
        response.json.side_effect = ValueError("Invalid JSON")
        result = parse_error_response(response, "/api/test")
        assert result is None


class TestIntegration:
    """Integration tests for error handler utilities."""

    def test_full_401_error_flow_with_auth_method(self):
        """Test complete flow of parsing 401 error with authMethod."""
        response = Mock(spec=httpx.Response)
        # Create a dict-like mock for headers
        headers_dict = {
            "content-type": "application/json",
            "x-correlation-id": "corr-401-test",
        }
        mock_headers = Mock()
        mock_headers.get.side_effect = lambda key, default="": headers_dict.get(key, default)
        mock_headers.__contains__ = lambda self, key: key in headers_dict
        response.headers = mock_headers
        response.json.return_value = {
            "errors": ["Bearer token has expired"],
            "type": "/Errors/Unauthorized",
            "title": "Unauthorized",
            "statusCode": 401,
            "authMethod": "bearer",
        }

        # Parse the error response
        error_response = parse_error_response(response, "/api/auth/validate")

        assert error_response is not None
        assert error_response.authMethod == "bearer"
        assert error_response.statusCode == 401
        assert error_response.correlationId == "corr-401-test"
        assert "Bearer token has expired" in error_response.errors

    def test_fallback_detection_when_no_auth_method_in_response(self):
        """Test fallback detection when controller doesn't return authMethod."""
        # Simulate request headers
        request_headers = {"Authorization": "Bearer invalid-token"}

        # Detect auth method from request headers (fallback)
        detected_method = detect_auth_method_from_headers(request_headers)

        assert detected_method == "bearer"
