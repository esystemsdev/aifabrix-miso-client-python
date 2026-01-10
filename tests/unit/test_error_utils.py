"""
Unit tests for error utilities.

This module contains comprehensive tests for error utilities including
transformError and handleApiError.
"""

import pytest

from miso_client.errors import MisoClientError
from miso_client.models.error_response import ErrorResponse
from miso_client.utils.error_utils import (
    ApiErrorException,
    extract_correlation_id_from_error,
    handleApiError,
    transformError,
)


class TestTransformError:
    """Test cases for transformError function."""

    def test_transform_camel_case_error(self):
        """Test transforming camelCase error data."""
        error_data = {
            "errors": ["Validation failed"],
            "type": "/Errors/Validation",
            "title": "Validation Error",
            "statusCode": 422,
            "instance": "/api/endpoint",
        }
        error_response = transformError(error_data)

        assert isinstance(error_response, ErrorResponse)
        assert error_response.errors == ["Validation failed"]
        assert error_response.type == "/Errors/Validation"
        assert error_response.title == "Validation Error"
        assert error_response.statusCode == 422
        assert error_response.instance == "/api/endpoint"

    def test_transform_error_without_optional_fields(self):
        """Test transformError without optional fields."""
        error_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }
        error_response = transformError(error_data)

        assert isinstance(error_response, ErrorResponse)
        assert error_response.statusCode == 400
        assert error_response.instance is None
        assert error_response.correlationId is None

    def test_transform_error_multiple_errors(self):
        """Test transforming error with multiple error messages."""
        error_data = {
            "errors": ["Error 1", "Error 2", "Error 3"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }
        error_response = transformError(error_data)

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
        error_response = transformError(error_data)

        assert error_response.instance is None

    def test_transform_error_with_correlation_id(self):
        """Test transforming error with correlationId field."""
        error_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "correlationId": "req-123",
        }
        error_response = transformError(error_data)

        assert error_response.correlationId == "req-123"


class TestApiErrorException:
    """Test cases for ApiErrorException class."""

    def test_api_error_exception_initialization(self):
        """Test ApiErrorException initialization."""
        error_response = ErrorResponse(
            errors=["Validation failed"],
            type="/Errors/Validation",
            title="Validation Error",
            statusCode=422,
            instance="/api/endpoint",
        )

        exception = ApiErrorException(error_response)

        assert str(exception) == "Validation Error"
        assert exception.name == "ApiErrorException"
        assert exception.statusCode == 422
        assert exception.type == "/Errors/Validation"
        assert exception.instance == "/api/endpoint"
        assert exception.errors == ["Validation failed"]

    def test_api_error_exception_without_title(self):
        """Test ApiErrorException without title."""
        error_response = ErrorResponse(
            errors=["Error message"],
            type="/Errors/Bad Input",
            title=None,
            statusCode=400,
        )

        exception = ApiErrorException(error_response)

        assert str(exception) == "API Error"  # Default title
        assert exception.statusCode == 400

    def test_api_error_exception_with_correlation_id(self):
        """Test ApiErrorException with correlationId."""
        error_response = ErrorResponse(
            errors=["Error message"],
            type="/Errors/Bad Input",
            title="Bad Request",
            statusCode=400,
            correlationId="req-123",
        )

        exception = ApiErrorException(error_response)

        assert exception.correlationId == "req-123"


class TestHandleApiError:
    """Test cases for handleApiError function."""

    def test_handle_api_error_raises_exception(self):
        """Test that handleApiError raises ApiErrorException."""
        response_data = {
            "errors": ["Validation failed"],
            "type": "/Errors/Validation",
            "title": "Validation Error",
            "statusCode": 422,
        }

        with pytest.raises(ApiErrorException) as exc_info:
            handleApiError(response_data, 422, "/api/endpoint")

        exception = exc_info.value
        assert exception.statusCode == 422
        assert exception.errors == ["Validation failed"]
        assert exception.instance == "/api/endpoint"

    def test_handle_api_error_with_instance_override(self):
        """Test handleApiError with instance parameter override."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "instance": "/api/original/endpoint",
        }

        with pytest.raises(ApiErrorException) as exc_info:
            handleApiError(response_data, 400, "/api/new/endpoint")

        exception = exc_info.value
        # Instance parameter should override data instance
        assert exception.instance == "/api/new/endpoint"

    def test_handle_api_error_with_status_code_override(self):
        """Test handleApiError with status_code parameter override."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }

        with pytest.raises(ApiErrorException) as exc_info:
            handleApiError(response_data, 500)

        exception = exc_info.value
        # Status code parameter should override data statusCode
        assert exception.statusCode == 500

    def test_handle_api_error_without_title(self):
        """Test handleApiError when title is missing."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "statusCode": 400,
        }

        with pytest.raises(ApiErrorException) as exc_info:
            handleApiError(response_data, 400)

        exception = exc_info.value
        # Title is set to None in ErrorResponse, and ApiErrorException uses error.title or "API Error"
        # Since title is None, it should use "API Error" as default
        assert str(exception) == "API Error"  # Default from ApiErrorException
        # The error response should have title as None
        # But ApiErrorException doesn't expose title directly, only through the error response

    def test_handle_api_error_without_instance(self):
        """Test handleApiError without instance in data or parameter."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }

        with pytest.raises(ApiErrorException) as exc_info:
            handleApiError(response_data, 400)

        exception = exc_info.value
        assert exception.instance is None

    def test_handle_api_error_with_correlation_id(self):
        """Test handleApiError with correlationId."""
        response_data = {
            "errors": ["Error message"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
            "correlationId": "req-123",
        }

        with pytest.raises(ApiErrorException) as exc_info:
            handleApiError(response_data, 400)

        exception = exc_info.value
        assert exception.correlationId == "req-123"

    def test_handle_api_error_multiple_errors(self):
        """Test handleApiError with multiple errors."""
        response_data = {
            "errors": ["Error 1", "Error 2", "Error 3"],
            "type": "/Errors/Bad Input",
            "title": "Bad Request",
            "statusCode": 400,
        }

        with pytest.raises(ApiErrorException) as exc_info:
            handleApiError(response_data, 400)

        exception = exc_info.value
        assert len(exception.errors) == 3
        assert exception.errors == ["Error 1", "Error 2", "Error 3"]


class TestExtractCorrelationIdFromError:
    """Test cases for extract_correlation_id_from_error function."""

    def test_extract_from_miso_client_error_with_correlation_id(self):
        """Test extracting correlation ID from MisoClientError with error_response."""
        error_response = ErrorResponse(
            errors=["Error message"],
            type="/Errors/Test",
            title="Test Error",
            statusCode=400,
            correlationId="req-123",
        )
        error = MisoClientError("Error", error_response=error_response)

        correlation_id = extract_correlation_id_from_error(error)

        assert correlation_id == "req-123"

    def test_extract_from_miso_client_error_without_correlation_id(self):
        """Test extracting correlation ID from MisoClientError without correlation ID."""
        error_response = ErrorResponse(
            errors=["Error message"],
            type="/Errors/Test",
            title="Test Error",
            statusCode=400,
        )
        error = MisoClientError("Error", error_response=error_response)

        correlation_id = extract_correlation_id_from_error(error)

        assert correlation_id is None

    def test_extract_from_miso_client_error_without_error_response(self):
        """Test extracting correlation ID from MisoClientError without error_response."""
        error = MisoClientError("Error")

        correlation_id = extract_correlation_id_from_error(error)

        assert correlation_id is None

    def test_extract_from_api_error_exception_with_correlation_id(self):
        """Test extracting correlation ID from ApiErrorException."""
        error_response = ErrorResponse(
            errors=["Error message"],
            type="/Errors/Test",
            title="Test Error",
            statusCode=400,
            correlationId="req-456",
        )
        error = ApiErrorException(error_response)

        correlation_id = extract_correlation_id_from_error(error)

        assert correlation_id == "req-456"

    def test_extract_from_api_error_exception_without_correlation_id(self):
        """Test extracting correlation ID from ApiErrorException without correlation ID."""
        error_response = ErrorResponse(
            errors=["Error message"],
            type="/Errors/Test",
            title="Test Error",
            statusCode=400,
        )
        error = ApiErrorException(error_response)

        correlation_id = extract_correlation_id_from_error(error)

        assert correlation_id is None

    def test_extract_from_generic_exception(self):
        """Test extracting correlation ID from generic exception."""
        error = ValueError("Generic error")

        correlation_id = extract_correlation_id_from_error(error)

        assert correlation_id is None
