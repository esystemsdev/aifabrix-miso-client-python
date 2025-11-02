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
        total_items: Total number of items across all pages
        current_page: Current page number (1-based, maps from `page` query param)
        page_size: Number of items per page (maps from `page_size` query param)
        type: Resource type identifier (e.g., 'item', 'user', 'group')
    """

    total_items: int = Field(..., alias="totalItems", description="Total number of items")
    current_page: int = Field(..., alias="currentPage", description="Current page number (1-based)")
    page_size: int = Field(..., alias="pageSize", description="Number of items per page")
    type: str = Field(..., description="Resource type identifier")

    class Config:
        populate_by_name = True  # Allow both snake_case and camelCase

    # Support camelCase attribute access
    @property
    def totalItems(self) -> int:
        """Get total_items as totalItems (camelCase)."""
        return self.total_items

    @property
    def currentPage(self) -> int:
        """Get current_page as currentPage (camelCase)."""
        return self.current_page

    @property
    def pageSize(self) -> int:
        """Get page_size as pageSize (camelCase)."""
        return self.page_size


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

    class Config:
        populate_by_name = True  # Allow both snake_case and camelCase
