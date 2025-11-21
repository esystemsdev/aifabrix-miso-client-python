"""
Pagination utilities for MisoClient SDK.

This module provides reusable pagination utilities for parsing pagination parameters,
creating meta objects, and working with paginated responses.
"""

from typing import Dict, List, Tuple, TypeVar

from ..models.pagination import Meta, PaginatedListResponse

T = TypeVar("T")


def parsePaginationParams(params: dict) -> Dict[str, int]:
    """
    Parse query parameters into pagination values.

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


# Alias for backward compatibility
def parse_pagination_params(params: dict) -> Tuple[int, int]:
    """
    Parse query parameters to pagination values (legacy function).

    Parses `page` and `page_size` query parameters into `current_page` and `page_size`.
    Both are 1-based (page starts at 1).

    Args:
        params: Dictionary with query parameters (e.g., {'page': '1', 'page_size': '25'})

    Returns:
        Tuple of (current_page, page_size) as integers

    Examples:
        >>> parse_pagination_params({'page': '1', 'page_size': '25'})
        (1, 25)
        >>> parse_pagination_params({'page': '2'})
        (2, 20)  # Default page_size is 20
    """
    result = parsePaginationParams(params)
    return (result["currentPage"], result["pageSize"])


def createMetaObject(totalItems: int, currentPage: int, pageSize: int, type: str) -> Meta:
    """
    Construct meta object for API response.

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


def create_meta_object(total_items: int, current_page: int, page_size: int, type: str) -> Meta:
    """
    Construct Meta object from pagination parameters.

    Args:
        total_items: Total number of items across all pages
        current_page: Current page number (1-based)
        page_size: Number of items per page
        type: Resource type identifier (e.g., 'item', 'user', 'group')

    Returns:
        Meta object with pagination metadata

    Examples:
        >>> meta = create_meta_object(120, 1, 25, 'item')
        >>> meta.totalItems
        120
        >>> meta.currentPage
        1
    """
    return Meta(
        totalItems=total_items,
        currentPage=current_page,
        pageSize=page_size,
        type=type,
    )


def applyPaginationToArray(items: List[T], currentPage: int, pageSize: int) -> List[T]:
    """
    Apply pagination to an array (for mock/testing).

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


def apply_pagination_to_array(items: List[T], current_page: int, page_size: int) -> List[T]:
    """
    Apply pagination to array (for testing/mocks).

    Args:
        items: Array of items to paginate
        current_page: Current page number (1-based)
        page_size: Number of items per page

    Returns:
        Paginated subset of items for the specified page

    Examples:
        >>> items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        >>> apply_pagination_to_array(items, 1, 3)
        [1, 2, 3]
        >>> apply_pagination_to_array(items, 2, 3)
        [4, 5, 6]
    """
    if not items:
        return []

    if current_page < 1:
        current_page = 1
    if page_size < 1:
        page_size = 25

    # Calculate start and end indices
    start_index = (current_page - 1) * page_size
    end_index = start_index + page_size

    # Return paginated subset
    return items[start_index:end_index]


def createPaginatedListResponse(
    items: List[T],
    totalItems: int,
    currentPage: int,
    pageSize: int,
    type: str,
) -> PaginatedListResponse[T]:
    """
    Wrap array + meta into a standard paginated response.

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


def create_paginated_list_response(
    items: List[T],
    total_items: int,
    current_page: int,
    page_size: int,
    type: str,
) -> PaginatedListResponse[T]:
    """
    Wrap array + meta into standard paginated response (legacy function).

    Args:
        items: Array of items for current page
        total_items: Total number of items across all pages
        current_page: Current page number (1-based)
        page_size: Number of items per page
        type: Resource type identifier (e.g., 'item', 'user', 'group')

    Returns:
        PaginatedListResponse with meta and data

    Examples:
        >>> items = [{'id': 1}, {'id': 2}]
        >>> response = create_paginated_list_response(items, 10, 1, 2, 'item')
        >>> response.meta.totalItems
        10
        >>> len(response.data)
        2
    """
    return createPaginatedListResponse(items, total_items, current_page, page_size, type)
