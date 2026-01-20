"""
API response utilities for normalizing controller responses.

The controller may return responses in different formats:
- With success/timestamp: {"success": true, "data": {...}, "timestamp": "..."}
- Without success/timestamp: {"data": {...}}
- Foreign key fields as strings instead of objects: {"applicationId": "id"} vs {"applicationId": {"id": "id"}}

This module provides utilities to normalize responses before parsing.
"""

from datetime import datetime
from typing import Any, Dict, cast


def _normalize_foreign_key(value: Any) -> Any:
    """
    Normalize foreign key reference from string to ForeignKeyReference object.

    Args:
        value: Value that might be a string ID or already a ForeignKeyReference

    Returns:
        Normalized foreign key reference dict or original value
    """
    if isinstance(value, str):
        # Convert string ID to ForeignKeyReference format
        return {"id": value}
    if isinstance(value, dict):
        # Already an object, check if it has 'id' field
        if "id" in value:
            return value
        # If it's a dict without 'id', treat the whole dict as the reference
        return value
    return value


def _normalize_log_entry(entry: Any) -> Any:
    """
    Normalize a log entry to convert string IDs to ForeignKeyReference objects.

    Args:
        entry: Log entry dict

    Returns:
        Normalized log entry dict
    """
    if not isinstance(entry, dict):
        return entry

    # Normalize applicationId and userId if they are strings
    if "applicationId" in entry and isinstance(entry["applicationId"], str):
        entry["applicationId"] = _normalize_foreign_key(entry["applicationId"])
    if "userId" in entry and isinstance(entry["userId"], str):
        entry["userId"] = _normalize_foreign_key(entry["userId"])

    return entry


def normalize_api_response(response: Any) -> Dict[str, Any]:
    """
    Normalize API response to include success and timestamp if missing.
    Also normalizes foreign key references from strings to objects.

    The controller may return responses without success/timestamp fields.
    Foreign key fields (applicationId, userId) may be strings instead of objects.

    Args:
        response: Raw API response (dict or other)

    Returns:
        Normalized response dict with success and timestamp fields
    """
    if not isinstance(response, dict):
        return cast(Dict[str, Any], response)

    # Normalize data array if present (for list responses)
    if "data" in response and isinstance(response["data"], list):
        response["data"] = [_normalize_log_entry(entry) for entry in response["data"]]
    elif "data" in response and isinstance(response["data"], dict):
        # Single data object
        response["data"] = _normalize_log_entry(response["data"])

    # If response already has success and timestamp, use as-is
    if "success" not in response:
        response["success"] = True
    if "timestamp" not in response:
        response["timestamp"] = datetime.now().isoformat() + "Z"

    return response
