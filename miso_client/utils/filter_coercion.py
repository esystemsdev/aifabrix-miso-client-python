"""Filter value coercion functions.

This module provides functions for coercing filter values to appropriate types
based on field definitions, including string, number, boolean, uuid, timestamp, and enum types.
"""

import uuid
from datetime import datetime
from typing import Any, List, Optional, Tuple, Union

from ..models.filter_schema import FilterError

# Error type URIs following RFC 7807 pattern
ERROR_TYPE_INVALID_TYPE = "/Errors/FilterValidation/InvalidType"
ERROR_TYPE_INVALID_UUID = "/Errors/FilterValidation/InvalidUuid"
ERROR_TYPE_INVALID_DATE = "/Errors/FilterValidation/InvalidDate"
ERROR_TYPE_INVALID_ENUM = "/Errors/FilterValidation/InvalidEnum"


def _unknown_field_type_error(field_type: str) -> FilterError:
    """Build standard error payload for unknown field types."""
    return FilterError(
        type=ERROR_TYPE_INVALID_TYPE,
        title="Invalid Type",
        statusCode=400,
        errors=[f"Unknown field type: {field_type}"],
    )


def coerce_single_value(
    value: Any, field_type: str, enum_values: Optional[List[str]]
) -> Tuple[Any, Optional[FilterError]]:
    """Coerce a single value based on field type."""
    if field_type == "string":
        return str(value), None
    coercers = {
        "number": lambda: coerce_number(value),
        "boolean": lambda: coerce_boolean(value),
        "uuid": lambda: coerce_uuid(value),
        "timestamp": lambda: coerce_timestamp(value),
        "enum": lambda: coerce_enum(value, enum_values),
    }
    coercer = coercers.get(field_type)
    if coercer is None:
        return value, _unknown_field_type_error(field_type)
    return coercer()


def coerce_number(value: Any) -> Tuple[Optional[Union[int, float]], Optional[FilterError]]:
    """Coerce value to number (int or float)."""
    if isinstance(value, (int, float)):
        return value, None

    if isinstance(value, str):
        try:
            if "." in value:
                return float(value), None
            return int(value), None
        except ValueError:
            return None, FilterError(
                type=ERROR_TYPE_INVALID_TYPE,
                title="Invalid Number",
                statusCode=400,
                errors=[f"Value '{value}' cannot be converted to a number"],
            )

    return None, FilterError(
        type=ERROR_TYPE_INVALID_TYPE,
        title="Invalid Number",
        statusCode=400,
        errors=[f"Value '{value}' is not a valid number"],
    )


def coerce_boolean(value: Any) -> Tuple[Optional[bool], Optional[FilterError]]:
    """Coerce value to boolean."""
    if isinstance(value, bool):
        return value, None

    if isinstance(value, str):
        lower_value = value.lower()
        if lower_value in ("true", "1", "yes"):
            return True, None
        if lower_value in ("false", "0", "no"):
            return False, None

    return None, FilterError(
        type=ERROR_TYPE_INVALID_TYPE,
        title="Invalid Boolean",
        statusCode=400,
        errors=[f"Value '{value}' cannot be converted to a boolean"],
    )


def coerce_uuid(value: Any) -> Tuple[Optional[str], Optional[FilterError]]:
    """Coerce value to UUID string."""
    if isinstance(value, str):
        try:
            # Validate UUID format
            uuid.UUID(value)
            return value, None
        except (ValueError, TypeError):
            return None, FilterError(
                type=ERROR_TYPE_INVALID_UUID,
                title="Invalid UUID",
                statusCode=400,
                errors=[f"Value '{value}' is not a valid UUID"],
            )

    return None, FilterError(
        type=ERROR_TYPE_INVALID_UUID,
        title="Invalid UUID",
        statusCode=400,
        errors=[f"Value '{value}' is not a valid UUID string"],
    )


def coerce_timestamp(value: Any) -> Tuple[Optional[str], Optional[FilterError]]:
    """Coerce value to ISO 8601 timestamp string."""
    if isinstance(value, str):
        try:
            # Try to parse ISO 8601 format
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value, None
        except (ValueError, AttributeError):
            return None, FilterError(
                type=ERROR_TYPE_INVALID_DATE,
                title="Invalid Timestamp",
                statusCode=400,
                errors=[f"Value '{value}' is not a valid ISO 8601 timestamp"],
            )

    if isinstance(value, datetime):
        return value.isoformat(), None

    return None, FilterError(
        type=ERROR_TYPE_INVALID_DATE,
        title="Invalid Timestamp",
        statusCode=400,
        errors=[f"Value '{value}' is not a valid timestamp"],
    )


def coerce_enum(
    value: Any, enum_values: Optional[List[str]]
) -> Tuple[Optional[str], Optional[FilterError]]:
    """Coerce value to enum (validate against allowed values)."""
    if enum_values is None:
        return None, FilterError(
            type=ERROR_TYPE_INVALID_ENUM,
            title="Invalid Enum",
            statusCode=400,
            errors=["Enum values not defined for enum field"],
        )

    str_value = str(value)
    if str_value not in enum_values:
        return None, FilterError(
            type=ERROR_TYPE_INVALID_ENUM,
            title="Invalid Enum Value",
            statusCode=400,
            errors=[f"Value '{str_value}' is not in allowed enum values: {', '.join(enum_values)}"],
        )

    return str_value, None
