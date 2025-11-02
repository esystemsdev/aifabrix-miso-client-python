"""
Sort types for MisoClient SDK.

This module contains Pydantic models that define sort structures
for query sorting matching the Miso/Dataplane API conventions.
"""

from typing import Literal

from pydantic import BaseModel, Field

SortOrder = Literal["asc", "desc"]


class SortOption(BaseModel):
    """
    Sort option with field and order.

    Fields:
        field: Field name to sort by
        order: Sort order ('asc' for ascending, 'desc' for descending)
    """

    field: str = Field(..., description="Field name to sort by")
    order: SortOrder = Field(..., description="Sort order ('asc' or 'desc')")
