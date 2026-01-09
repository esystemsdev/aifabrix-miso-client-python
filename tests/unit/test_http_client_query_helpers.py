"""
Unit tests for HTTP client query helpers.

Tests the extracted filter and pagination helper functions from http_client.py.
"""

from miso_client.models.filter import FilterBuilder, FilterOption, FilterQuery, JsonFilter
from miso_client.models.pagination import PaginatedListResponse
from miso_client.utils.http_client_query_helpers import (
    add_pagination_params,
    merge_filter_params,
    parse_filter_query_string,
    parse_paginated_response,
    prepare_filter_params,
    prepare_json_filter_body,
)


class TestParseFilterQueryString:
    """Test cases for parse_filter_query_string function."""

    def test_parse_filter_query_string_single_value(self):
        """Test parsing query string with single value."""
        query_string = "filter=status:eq:active"
        result = parse_filter_query_string(query_string)

        assert "filter" in result
        assert result["filter"] == "status:eq:active"

    def test_parse_filter_query_string_multiple_filters(self):
        """Test parsing query string with multiple filters."""
        query_string = "filter=status:eq:active&filter=region:in:eu,us"
        result = parse_filter_query_string(query_string)

        assert "filter" in result
        # Should be a list for multiple values
        assert isinstance(result["filter"], list) or isinstance(result["filter"], str)

    def test_parse_filter_query_string_with_pagination(self):
        """Test parsing query string with pagination."""
        query_string = "filter=status:eq:active&page=1&pageSize=25"
        result = parse_filter_query_string(query_string)

        assert "filter" in result
        assert "page" in result
        assert "pageSize" in result


class TestMergeFilterParams:
    """Test cases for merge_filter_params function."""

    def test_merge_filter_params_no_existing(self):
        """Test merging filter params when no existing params."""
        kwargs = {}
        filter_params = {"filter": "status:eq:active"}

        merge_filter_params(kwargs, filter_params)

        assert kwargs["params"] == filter_params

    def test_merge_filter_params_with_existing(self):
        """Test merging filter params with existing params."""
        kwargs = {"params": {"other": "value"}}
        filter_params = {"filter": "status:eq:active"}

        merge_filter_params(kwargs, filter_params)

        assert kwargs["params"]["filter"] == "status:eq:active"
        assert kwargs["params"]["other"] == "value"


class TestAddPaginationParams:
    """Test cases for add_pagination_params function."""

    def test_add_pagination_params_both(self):
        """Test adding both page and page_size."""
        kwargs = {}
        add_pagination_params(kwargs, page=1, page_size=25)

        assert kwargs["params"]["page"] == 1
        assert kwargs["params"]["pageSize"] == 25

    def test_add_pagination_params_only_page(self):
        """Test adding only page."""
        kwargs = {}
        add_pagination_params(kwargs, page=2, page_size=None)

        assert kwargs["params"]["page"] == 2
        assert "pageSize" not in kwargs["params"]

    def test_add_pagination_params_only_page_size(self):
        """Test adding only page_size."""
        kwargs = {}
        add_pagination_params(kwargs, page=None, page_size=50)

        assert kwargs["params"]["pageSize"] == 50
        assert "page" not in kwargs["params"]

    def test_add_pagination_params_with_existing(self):
        """Test adding pagination params with existing params."""
        kwargs = {"params": {"other": "value"}}
        add_pagination_params(kwargs, page=1, page_size=25)

        assert kwargs["params"]["page"] == 1
        assert kwargs["params"]["pageSize"] == 25
        assert kwargs["params"]["other"] == "value"

    def test_add_pagination_params_none(self):
        """Test adding pagination params with None values."""
        kwargs = {}
        add_pagination_params(kwargs, page=None, page_size=None)

        # Should not add params if both are None
        assert "params" not in kwargs or kwargs.get("params") == {}


class TestParsePaginatedResponse:
    """Test cases for parse_paginated_response function."""

    def test_parse_paginated_response_valid(self):
        """Test parsing valid paginated response."""
        response_data = {
            "meta": {"totalItems": 120, "currentPage": 1, "pageSize": 25, "type": "item"},
            "data": [{"id": 1}, {"id": 2}],
        }

        result = parse_paginated_response(response_data)

        assert isinstance(result, PaginatedListResponse)
        assert result.meta.totalItems == 120
        assert result.meta.currentPage == 1
        assert result.meta.pageSize == 25
        assert len(result.data) == 2

    def test_parse_paginated_response_invalid(self):
        """Test parsing invalid paginated response (should return as-is)."""
        response_data = {"items": [{"id": 1}], "total": 10}

        result = parse_paginated_response(response_data)

        # Should return raw response if format doesn't match
        assert result == response_data

    def test_parse_paginated_response_empty(self):
        """Test parsing empty response."""
        response_data = {}

        result = parse_paginated_response(response_data)

        # Should return raw response if format doesn't match
        assert result == response_data


class TestPrepareFilterParams:
    """Test cases for prepare_filter_params function."""

    def test_prepare_filter_params_with_filter_builder(self):
        """Test preparing filter params from FilterBuilder."""
        filter_builder = FilterBuilder().add("status", "eq", "active")

        result = prepare_filter_params(filter_builder)

        assert result is not None
        assert "filter" in result

    def test_prepare_filter_params_no_filter_builder(self):
        """Test preparing filter params without FilterBuilder."""
        result = prepare_filter_params(None)

        assert result is None

    def test_prepare_filter_params_empty_filter_builder(self):
        """Test preparing filter params with empty FilterBuilder."""
        filter_builder = FilterBuilder()

        result = prepare_filter_params(filter_builder)

        # Should return None if no filters
        assert result is None


class TestPrepareJsonFilterBody:
    """Test cases for prepare_json_filter_body function."""

    def test_prepare_json_filter_body_with_json_filter(self):
        """Test preparing body with JsonFilter."""
        json_filter = JsonFilter(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )

        result = prepare_json_filter_body(json_filter)

        assert "filters" in result
        assert result["page"] == 1
        assert result["pageSize"] == 25

    def test_prepare_json_filter_body_with_filter_query(self):
        """Test preparing body with FilterQuery."""
        filter_query = FilterQuery(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )

        result = prepare_json_filter_body(filter_query)

        assert "filters" in result
        assert result["page"] == 1
        assert result["pageSize"] == 25

    def test_prepare_json_filter_body_with_dict(self):
        """Test preparing body with dict filter."""
        filter_dict = {"filters": [{"field": "status", "op": "eq", "value": "active"}]}

        result = prepare_json_filter_body(filter_dict)

        assert "filters" in result

    def test_prepare_json_filter_body_with_json_body(self):
        """Test preparing body with existing JSON body."""
        json_filter = JsonFilter(filters=[FilterOption(field="status", op="eq", value="active")])
        json_body = {"includeMetadata": True, "otherField": "value"}

        result = prepare_json_filter_body(json_filter, json_body)

        assert "filters" in result
        assert result["includeMetadata"] is True
        assert result["otherField"] == "value"

    def test_prepare_json_filter_body_no_filter(self):
        """Test preparing body without filter."""
        json_body = {"includeMetadata": True}

        result = prepare_json_filter_body(None, json_body)

        assert result == json_body

    def test_prepare_json_filter_body_no_body_no_filter(self):
        """Test preparing body with neither filter nor body."""
        result = prepare_json_filter_body(None, None)

        assert result == {}
