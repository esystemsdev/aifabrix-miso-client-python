"""
Filter parsing utilities for MisoClient SDK.

This module provides utilities for parsing filter parameters from query strings
and converting them into FilterOption objects.
"""

from typing import Any, List, Optional, Union, cast
from urllib.parse import unquote

from ..models.filter import FilterOperator, FilterOption


def parse_filter_params(params: dict) -> List[FilterOption]:
    """
    Parse filter query parameters into FilterOption list.

    Parses `?filter=field:op:value` format into FilterOption objects.
    Supports multiple filter parameters (array of filter strings).

    Args:
        params: Dictionary with query parameters (e.g., {'filter': ['status:eq:active', 'region:in:eu,us']})

    Returns:
        List of FilterOption objects

    Examples:
        >>> parse_filter_params({'filter': ['status:eq:active']})
        [FilterOption(field='status', op='eq', value='active')]
        >>> parse_filter_params({'filter': ['region:in:eu,us']})
        [FilterOption(field='region', op='in', value=['eu', 'us'])]
    """
    filters: List[FilterOption] = []

    # Get filter parameter (can be string or list)
    filter_param = params.get("filter") or params.get("filters")
    if not filter_param:
        return filters

    # Normalize to list
    if isinstance(filter_param, str):
        filter_strings = [filter_param]
    elif isinstance(filter_param, list):
        filter_strings = filter_param
    else:
        return filters

    # Parse each filter string
    for filter_str in filter_strings:
        if not isinstance(filter_str, str):
            continue

        # Split by colon (field:op:value)
        # For isNull/isNotNull, value part may be empty or missing
        parts = filter_str.split(":", 2)
        if len(parts) < 2:
            continue  # Skip invalid filter format

        field = unquote(parts[0].strip())
        op = parts[1].strip()
        value_str = unquote(parts[2].strip()) if len(parts) > 2 else ""

        # Validate operator
        valid_operators = [
            "eq",
            "neq",
            "in",
            "nin",
            "gt",
            "lt",
            "gte",
            "lte",
            "contains",
            "like",
            "isNull",
            "isNotNull",
        ]
        if op not in valid_operators:
            continue  # Skip invalid operator

        # Parse value based on operator
        parsed_value: Optional[Union[str, int, float, bool, List[Any]]] = None
        if op in ("isNull", "isNotNull"):
            # Null check operators don't need values
            parsed_value = None
        elif op in ("in", "nin"):
            # Array values: comma-separated
            parsed_value = [v.strip() for v in value_str.split(",") if v.strip()]
        else:
            # Single value: try to parse as number/boolean, fallback to string
            single_value: Union[str, int, float, bool] = value_str
            # Try to parse as integer
            try:
                if "." not in value_str:
                    single_value = int(value_str)
                else:
                    single_value = float(value_str)
            except (ValueError, TypeError):
                # Try boolean
                if value_str.lower() in ("true", "false"):
                    single_value = value_str.lower() == "true"
                else:
                    single_value = value_str
            parsed_value = single_value

        value = parsed_value

        filters.append(FilterOption(field=field, op=cast(FilterOperator, op), value=value))

    return filters
