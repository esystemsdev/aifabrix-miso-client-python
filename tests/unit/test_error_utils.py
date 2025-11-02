"""
Unit tests for error utilities.

This module contains comprehensive tests for error utilities including
transform_error_to_snake_case and handle_api_error_snake_case.
"""

from miso_client.errors import MisoClientError
from miso_client.models.error_response import ErrorResponse
from miso_client.utils.error_utils import handle_api_error_snake_case, transform_error_to_snake_case


class TestTransformErrorToSnakeCase:
    """Test cases for transform_error_to_snake_case function."""

    def test_transform_snake_case_error(self):
        """Test transforming camelCase error data."""
        error_data = {
            "errors": ["Validation failed"],
            "type": "/Errors/Validation",
            "title": "Validation Error",
            "statusCode": 422,
            "instance": "/api/endpoint",
        }
        error_response = transform_error_to_snake_case(error_data)

        assert isinstance(error_response, ErrorResponse)
        assert error_response.errors == ["Validation failed"]
        assert error_response.type == "/Errors/Validation"
        assert error_response.title == "Validation Error"
        assert error_response.statusCode == 422
        assert error_response.instance == "/api/endpoint"

    def test_transform_camel_case_error(self):
        """Test transforming camelCase error data."""
        error_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "instance": "/api/endpoint",
        }
        error_response = transform_error_to_snake_case(error_data)

        assert isinstance(error_response, ErrorResponse)
        assert error_response.statusCode == 400

    def test_transform_mixed_case_error(self):
        """Test transforming camelCase error data."""
        error_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "instance": "/api/endpoint",
            "correlationId": "req-123",
        }
        error_response = transform_error_to_snake_case(error_data)

        assert isinstance(error_response, ErrorResponse)
        assert error_response.statusCode == 400
        assert error_response.correlationId == "req-123"

    def test_transform_error_multiple_errors(self):
        """Test transforming error with multiple error messages."""
        error_data = {
            "errors": ["Error 1", "Error 2", "Error 3"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }
        error_response = transform_error_to_snake_case(error_data)

        assert len(error_response.errors) == 3
        assert error_response.errors == ["Error 1", "Error 2", "Error 3"]

    def test_transform_error_without_instance(self):
        """Test transforming error without instance field."""
        error_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }
        error_response = transform_error_to_snake_case(error_data)

        assert error_response.instance is None

    def test_transform_error_with_request_key(self):
        """Test transforming error with correlationId field."""
        error_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "correlationId": "req-123",
        }
        error_response = transform_error_to_snake_case(error_data)

        assert error_response.correlationId == "req-123"


class TestHandleApiErrorSnakeCase:
    """Test cases for handle_api_error_snake_case function."""

    def test_handle_error_snake_case(self):
        """Test handling error with camelCase format."""
        response_data = {
            "errors": ["Validation failed"],
            "type": "/Errors/Validation",
            "title": "Validation Error",
            "statusCode": 422,
        }
        error = handle_api_error_snake_case(response_data, 422, "/api/endpoint")

        assert isinstance(error, MisoClientError)
        assert error.status_code == 422
        assert error.error_response is not None
        assert error.error_response.statusCode == 422
        assert error.error_response.errors == ["Validation failed"]
        assert error.message == "Validation failed"  # Single error uses first message

    def test_handle_error_camel_case(self):
        """Test handling error with camelCase format."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }
        error = handle_api_error_snake_case(response_data, 400)

        assert isinstance(error, MisoClientError)
        assert error.status_code == 400
        assert error.error_response.statusCode == 400

    def test_handle_error_with_instance(self):
        """Test handling error with instance parameter."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }
        error = handle_api_error_snake_case(response_data, 400, "/api/custom/endpoint")

        assert error.error_response.instance == "/api/custom/endpoint"

    def test_handle_error_instance_in_data(self):
        """Test handling error when instance is already in data."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "instance": "/api/original/endpoint",
        }
        error = handle_api_error_snake_case(response_data, 400, "/api/new/endpoint")

        # Instance parameter should override data instance
        assert error.error_response.instance == "/api/new/endpoint"

    def test_handle_error_multiple_errors(self):
        """Test handling error with multiple error messages."""
        response_data = {
            "errors": ["Error 1", "Error 2", "Error 3"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }
        error = handle_api_error_snake_case(response_data, 400)

        assert isinstance(error, MisoClientError)
        assert len(error.error_response.errors) == 3
        assert "Bad Request: Error 1; Error 2; Error 3" in error.message

    def test_handle_error_no_status_code_in_data(self):
        """Test handling error when status_code is not in data."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
        }
        error = handle_api_error_snake_case(response_data, 500)

        assert error.status_code == 500
        assert error.error_response.statusCode == 500

    def test_handle_error_status_code_override(self):
        """Test that parameter status_code overrides data status_code."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }
        error = handle_api_error_snake_case(response_data, 500)

        assert error.status_code == 500
        assert error.error_response.statusCode == 500

    def test_handle_error_empty_errors_list(self):
        """Test handling error with empty errors list."""
        response_data = {
            "errors": [],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }
        error = handle_api_error_snake_case(response_data, 400)

        assert isinstance(error, MisoClientError)
        assert error.message == "Bad Request"  # Uses title when no errors

    def test_handle_error_no_title(self):
        """Test handling error without title (should still work)."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "statusCode": 400,
        }
        error = handle_api_error_snake_case(response_data, 400)

        assert isinstance(error, MisoClientError)
        assert error.error_response.errors == ["Error message"]

    def test_handle_error_with_request_key(self):
        """Test handling error with correlationId field."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "correlationId": "req-123",
        }
        error = handle_api_error_snake_case(response_data, 400)

        assert error.error_response.correlationId == "req-123"
