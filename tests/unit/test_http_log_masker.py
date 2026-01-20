"""
Unit tests for HTTP log masker utilities.
"""

from unittest.mock import MagicMock, patch

from miso_client.utils.data_masker import DataMasker
from miso_client.utils.http_log_masker import (
    estimate_object_size,
    extract_and_mask_query_params,
    mask_error_message,
    mask_request_data,
    mask_response_data,
    truncate_response_body,
)


class TestMaskErrorMessage:
    """Test cases for mask_error_message."""

    def test_mask_error_message_none(self):
        """Test mask_error_message with None error."""
        result = mask_error_message(None)
        assert result is None

    def test_mask_error_message_with_password(self):
        """Test mask_error_message with password in error."""
        error = Exception("Invalid password provided")
        result = mask_error_message(error)
        assert result == DataMasker.MASKED_VALUE

    def test_mask_error_message_with_token(self):
        """Test mask_error_message with token in error."""
        error = Exception("Token expired")
        result = mask_error_message(error)
        assert result == DataMasker.MASKED_VALUE

    def test_mask_error_message_with_secret(self):
        """Test mask_error_message with secret in error."""
        error = Exception("Secret key not found")
        result = mask_error_message(error)
        assert result == DataMasker.MASKED_VALUE

    def test_mask_error_message_with_key(self):
        """Test mask_error_message with key in error."""
        error = Exception("API key invalid")
        result = mask_error_message(error)
        assert result == DataMasker.MASKED_VALUE

    def test_mask_error_message_no_sensitive_data(self):
        """Test mask_error_message with no sensitive data."""
        error = Exception("Connection timeout")
        result = mask_error_message(error)
        assert result == "Connection timeout"

    def test_mask_error_message_case_insensitive(self):
        """Test mask_error_message is case insensitive."""
        error = Exception("PASSWORD is required")
        result = mask_error_message(error)
        assert result == DataMasker.MASKED_VALUE

    def test_mask_error_message_exception_during_str(self):
        """Test mask_error_message when str() raises exception."""
        error = MagicMock()
        error.__str__ = MagicMock(side_effect=Exception("Cannot convert to string"))
        result = mask_error_message(error)
        assert result is None


class TestMaskRequestData:
    """Test cases for mask_request_data."""

    def test_mask_request_data_with_headers_and_body(self):
        """Test mask_request_data with both headers and body."""
        headers = {"Authorization": "Bearer token123", "Content-Type": "application/json"}
        body = {"username": "user", "password": "secret123"}

        masked_headers, masked_body = mask_request_data(headers, body)

        assert masked_headers["Authorization"] == DataMasker.MASKED_VALUE
        assert masked_headers["Content-Type"] == "application/json"
        assert masked_body["username"] == "user"
        assert masked_body["password"] == DataMasker.MASKED_VALUE

    def test_mask_request_data_none_headers(self):
        """Test mask_request_data with None headers."""
        body = {"data": "value"}
        masked_headers, masked_body = mask_request_data(None, body)

        assert masked_headers is None
        assert masked_body["data"] == "value"

    def test_mask_request_data_none_body(self):
        """Test mask_request_data with None body."""
        headers = {"Authorization": "Bearer token123"}
        masked_headers, masked_body = mask_request_data(headers, None)

        assert masked_headers["Authorization"] == DataMasker.MASKED_VALUE
        assert masked_body is None

    def test_mask_request_data_both_none(self):
        """Test mask_request_data with both None."""
        masked_headers, masked_body = mask_request_data(None, None)

        assert masked_headers is None
        assert masked_body is None

    def test_mask_request_data_empty_dicts(self):
        """Test mask_request_data with empty dictionaries."""
        masked_headers, masked_body = mask_request_data({}, {})

        # Empty dict is falsy, so headers will be None
        assert masked_headers is None
        # Body is not None, so it will be processed (empty dict after masking)
        assert masked_body == {}


class TestExtractAndMaskQueryParams:
    """Test cases for extract_and_mask_query_params."""

    def test_extract_and_mask_query_params_with_params(self):
        """Test extract_and_mask_query_params with query parameters."""
        url = "https://example.com/api?username=john&password=secret123&token=abc123"
        result = extract_and_mask_query_params(url)

        assert result is not None
        assert result["username"] == "john"
        assert result["password"] == DataMasker.MASKED_VALUE
        assert result["token"] == DataMasker.MASKED_VALUE

    def test_extract_and_mask_query_params_no_query(self):
        """Test extract_and_mask_query_params with no query string."""
        url = "https://example.com/api"
        result = extract_and_mask_query_params(url)

        assert result is None

    def test_extract_and_mask_query_params_empty_query(self):
        """Test extract_and_mask_query_params with empty query string."""
        url = "https://example.com/api?"
        result = extract_and_mask_query_params(url)

        assert result is None

    def test_extract_and_mask_query_params_multiple_values(self):
        """Test extract_and_mask_query_params with multiple values."""
        url = "https://example.com/api?status=active&status=pending"
        result = extract_and_mask_query_params(url)

        assert result is not None
        assert isinstance(result["status"], list)
        assert len(result["status"]) == 2

    def test_extract_and_mask_query_params_invalid_url(self):
        """Test extract_and_mask_query_params with invalid URL."""
        url = "not a valid url://"
        result = extract_and_mask_query_params(url)

        assert result is None

    def test_extract_and_mask_query_params_exception(self):
        """Test extract_and_mask_query_params when exception occurs."""
        with patch(
            "miso_client.utils.http_log_masker.urlparse", side_effect=Exception("Parse error")
        ):
            url = "https://example.com/api?param=value"
            result = extract_and_mask_query_params(url)

            assert result is None


class TestEstimateObjectSize:
    """Test cases for estimate_object_size."""

    def test_estimate_object_size_none(self):
        """Test estimate_object_size with None."""
        result = estimate_object_size(None)
        assert result == 0

    def test_estimate_object_size_string(self):
        """Test estimate_object_size with string."""
        result = estimate_object_size("hello world")
        assert result == len("hello world".encode("utf-8"))

    def test_estimate_object_size_empty_string(self):
        """Test estimate_object_size with empty string."""
        result = estimate_object_size("")
        assert result == 0

    def test_estimate_object_size_int(self):
        """Test estimate_object_size with integer."""
        result = estimate_object_size(123)
        assert result == 10

    def test_estimate_object_size_float(self):
        """Test estimate_object_size with float."""
        result = estimate_object_size(3.14)
        assert result == 10

    def test_estimate_object_size_bool(self):
        """Test estimate_object_size with boolean."""
        result = estimate_object_size(True)
        assert result == 10

    def test_estimate_object_size_empty_list(self):
        """Test estimate_object_size with empty list."""
        result = estimate_object_size([])
        assert result == 10

    def test_estimate_object_size_list_with_items(self):
        """Test estimate_object_size with list containing items."""
        items = ["item1", "item2", "item3", "item4", "item5"]
        result = estimate_object_size(items)

        # Should sample first 3 items and estimate based on average
        assert result > 0
        assert isinstance(result, int)

    def test_estimate_object_size_list_single_item(self):
        """Test estimate_object_size with list containing single item."""
        items = ["single item"]
        result = estimate_object_size(items)

        assert result > 0
        assert isinstance(result, int)

    def test_estimate_object_size_list_less_than_three_items(self):
        """Test estimate_object_size with list containing less than 3 items."""
        items = ["item1", "item2"]
        result = estimate_object_size(items)

        assert result > 0
        assert isinstance(result, int)

    def test_estimate_object_size_dict(self):
        """Test estimate_object_size with dictionary."""
        data = {
            "key1": "value1",
            "key2": "value2",
            "key3": 123,
        }
        result = estimate_object_size(data)

        assert result > 0
        assert isinstance(result, int)

    def test_estimate_object_size_nested_dict(self):
        """Test estimate_object_size with nested dictionary."""
        data = {
            "outer": {
                "inner": "value",
                "number": 42,
            },
            "list": [1, 2, 3],
        }
        result = estimate_object_size(data)

        assert result > 0
        assert isinstance(result, int)


class TestTruncateResponseBody:
    """Test cases for truncate_response_body."""

    def test_truncate_response_body_none(self):
        """Test truncate_response_body with None."""
        body, was_truncated = truncate_response_body(None)
        assert body is None
        assert was_truncated is False

    def test_truncate_response_body_string_within_limit(self):
        """Test truncate_response_body with string within limit."""
        body = "short string"
        truncated, was_truncated = truncate_response_body(body, max_size=10000)

        assert truncated == body
        assert was_truncated is False

    def test_truncate_response_body_string_exceeds_limit(self):
        """Test truncate_response_body with string exceeding limit."""
        body = "x" * 20000
        truncated, was_truncated = truncate_response_body(body, max_size=10000)

        assert len(truncated) <= 10000 + len("...")
        assert truncated.endswith("...")
        assert was_truncated is True

    def test_truncate_response_body_string_exact_limit(self):
        """Test truncate_response_body with string at exact limit."""
        body = "x" * 10000
        truncated, was_truncated = truncate_response_body(body, max_size=10000)

        assert truncated == body
        assert was_truncated is False

    def test_truncate_response_body_dict_within_limit(self):
        """Test truncate_response_body with dict within limit."""
        body = {"key": "value", "number": 123}
        truncated, was_truncated = truncate_response_body(body, max_size=10000)

        assert truncated == body
        assert was_truncated is False

    def test_truncate_response_body_dict_exceeds_limit(self):
        """Test truncate_response_body with dict exceeding limit."""
        # Create a large dict that will exceed the limit
        body = {"key" + str(i): "value" * 1000 for i in range(100)}
        truncated, was_truncated = truncate_response_body(body, max_size=10000)

        assert isinstance(truncated, dict)
        assert "_message" in truncated
        assert "_estimatedSize" in truncated
        assert was_truncated is True

    def test_truncate_response_body_list_within_limit(self):
        """Test truncate_response_body with list within limit."""
        body = [1, 2, 3, 4, 5]
        truncated, was_truncated = truncate_response_body(body, max_size=10000)

        assert truncated == body
        assert was_truncated is False

    def test_truncate_response_body_list_exceeds_limit(self):
        """Test truncate_response_body with list exceeding limit."""
        # Create a large list that will exceed the limit
        body = ["item" * 1000 for _ in range(100)]
        truncated, was_truncated = truncate_response_body(body, max_size=10000)

        assert isinstance(truncated, dict)
        assert "_message" in truncated
        assert "_estimatedSize" in truncated
        assert was_truncated is True

    def test_truncate_response_body_unicode_string(self):
        """Test truncate_response_body with unicode string."""
        body = "测试" * 5000  # Chinese characters
        truncated, was_truncated = truncate_response_body(body, max_size=10000)

        # Should handle unicode properly
        assert isinstance(truncated, str)
        if was_truncated:
            assert truncated.endswith("...")


class TestMaskResponseData:
    """Test cases for mask_response_data."""

    def test_mask_response_data_none(self):
        """Test mask_response_data with None."""
        result = mask_response_data(None)
        assert result is None

    def test_mask_response_data_dict_within_limit(self):
        """Test mask_response_data with dict within size limit."""
        response = {"username": "john", "password": "secret123", "email": "john@example.com"}
        result = mask_response_data(response)

        assert result is not None
        assert isinstance(result, str)
        assert DataMasker.MASKED_VALUE in result

    def test_mask_response_data_dict_exceeds_masking_size(self):
        """Test mask_response_data with dict exceeding max_masking_size."""
        # Create a large dict that exceeds max_masking_size
        response = {"key" + str(i): "value" * 1000 for i in range(1000)}
        result = mask_response_data(response, max_masking_size=50000)

        assert result is not None
        assert isinstance(result, str)
        assert "too large" in result.lower()
        assert "masking skipped" in result.lower()

    def test_mask_response_data_string(self):
        """Test mask_response_data with string."""
        response = "Simple string response"
        result = mask_response_data(response)

        assert result == response

    def test_mask_response_data_truncated_dict(self):
        """Test mask_response_data with truncated dict."""
        # Create a dict that will be truncated
        response = {"key" + str(i): "value" * 100 for i in range(200)}
        result = mask_response_data(response, max_size=1000)

        assert result is not None
        assert isinstance(result, str)

    def test_mask_response_data_truncated_dict_long_result(self):
        """Test mask_response_data with truncated dict that produces long result string."""
        # Create a dict that will be truncated and produce a long string result
        response = {"key" + str(i): "value" * 50 for i in range(100)}
        result = mask_response_data(response, max_size=500)

        assert result is not None
        assert isinstance(result, str)
        # If result is too long, it should be truncated
        if len(result) > 1000:
            assert result.endswith("...")

    def test_mask_response_data_custom_max_size(self):
        """Test mask_response_data with custom max_size."""
        response = {"data": "value" * 1000}
        result = mask_response_data(response, max_size=5000)

        assert result is not None
        assert isinstance(result, str)

    def test_mask_response_data_custom_max_masking_size(self):
        """Test mask_response_data with custom max_masking_size."""
        response = {"key" + str(i): "value" * 100 for i in range(1000)}
        result = mask_response_data(response, max_masking_size=10000)

        assert result is not None
        assert isinstance(result, str)
        assert "too large" in result.lower()

    def test_mask_response_data_exception_during_masking(self):
        """Test mask_response_data when masking raises exception."""
        response = {"data": "value"}
        with patch(
            "miso_client.utils.http_log_masker.DataMasker.mask_sensitive_data",
            side_effect=Exception("Mask error"),
        ):
            result = mask_response_data(response)

            # Should return string representation of response
            assert result is not None
            assert isinstance(result, str)

    def test_mask_response_data_exception_during_processing(self):
        """Test mask_response_data when processing raises exception."""
        response = {"data": "value"}
        with patch(
            "miso_client.utils.http_log_masker.estimate_object_size",
            side_effect=Exception("Size error"),
        ):
            result = mask_response_data(response)

            assert result is None

    def test_mask_response_data_non_dict_non_string(self):
        """Test mask_response_data with non-dict, non-string type."""
        response = [1, 2, 3, 4, 5]
        result = mask_response_data(response)

        assert result is not None
        assert isinstance(result, str)
        assert "1" in result or "2" in result  # Should contain string representation

    def test_mask_response_data_empty_dict(self):
        """Test mask_response_data with empty dict."""
        response = {}
        result = mask_response_data(response)

        assert result is not None
        assert isinstance(result, str)

    def test_mask_response_data_empty_string(self):
        """Test mask_response_data with empty string."""
        response = ""
        result = mask_response_data(response)

        assert result == ""

    def test_mask_response_data_truncated_dict_long_string_result(self):
        """Test mask_response_data with truncated dict that produces long string result (>1000 chars)."""
        # Create a dict that will be truncated (estimated size > max_size but <= max_masking_size)
        large_dict = {"key" + str(i): "x" * 100 for i in range(20)}

        # Patch estimate_object_size to return a size that:
        # - Is > max_size (to force truncation, was_truncated=True)
        # - Is <= max_masking_size (to avoid early return)
        # Then patch DataMasker.mask_sensitive_data to return a dict that, when converted
        # to string, is > 1000 chars. This will trigger the truncation on line 193.
        with patch(
            "miso_client.utils.http_log_masker.estimate_object_size"
        ) as mock_estimate, patch(
            "miso_client.utils.http_log_masker.DataMasker.mask_sensitive_data"
        ) as mock_mask:
            # Return size that's > max_size (100) but <= max_masking_size (50000 default)
            # This will force truncation but not skip masking
            mock_estimate.return_value = 5000

            # Return a dict that will produce a string > 1000 chars when converted
            # The placeholder dict from truncate_response_body will be masked,
            # and we want the result to be > 1000 chars
            long_string_dict = {
                "_message": "Response body too large, truncated for performance",
                "_estimatedSize": 1234567890,
                "_extra": "x" * 950,
            }  # This will make the string > 1000 chars
            mock_mask.return_value = long_string_dict

            # Use a very small max_size to force truncation
            # max_masking_size defaults to 50000, so estimated_size (5000) < max_masking_size
            result = mask_response_data(large_dict, max_size=100)

            assert result is not None
            assert isinstance(result, str)
            # The result should be truncated to 1000 chars + "..." since it exceeds 1000
            assert result.endswith("...")
            assert len(result) == 1003  # 1000 + "..."
