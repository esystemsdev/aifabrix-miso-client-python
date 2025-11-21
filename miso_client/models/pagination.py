"""
Pagination types for MisoClient SDK.

This module contains Pydantic models that define pagination structures
for paginated list responses matching the Miso/Dataplane API conventions.
"""

from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    """
    Pagination metadata for list responses.

    Fields:
        totalItems: Total number of items across all pages
        currentPage: Current page number (1-based, maps from `page` query param)
        pageSize: Number of items per page (maps from `pageSize` query param)
        type: Resource type identifier (e.g., 'item', 'user', 'group')
    """

    totalItems: int = Field(..., description="Total number of items")
    currentPage: int = Field(..., description="Current page number (1-based)")
    pageSize: int = Field(..., description="Number of items per page")
    type: str = Field(..., description="Resource type identifier")


class PaginatedListResponse(BaseModel, Generic[T]):
    """
    Paginated list response structure.

    Generic type parameter T represents the item type in the data array.

    Fields:
        meta: Pagination metadata
        data: Array of items for current page
    """

    meta: Meta = Field(..., description="Pagination metadata")
    data: List[T] = Field(..., description="Array of items for current page")
