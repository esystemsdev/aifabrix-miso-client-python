"""Pagination utilities for MisoClient SDK.

This module provides reusable pagination utilities for parsing pagination parameters,
creating meta objects, and working with paginated responses.
"""

from typing import Any, Dict, List, TypeVar

from ..models.pagination import Meta, PaginatedListResponse

T = TypeVar("T")


def _parse_positive_int(value: Any, default: int, minimum: int = 1) -> int:
    """Parse integer with fallback default and minimum constraint."""
    try:
        parsed = int(value) if value is not None else default
    except (ValueError, TypeError):
        return default
    return parsed if parsed >= minimum else minimum


def _pick_first(params: dict, keys: list[str]) -> Any:
    """Return first non-None value for provided key candidates."""
    for key in keys:
        value = params.get(key)
        if value is not None:
            return value
    return None


def _parse_page_size_legacy(value: Any, default: int) -> int:
    """Parse legacy page_size where non-positive values fallback to default."""
    try:
        parsed = int(value) if value is not None else default
    except (ValueError, TypeError):
        return default
    return parsed if parsed >= 1 else default


def parsePaginationParams(params: dict) -> Dict[str, int]:
    """Parse query parameters into pagination values.

    Parses `page` and `pageSize` query parameters into `currentPage` and `pageSize`.
    Both are 1-based (page starts at 1).
    Also accepts legacy `page_size` for backward compatibility.

    Args:
        params: Dictionary with query parameters (e.g., {'page': '1', 'pageSize': '25'})

    Returns:
        Dictionary with 'currentPage' and 'pageSize' keys (camelCase)

    Examples:
        >>> parsePaginationParams({'page': '1', 'pageSize': '25'})
        {'currentPage': 1, 'pageSize': 25}
        >>> parsePaginationParams({'page': '2'})
        {'currentPage': 2, 'pageSize': 20}  # Default pageSize is 20

    """
    default_page = 1
    default_page_size = 20
    page_value = _pick_first(params, ["page", "current_page"])
    current_page = _parse_positive_int(page_value, default_page, minimum=1)
    if params.get("pageSize") is not None:
        page_size = _parse_positive_int(params.get("pageSize"), default_page_size, minimum=1)
    else:
        page_size = _parse_page_size_legacy(params.get("page_size"), default_page_size)
    return {"currentPage": current_page, "pageSize": page_size}


def parse_pagination_params(params: dict[str, Any]) -> tuple[int, int]:
    """Parse and normalize pagination params into (page, page_size)."""
    page_value = _pick_first(params, ["page"])
    page_size_value = _pick_first(params, ["page_size", "pageSize"])
    page = _parse_positive_int(page_value, 1, minimum=1)
    page_size = _parse_positive_int(page_size_value, 20, minimum=1)
    return page, page_size


def createMetaObject(totalItems: int, currentPage: int, pageSize: int, type: str) -> Meta:
    """Construct meta object for API response.

    Args:
        totalItems: Total number of items available in full dataset
        currentPage: Current page index (1-based)
        pageSize: Number of items per page
        type: Logical resource type (e.g., "application", "environment")

    Returns:
        Meta object

    Examples:
        >>> meta = createMetaObject(120, 1, 25, 'item')
        >>> meta.totalItems
        120
        >>> meta.currentPage
        1

    """
    return Meta(
        totalItems=totalItems,
        currentPage=currentPage,
        pageSize=pageSize,
        type=type,
    )


def applyPaginationToArray(items: List[T], currentPage: int, pageSize: int) -> List[T]:
    """Apply pagination to a local array for mocks/tests."""
    if not items:
        return []

    if currentPage < 1:
        currentPage = 1
    if pageSize < 1:
        pageSize = 25

    # Calculate start and end indices
    start_index = (currentPage - 1) * pageSize
    end_index = start_index + pageSize

    # Return paginated subset
    return items[start_index:end_index]


def createPaginatedListResponse(
    items: List[T],
    totalItems: int,
    currentPage: int,
    pageSize: int,
    type: str,
) -> PaginatedListResponse[T]:
    """Wrap array + meta into a standard paginated response.

    Args:
        items: Array of items for the current page
        totalItems: Total number of items available in full dataset
        currentPage: Current page index (1-based)
        pageSize: Number of items per page
        type: Logical resource type (e.g., "application", "environment")

    Returns:
        PaginatedListResponse object

    Examples:
        >>> items = [{'id': 1}, {'id': 2}]
        >>> response = createPaginatedListResponse(items, 10, 1, 2, 'item')
        >>> response.meta.totalItems
        10
        >>> len(response.data)
        2

    """
    meta = createMetaObject(totalItems, currentPage, pageSize, type)
    return PaginatedListResponse(meta=meta, data=items)
