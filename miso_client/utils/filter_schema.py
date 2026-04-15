"""Filter schema validation and SQL compilation utilities for MisoClient SDK.

This module provides utilities for validating filters against schemas,
coercing values to appropriate types, and compiling filters to SQL.
"""

from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple, cast

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


def _build_unknown_field_error(field: str, resource: str) -> FilterError:
    """Create unknown-field error response."""
    return FilterError(
        type=ERROR_TYPE_UNKNOWN_FIELD,
        title="Unknown Field",
        statusCode=400,
        errors=[f"Field '{field}' is not filterable for resource '{resource}'"],
    )


def _build_invalid_operator_error(field: str, op: str, allowed: Sequence[str]) -> FilterError:
    """Create invalid-operator error response."""
    return FilterError(
        type=ERROR_TYPE_INVALID_OPERATOR,
        title="Invalid Operator",
        statusCode=400,
        errors=[
            f"Operator '{op}' is not allowed for field '{field}'. "
            f"Allowed operators: {', '.join(allowed)}"
        ],
    )


def validate_filter(
    filter_option: FilterOption, schema: FilterSchema
) -> Tuple[bool, Optional[FilterError]]:
    """Validate a FilterOption against a FilterSchema."""
    if filter_option.field not in schema.fields:
        return False, _build_unknown_field_error(filter_option.field, schema.resource)

    field_def = schema.fields[filter_option.field]
    if filter_option.op not in field_def.operators:
        return False, _build_invalid_operator_error(
            filter_option.field, filter_option.op, field_def.operators
        )

    if filter_option.op not in ("isNull", "isNotNull"):
        _, error = coerce_value(filter_option.value, field_def)
        if error:
            return False, error

    return True, None


def coerce_value(value: Any, field_def: FilterFieldDefinition) -> Tuple[Any, Optional[FilterError]]:
    """Coerce and validate a value based on field definition type."""
    field_type = field_def.type

    if isinstance(value, list):
        coerced_list = []
        for item in value:
            coerced_item, error = coerce_single_value(item, field_type, field_def.enum)
            if error:
                return None, error
            coerced_list.append(coerced_item)
        return coerced_list, None

    return coerce_single_value(value, field_type, field_def.enum)


def _compile_sql_clause(
    column: str, op: FilterOperator, value: Any, param_index: int
) -> Tuple[str, List[Any]]:
    """Compile one filter operator into SQL clause and params."""
    if op == "isNull":
        return f"{column} IS NULL", []
    if op == "isNotNull":
        return f"{column} IS NOT NULL", []
    if op == "contains":
        return f"{column} ILIKE ${param_index}", [f"%{value}%"]

    clause_map: Dict[FilterOperator, str] = {
        "eq": "=",
        "neq": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "like": "LIKE",
        "ilike": "ILIKE",
    }
    if op in clause_map:
        return f"{column} {clause_map[op]} ${param_index}", [value]
    if op == "in":
        return f"{column} = ANY(${param_index})", [value]
    if op == "nin":
        return f"{column} != ALL(${param_index})", [value]
    return f"{column} = ${param_index}", [value]


def compile_filter(
    filter_option: FilterOption, schema: FilterSchema, param_index: int = 1
) -> CompiledFilter:
    """Compile a FilterOption into parameterized SQL fragment."""
    field_def = schema.fields[filter_option.field]
    column = field_def.column
    op = filter_option.op
    value = filter_option.value

    coerced_value, _ = coerce_value(value, field_def)
    if coerced_value is None and op not in ("isNull", "isNotNull"):
        coerced_value = value

    sql, params = _compile_sql_clause(column, op, coerced_value, param_index)

    return CompiledFilter(sql=sql, params=params, param_index=param_index + len(params))


def parse_json_filter(json_data: dict) -> List[FilterOption]:
    """Parse JSON filter payload into FilterOption list."""
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
    """Validate multiple filters against a schema."""
    errors = [
        error
        for filter_option in filters
        for is_valid, error in [validate_filter(filter_option, schema)]
        if not is_valid and error is not None
    ]
    return len(errors) == 0, errors


def compile_filters(
    filters: List[FilterOption],
    schema: FilterSchema,
    logic: Literal["and", "or"] = "and",
) -> CompiledFilter:
    """Compile multiple filters into one parameterized SQL fragment."""
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


def _build_field_definition(field_def: Dict[str, Any]) -> FilterFieldDefinition:
    """Build one FilterFieldDefinition from raw schema dict."""
    field_type = field_def.get("type", "string")
    operators_raw = field_def.get("operators") or DEFAULT_OPERATORS_BY_TYPE.get(field_type, ["eq"])
    operators = cast(List[FilterOperator], operators_raw)
    return FilterFieldDefinition(
        column=field_def["column"],
        type=cast(Literal["string", "number", "boolean", "uuid", "timestamp", "enum"], field_type),
        operators=operators,
        enum=field_def.get("enum"),
        nullable=field_def.get("nullable"),
        description=field_def.get("description"),
    )


def create_filter_schema(
    resource: str,
    fields: Dict[str, Dict[str, Any]],
    version: Optional[str] = None,
) -> FilterSchema:
    """Create a FilterSchema with default operators by field type."""
    complete_fields = {
        field_name: _build_field_definition(field_def) for field_name, field_def in fields.items()
    }

    return FilterSchema(resource=resource, version=version, fields=complete_fields)
