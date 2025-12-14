"""
Sort utilities for MisoClient SDK.

This module provides reusable sort utilities for parsing sort parameters
and building sort query strings.
"""

from typing import List, cast
from urllib.parse import quote

from ..models.sort import SortOption, SortOrder


def parse_sort_params(params: dict) -> List[SortOption]:
    """
    Parse sort query parameters into SortOption list.

    Parses `?sort=-field` format into SortOption objects.
    Supports multiple sort parameters (array of sort strings).
    Prefix with '-' for descending order, otherwise ascending.

    Args:
        params: Dictionary with query parameters (e.g., {'sort': '-updated_at'} or {'sort': ['-updated_at', 'created_at']})

    Returns:
        List of SortOption objects

    Examples:
        >>> parse_sort_params({'sort': '-updated_at'})
        [SortOption(field='updated_at', order='desc')]
        >>> parse_sort_params({'sort': ['-updated_at', 'created_at']})
        [SortOption(field='updated_at', order='desc'), SortOption(field='created_at', order='asc')]
    """
    sort_options: List[SortOption] = []

    # Get sort parameter (can be string or list)
    sort_param = params.get("sort")
    if not sort_param:
        return sort_options

    # Normalize to list
    if isinstance(sort_param, str):
        sort_strings = [sort_param]
    elif isinstance(sort_param, list):
        sort_strings = sort_param
    else:
        return sort_options

    # Parse each sort string
    for sort_str in sort_strings:
        if not isinstance(sort_str, str):
            continue

        sort_str = sort_str.strip()
        if not sort_str:
            continue

        # Check for descending order (prefix with '-')
        if sort_str.startswith("-"):
            field = sort_str[1:].strip()
            order: SortOrder = "desc"
        else:
            field = sort_str.strip()
            order = "asc"

        if field:
            sort_options.append(SortOption(field=field, order=cast(SortOrder, order)))

    return sort_options


def build_sort_string(sort_options: List[SortOption]) -> str:
    """
    Convert SortOption list to query string format.

    Converts SortOption objects to sort query string format.
    Descending order fields are prefixed with '-'.

    Args:
        sort_options: List of SortOption objects

    Returns:
        Sort query string (e.g., '-updated_at,created_at' or single value '-updated_at')

    Examples:
        >>> from miso_client.models.sort import SortOption
        >>> sort_options = [SortOption(field='updated_at', order='desc')]
        >>> build_sort_string(sort_options)
        '-updated_at'
        >>> sort_options = [
        ...     SortOption(field='updated_at', order='desc'),
        ...     SortOption(field='created_at', order='asc')
        ... ]
        >>> build_sort_string(sort_options)
        '-updated_at,created_at'
    """
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
