"""Filter schema validation and SQL compilation utilities for MisoClient SDK.

This module provides utilities for validating filters against schemas,
coercing values to appropriate types, and compiling filters to SQL.
"""

from typing import Any, Dict, List, Literal, Optional, Tuple, cast

from ..models.filter import FilterOperator, FilterOption
from ..models.filter_schema import (
    CompiledFilter,
    FilterError,
    FilterFieldDefinition,
    FilterSchema,
)
from .filter_coercion import coerce_single_value

# Error type URIs following RFC 7807 pattern
ERROR_TYPE_UNKNOWN_FIELD = "/Errors/FilterValidation/UnknownField"
ERROR_TYPE_INVALID_OPERATOR = "/Errors/FilterValidation/InvalidOperator"
ERROR_TYPE_INVALID_TYPE = "/Errors/FilterValidation/InvalidType"
ERROR_TYPE_INVALID_UUID = "/Errors/FilterValidation/InvalidUuid"
ERROR_TYPE_INVALID_DATE = "/Errors/FilterValidation/InvalidDate"
ERROR_TYPE_INVALID_ENUM = "/Errors/FilterValidation/InvalidEnum"
ERROR_TYPE_INVALID_IN = "/Errors/FilterValidation/InvalidIn"
ERROR_TYPE_INVALID_FORMAT = "/Errors/FilterValidation/InvalidFormat"


def validate_filter(
    filter_option: FilterOption, schema: FilterSchema
) -> Tuple[bool, Optional[FilterError]]:
    """Validate a FilterOption against a FilterSchema.

    Checks if the field exists, operator is allowed, and value type is valid.

    Args:
        filter_option: FilterOption to validate
        schema: FilterSchema to validate against

    Returns:
        Tuple of (is_valid, error). If valid, error is None.
        If invalid, error is a FilterError with RFC 7807 compliant structure.

    Examples:
        >>> schema = FilterSchema(resource="apps", fields={...})
        >>> filter_opt = FilterOption(field="name", op="eq", value="test")
        >>> is_valid, error = validate_filter(filter_opt, schema)
        >>> if not is_valid:
        ...     print(error.errors)

    """
    # Check if field exists in schema
    if filter_option.field not in schema.fields:
        return False, FilterError(
            type=ERROR_TYPE_UNKNOWN_FIELD,
            title="Unknown Field",
            statusCode=400,
            errors=[
                f"Field '{filter_option.field}' is not filterable for resource '{schema.resource}'"
            ],
        )

    field_def = schema.fields[filter_option.field]

    # Check if operator is allowed for this field
    if filter_option.op not in field_def.operators:
        return False, FilterError(
            type=ERROR_TYPE_INVALID_OPERATOR,
            title="Invalid Operator",
            statusCode=400,
            errors=[
                f"Operator '{filter_option.op}' is not allowed for field '{filter_option.field}'. "
                f"Allowed operators: {', '.join(field_def.operators)}"
            ],
        )

    # Validate value type and coerce if needed
    if filter_option.op not in ("isNull", "isNotNull"):
        coerced_value, error = coerce_value(filter_option.value, field_def)
        if error:
            return False, error

    return True, None


def coerce_value(value: Any, field_def: FilterFieldDefinition) -> Tuple[Any, Optional[FilterError]]:
    """Coerce and validate a value based on field definition type.

    Supports type coercion for string, number, boolean, uuid, timestamp, and enum types.

    Args:
        value: Value to coerce and validate
        field_def: FilterFieldDefinition with type and constraints

    Returns:
        Tuple of (coerced_value, error). If valid, error is None.
        If invalid, error is a FilterError with RFC 7807 compliant structure.

    Examples:
        >>> field_def = FilterFieldDefinition(
        ...     column="age", type="number", operators=["eq", "gt"]
        ... )
        >>> coerced, error = coerce_value("25", field_def)
        >>> print(coerced)  # 25 (int)

    """
    field_type = field_def.type

    # Handle list values (for 'in'/'nin' operators)
    if isinstance(value, list):
        coerced_list = []
        for item in value:
            coerced_item, error = coerce_single_value(item, field_type, field_def.enum)
            if error:
                return None, error
            coerced_list.append(coerced_item)
        return coerced_list, None

    # Handle single values
    return coerce_single_value(value, field_type, field_def.enum)


def compile_filter(
    filter_option: FilterOption, schema: FilterSchema, param_index: int = 1
) -> CompiledFilter:
    """Compile a FilterOption to PostgreSQL SQL with parameterized queries.

    Generates SQL WHERE clause fragments with parameter placeholders ($1, $2, etc.).

    Args:
        filter_option: FilterOption to compile
        schema: FilterSchema for field information
        param_index: Starting parameter index (default: 1)

    Returns:
        CompiledFilter with SQL fragment and parameters

    Examples:
        >>> schema = FilterSchema(resource="apps", fields={...})
        >>> filter_opt = FilterOption(field="name", op="eq", value="test")
        >>> compiled = compile_filter(filter_opt, schema)
        >>> print(compiled.sql)  # "name = $1"
        >>> print(compiled.params)  # ["test"]

    """
    field_def = schema.fields[filter_option.field]
    column = field_def.column
    op = filter_option.op
    value = filter_option.value

    # Coerce value before compiling
    coerced_value, _ = coerce_value(value, field_def)
    if coerced_value is None and op not in ("isNull", "isNotNull"):
        coerced_value = value

    # Generate SQL based on operator
    if op == "eq":
        sql = f"{column} = ${param_index}"
        params = [coerced_value]
    elif op == "neq":
        sql = f"{column} != ${param_index}"
        params = [coerced_value]
    elif op == "gt":
        sql = f"{column} > ${param_index}"
        params = [coerced_value]
    elif op == "gte":
        sql = f"{column} >= ${param_index}"
        params = [coerced_value]
    elif op == "lt":
        sql = f"{column} < ${param_index}"
        params = [coerced_value]
    elif op == "lte":
        sql = f"{column} <= ${param_index}"
        params = [coerced_value]
    elif op == "in":
        sql = f"{column} = ANY(${param_index})"
        params = [coerced_value]
    elif op == "nin":
        sql = f"{column} != ALL(${param_index})"
        params = [coerced_value]
    elif op == "like":
        sql = f"{column} LIKE ${param_index}"
        params = [coerced_value]
    elif op == "ilike":
        sql = f"{column} ILIKE ${param_index}"
        params = [coerced_value]
    elif op == "contains":
        sql = f"{column} ILIKE ${param_index}"
        params = [f"%{coerced_value}%"]
    elif op == "isNull":
        sql = f"{column} IS NULL"
        params = []
    elif op == "isNotNull":
        sql = f"{column} IS NOT NULL"
        params = []
    else:
        # Fallback for unknown operators
        sql = f"{column} = ${param_index}"
        params = [coerced_value]

    return CompiledFilter(sql=sql, params=params, param_index=param_index + len(params))


def parse_json_filter(json_data: dict) -> List[FilterOption]:
    """Parse JSON format filter into FilterOption list.

    Supports both nested JSON format: {"field": {"op": "value"}}
    and flat format: {"field": "value"} (defaults to "eq" operator).

    Args:
        json_data: Dictionary with filter data in JSON format

    Returns:
        List of FilterOption objects

    Examples:
        >>> json_data = {"status": {"eq": "active"}, "name": {"ilike": "test"}}
        >>> filters = parse_json_filter(json_data)
        >>> len(filters)
        2

    """
    filters: List[FilterOption] = []

    for field, value_spec in json_data.items():
        if isinstance(value_spec, dict):
            # Nested format: {"field": {"op": "value"}}
            for op, value in value_spec.items():
                filters.append(FilterOption(field=field, op=op, value=value))
        else:
            # Flat format: {"field": "value"} (defaults to "eq")
            filters.append(FilterOption(field=field, op="eq", value=value_spec))

    return filters


# Default operators allowed per field type (matches TypeScript DefaultOperatorsByType)
DEFAULT_OPERATORS_BY_TYPE: Dict[str, List[str]] = {
    "string": ["eq", "neq", "in", "nin", "contains", "like", "ilike"],
    "number": ["eq", "neq", "gt", "gte", "lt", "lte", "in", "nin"],
    "boolean": ["eq"],
    "uuid": ["eq", "in"],
    "timestamp": ["eq", "gt", "gte", "lt", "lte"],
    "enum": ["eq", "in"],
}


def validate_filters(
    filters: List[FilterOption], schema: FilterSchema
) -> Tuple[bool, List[FilterError]]:
    """Validate multiple filters against a schema.

    Validates all filters and returns all errors found (not just the first one).

    Args:
        filters: List of FilterOption objects to validate
        schema: FilterSchema to validate against

    Returns:
        Tuple of (is_valid, errors). If valid, errors is an empty list.
        If invalid, errors contains all FilterError objects found.

    Examples:
        >>> schema = FilterSchema(resource="apps", fields={...})
        >>> filters = [
        ...     FilterOption(field="name", op="eq", value="test"),
        ...     FilterOption(field="unknown", op="eq", value="bad"),
        ... ]
        >>> is_valid, errors = validate_filters(filters, schema)
        >>> print(is_valid)  # False
        >>> print(len(errors))  # 1

    """
    errors: List[FilterError] = []

    for filter_option in filters:
        is_valid, error = validate_filter(filter_option, schema)
        if not is_valid and error is not None:
            errors.append(error)

    return len(errors) == 0, errors


def compile_filters(
    filters: List[FilterOption],
    schema: FilterSchema,
    logic: Literal["and", "or"] = "and",
) -> CompiledFilter:
    """Compile multiple filters to PostgreSQL SQL with parameterized queries.

    Combines multiple filter clauses with AND or OR logic.

    Args:
        filters: List of FilterOption objects to compile
        schema: FilterSchema for field information
        logic: Logic operator to join clauses ("and" or "or"), defaults to "and"

    Returns:
        CompiledFilter with combined SQL and parameters

    Raises:
        KeyError: If a filter references a field not in the schema

    Examples:
        >>> schema = FilterSchema(resource="apps", fields={...})
        >>> filters = [
        ...     FilterOption(field="name", op="eq", value="test"),
        ...     FilterOption(field="status", op="eq", value="active"),
        ... ]
        >>> compiled = compile_filters(filters, schema)
        >>> print(compiled.sql)  # "name = $1 AND status = $2"
        >>> print(compiled.params)  # ["test", "active"]

        >>> compiled_or = compile_filters(filters, schema, logic="or")
        >>> print(compiled_or.sql)  # "name = $1 OR status = $2"

    """
    if not filters:
        return CompiledFilter(sql="", params=[], param_index=1)

    clauses: List[str] = []
    params: List[Any] = []
    current_param_index = 1

    for filter_option in filters:
        compiled = compile_filter(filter_option, schema, param_index=current_param_index)
        clauses.append(compiled.sql)
        params.extend(compiled.params)
        current_param_index = compiled.param_index

    join_operator = " OR " if logic == "or" else " AND "
    combined_sql = join_operator.join(clauses)

    return CompiledFilter(sql=combined_sql, params=params, param_index=current_param_index)


def create_filter_schema(
    resource: str,
    fields: Dict[str, Dict[str, Any]],
    version: Optional[str] = None,
) -> FilterSchema:
    """Create a FilterSchema with default operators per field type.

    Convenience function for creating schemas where operators can be omitted
    and will be filled in based on the field type using DEFAULT_OPERATORS_BY_TYPE.

    Args:
        resource: Resource name (e.g., "applications")
        fields: Dictionary of field definitions. Each field should have:
            - column: str (required) - Database column name
            - type: str (required) - Field type (string, number, boolean, uuid, timestamp, enum)
            - operators: List[str] (optional) - Allowed operators (defaults based on type)
            - enum: List[str] (optional) - Enum values (required if type is "enum")
            - nullable: bool (optional) - Whether field can be null
            - description: str (optional) - Field description
        version: Optional schema version string

    Returns:
        FilterSchema with complete field definitions

    Examples:
        >>> schema = create_filter_schema(
        ...     resource="applications",
        ...     fields={
        ...         "name": {"column": "name", "type": "string"},
        ...         "status": {"column": "status", "type": "enum", "enum": ["active", "disabled"]},
        ...     },
        ...     version="1.0"
        ... )
        >>> schema.fields["name"].operators
        ['eq', 'neq', 'in', 'nin', 'contains', 'like', 'ilike']

    """
    complete_fields: Dict[str, FilterFieldDefinition] = {}

    for field_name, field_def in fields.items():
        field_type = field_def.get("type", "string")

        # Use provided operators or default based on type
        operators_raw = field_def.get("operators") or DEFAULT_OPERATORS_BY_TYPE.get(
            field_type, ["eq"]
        )
        operators = cast(List[FilterOperator], operators_raw)

        complete_fields[field_name] = FilterFieldDefinition(
            column=field_def["column"],
            type=cast(
                Literal["string", "number", "boolean", "uuid", "timestamp", "enum"], field_type
            ),
            operators=operators,
            enum=field_def.get("enum"),
            nullable=field_def.get("nullable"),
            description=field_def.get("description"),
        )

    return FilterSchema(resource=resource, version=version, fields=complete_fields)
