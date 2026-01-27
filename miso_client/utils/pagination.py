"""Pagination utilities for MisoClient SDK.

This module provides reusable pagination utilities for parsing pagination parameters,
creating meta objects, and working with paginated responses.
"""

from typing import Any, Dict, List, TypeVar

from ..models.pagination import Meta, PaginatedListResponse

T = TypeVar("T")


def parsePaginationParams(params: dict) -> Dict[str, int]:
    """Parse query parameters into pagination values.

    Parses `page` and `page_size` query parameters into `currentPage` and `pageSize`.
    Both are 1-based (page starts at 1).

    Args:
        params: Dictionary with query parameters (e.g., {'page': '1', 'page_size': '25'})

    Returns:
        Dictionary with 'currentPage' and 'pageSize' keys (camelCase)

    Examples:
        >>> parsePaginationParams({'page': '1', 'page_size': '25'})
        {'currentPage': 1, 'pageSize': 25}
        >>> parsePaginationParams({'page': '2'})
        {'currentPage': 2, 'pageSize': 20}  # Default pageSize is 20

    """
    # Default values (matching TypeScript default of 20)
    default_page = 1
    default_page_size = 20

    # Parse page (must be >= 1)
    page_str = params.get("page") or params.get("current_page")
    if page_str is None:
        current_page = default_page
    else:
        try:
            current_page = int(page_str)
            if current_page < 1:
                current_page = default_page
        except (ValueError, TypeError):
            current_page = default_page

    # Parse page_size (must be >= 1)
    page_size_str = params.get("page_size") or params.get("pageSize")
    if page_size_str is None:
        page_size = default_page_size
    else:
        try:
            page_size = int(page_size_str)
            if page_size < 1:
                page_size = default_page_size
        except (ValueError, TypeError):
            page_size = default_page_size

    return {"currentPage": current_page, "pageSize": page_size}


def parse_pagination_params(params: dict[str, Any]) -> tuple[int, int]:
    """Parse pagination parameters from a dictionary.

    This function normalizes pagination parameters, ensuring they are valid integers
    and enforcing minimum values. It follows the same pattern as parse_filter_params
    and parse_sort_params.

    Args:
        params: Dictionary with "page" and "page_size" keys.
                Values can be int, str, or None.

    Returns:
        Tuple of (page, page_size) as integers.

    Defaults:
        - page: 1 if not provided or invalid
        - page_size: 20 if not provided or invalid

    Validation:
        - page must be >= 1 (enforced via max(1, page))
        - page_size must be >= 1 (enforced via max(1, page_size))
        - Invalid values (non-numeric strings, None) default to safe values

    Examples:
        >>> parse_pagination_params({"page": 2, "page_size": 50})
        (2, 50)
        >>> parse_pagination_params({"page": "3", "page_size": "25"})
        (3, 25)
        >>> parse_pagination_params({"page": 1})
        (1, 20)
        >>> parse_pagination_params({})
        (1, 20)
        >>> parse_pagination_params({"page": 0, "page_size": -5})
        (1, 1)
        >>> parse_pagination_params({"page": None, "page_size": "invalid"})
        (1, 20)

    """
    page = params.get("page", 1)
    page_size = params.get("page_size", 20)

    # Convert to int if needed (handles string inputs from query params)
    try:
        page = int(page) if page is not None else 1
    except (ValueError, TypeError):
        page = 1

    try:
        page_size = int(page_size) if page_size is not None else 20
    except (ValueError, TypeError):
        page_size = 20

    # Ensure minimum values (page and page_size must be >= 1)
    page = max(1, page)
    page_size = max(1, page_size)

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
    """Apply pagination to an array (for mock/testing).

    Args:
        items: Array of items to paginate
        currentPage: Current page index (1-based)
        pageSize: Number of items per page

    Returns:
        Paginated slice of the array

    Examples:
        >>> items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        >>> applyPaginationToArray(items, 1, 3)
        [1, 2, 3]
        >>> applyPaginationToArray(items, 2, 3)
        [4, 5, 6]

    """
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
