"""
Unit tests for error types.
"""

from miso_client.errors import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConnectionError,
    MisoClientError,
)
from miso_client.models.error_response import ErrorResponse


class TestErrors:
    """Test cases for error types."""

    def test_miso_client_error(self):
        """Test base MisoClientError."""
        error = MisoClientError("Test error", status_code=400, error_body={"code": "ERR001"})

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.status_code == 400
        assert error.error_body == {"code": "ERR001"}

    def test_miso_client_error_minimal(self):
        """Test MisoClientError with minimal args."""
        error = MisoClientError("Simple error")

        assert str(error) == "Simple error"
        assert error.status_code is None
        assert error.error_body is None

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError("Auth failed", status_code=401)

        assert isinstance(error, MisoClientError)
        assert str(error) == "Auth failed"
        assert error.status_code == 401

    def test_authorization_error(self):
        """Test AuthorizationError."""
        error = AuthorizationError("Not authorized", status_code=403)

        assert isinstance(error, MisoClientError)
        assert str(error) == "Not authorized"
        assert error.status_code == 403

    def test_connection_error(self):
        """Test ConnectionError."""
        error = ConnectionError("Connection failed")

        assert isinstance(error, MisoClientError)
        assert str(error) == "Connection failed"

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Config invalid")

        assert isinstance(error, MisoClientError)
        assert str(error) == "Config invalid"

    def test_error_inheritance(self):
        """Test error inheritance hierarchy."""
        auth_error = AuthenticationError("test")
        authz_error = AuthorizationError("test")
        conn_error = ConnectionError("test")
        config_error = ConfigurationError("test")

        assert isinstance(auth_error, MisoClientError)
        assert isinstance(authz_error, MisoClientError)
        assert isinstance(conn_error, MisoClientError)
        assert isinstance(config_error, MisoClientError)

    def test_error_response_model(self):
        """Test ErrorResponse model parsing."""
        error_data = {
            "errors": ["Error message 1", "Error message 2"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "instance": "/OpenApi/rest/Xzy",
        }
        error_response = ErrorResponse(**error_data)

        assert error_response.errors == ["Error message 1", "Error message 2"]
        assert error_response.type == "/Errors/Bad Input"
        assert error_response.title == "Bad Request"
        assert error_response.statusCode == 400
        assert error_response.instance == "/OpenApi/rest/Xzy"

    def test_error_response_model_snake_case(self):
        """Test ErrorResponse model with camelCase field names."""
        error_data = {
            "errors": ["Error message"],
            "type": "/Errors/Validation",
            "title": "Validation Error",
            "statusCode": 422,
            "instance": "/api/endpoint",
        }
        error_response = ErrorResponse(**error_data)

        assert error_response.statusCode == 422
        assert error_response.instance == "/api/endpoint"

    def test_error_response_model_optional_instance(self):
        """Test ErrorResponse model without instance."""
        error_data = {
            "errors": ["Error message"],
            "type": "/Errors/Server Error",
            "title": "Internal Server Error",
            "statusCode": 500,
        }
        error_response = ErrorResponse(**error_data)

        assert error_response.instance is None

    def test_miso_client_error_with_error_response(self):
        """Test MisoClientError with structured error response."""
        error_response = ErrorResponse(
            errors=["The user has provided input that the browser is unable to convert."],
            type="/Errors/Bad Input",
            title="Bad Request",
            statusCode=400,
            instance="/OpenApi/rest/Xzy",
        )
        error = MisoClientError("Test error", error_response=error_response)

        assert error.error_response == error_response
        assert error.message == "The user has provided input that the browser is unable to convert."
        assert error.status_code == 400

    def test_miso_client_error_with_multiple_errors(self):
        """Test MisoClientError with multiple error messages."""
        error_response = ErrorResponse(
            errors=[
                "Error message 1",
                "Error message 2",
                "Error message 3",
            ],
            type="/Errors/Bad Input",
            title="Bad Request",
            statusCode=400,
        )
        error = MisoClientError("Test error", error_response=error_response)

        assert error.message == "Bad Request: Error message 1; Error message 2; Error message 3"
        assert error.status_code == 400

    def test_miso_client_error_backward_compatibility(self):
        """Test backward compatibility with existing error_body."""
        error = MisoClientError(
            "Test error",
            status_code=400,
            error_body={"code": "ERR001", "message": "Test"},
        )

        assert error.error_body == {"code": "ERR001", "message": "Test"}
        assert error.error_response is None
        assert error.status_code == 400

    def test_miso_client_error_with_both_error_body_and_response(self):
        """Test MisoClientError with both error_body and error_response (error_response takes precedence)."""
        error_response = ErrorResponse(
            errors=["Structured error"],
            type="/Errors/Bad Input",
            title="Bad Request",
            statusCode=400,
        )
        error = MisoClientError(
            "Test error",
            status_code=500,
            error_body={"code": "ERR001"},
            error_response=error_response,
        )

        assert error.error_response == error_response
        assert error.error_body == {"code": "ERR001"}
        assert error.message == "Structured error"  # Message from error_response
        assert error.status_code == 400  # Status code from error_response
