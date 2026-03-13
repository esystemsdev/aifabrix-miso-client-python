"""Filter parsing utilities for MisoClient SDK.

This module provides utilities for parsing filter parameters from query strings
and converting them into FilterOption objects.
"""

from typing import Any, List, Optional, Union, cast
from urllib.parse import unquote

from ..models.filter import FilterOperator, FilterOption

VALID_OPERATORS = {
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
    "ilike",
    "isNull",
    "isNotNull",
}


def _normalize_filter_strings(filter_param: Any) -> List[str]:
    """Normalize raw filter parameter into a list of strings."""
    if isinstance(filter_param, str):
        return [filter_param]
    if isinstance(filter_param, list):
        return [item for item in filter_param if isinstance(item, str)]
    return []


def _parse_single_value(value_str: str) -> Union[str, int, float, bool]:
    """Parse scalar value as int/float/bool when possible."""
    try:
        return int(value_str) if "." not in value_str else float(value_str)
    except (ValueError, TypeError):
        if value_str.lower() in ("true", "false"):
            return value_str.lower() == "true"
        return value_str


def _parse_filter_value(
    op: str, value_str: str
) -> Optional[Union[str, int, float, bool, List[Any]]]:
    """Parse filter value according to operator semantics."""
    if op in ("isNull", "isNotNull"):
        return None
    if op in ("in", "nin"):
        return [v.strip() for v in value_str.split(",") if v.strip()]
    return _parse_single_value(value_str)


def _parse_filter_option(filter_str: str) -> Optional[FilterOption]:
    """Parse one filter expression string into FilterOption."""
    parts = filter_str.split(":", 2)
    if len(parts) < 2:
        return None

    field = unquote(parts[0].strip())
    op = parts[1].strip()
    if op not in VALID_OPERATORS:
        return None

    value_str = unquote(parts[2].strip()) if len(parts) > 2 else ""
    value = _parse_filter_value(op, value_str)
    return FilterOption(field=field, op=cast(FilterOperator, op), value=value)


def parse_filter_params(params: dict) -> List[FilterOption]:
    """Parse query filter parameters into FilterOption list."""
    filters: List[FilterOption] = []

    filter_param = params.get("filter") or params.get("filters")
    if not filter_param:
        return filters

    for filter_str in _normalize_filter_strings(filter_param):
        parsed = _parse_filter_option(filter_str)
        if parsed is not None:
            filters.append(parsed)

    return filters
