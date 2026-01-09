"""
HTTP client query helpers for filters and pagination.

Extracted from http_client.py to reduce file size and improve maintainability.
"""

from typing import Any, Dict, Optional, Union
from urllib.parse import parse_qs, urlparse

from ..models.filter import FilterBuilder, FilterQuery, JsonFilter
from ..models.pagination import PaginatedListResponse
from ..utils.filter import build_query_string


def parse_filter_query_string(query_string: str) -> Dict[str, Any]:
    """
    Parse filter query string into params dictionary.

    Args:
        query_string: Query string from FilterQuery

    Returns:
        Params dictionary with filters
    """
    query_params = parse_qs(query_string)
    return {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}


def merge_filter_params(kwargs: Dict[str, Any], filter_params: Dict[str, Any]) -> None:
    """
    Merge filter params with existing params.

    Args:
        kwargs: Request kwargs dictionary
        filter_params: Filter params from FilterBuilder
    """
    existing_params = kwargs.get("params", {})
    if existing_params:
        merged_params = {**existing_params, **filter_params}
    else:
        merged_params = filter_params
    kwargs["params"] = merged_params


def add_pagination_params(
    kwargs: Dict[str, Any], page: Optional[int], page_size: Optional[int]
) -> None:
    """
    Add pagination params to kwargs.

    Args:
        kwargs: Request kwargs dictionary
        page: Optional page number (1-based)
        page_size: Optional number of items per page
    """
    params = kwargs.get("params", {})
    if page is not None:
        params["page"] = page
    if page_size is not None:
        params["pageSize"] = page_size

    if params:
        kwargs["params"] = params


def parse_paginated_response(response_data: Any) -> Any:
    """
    Parse response as PaginatedListResponse if possible.

    Args:
        response_data: Response data from API

    Returns:
        PaginatedListResponse if format matches, otherwise raw response
    """
    try:
        return PaginatedListResponse(**response_data)
    except Exception:
        # If response doesn't match PaginatedListResponse format, return as-is
        # This allows flexibility for different response formats
        return response_data


def prepare_filter_params(filter_builder: Optional[FilterBuilder]) -> Optional[Dict[str, Any]]:
    """
    Prepare filter parameters from FilterBuilder.

    Args:
        filter_builder: Optional FilterBuilder instance

    Returns:
        Dictionary of filter parameters, or None if no filters
    """
    if not filter_builder:
        return None

    filter_query = FilterQuery(filters=filter_builder.build())
    query_string = build_query_string(filter_query)

    if query_string:
        # Parse query string into params dict
        parsed = urlparse(f"?{query_string}")
        params = parse_qs(parsed.query)
        # Convert lists to single values where appropriate
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}

    return None


def prepare_json_filter_body(
    json_filter: Optional[Union[JsonFilter, FilterQuery, Dict[str, Any]]],
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Prepare JSON body with filter data.

    Args:
        json_filter: Optional JsonFilter, FilterQuery, or dict
        json_body: Optional existing JSON body

    Returns:
        Dictionary with merged filter and body data
    """
    request_body: Dict[str, Any] = {}
    if json_body:
        request_body.update(json_body)

    if json_filter:
        if isinstance(json_filter, JsonFilter):
            filter_dict = json_filter.model_dump(exclude_none=True)
        elif isinstance(json_filter, FilterQuery):
            filter_dict = json_filter.to_json()
        else:
            filter_dict = json_filter

        request_body.update(filter_dict)

    return request_body
