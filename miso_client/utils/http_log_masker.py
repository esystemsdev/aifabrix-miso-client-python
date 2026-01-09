"""
HTTP log data masking utilities for ISO 27001 compliant logging.

This module provides data masking functions specifically for HTTP request/response
logging. All sensitive data is masked using DataMasker before logging.
"""

from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .data_masker import DataMasker


def mask_error_message(error: Exception) -> Optional[str]:
    """
    Mask sensitive data in error message.

    Args:
        error: Exception object

    Returns:
        Masked error message string, or None if no error
    """
    if error is None:
        return None

    try:
        error_message = str(error)
        # Mask if error message contains sensitive keywords
        if isinstance(error_message, str) and any(
            keyword in error_message.lower() for keyword in ["password", "token", "secret", "key"]
        ):
            return DataMasker.MASKED_VALUE
        return error_message
    except Exception:
        return None


def mask_request_data(
    request_headers: Optional[Dict[str, Any]], request_data: Optional[Dict[str, Any]]
) -> tuple[Optional[Dict[str, Any]], Optional[Any]]:
    """
    Mask sensitive data in request headers and body.

    Args:
        request_headers: Request headers dictionary
        request_data: Request body data

    Returns:
        Tuple of (masked_headers, masked_body)
    """
    masked_headers: Optional[Dict[str, Any]] = None
    if request_headers:
        masked_headers = DataMasker.mask_sensitive_data(request_headers)

    masked_body: Optional[Any] = None
    if request_data is not None:
        masked_body = DataMasker.mask_sensitive_data(request_data)

    return masked_headers, masked_body


def extract_and_mask_query_params(url: str) -> Optional[Dict[str, Any]]:
    """
    Extract query parameters from URL and mask sensitive data.

    Args:
        url: Request URL with query string

    Returns:
        Masked query parameters dictionary, or None if no query params
    """
    try:
        parsed_url = urlparse(url)
        if not parsed_url.query:
            return None

        query_dict = parse_qs(parsed_url.query)
        # Convert lists to single values for simplicity
        query_simple: Dict[str, Any] = {
            k: v[0] if len(v) == 1 else v for k, v in query_dict.items()
        }
        masked = DataMasker.mask_sensitive_data(query_simple)
        return masked if isinstance(masked, dict) else None
    except Exception:
        return None


def estimate_object_size(obj: Any) -> int:
    """
    Quick size estimation without full JSON serialization.

    Args:
        obj: Object to estimate size for

    Returns:
        Estimated size in bytes
    """
    if obj is None:
        return 0

    if isinstance(obj, str):
        return len(obj.encode("utf-8"))

    if not isinstance(obj, (dict, list)):
        return 10  # Estimate for primitives

    if isinstance(obj, list):
        if len(obj) == 0:
            return 10
        # Sample first few items for estimation
        sample_size = min(3, len(obj))
        estimated_item_size = sum(estimate_object_size(item) for item in obj[:sample_size])
        avg_item_size = estimated_item_size / sample_size if sample_size > 0 else 100
        return int(len(obj) * avg_item_size)

    # Object: estimate based on property count and values
    size = 0
    for key, value in obj.items():
        size += len(str(key).encode("utf-8")) + estimate_object_size(value)
    return size


def truncate_response_body(body: Any, max_size: int = 10000) -> tuple[Any, bool]:
    """
    Truncate response body to reduce processing cost.

    Args:
        body: Response body to truncate
        max_size: Maximum size in bytes

    Returns:
        Tuple of (truncated_data, was_truncated)
    """
    if body is None:
        return body, False

    # For strings, truncate directly
    if isinstance(body, str):
        body_bytes = body.encode("utf-8")
        if len(body_bytes) <= max_size:
            return body, False
        truncated = body_bytes[:max_size].decode("utf-8", errors="ignore") + "..."
        return truncated, True

    # For objects/arrays, estimate size first
    estimated_size = estimate_object_size(body)
    if estimated_size <= max_size:
        return body, False

    # If estimated size is too large, return placeholder
    return {
        "_message": "Response body too large, truncated for performance",
        "_estimatedSize": estimated_size,
    }, True


def mask_response_data(
    response: Optional[Any], max_size: Optional[int] = None, max_masking_size: Optional[int] = None
) -> Optional[str]:
    """
    Mask sensitive data in response body and limit size.

    Args:
        response: Response data
        max_size: Maximum size before truncation (default: 10000)
        max_masking_size: Maximum size before skipping masking (default: 50000)

    Returns:
        Masked response body as string, or None
    """
    if response is None:
        return None

    max_size = max_size or 10000
    max_masking_size = max_masking_size or 50000

    try:
        # Check if we should skip masking due to size
        estimated_size = estimate_object_size(response)
        if estimated_size > max_masking_size:
            return str({" _message": "Response body too large, masking skipped"})

        # Truncate if needed
        truncated_body, was_truncated = truncate_response_body(response, max_size)

        # Mask sensitive data
        try:
            if isinstance(truncated_body, dict):
                masked_dict = DataMasker.mask_sensitive_data(truncated_body)
                result = str(masked_dict)
                if was_truncated and len(result) > 1000:
                    result = result[:1000] + "..."
                return result
            elif isinstance(truncated_body, str):
                # Already truncated string
                return truncated_body
            else:
                return str(truncated_body)
        except Exception:
            return str(truncated_body) if was_truncated else str(response)
    except Exception:
        return None
