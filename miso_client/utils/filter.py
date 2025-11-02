"""
Filter utilities for MisoClient SDK.

This module provides reusable filter utilities for parsing filter parameters,
building query strings, and applying filters to arrays.
"""

from typing import Any, Dict, List
from urllib.parse import quote, unquote

from ..models.filter import FilterOption, FilterQuery


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
        parts = filter_str.split(":", 2)
        if len(parts) != 3:
            continue  # Skip invalid filter format

        field = unquote(parts[0].strip())
        op = parts[1].strip()
        value_str = unquote(parts[2].strip())

        # Validate operator
        valid_operators = ["eq", "neq", "in", "nin", "gt", "lt", "gte", "lte", "contains", "like"]
        if op not in valid_operators:
            continue  # Skip invalid operator

        # Parse value based on operator
        if op in ("in", "nin"):
            # Array values: comma-separated
            value = [v.strip() for v in value_str.split(",") if v.strip()]
        else:
            # Single value: try to parse as number/boolean, fallback to string
            value = value_str
            # Try to parse as integer
            try:
                if "." not in value_str:
                    value = int(value_str)
                else:
                    value = float(value_str)
            except (ValueError, TypeError):
                # Try boolean
                if value_str.lower() in ("true", "false"):
                    value = value_str.lower() == "true"
                else:
                    value = value_str

        filters.append(FilterOption(field=field, op=op, value=value))

    return filters


def build_query_string(filter_query: FilterQuery) -> str:
    """
    Convert FilterQuery object to query string.

    Builds query string with filter, sort, page, pageSize, and fields parameters.

    Args:
        filter_query: FilterQuery object with filters, sort, pagination, and fields

    Returns:
        Query string (e.g., '?filter=status:eq:active&page=1&pageSize=25&sort=-updated_at')

    Examples:
        >>> from miso_client.models.filter import FilterQuery, FilterOption
        >>> query = FilterQuery(
        ...     filters=[FilterOption(field='status', op='eq', value='active')],
        ...     page=1,
        ...     pageSize=25
        ... )
        >>> build_query_string(query)
        'filter=status:eq:active&page=1&pageSize=25'
    """
    query_parts: List[str] = []

    # Add filters
    if filter_query.filters:
        for filter_option in filter_query.filters:
            # Format value for query string
            if isinstance(filter_option.value, list):
                # For arrays (in/nin), join with commas (don't encode the comma delimiter)
                # URL encode each value individually, then join with comma
                value_parts = [quote(str(v)) for v in filter_option.value]
                value_str = ",".join(value_parts)
            else:
                value_str = quote(str(filter_option.value))

            # URL encode field
            field_encoded = quote(filter_option.field)

            query_parts.append(f"filter={field_encoded}:{filter_option.op}:{value_str}")

    # Add sort
    if filter_query.sort:
        for sort_field in filter_query.sort:
            query_parts.append(f"sort={quote(sort_field)}")

    # Add pagination
    if filter_query.page is not None:
        query_parts.append(f"page={filter_query.page}")

    if filter_query.pageSize is not None:
        query_parts.append(f"pageSize={filter_query.pageSize}")

    # Add fields
    if filter_query.fields:
        fields_str = ",".join(quote(f) for f in filter_query.fields)
        query_parts.append(f"fields={fields_str}")

    return "&".join(query_parts)


def apply_filters(items: List[Dict[str, Any]], filters: List[FilterOption]) -> List[Dict[str, Any]]:
    """
    Apply filters to array locally (for testing/mocks).

    Args:
        items: Array of dictionaries to filter
        filters: List of FilterOption objects to apply

    Returns:
        Filtered array of items

    Examples:
        >>> items = [{'status': 'active', 'region': 'eu'}, {'status': 'inactive', 'region': 'us'}]
        >>> filters = [FilterOption(field='status', op='eq', value='active')]
        >>> apply_filters(items, filters)
        [{'status': 'active', 'region': 'eu'}]
    """
    if not filters:
        return items

    filtered_items = items.copy()

    for filter_option in filters:
        field = filter_option.field
        op = filter_option.op
        value = filter_option.value

        # Apply filter based on operator
        if op == "eq":
            filtered_items = [
                item for item in filtered_items if field in item and item[field] == value
            ]
        elif op == "neq":
            filtered_items = [
                item for item in filtered_items if field not in item or item[field] != value
            ]
        elif op == "in":
            if isinstance(value, list):
                filtered_items = [
                    item for item in filtered_items if field in item and item[field] in value
                ]
            else:
                filtered_items = [
                    item for item in filtered_items if field in item and item[field] == value
                ]
        elif op == "nin":
            if isinstance(value, list):
                filtered_items = [
                    item for item in filtered_items if field not in item or item[field] not in value
                ]
            else:
                filtered_items = [
                    item for item in filtered_items if field not in item or item[field] != value
                ]
        elif op == "gt":
            filtered_items = [
                item
                for item in filtered_items
                if field in item and isinstance(item[field], (int, float)) and item[field] > value
            ]
        elif op == "lt":
            filtered_items = [
                item
                for item in filtered_items
                if field in item and isinstance(item[field], (int, float)) and item[field] < value
            ]
        elif op == "gte":
            filtered_items = [
                item
                for item in filtered_items
                if field in item and isinstance(item[field], (int, float)) and item[field] >= value
            ]
        elif op == "lte":
            filtered_items = [
                item
                for item in filtered_items
                if field in item and isinstance(item[field], (int, float)) and item[field] <= value
            ]
        elif op == "contains":
            if isinstance(value, str):
                filtered_items = [
                    item
                    for item in filtered_items
                    if field in item and isinstance(item[field], str) and value in item[field]
                ]
            else:
                # For non-string values, check if value is in list/array field
                filtered_items = [
                    item
                    for item in filtered_items
                    if field in item and isinstance(item[field], list) and value in item[field]
                ]
        elif op == "like":
            if isinstance(value, str):
                # Simple like matching (contains)
                filtered_items = [
                    item
                    for item in filtered_items
                    if field in item
                    and isinstance(item[field], str)
                    and value.lower() in item[field].lower()
                ]

    return filtered_items
