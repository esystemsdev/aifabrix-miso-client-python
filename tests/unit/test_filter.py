"""
Unit tests for filter utilities.

This module contains comprehensive tests for filter utilities including
parse_filter_params, build_query_string, apply_filters, FilterBuilder class,
and JSON filter models with conversion utilities.
"""

from miso_client.models.filter import (
    FilterBuilder,
    FilterGroup,
    FilterOperator,
    FilterOption,
    FilterQuery,
    JsonFilter,
)
from miso_client.utils.filter import (
    apply_filters,
    build_query_string,
    filter_query_to_json,
    json_filter_to_query_string,
    json_to_filter_query,
    parse_filter_params,
    query_string_to_json_filter,
    validate_filter_option,
    validate_json_filter,
)


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

    def test_parse_filter_non_string_filter_param(self):
        """Test parsing filter with non-string filter_param (dict)."""
        params = {"filter": {"not": "a string"}}
        filters = parse_filter_params(params)

        assert len(filters) == 0

    def test_parse_filter_non_string_filter_param_int(self):
        """Test parsing filter with non-string filter_param (int)."""
        params = {"filter": 123}
        filters = parse_filter_params(params)

        assert len(filters) == 0

    def test_parse_filter_list_with_non_string_items(self):
        """Test parsing filter list with non-string items."""
        params = {"filter": ["status:eq:active", 123, {"not": "string"}]}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].field == "status"

    def test_parse_filter_empty_string_in_list(self):
        """Test parsing filter list with empty string."""
        params = {"filter": ["status:eq:active", ""]}
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
            "isNull",
            "isNotNull",
        ]

        builder = FilterBuilder()
        for i, op in enumerate(operators):
            if op in ("isNull", "isNotNull"):
                builder.add(f"field_{i}", op, None)
            else:
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

    def test_apply_filters_in_with_non_list_value(self):
        """Test applying 'in' filter with non-list value (should treat as single value)."""
        items = [
            {"region": "eu", "id": 1},
            {"region": "us", "id": 2},
            {"region": "uk", "id": 3},
        ]
        filters = [FilterOption(field="region", op="in", value="eu")]  # String instead of list

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["region"] == "eu"

    def test_apply_filters_nin_with_non_list_value(self):
        """Test applying 'nin' filter with non-list value (should treat as single value)."""
        items = [
            {"region": "eu", "id": 1},
            {"region": "us", "id": 2},
            {"region": "uk", "id": 3},
        ]
        filters = [FilterOption(field="region", op="nin", value="eu")]  # String instead of list

        result = apply_filters(items, filters)

        assert len(result) == 2
        assert all(item["region"] != "eu" for item in result)

    def test_apply_filters_contains_with_non_string_value(self):
        """Test applying 'contains' filter with non-string value (check if value in list field)."""
        items = [
            {"tags": ["python", "testing"], "id": 1},
            {"tags": ["java", "testing"], "id": 2},
            {"tags": ["python"], "id": 3},
        ]
        filters = [FilterOption(field="tags", op="contains", value="testing")]

        result = apply_filters(items, filters)

        assert len(result) == 2
        assert all("testing" in item["tags"] for item in result)

    def test_apply_filters_contains_string_value_in_non_string_field(self):
        """Test applying 'contains' filter with string value in non-string field."""
        items = [
            {"tags": ["python", "testing"], "id": 1},
            {"tags": ["java"], "id": 2},
            {"name": "python", "id": 3},  # Missing tags field
        ]
        filters = [FilterOption(field="tags", op="contains", value="python")]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_apply_filters_like_with_empty_string(self):
        """Test applying 'like' filter with empty string."""
        items = [
            {"name": "John Doe", "id": 1},
            {"name": "Jane Smith", "id": 2},
        ]
        filters = [FilterOption(field="name", op="like", value="")]

        result = apply_filters(items, filters)

        # Empty string should match all strings
        assert len(result) == 2

    def test_apply_filters_gt_with_non_numeric_field(self):
        """Test applying gt filter with non-numeric field value."""
        items = [
            {"age": "twenty", "id": 1},  # String instead of number
            {"age": 25, "id": 2},
            {"age": 30, "id": 3},
        ]
        filters = [FilterOption(field="age", op="gt", value=20)]

        result = apply_filters(items, filters)

        # Only numeric values should be compared
        assert len(result) == 2
        assert all(isinstance(item["age"], (int, float)) and item["age"] > 20 for item in result)

    def test_apply_filters_lt_with_missing_field(self):
        """Test applying lt filter when field is missing."""
        items = [
            {"age": 25, "id": 1},
            {"id": 2},  # Missing age field
        ]
        filters = [FilterOption(field="age", op="lt", value=30)]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_apply_filters_gte_with_non_numeric_value(self):
        """Test applying gte filter with non-numeric comparison value."""
        items = [
            {"age": 25, "id": 1},
            {"age": 30, "id": 2},
        ]
        filters = [FilterOption(field="age", op="gte", value="twenty")]  # String value

        result = apply_filters(items, filters)

        # Should handle gracefully - no matches since comparison fails
        assert len(result) == 0

    def test_apply_filters_lte_with_float_values(self):
        """Test applying lte filter with float values."""
        items = [
            {"price": 9.99, "id": 1},
            {"price": 19.99, "id": 2},
            {"price": 29.99, "id": 3},
        ]
        filters = [FilterOption(field="price", op="lte", value=19.99)]

        result = apply_filters(items, filters)

        assert len(result) == 2
        assert all(item["price"] <= 19.99 for item in result)


class TestJsonFilter:
    """Test cases for JsonFilter model."""

    def test_json_filter_basic(self):
        """Test creating basic JsonFilter."""
        json_filter = JsonFilter(filters=[FilterOption(field="status", op="eq", value="active")])

        assert json_filter.filters is not None
        assert len(json_filter.filters) == 1
        assert json_filter.filters[0].field == "status"

    def test_json_filter_with_pagination(self):
        """Test JsonFilter with pagination."""
        json_filter = JsonFilter(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )

        assert json_filter.page == 1
        assert json_filter.pageSize == 25

    def test_json_filter_with_sort(self):
        """Test JsonFilter with sort."""
        json_filter = JsonFilter(
            filters=[FilterOption(field="status", op="eq", value="active")],
            sort=["-updated_at", "created_at"],
        )

        assert json_filter.sort == ["-updated_at", "created_at"]

    def test_json_filter_with_fields(self):
        """Test JsonFilter with fields selection."""
        json_filter = JsonFilter(
            filters=[FilterOption(field="status", op="eq", value="active")],
            fields=["id", "name", "status"],
        )

        assert json_filter.fields == ["id", "name", "status"]

    def test_json_filter_empty(self):
        """Test creating empty JsonFilter."""
        json_filter = JsonFilter()

        assert json_filter.filters is None
        assert json_filter.page is None
        assert json_filter.pageSize is None

    def test_json_filter_serialization(self):
        """Test JsonFilter JSON serialization."""
        json_filter = JsonFilter(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )

        json_data = json_filter.model_dump(exclude_none=True)
        assert "filters" in json_data
        assert json_data["page"] == 1
        assert json_data["pageSize"] == 25


class TestFilterGroup:
    """Test cases for FilterGroup model."""

    def test_filter_group_basic(self):
        """Test creating basic FilterGroup."""
        group = FilterGroup(
            operator="and",
            filters=[FilterOption(field="status", op="eq", value="active")],
        )

        assert group.operator == "and"
        assert group.filters is not None
        assert len(group.filters) == 1

    def test_filter_group_or_operator(self):
        """Test FilterGroup with 'or' operator."""
        group = FilterGroup(
            operator="or",
            filters=[
                FilterOption(field="age", op="gte", value=18),
                FilterOption(field="age", op="lte", value=65),
            ],
        )

        assert group.operator == "or"
        assert len(group.filters) == 2

    def test_filter_group_nested(self):
        """Test FilterGroup with nested groups."""
        nested_group = FilterGroup(
            operator="or",
            filters=[FilterOption(field="region", op="eq", value="eu")],
        )
        parent_group = FilterGroup(
            operator="and",
            filters=[FilterOption(field="status", op="eq", value="active")],
            groups=[nested_group],
        )

        assert parent_group.groups is not None
        assert len(parent_group.groups) == 1
        assert parent_group.groups[0].operator == "or"

    def test_filter_group_default_operator(self):
        """Test FilterGroup defaults to 'and' operator."""
        group = FilterGroup(filters=[FilterOption(field="status", op="eq", value="active")])

        assert group.operator == "and"


class TestFilterQueryJsonMethods:
    """Test cases for FilterQuery JSON serialization methods."""

    def test_filter_query_to_json(self):
        """Test converting FilterQuery to JSON dict."""
        filter_query = FilterQuery(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )

        json_data = filter_query.to_json()

        assert "filters" in json_data
        assert json_data["page"] == 1
        assert json_data["pageSize"] == 25

    def test_filter_query_from_json(self):
        """Test creating FilterQuery from JSON dict."""
        json_data = {
            "filters": [{"field": "status", "op": "eq", "value": "active"}],
            "page": 1,
            "pageSize": 25,
        }

        filter_query = FilterQuery.from_json(json_data)

        assert filter_query.filters is not None
        assert len(filter_query.filters) == 1
        assert filter_query.page == 1
        assert filter_query.pageSize == 25

    def test_filter_query_to_json_filter(self):
        """Test converting FilterQuery to JsonFilter."""
        filter_query = FilterQuery(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )

        json_filter = filter_query.to_json_filter()

        assert isinstance(json_filter, JsonFilter)
        assert json_filter.filters is not None
        assert json_filter.page == 1
        assert json_filter.pageSize == 25


class TestFilterBuilderJsonMethods:
    """Test cases for FilterBuilder JSON conversion methods."""

    def test_filter_builder_to_json_filter(self):
        """Test converting FilterBuilder to JsonFilter."""
        builder = FilterBuilder()
        builder.add("status", "eq", "active")

        json_filter = builder.to_json_filter()

        assert isinstance(json_filter, JsonFilter)
        assert json_filter.filters is not None
        assert len(json_filter.filters) == 1

    def test_filter_builder_to_json(self):
        """Test converting FilterBuilder to JSON dict."""
        builder = FilterBuilder()
        builder.add("status", "eq", "active")

        json_data = builder.to_json()

        assert "filters" in json_data
        assert isinstance(json_data["filters"], list)


class TestFilterConversionUtilities:
    """Test cases for filter conversion utilities."""

    def test_filter_query_to_json_utility(self):
        """Test filter_query_to_json utility function."""
        filter_query = FilterQuery(filters=[FilterOption(field="status", op="eq", value="active")])

        json_data = filter_query_to_json(filter_query)

        assert "filters" in json_data

    def test_json_to_filter_query_utility(self):
        """Test json_to_filter_query utility function."""
        json_data = {"filters": [{"field": "status", "op": "eq", "value": "active"}]}

        filter_query = json_to_filter_query(json_data)

        assert isinstance(filter_query, FilterQuery)
        assert filter_query.filters is not None

    def test_json_filter_to_query_string(self):
        """Test converting JsonFilter to query string."""
        json_filter = JsonFilter(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )

        query_string = json_filter_to_query_string(json_filter)

        assert "filter=status:eq:active" in query_string
        assert "page=1" in query_string
        assert "pageSize=25" in query_string

    def test_query_string_to_json_filter(self):
        """Test converting query string to JsonFilter."""
        query_string = "filter=status:eq:active&page=1&pageSize=25"

        json_filter = query_string_to_json_filter(query_string)

        assert isinstance(json_filter, JsonFilter)
        assert json_filter.filters is not None
        assert len(json_filter.filters) == 1
        assert json_filter.page == 1
        assert json_filter.pageSize == 25

    def test_query_string_to_json_filter_with_sort(self):
        """Test converting query string with sort to JsonFilter."""
        query_string = "filter=status:eq:active&sort=-updated_at&sort=created_at"

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.sort is not None
        assert "-updated_at" in json_filter.sort
        assert "created_at" in json_filter.sort

    def test_query_string_to_json_filter_with_fields(self):
        """Test converting query string with fields to JsonFilter."""
        query_string = "filter=status:eq:active&fields=id,name,status"

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.fields is not None
        assert "id" in json_filter.fields
        assert "name" in json_filter.fields
        assert "status" in json_filter.fields

    def test_query_string_to_json_filter_with_question_mark(self):
        """Test converting query string with leading ? to JsonFilter."""
        query_string = "?filter=status:eq:active&page=1"

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.filters is not None
        assert json_filter.page == 1

    def test_query_string_to_json_filter_invalid_page(self):
        """Test converting query string with invalid page value."""
        query_string = "filter=status:eq:active&page=not-a-number"

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.filters is not None
        assert json_filter.page is None  # Should be None when invalid

    def test_query_string_to_json_filter_invalid_page_size(self):
        """Test converting query string with invalid pageSize value."""
        query_string = "filter=status:eq:active&pageSize=invalid"

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.filters is not None
        assert json_filter.pageSize is None  # Should be None when invalid

    def test_query_string_to_json_filter_page_as_list(self):
        """Test converting query string with page as list parameter."""
        query_string = "filter=status:eq:active&page=1&page=2"  # Duplicate page param

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.page == 1  # Should take first value

    def test_query_string_to_json_filter_sort_as_string(self):
        """Test converting query string with sort as single string."""
        query_string = "filter=status:eq:active&sort=-updated_at"

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.sort is not None
        assert len(json_filter.sort) == 1
        assert json_filter.sort[0] == "-updated_at"

    def test_query_string_to_json_filter_sort_as_list(self):
        """Test converting query string with sort as list."""
        query_string = "filter=status:eq:active&sort=-updated_at&sort=created_at"

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.sort is not None
        assert len(json_filter.sort) == 2
        assert "-updated_at" in json_filter.sort
        assert "created_at" in json_filter.sort

    def test_query_string_to_json_filter_fields_as_string(self):
        """Test converting query string with fields as single string."""
        query_string = "filter=status:eq:active&fields=id,name"

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.fields is not None
        assert len(json_filter.fields) == 2
        assert "id" in json_filter.fields
        assert "name" in json_filter.fields

    def test_query_string_to_json_filter_empty_query_string(self):
        """Test converting empty query string."""
        query_string = ""

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.filters is None
        assert json_filter.page is None
        assert json_filter.pageSize is None

    def test_query_string_to_json_filter_only_question_mark(self):
        """Test converting query string with only ?."""
        query_string = "?"

        json_filter = query_string_to_json_filter(query_string)

        assert json_filter.filters is None
        assert json_filter.page is None


class TestFilterValidation:
    """Test cases for filter validation utilities."""

    def test_validate_filter_option_valid(self):
        """Test validating valid filter option."""
        option = {"field": "status", "op": "eq", "value": "active"}

        assert validate_filter_option(option) is True

    def test_validate_filter_option_missing_field(self):
        """Test validating filter option with missing field."""
        option = {"op": "eq", "value": "active"}

        assert validate_filter_option(option) is False

    def test_validate_filter_option_invalid_operator(self):
        """Test validating filter option with invalid operator."""
        option = {"field": "status", "op": "invalid", "value": "active"}

        assert validate_filter_option(option) is False

    def test_validate_json_filter_valid(self):
        """Test validating valid JSON filter."""
        json_data = {
            "filters": [{"field": "status", "op": "eq", "value": "active"}],
            "page": 1,
            "pageSize": 25,
        }

        assert validate_json_filter(json_data) is True

    def test_validate_json_filter_with_groups(self):
        """Test validating JSON filter with groups."""
        json_data = {
            "groups": [
                {
                    "operator": "or",
                    "filters": [
                        {"field": "age", "op": "gte", "value": 18},
                        {"field": "age", "op": "lte", "value": 65},
                    ],
                }
            ]
        }

        assert validate_json_filter(json_data) is True

    def test_validate_json_filter_invalid_filters(self):
        """Test validating JSON filter with invalid filters."""
        json_data = {
            "filters": [{"field": "status"}],  # Missing op and value
            "page": 1,
        }

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_invalid_groups(self):
        """Test validating JSON filter with invalid groups."""
        json_data = {
            "groups": [
                {
                    "operator": "invalid",  # Invalid operator
                    "filters": [{"field": "status", "op": "eq", "value": "active"}],
                }
            ]
        }

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_invalid_page(self):
        """Test validating JSON filter with invalid page."""
        json_data = {"page": "not-a-number"}

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_empty(self):
        """Test validating empty JSON filter."""
        json_data = {}

        assert validate_json_filter(json_data) is True

    def test_validate_json_filter_nested_groups(self):
        """Test validating JSON filter with nested groups."""
        json_data = {
            "groups": [
                {
                    "operator": "and",
                    "filters": [{"field": "status", "op": "eq", "value": "active"}],
                    "groups": [
                        {
                            "operator": "or",
                            "filters": [{"field": "region", "op": "eq", "value": "eu"}],
                        }
                    ],
                }
            ]
        }

        assert validate_json_filter(json_data) is True

    def test_validate_json_filter_nested_groups_missing_operator(self):
        """Test validating JSON filter with nested groups missing operator."""
        json_data = {
            "groups": [
                {
                    "operator": "and",
                    "filters": [{"field": "status", "op": "eq", "value": "active"}],
                    "groups": [{"filters": [{"field": "region", "op": "eq", "value": "eu"}]}],
                }
            ]
        }

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_groups_invalid_nested_groups_type(self):
        """Test validating JSON filter with invalid nested groups type."""
        json_data = {
            "groups": [
                {
                    "operator": "and",
                    "filters": [{"field": "status", "op": "eq", "value": "active"}],
                    "groups": "not-a-list",
                }
            ]
        }

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_groups_invalid_nested_group_dict(self):
        """Test validating JSON filter with invalid nested group (not a dict)."""
        json_data = {
            "groups": [
                {
                    "operator": "and",
                    "filters": [{"field": "status", "op": "eq", "value": "active"}],
                    "groups": ["not-a-dict"],
                }
            ]
        }

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_sort_non_string_items(self):
        """Test validating JSON filter with sort containing non-string items."""
        json_data = {"sort": ["-updated_at", 123, "created_at"]}

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_page_non_int(self):
        """Test validating JSON filter with page as non-int."""
        json_data = {"page": "not-a-number"}

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_page_float(self):
        """Test validating JSON filter with page as float."""
        json_data = {"page": 1.5}

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_page_size_non_int(self):
        """Test validating JSON filter with pageSize as non-int."""
        json_data = {"pageSize": "not-a-number"}

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_page_size_float(self):
        """Test validating JSON filter with pageSize as float."""
        json_data = {"pageSize": 25.5}

        assert validate_json_filter(json_data) is False

    def test_validate_json_filter_fields_non_string_items(self):
        """Test validating JSON filter with fields containing non-string items."""
        json_data = {"fields": ["id", 123, "name"]}

        assert validate_json_filter(json_data) is False


class TestNullCheckOperators:
    """Test cases for isNull and isNotNull operators."""

    def test_parse_filter_is_null(self):
        """Test parsing filter with isNull operator."""
        params = {"filter": "deleted_at:isNull:"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].field == "deleted_at"
        assert filters[0].op == "isNull"
        assert filters[0].value is None

    def test_parse_filter_is_not_null(self):
        """Test parsing filter with isNotNull operator."""
        params = {"filter": "status:isNotNull:"}
        filters = parse_filter_params(params)

        assert len(filters) == 1
        assert filters[0].field == "status"
        assert filters[0].op == "isNotNull"
        assert filters[0].value is None

    def test_build_query_string_is_null(self):
        """Test building query string with isNull operator."""
        filter_query = FilterQuery(
            filters=[FilterOption(field="deleted_at", op="isNull", value=None)]
        )
        query_string = build_query_string(filter_query)

        assert "filter=deleted_at:isNull" in query_string
        # Should not have a third colon (no value part)
        parts = query_string.split("isNull")
        assert len(parts) == 2
        assert ":" not in parts[1] or parts[1].startswith("&") or parts[1] == ""

    def test_build_query_string_is_not_null(self):
        """Test building query string with isNotNull operator."""
        filter_query = FilterQuery(
            filters=[FilterOption(field="status", op="isNotNull", value=None)]
        )
        query_string = build_query_string(filter_query)

        assert "filter=status:isNotNull" in query_string
        # Should not have a third colon (no value part)
        parts = query_string.split("isNotNull")
        assert len(parts) == 2
        assert ":" not in parts[1] or parts[1].startswith("&") or parts[1] == ""

    def test_apply_filters_is_null(self):
        """Test applying isNull filter."""
        items = [
            {"status": "active", "id": 1},
            {"status": None, "id": 2},
            {"id": 3},  # Missing status field
        ]
        filters = [FilterOption(field="status", op="isNull", value=None)]

        result = apply_filters(items, filters)

        assert len(result) == 2
        assert result[0]["id"] == 2
        assert result[1]["id"] == 3

    def test_apply_filters_is_not_null(self):
        """Test applying isNotNull filter."""
        items = [
            {"status": "active", "id": 1},
            {"status": None, "id": 2},
            {"id": 3},  # Missing status field
        ]
        filters = [FilterOption(field="status", op="isNotNull", value=None)]

        result = apply_filters(items, filters)

        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_validate_filter_option_is_null(self):
        """Test validating filter option with isNull operator."""
        option = {"field": "deleted_at", "op": "isNull"}

        assert validate_filter_option(option) is True

    def test_validate_filter_option_is_not_null(self):
        """Test validating filter option with isNotNull operator."""
        option = {"field": "status", "op": "isNotNull"}

        assert validate_filter_option(option) is True

    def test_filter_builder_is_null(self):
        """Test FilterBuilder with isNull operator."""
        builder = FilterBuilder()
        builder.add("deleted_at", "isNull", None)

        filters = builder.build()
        assert len(filters) == 1
        assert filters[0].op == "isNull"
        assert filters[0].value is None

    def test_filter_builder_is_not_null(self):
        """Test FilterBuilder with isNotNull operator."""
        builder = FilterBuilder()
        builder.add("status", "isNotNull", None)

        filters = builder.build()
        assert len(filters) == 1
        assert filters[0].op == "isNotNull"
        assert filters[0].value is None

    def test_filter_builder_to_query_string_is_null(self):
        """Test converting FilterBuilder with isNull to query string."""
        builder = FilterBuilder()
        builder.add("deleted_at", "isNull", None)

        query_string = builder.to_query_string()
        assert "filter=deleted_at:isNull" in query_string
        # Should not have a third colon (no value part)
        parts = query_string.split("isNull")
        assert len(parts) == 2

    def test_filter_builder_to_query_string_is_not_null(self):
        """Test converting FilterBuilder with isNotNull to query string."""
        builder = FilterBuilder()
        builder.add("status", "isNotNull", None)

        query_string = builder.to_query_string()
        assert "filter=status:isNotNull" in query_string
        # Should not have a third colon (no value part)
        parts = query_string.split("isNotNull")
        assert len(parts) == 2
