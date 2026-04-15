"""Filter application utilities for MisoClient SDK.

This module provides utilities for applying filters to arrays locally,
useful for testing and mocking scenarios.
"""

from typing import Any, Dict, List

from ..models.filter import FilterOption


def _numeric_compare(item_value: Any, filter_value: Any, op: str) -> bool:
    """Compare numeric values for gt/lt/gte/lte operators."""
    if not isinstance(item_value, (int, float)) or not isinstance(filter_value, (int, float)):
        return False
    if op == "gt":
        return item_value > filter_value
    if op == "lt":
        return item_value < filter_value
    if op == "gte":
        return item_value >= filter_value
    return item_value <= filter_value


def _contains_match(item_value: Any, filter_value: Any) -> bool:
    """Evaluate contains semantics for strings and arrays."""
    if isinstance(filter_value, str):
        return (isinstance(item_value, str) and filter_value in item_value) or (
            isinstance(item_value, list) and filter_value in item_value
        )
    return isinstance(item_value, list) and filter_value in item_value


def _like_match(item_value: Any, filter_value: Any) -> bool:
    """Evaluate like/ilike semantics for in-memory filtering."""
    return (
        isinstance(filter_value, str)
        and isinstance(item_value, str)
        and (filter_value.lower() in item_value.lower())
    )


def _matches_filter(item: Dict[str, Any], filter_option: FilterOption) -> bool:
    """Evaluate one item against one filter option."""
    field = filter_option.field
    op = filter_option.op
    value = filter_option.value
    has_field = field in item
    item_value = item.get(field)

    if op == "eq":
        return has_field and item_value == value
    if op == "neq":
        return (not has_field) or item_value != value
    if op == "in":
        return has_field and (
            item_value in value if isinstance(value, list) else item_value == value
        )
    if op == "nin":
        return (not has_field) or (
            item_value not in value if isinstance(value, list) else item_value != value
        )
    if op in {"gt", "lt", "gte", "lte"}:
        return has_field and _numeric_compare(item_value, value, op)
    if op == "contains":
        return has_field and _contains_match(item_value, value)
    if op in {"like", "ilike"}:
        return has_field and _like_match(item_value, value)
    if op == "isNull":
        return (not has_field) or item_value is None
    if op == "isNotNull":
        return has_field and item_value is not None
    return True


def apply_filters(items: List[Dict[str, Any]], filters: List[FilterOption]) -> List[Dict[str, Any]]:
    """Apply filters to array locally (for testing/mocks)."""
    if not filters:
        return items

    filtered_items = items.copy()
    for filter_option in filters:
        filtered_items = [item for item in filtered_items if _matches_filter(item, filter_option)]
    return filtered_items
