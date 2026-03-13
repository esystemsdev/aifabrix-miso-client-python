"""Filter utilities for MisoClient SDK.

This module provides reusable filter utilities for parsing filter parameters,
building query strings, and applying filters to arrays.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Tuple, cast
from urllib.parse import parse_qs, quote, urlparse

if TYPE_CHECKING:
    from ..models.filter_schema import FilterError, FilterSchema

from ..models.filter import FilterOption, FilterQuery, JsonFilter
from .filter_applier import apply_filters  # noqa: F401
from .filter_parser import parse_filter_params  # noqa: F401

VALID_FILTER_OPERATORS = {
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
    "ilike",
    "isNull",
    "isNotNull",
}


def _build_filter_query_part(filter_option: FilterOption) -> str:
    """Build a single filter query segment."""
    field_encoded = quote(filter_option.field)
    if filter_option.op in ("isNull", "isNotNull"):
        return f"filter={field_encoded}:{filter_option.op}"

    if isinstance(filter_option.value, list):
        value_str = ",".join(quote(str(v)) for v in filter_option.value)
    elif filter_option.value is not None:
        value_str = quote(str(filter_option.value))
    else:
        value_str = ""
    return f"filter={field_encoded}:{filter_option.op}:{value_str}"


def _parse_optional_int(params: Dict[str, Any], key: str) -> Optional[int]:
    """Parse optional integer value from parsed query params."""
    if key not in params:
        return None
    raw_value = params[key][0] if isinstance(params[key], list) else params[key]
    try:
        return int(raw_value)
    except (ValueError, TypeError):
        return None


def _parse_sort(params: Dict[str, Any]) -> Optional[List[str]]:
    """Parse sort list from query params."""
    if "sort" not in params:
        return None
    sort_values = params["sort"]
    if isinstance(sort_values, list):
        return [value for value in sort_values if isinstance(value, str)]
    if isinstance(sort_values, str):
        return [sort_values]
    return None


def _parse_fields(params: Dict[str, Any]) -> Optional[List[str]]:
    """Parse fields selector list from query params."""
    if "fields" not in params:
        return None
    fields_raw = params["fields"][0] if isinstance(params["fields"], list) else params["fields"]
    if not isinstance(fields_raw, str):
        return None
    fields = [field.strip() for field in fields_raw.split(",") if field.strip()]
    return fields or None


def _validate_group_structure(group: Any) -> bool:
    """Validate one logical group structure (including nested groups)."""
    if not isinstance(group, dict):
        return False
    if "operator" not in group or group["operator"] not in ["and", "or"]:
        return False

    if "filters" in group and group["filters"] is not None:
        if not isinstance(group["filters"], list):
            return False
        for filter_option in group["filters"]:
            if not validate_filter_option(filter_option):
                return False

    if "groups" in group and group["groups"] is not None:
        if not isinstance(group["groups"], list):
            return False
        for nested_group in group["groups"]:
            if not isinstance(nested_group, dict):
                return False
            if "operator" not in nested_group:
                return False
    return True


def _validate_string_list(value: Any) -> bool:
    """Return True when value is a list[str]."""
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_filters_payload(value: Any) -> bool:
    """Validate top-level filters payload list."""
    if value is None:
        return True
    if not isinstance(value, list):
        return False
    return all(validate_filter_option(filter_option) for filter_option in value)


def _validate_groups_payload(value: Any) -> bool:
    """Validate top-level groups payload list."""
    if value is None:
        return True
    if not isinstance(value, list):
        return False
    return all(_validate_group_structure(group) for group in value)


def build_query_string(filter_query: FilterQuery) -> str:
    """Convert FilterQuery object to query string."""
    query_parts: List[str] = []

    if filter_query.filters:
        for filter_option in filter_query.filters:
            query_parts.append(_build_filter_query_part(filter_option))

    # Add sort
    if filter_query.sort:
        for sort_field in filter_query.sort:
            query_parts.append(f"sort={quote(sort_field)}")

    # Add pagination
    if filter_query.page is not None:
        query_parts.append(f"page={filter_query.page}")

    if filter_query.pageSize is not None:
        query_parts.append(f"pageSize={filter_query.pageSize}")

    # Add fields
    if filter_query.fields:
        fields_str = ",".join(quote(f) for f in filter_query.fields)
        query_parts.append(f"fields={fields_str}")

    return "&".join(query_parts)


def filter_query_to_json(filter_query: FilterQuery) -> Dict[str, Any]:
    """Convert FilterQuery to JSON dict (camelCase).

    Args:
        filter_query: FilterQuery instance

    Returns:
        Dictionary with filter data in camelCase format

    Examples:
        >>> from miso_client.models.filter import FilterQuery, FilterOption
        >>> query = FilterQuery(
        ...     filters=[FilterOption(field='status', op='eq', value='active')],
        ...     page=1,
        ...     pageSize=25
        ... )
        >>> filter_query_to_json(query)
        {'filters': [...], 'page': 1, 'pageSize': 25}

    """
    return filter_query.to_json()


def json_to_filter_query(json_data: Dict[str, Any]) -> FilterQuery:
    """Convert JSON dict to FilterQuery.

    Args:
        json_data: Dictionary with filter data (camelCase or snake_case)

    Returns:
        FilterQuery instance

    Examples:
        >>> json_data = {'filters': [{'field': 'status', 'op': 'eq', 'value': 'active'}]}
        >>> json_to_filter_query(json_data)
        FilterQuery(filters=[FilterOption(...)])

    """
    return FilterQuery.from_json(json_data)


def json_filter_to_query_string(json_filter: JsonFilter) -> str:
    """Convert JsonFilter to query string.

    Args:
        json_filter: JsonFilter instance

    Returns:
        Query string (e.g., 'filter=status:eq:active&page=1&pageSize=25')

    Examples:
        >>> from miso_client.models.filter import JsonFilter, FilterOption
        >>> json_filter = JsonFilter(
        ...     filters=[FilterOption(field='status', op='eq', value='active')],
        ...     page=1,
        ...     pageSize=25
        ... )
        >>> json_filter_to_query_string(json_filter)
        'filter=status:eq:active&page=1&pageSize=25'

    """
    # Convert JsonFilter to FilterQuery, then use existing build_query_string
    filter_query = FilterQuery(
        filters=json_filter.filters,
        sort=json_filter.sort,
        page=json_filter.page,
        pageSize=json_filter.pageSize,
        fields=json_filter.fields,
    )
    return build_query_string(filter_query)


def query_string_to_json_filter(query_string: str) -> JsonFilter:
    """Convert query string to JsonFilter.

    Args:
        query_string: Query string (e.g., '?filter=status:eq:active&page=1&pageSize=25')

    Returns:
        JsonFilter instance

    Examples:
        >>> query_string = '?filter=status:eq:active&page=1&pageSize=25'
        >>> json_filter = query_string_to_json_filter(query_string)
        >>> json_filter.filters[0].field
        'status'

    """
    if query_string.startswith("?"):
        query_string = query_string[1:]

    parsed = urlparse(f"?{query_string}")
    params = parse_qs(parsed.query)
    filters = parse_filter_params(params)
    return JsonFilter(
        filters=filters if filters else None,
        sort=_parse_sort(params),
        page=_parse_optional_int(params, "page"),
        pageSize=_parse_optional_int(params, "pageSize"),
        fields=_parse_fields(params),
    )


def validate_filter_option(option: Dict[str, Any]) -> bool:
    """Validate single filter option structure."""
    if not isinstance(option, dict):
        return False

    # Check required fields
    if "field" not in option or "op" not in option:
        return False

    if option["op"] not in VALID_FILTER_OPERATORS:
        return False

    # Value is optional for null check operators
    if option["op"] not in ("isNull", "isNotNull") and "value" not in option:
        return False

    # Validate field is string
    if not isinstance(option["field"], str):
        return False

    return True


def validate_json_filter(json_data: Dict[str, Any]) -> bool:
    """Validate JSON filter structure."""
    if not isinstance(json_data, dict):
        return False

    if not _validate_filters_payload(json_data.get("filters")):
        return False
    if not _validate_groups_payload(json_data.get("groups")):
        return False

    if (
        "sort" in json_data
        and json_data["sort"] is not None
        and not _validate_string_list(json_data["sort"])
    ):
        return False

    if "page" in json_data and json_data["page"] is not None:
        if not isinstance(json_data["page"], int):
            return False

    if "pageSize" in json_data and json_data["pageSize"] is not None:
        if not isinstance(json_data["pageSize"], int):
            return False

    if (
        "fields" in json_data
        and json_data["fields"] is not None
        and not _validate_string_list(json_data["fields"])
    ):
        return False

    return True


def validate_filter_with_schema(
    filter_option: FilterOption, schema: "FilterSchema"
) -> Tuple[bool, Optional["FilterError"]]:
    """Validate a FilterOption against a FilterSchema.

    Convenience wrapper around filter_schema.validate_filter().

    Args:
        filter_option: FilterOption to validate
        schema: FilterSchema to validate against

    Returns:
        Tuple of (is_valid, error). If valid, error is None.
        If invalid, error is a FilterError with RFC 7807 compliant structure.

    Examples:
        >>> from miso_client.models.filter import FilterOption
        >>> from miso_client.models.filter_schema import FilterSchema
        >>> schema = FilterSchema(resource="apps", fields={...})
        >>> filter_opt = FilterOption(field="name", op="eq", value="test")
        >>> is_valid, error = validate_filter_with_schema(filter_opt, schema)

    """
    from .filter_schema import validate_filter

    return validate_filter(filter_option, schema)


def coerce_filter_value(
    value: Any, field_type: str, enum_values: Optional[List[str]] = None
) -> Tuple[Any, Optional["FilterError"]]:
    """Coerce and validate a filter value based on field type."""
    from ..models.filter_schema import FilterFieldDefinition
    from .filter_schema import coerce_value

    valid_types = {"string", "number", "boolean", "uuid", "timestamp", "enum"}
    normalized_type = field_type if field_type in valid_types else "string"
    field_def = FilterFieldDefinition(
        column="temp",
        type=cast(
            Literal["string", "number", "boolean", "uuid", "timestamp", "enum"],
            normalized_type,
        ),
        operators=["eq"],
        enum=enum_values,
    )
    return coerce_value(value, field_def)
