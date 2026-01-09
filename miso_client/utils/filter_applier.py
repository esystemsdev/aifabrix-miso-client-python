"""
Filter application utilities for MisoClient SDK.

This module provides utilities for applying filters to arrays locally,
useful for testing and mocking scenarios.
"""

from typing import Any, Dict, List

from ..models.filter import FilterOption


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
                if field in item
                and isinstance(item[field], (int, float))
                and isinstance(value, (int, float))
                and item[field] > value
            ]
        elif op == "lt":
            filtered_items = [
                item
                for item in filtered_items
                if field in item
                and isinstance(item[field], (int, float))
                and isinstance(value, (int, float))
                and item[field] < value
            ]
        elif op == "gte":
            filtered_items = [
                item
                for item in filtered_items
                if field in item
                and isinstance(item[field], (int, float))
                and isinstance(value, (int, float))
                and item[field] >= value
            ]
        elif op == "lte":
            filtered_items = [
                item
                for item in filtered_items
                if field in item
                and isinstance(item[field], (int, float))
                and isinstance(value, (int, float))
                and item[field] <= value
            ]
        elif op == "contains":
            if isinstance(value, str):
                # For string values, check both string fields (substring) and list fields (membership)
                filtered_items = [
                    item
                    for item in filtered_items
                    if field in item
                    and (
                        (isinstance(item[field], str) and value in item[field])
                        or (isinstance(item[field], list) and value in item[field])
                    )
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
        elif op == "isNull":
            # Field is missing or value is None
            filtered_items = [
                item for item in filtered_items if field not in item or item[field] is None
            ]
        elif op == "isNotNull":
            # Field exists and value is not None
            filtered_items = [
                item for item in filtered_items if field in item and item[field] is not None
            ]

    return filtered_items
