"""Sort utilities for MisoClient SDK.

This module provides reusable sort utilities for parsing sort parameters
and building sort query strings.
"""

from typing import List, cast
from urllib.parse import quote

from ..models.sort import SortOption, SortOrder


def _normalize_sort_strings(sort_param: object) -> List[str]:
    """Normalize raw sort query parameter into list of strings."""
    if isinstance(sort_param, str):
        return [sort_param]
    if isinstance(sort_param, list):
        return [item for item in sort_param if isinstance(item, str)]
    return []


def _parse_sort_option(sort_str: str) -> SortOption | None:
    """Parse a single sort expression into SortOption."""
    normalized = sort_str.strip()
    if not normalized:
        return None
    if normalized.startswith("-"):
        field = normalized[1:].strip()
        order: SortOrder = "desc"
    else:
        field = normalized
        order = "asc"
    if not field:
        return None
    return SortOption(field=field, order=cast(SortOrder, order))


def parse_sort_params(params: dict) -> List[SortOption]:
    """Parse sort query parameters into SortOption list.

    Parses `?sort=-field` format into SortOption objects.
    Supports multiple sort parameters (array of sort strings).
    Prefix with '-' for descending order, otherwise ascending.

    Args:
        params: Query parameters dict (e.g., {'sort': '-updated_at'} or list of fields)

    Returns:
        List of SortOption objects

    Examples:
        >>> parse_sort_params({'sort': '-updated_at'})
        [SortOption(field='updated_at', order='desc')]
        >>> parse_sort_params({'sort': ['-updated_at', 'created_at']})
        [SortOption(field='updated_at', order='desc'), SortOption(field='created_at', order='asc')]

    """
    sort_param = params.get("sort")
    if not sort_param:
        return []
    sort_options: List[SortOption] = []
    for sort_str in _normalize_sort_strings(sort_param):
        parsed = _parse_sort_option(sort_str)
        if parsed:
            sort_options.append(parsed)
    return sort_options


def build_sort_string(sort_options: List[SortOption]) -> str:
    """Convert sort options into comma-separated query-string value."""
    if not sort_options:
        return ""

    sort_strings: List[str] = []
    for sort_option in sort_options:
        field = sort_option.field
        order = sort_option.order

        # URL encode field name
        field_encoded = quote(field)

        # Add '-' prefix for descending order
        if order == "desc":
            sort_strings.append(f"-{field_encoded}")
        else:
            sort_strings.append(field_encoded)

    # Join multiple sorts with comma (if needed for single sort param)
    # Or return as comma-separated string
    return ",".join(sort_strings)
