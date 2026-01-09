"""
Filter utilities for MisoClient SDK.

This module provides reusable filter utilities for parsing filter parameters,
building query strings, and applying filters to arrays.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote, urlparse

from ..models.filter import FilterQuery, JsonFilter
from .filter_applier import apply_filters  # noqa: F401
from .filter_parser import parse_filter_params  # noqa: F401


def build_query_string(filter_query: FilterQuery) -> str:
    """
    Convert FilterQuery object to query string.

    Builds query string with filter, sort, page, pageSize, and fields parameters.

    Args:
        filter_query: FilterQuery object with filters, sort, pagination, and fields

    Returns:
        Query string (e.g., '?filter=status:eq:active&page=1&pageSize=25&sort=-updated_at')

    Examples:
        >>> from miso_client.models.filter import FilterQuery, FilterOption
        >>> query = FilterQuery(
        ...     filters=[FilterOption(field='status', op='eq', value='active')],
        ...     page=1,
        ...     pageSize=25
        ... )
        >>> build_query_string(query)
        'filter=status:eq:active&page=1&pageSize=25'
    """
    query_parts: List[str] = []

    # Add filters
    if filter_query.filters:
        for filter_option in filter_query.filters:
            # URL encode field
            field_encoded = quote(filter_option.field)

            # Handle null check operators (no value needed)
            if filter_option.op in ("isNull", "isNotNull"):
                query_parts.append(f"filter={field_encoded}:{filter_option.op}")
            else:
                # Format value for query string
                if isinstance(filter_option.value, list):
                    # For arrays (in/nin), join with commas (don't encode the comma delimiter)
                    # URL encode each value individually, then join with comma
                    value_parts = [quote(str(v)) for v in filter_option.value]
                    value_str = ",".join(value_parts)
                elif filter_option.value is not None:
                    value_str = quote(str(filter_option.value))
                else:
                    # Value is None but operator requires value - skip or use empty string
                    value_str = ""

                query_parts.append(f"filter={field_encoded}:{filter_option.op}:{value_str}")

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
    """
    Convert FilterQuery to JSON dict (camelCase).

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
    """
    Convert JSON dict to FilterQuery.

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
    """
    Convert JsonFilter to query string.

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
    """
    Convert query string to JsonFilter.

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
    # Remove leading ? if present
    if query_string.startswith("?"):
        query_string = query_string[1:]

    # Parse query string
    parsed = urlparse(f"?{query_string}")
    params = parse_qs(parsed.query)

    # Parse filters
    filters = parse_filter_params(params)

    # Parse sort
    sort: Optional[List[str]] = None
    if "sort" in params:
        sort_list = params["sort"]
        if isinstance(sort_list, list):
            sort = [s for s in sort_list if isinstance(s, str)]
        elif isinstance(sort_list, str):
            sort = [sort_list]

    # Parse pagination
    page: Optional[int] = None
    if "page" in params:
        page_str = params["page"][0] if isinstance(params["page"], list) else params["page"]
        try:
            page = int(page_str)
        except (ValueError, TypeError):
            pass

    page_size: Optional[int] = None
    if "pageSize" in params:
        page_size_str = (
            params["pageSize"][0] if isinstance(params["pageSize"], list) else params["pageSize"]
        )
        try:
            page_size = int(page_size_str)
        except (ValueError, TypeError):
            pass

    # Parse fields
    fields: Optional[List[str]] = None
    if "fields" in params:
        fields_str = params["fields"][0] if isinstance(params["fields"], list) else params["fields"]
        if isinstance(fields_str, str):
            fields = [f.strip() for f in fields_str.split(",") if f.strip()]

    return JsonFilter(
        filters=filters if filters else None,
        sort=sort,
        page=page,
        pageSize=page_size,
        fields=fields,
    )


def validate_filter_option(option: Dict[str, Any]) -> bool:
    """
    Validate single filter option structure.

    Args:
        option: Dictionary with filter option data

    Returns:
        True if valid, False otherwise

    Examples:
        >>> validate_filter_option({'field': 'status', 'op': 'eq', 'value': 'active'})
        True
        >>> validate_filter_option({'field': 'status'})  # Missing op/value
        False
    """
    if not isinstance(option, dict):
        return False

    # Check required fields
    if "field" not in option or "op" not in option:
        return False

    # Validate operator
    valid_operators = [
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
        "isNull",
        "isNotNull",
    ]
    if option["op"] not in valid_operators:
        return False

    # Value is optional for null check operators
    if option["op"] not in ("isNull", "isNotNull") and "value" not in option:
        return False

    # Validate field is string
    if not isinstance(option["field"], str):
        return False

    return True


def validate_json_filter(json_data: Dict[str, Any]) -> bool:
    """
    Validate JSON filter structure.

    Args:
        json_data: Dictionary with filter data

    Returns:
        True if valid, False otherwise

    Examples:
        >>> json_data = {
        ...     'filters': [{'field': 'status', 'op': 'eq', 'value': 'active'}],
        ...     'page': 1,
        ...     'pageSize': 25
        ... }
        >>> validate_json_filter(json_data)
        True
    """
    if not isinstance(json_data, dict):
        return False

    # Validate filters if present
    if "filters" in json_data and json_data["filters"] is not None:
        if not isinstance(json_data["filters"], list):
            return False
        for filter_option in json_data["filters"]:
            if not validate_filter_option(filter_option):
                return False

    # Validate groups if present
    if "groups" in json_data and json_data["groups"] is not None:
        if not isinstance(json_data["groups"], list):
            return False
        for group in json_data["groups"]:
            if not isinstance(group, dict):
                return False
            if "operator" not in group:
                return False
            if group["operator"] not in ["and", "or"]:
                return False
            # Validate filters in group
            if "filters" in group and group["filters"] is not None:
                if not isinstance(group["filters"], list):
                    return False
                for filter_option in group["filters"]:
                    if not validate_filter_option(filter_option):
                        return False
            # Validate nested groups recursively
            if "groups" in group and group["groups"] is not None:
                if not isinstance(group["groups"], list):
                    return False
                for nested_group in group["groups"]:
                    if not isinstance(nested_group, dict):
                        return False
                    # Recursive validation (simplified - just check structure)
                    if "operator" not in nested_group:
                        return False

    # Validate sort if present
    if "sort" in json_data and json_data["sort"] is not None:
        if not isinstance(json_data["sort"], list):
            return False
        for sort_item in json_data["sort"]:
            if not isinstance(sort_item, str):
                return False

    # Validate page if present
    if "page" in json_data and json_data["page"] is not None:
        if not isinstance(json_data["page"], int):
            return False

    # Validate pageSize if present
    if "pageSize" in json_data and json_data["pageSize"] is not None:
        if not isinstance(json_data["pageSize"], int):
            return False

    # Validate fields if present
    if "fields" in json_data and json_data["fields"] is not None:
        if not isinstance(json_data["fields"], list):
            return False
        for field in json_data["fields"]:
            if not isinstance(field, str):
                return False

    return True
