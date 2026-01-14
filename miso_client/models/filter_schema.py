"""
Filter schema types for MisoClient SDK.

This module contains Pydantic models for defining filter schemas, field definitions,
and compiled filter results for schema-based validation.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .error_response import ErrorResponse
from .filter import FilterOperator

# Reuse ErrorResponse for FilterError (RFC 7807 compliant)
FilterError = ErrorResponse


class FilterFieldDefinition(BaseModel):
    """
    Definition of a filterable field with its type, allowed operators, and constraints.

    Fields:
        column: Database column name
        type: Field type (string, number, boolean, uuid, timestamp, enum)
        operators: List of allowed operators for this field
        enum: Optional list of enum values (required if type is "enum")
        nullable: Whether the field can be null (enables isNull/isNotNull operators)
        description: Human-readable description of the field
    """

    column: str = Field(..., description="Database column name")
    type: Literal["string", "number", "boolean", "uuid", "timestamp", "enum"] = Field(
        ..., description="Field type"
    )
    operators: List[FilterOperator] = Field(..., description="Allowed operators for this field")
    enum: Optional[List[str]] = Field(
        default=None, description="Enum values (required if type is 'enum')"
    )
    nullable: Optional[bool] = Field(
        default=None, description="Whether the field can be null (enables isNull/isNotNull)"
    )
    description: Optional[str] = Field(
        default=None, description="Human-readable description of the field"
    )


class FilterSchema(BaseModel):
    """
    Complete filter schema for a resource.

    Defines all filterable fields, their types, and allowed operators for a resource.

    Fields:
        resource: Resource name (e.g., "applications")
        version: Schema version for compatibility tracking
        fields: Dictionary mapping field names to FilterFieldDefinition objects
    """

    resource: str = Field(..., description="Resource name (e.g., 'applications')")
    version: Optional[str] = Field(
        default=None, description="Schema version for compatibility tracking"
    )
    fields: Dict[str, FilterFieldDefinition] = Field(
        ..., description="Field definitions keyed by field name"
    )


class CompiledFilter(BaseModel):
    """
    Compiled filter result with SQL and parameters.

    Used for generating PostgreSQL-safe parameterized queries.

    Fields:
        sql: SQL WHERE clause fragment
        params: List of parameter values for the SQL query
        param_index: Current parameter index (for building queries with multiple filters)
    """

    sql: str = Field(..., description="SQL WHERE clause fragment")
    params: List[Any] = Field(..., description="List of parameter values")
    param_index: int = Field(default=1, description="Current parameter index")
