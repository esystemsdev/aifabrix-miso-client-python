"""
Filter types for MisoClient SDK.

This module contains Pydantic models and classes that define filter structures
for query filtering matching the Miso/Dataplane API conventions.
"""

from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field

FilterOperator = Literal[
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
]


class FilterOption(BaseModel):
    """
    Single filter option with field, operator, and value.

    Fields:
        field: Field name to filter on
        op: Filter operator (eq, neq, in, nin, gt, lt, gte, lte, contains, like)
        value: Filter value (supports single values or arrays for 'in'/'nin' operators)
    """

    field: str = Field(..., description="Field name to filter on")
    op: FilterOperator = Field(..., description="Filter operator")
    value: Union[str, int, float, bool, List[Any]] = Field(
        ..., description="Filter value (supports arrays for 'in'/'nin' operators)"
    )


class FilterQuery(BaseModel):
    """
    Complete filter query with filters, sort, pagination, and field selection.

    Fields:
        filters: Optional list of filter options
        sort: Optional list of sort options (field strings with optional '-' prefix for desc)
        page: Optional page number (1-based)
        pageSize: Optional number of items per page
        fields: Optional list of fields to include in response
    """

    filters: Optional[List[FilterOption]] = Field(
        default=None, description="List of filter options"
    )
    sort: Optional[List[str]] = Field(
        default=None,
        description="List of sort options (e.g., ['-updated_at', 'created_at'])",
    )
    page: Optional[int] = Field(default=None, description="Page number (1-based)")
    pageSize: Optional[int] = Field(default=None, description="Number of items per page")
    fields: Optional[List[str]] = Field(
        default=None, description="List of fields to include in response"
    )


class FilterBuilder:
    """
    Builder pattern for dynamic filter construction.

    Allows chaining filter additions for building complex filter queries.
    """

    def __init__(self):
        """Initialize empty filter builder."""
        self._filters: List[FilterOption] = []

    def add(self, field: str, op: FilterOperator, value: Any) -> "FilterBuilder":
        """
        Add a filter option to the builder.

        Args:
            field: Field name to filter on
            op: Filter operator
            value: Filter value

        Returns:
            FilterBuilder instance for method chaining
        """
        self._filters.append(FilterOption(field=field, op=op, value=value))
        return self

    def add_many(self, filters: List[FilterOption]) -> "FilterBuilder":
        """
        Add multiple filter options to the builder.

        Args:
            filters: List of FilterOption objects

        Returns:
            FilterBuilder instance for method chaining
        """
        self._filters.extend(filters)
        return self

    def build(self) -> List[FilterOption]:
        """
        Build the filter list.

        Returns:
            List of FilterOption objects
        """
        return self._filters.copy()

    def to_query_string(self) -> str:
        """
        Convert filters to query string format.

        Format: ?filter=field:op:value&filter=field:op:value

        Returns:
            Query string with filter parameters
        """
        if not self._filters:
            return ""

        query_parts: List[str] = []
        for filter_option in self._filters:
            # Format value for query string
            if isinstance(filter_option.value, list):
                # For arrays (in/nin), join with commas
                value_str = ",".join(str(v) for v in filter_option.value)
            else:
                value_str = str(filter_option.value)

            query_parts.append(f"filter={filter_option.field}:{filter_option.op}:{value_str}")

        return "&".join(query_parts)
