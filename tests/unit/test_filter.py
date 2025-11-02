"""
Unit tests for filter utilities.

This module contains comprehensive tests for filter utilities including
parse_filter_params, build_query_string, apply_filters, and FilterBuilder class.
"""

from miso_client.models.filter import FilterBuilder, FilterOperator, FilterOption, FilterQuery
from miso_client.utils.filter import apply_filters, build_query_string, parse_filter_params


class TestParseFilterParams:
    """Test cases for parse_filter_params function."""

    def test_parse_single_filter_string(self):
        """Test parsing single filter string."""
        params = {"filter": "status:eq:active"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].field == "status"
        assert filters[0].op == "eq"
        assert filters[0].value == "active"

    def test_parse_multiple_filters_list(self):
        """Test parsing multiple filters as list."""
        params = {"filter": ["status:eq:active", "region:in:eu,us"]}
        filters = parse_filter_params(params)

        assert len(filters) == 2
        assert filters[0].field == "status"
        assert filters[0].op == "eq"
        assert filters[1].field == "region"
        assert filters[1].op == "in"
        assert filters[1].value == ["eu", "us"]

    def test_parse_filter_with_in_operator(self):
        """Test parsing filter with 'in' operator (array values)."""
        params = {"filter": "region:in:eu,us,uk"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].op == "in"
        assert filters[0].value == ["eu", "us", "uk"]

    def test_parse_filter_with_nin_operator(self):
        """Test parsing filter with 'nin' operator (array values)."""
        params = {"filter": "status:nin:deleted,archived"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].op == "nin"
        assert filters[0].value == ["deleted", "archived"]

    def test_parse_filter_with_numeric_value(self):
        """Test parsing filter with numeric value."""
        params = {"filter": "age:gt:18"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].op == "gt"
        assert isinstance(filters[0].value, int)
        assert filters[0].value == 18

    def test_parse_filter_with_float_value(self):
        """Test parsing filter with float value."""
        params = {"filter": "price:gte:99.99"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].op == "gte"
        assert isinstance(filters[0].value, float)
        assert filters[0].value == 99.99

    def test_parse_filter_with_boolean_value(self):
        """Test parsing filter with boolean value."""
        params = {"filter": "active:eq:true"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].value is True

    def test_parse_filter_empty_params(self):
        """Test parsing empty params."""
        params = {}
        filters = parse_filter_params(params)

        assert len(filters) == 0

    def test_parse_filter_invalid_format(self):
        """Test parsing filter with invalid format."""
        params = {"filter": "invalid-format"}
        filters = parse_filter_params(params)

        assert len(filters) == 0

    def test_parse_filter_invalid_operator(self):
        """Test parsing filter with invalid operator."""
        params = {"filter": "field:invalid_op:value"}
        filters = parse_filter_params(params)

        assert len(filters) == 0

    def test_parse_filter_url_encoded(self):
        """Test parsing URL-encoded filter values."""
        from urllib.parse import quote

        field = quote("user name")
        value = quote("john doe")
        params = {"filter": f"{field}:eq:{value}"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].field == "user name"
        assert filters[0].value == "john doe"

    def test_parse_filter_alternative_key(self):
        """Test parsing filter with alternative key name."""
        params = {"filters": "status:eq:active"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].field == "status"


class TestBuildQueryString:
    """Test cases for build_query_string function."""

    def test_build_query_string_single_filter(self):
        """Test building query string with single filter."""
        filter_query = FilterQuery(filters=[FilterOption(field="status", op="eq", value="active")])
        query_string = build_query_string(filter_query)

        assert "filter=status:eq:active" in query_string

    def test_build_query_string_multiple_filters(self):
        """Test building query string with multiple filters."""
        filter_query = FilterQuery(
            filters=[
                FilterOption(field="status", op="eq", value="active"),
                FilterOption(field="region", op="in", value=["eu", "us"]),
            ]
        )
        query_string = build_query_string(filter_query)

        assert "filter=status:eq:active" in query_string
        assert "filter=region:in:eu,us" in query_string

    def test_build_query_string_with_sort(self):
        """Test building query string with sort."""
        filter_query = FilterQuery(
            filters=[FilterOption(field="status", op="eq", value="active")],
            sort=["-updated_at", "created_at"],
        )
        query_string = build_query_string(filter_query)

        assert "filter=status:eq:active" in query_string
        assert "sort=-updated_at" in query_string
        assert "sort=created_at" in query_string

    def test_build_query_string_with_pagination(self):
        """Test building query string with pagination."""
        filter_query = FilterQuery(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )
        query_string = build_query_string(filter_query)

        assert "filter=status:eq:active" in query_string
        assert "page=1" in query_string
        assert "pageSize=25" in query_string

    def test_build_query_string_with_fields(self):
        """Test building query string with fields selection."""
        filter_query = FilterQuery(
            filters=[FilterOption(field="status", op="eq", value="active")],
            fields=["id", "name", "status"],
        )
        query_string = build_query_string(filter_query)

        assert "filter=status:eq:active" in query_string
        assert "fields=" in query_string

    def test_build_query_string_complete(self):
        """Test building complete query string with all options."""
        filter_query = FilterQuery(
            filters=[
                FilterOption(field="status", op="eq", value="active"),
                FilterOption(field="region", op="in", value=["eu", "us"]),
            ],
            sort=["-updated_at"],
            page=2,
            pageSize=50,
            fields=["id", "name"],
        )
        query_string = build_query_string(filter_query)

        assert "filter=status:eq:active" in query_string
        assert "filter=region:in:eu,us" in query_string
        assert "sort=-updated_at" in query_string
        assert "page=2" in query_string
        assert "pageSize=50" in query_string
        assert "fields=" in query_string

    def test_build_query_string_empty(self):
        """Test building query string with empty FilterQuery."""
        filter_query = FilterQuery()
        query_string = build_query_string(filter_query)

        assert query_string == ""

    def test_build_query_string_url_encoding(self):
        """Test that query string properly URL encodes values."""
        filter_query = FilterQuery(
            filters=[FilterOption(field="user name", op="eq", value="john doe")]
        )
        query_string = build_query_string(filter_query)

        assert "%20" in query_string or "user%20name" in query_string


class TestFilterBuilder:
    """Test cases for FilterBuilder class."""

    def test_filter_builder_add_single(self):
        """Test adding single filter to builder."""
        builder = FilterBuilder()
        builder.add("status", "eq", "active")

        filters = builder.build()
        assert len(filters) == 1
        assert filters[0].field == "status"
        assert filters[0].op == "eq"
        assert filters[0].value == "active"

    def test_filter_builder_chaining(self):
        """Test method chaining with FilterBuilder."""
        builder = FilterBuilder().add("status", "eq", "active").add("region", "in", ["eu", "us"])

        filters = builder.build()
        assert len(filters) == 2

    def test_filter_builder_add_many(self):
        """Test adding multiple filters at once."""
        builder = FilterBuilder()
        existing_filters = [
            FilterOption(field="status", op="eq", value="active"),
            FilterOption(field="region", op="in", value=["eu", "us"]),
        ]
        builder.add_many(existing_filters)

        filters = builder.build()
        assert len(filters) == 2

    def test_filter_builder_build_returns_copy(self):
        """Test that build() returns a copy, not reference."""
        builder = FilterBuilder()
        builder.add("status", "eq", "active")

        filters1 = builder.build()
        filters2 = builder.build()

        assert filters1 is not filters2
        assert filters1 == filters2

    def test_filter_builder_to_query_string(self):
        """Test converting FilterBuilder to query string."""
        builder = FilterBuilder()
        builder.add("status", "eq", "active")

        query_string = builder.to_query_string()
        assert "filter=status:eq:active" in query_string

    def test_filter_builder_to_query_string_multiple(self):
        """Test converting FilterBuilder with multiple filters to query string."""
        builder = FilterBuilder()
        builder.add("status", "eq", "active")
        builder.add("region", "in", ["eu", "us"])

        query_string = builder.to_query_string()
        assert "filter=status:eq:active" in query_string
        assert "filter=region:in:eu,us" in query_string

    def test_filter_builder_to_query_string_empty(self):
        """Test converting empty FilterBuilder to query string."""
        builder = FilterBuilder()
        query_string = builder.to_query_string()

        assert query_string == ""

    def test_filter_builder_all_operators(self):
        """Test FilterBuilder with all supported operators."""
        operators: list[FilterOperator] = [
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

        builder = FilterBuilder()
        for i, op in enumerate(operators):
            builder.add(
                f"field_{i}", op, "value" if op not in ["in", "nin"] else ["value1", "value2"]
            )

        filters = builder.build()
        assert len(filters) == len(operators)


class TestApplyFilters:
    """Test cases for apply_filters function."""

    def test_apply_filters_eq(self):
        """Test applying eq filter."""
        items = [
            {"status": "active", "id": 1},
            {"status": "inactive", "id": 2},
            {"status": "active", "id": 3},
        ]
        filters = [FilterOption(field="status", op="eq", value="active")]

        result = apply_filters(items, filters)

        assert len(result) == 2
        assert all(item["status"] == "active" for item in result)

    def test_apply_filters_neq(self):
        """Test applying neq filter."""
        items = [
            {"status": "active", "id": 1},
            {"status": "inactive", "id": 2},
            {"status": "active", "id": 3},
        ]
        filters = [FilterOption(field="status", op="neq", value="active")]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["status"] == "inactive"

    def test_apply_filters_in(self):
        """Test applying 'in' filter."""
        items = [
            {"region": "eu", "id": 1},
            {"region": "us", "id": 2},
            {"region": "uk", "id": 3},
        ]
        filters = [FilterOption(field="region", op="in", value=["eu", "us"])]

        result = apply_filters(items, filters)

        assert len(result) == 2
        assert all(item["region"] in ["eu", "us"] for item in result)

    def test_apply_filters_nin(self):
        """Test applying 'nin' filter."""
        items = [
            {"region": "eu", "id": 1},
            {"region": "us", "id": 2},
            {"region": "uk", "id": 3},
        ]
        filters = [FilterOption(field="region", op="nin", value=["eu", "us"])]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["region"] == "uk"

    def test_apply_filters_gt(self):
        """Test applying gt filter."""
        items = [
            {"age": 18, "id": 1},
            {"age": 25, "id": 2},
            {"age": 30, "id": 3},
        ]
        filters = [FilterOption(field="age", op="gt", value=20)]

        result = apply_filters(items, filters)

        assert len(result) == 2
        assert all(item["age"] > 20 for item in result)

    def test_apply_filters_lt(self):
        """Test applying lt filter."""
        items = [
            {"age": 18, "id": 1},
            {"age": 25, "id": 2},
            {"age": 30, "id": 3},
        ]
        filters = [FilterOption(field="age", op="lt", value=25)]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["age"] == 18

    def test_apply_filters_gte(self):
        """Test applying gte filter."""
        items = [
            {"age": 18, "id": 1},
            {"age": 25, "id": 2},
            {"age": 30, "id": 3},
        ]
        filters = [FilterOption(field="age", op="gte", value=25)]

        result = apply_filters(items, filters)

        assert len(result) == 2
        assert all(item["age"] >= 25 for item in result)

    def test_apply_filters_lte(self):
        """Test applying lte filter."""
        items = [
            {"age": 18, "id": 1},
            {"age": 25, "id": 2},
            {"age": 30, "id": 3},
        ]
        filters = [FilterOption(field="age", op="lte", value=25)]

        result = apply_filters(items, filters)

        assert len(result) == 2
        assert all(item["age"] <= 25 for item in result)

    def test_apply_filters_contains(self):
        """Test applying contains filter."""
        items = [
            {"name": "john doe", "id": 1},
            {"name": "jane smith", "id": 2},
            {"name": "bob", "id": 3},
        ]
        filters = [FilterOption(field="name", op="contains", value="john")]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert "john" in result[0]["name"]

    def test_apply_filters_like(self):
        """Test applying like filter (case-insensitive contains)."""
        items = [
            {"name": "John Doe", "id": 1},
            {"name": "Jane Smith", "id": 2},
            {"name": "Bob", "id": 3},
        ]
        filters = [FilterOption(field="name", op="like", value="john")]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["name"].lower() == "john doe"

    def test_apply_filters_multiple(self):
        """Test applying multiple filters."""
        items = [
            {"status": "active", "region": "eu", "age": 25, "id": 1},
            {"status": "active", "region": "us", "age": 30, "id": 2},
            {"status": "inactive", "region": "eu", "age": 25, "id": 3},
        ]
        filters = [
            FilterOption(field="status", op="eq", value="active"),
            FilterOption(field="region", op="eq", value="eu"),
            FilterOption(field="age", op="gte", value=25),
        ]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_apply_filters_empty_items(self):
        """Test applying filters to empty array."""
        items = []
        filters = [FilterOption(field="status", op="eq", value="active")]

        result = apply_filters(items, filters)

        assert result == []

    def test_apply_filters_empty_filters(self):
        """Test applying empty filters."""
        items = [{"status": "active", "id": 1}]
        filters = []

        result = apply_filters(items, filters)

        assert result == items

    def test_apply_filters_missing_field(self):
        """Test applying filter when field is missing."""
        items = [
            {"status": "active", "id": 1},
            {"id": 2},  # Missing status field
        ]
        filters = [FilterOption(field="status", op="eq", value="active")]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["id"] == 1
