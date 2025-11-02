"""
Unit tests for pagination utilities.

This module contains comprehensive tests for pagination utilities including
parse_pagination_params, create_meta_object, apply_pagination_to_array,
and create_paginated_list_response.
"""

from miso_client.utils.pagination import (
    apply_pagination_to_array,
    create_meta_object,
    create_paginated_list_response,
    parse_pagination_params,
)


class TestParsePaginationParams:
    """Test cases for parse_pagination_params function."""

    def test_parse_basic_params(self):
        """Test parsing basic pagination parameters."""
        params = {"page": "1", "page_size": "25"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1
        assert page_size == 25

    def test_parse_with_defaults(self):
        """Test parsing with missing parameters (uses defaults)."""
        params = {}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1  # Default page
        assert page_size == 25  # Default page_size

    def test_parse_with_only_page(self):
        """Test parsing with only page parameter."""
        params = {"page": "2"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 2
        assert page_size == 25  # Default page_size

    def test_parse_with_only_page_size(self):
        """Test parsing with only page_size parameter."""
        params = {"page_size": "50"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1  # Default page
        assert page_size == 50

    def test_parse_with_alternative_names(self):
        """Test parsing with alternative parameter names."""
        params = {"current_page": "2", "pageSize": "30"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 2
        assert page_size == 30

    def test_parse_invalid_page(self):
        """Test parsing with invalid page value."""
        params = {"page": "invalid", "page_size": "25"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1  # Default on invalid
        assert page_size == 25

    def test_parse_negative_page(self):
        """Test parsing with negative page value."""
        params = {"page": "-1", "page_size": "25"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1  # Default on negative
        assert page_size == 25

    def test_parse_zero_page(self):
        """Test parsing with zero page value."""
        params = {"page": "0", "page_size": "25"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1  # Default on zero
        assert page_size == 25

    def test_parse_invalid_page_size(self):
        """Test parsing with invalid page_size value."""
        params = {"page": "1", "page_size": "invalid"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1
        assert page_size == 25  # Default on invalid

    def test_parse_negative_page_size(self):
        """Test parsing with negative page_size value."""
        params = {"page": "1", "page_size": "-10"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1
        assert page_size == 25  # Default on negative

    def test_parse_zero_page_size(self):
        """Test parsing with zero page_size value."""
        params = {"page": "1", "page_size": "0"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1
        assert page_size == 25  # Default on zero

    def test_parse_large_values(self):
        """Test parsing with large values."""
        params = {"page": "100", "page_size": "1000"}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 100
        assert page_size == 1000

    def test_parse_none_values(self):
        """Test parsing with None values."""
        params = {"page": None, "page_size": None}
        current_page, page_size = parse_pagination_params(params)

        assert current_page == 1  # Default
        assert page_size == 25  # Default


class TestCreateMetaObject:
    """Test cases for create_meta_object function."""

    def test_create_meta_basic(self):
        """Test creating basic meta object."""
        meta = create_meta_object(total_items=120, current_page=1, page_size=25, type="item")

        assert meta.total_items == 120
        assert meta.current_page == 1
        assert meta.page_size == 25
        assert meta.type == "item"

    def test_create_meta_with_aliases(self):
        """Test creating meta object with camelCase aliases."""
        meta = create_meta_object(total_items=120, current_page=1, page_size=25, type="item")

        # Test camelCase access
        assert meta.totalItems == 120
        assert meta.currentPage == 1
        assert meta.pageSize == 25

    def test_create_meta_different_type(self):
        """Test creating meta object with different type."""
        meta = create_meta_object(total_items=50, current_page=2, page_size=10, type="user")

        assert meta.type == "user"
        assert meta.total_items == 50

    def test_create_meta_large_values(self):
        """Test creating meta object with large values."""
        meta = create_meta_object(total_items=10000, current_page=100, page_size=100, type="item")

        assert meta.total_items == 10000
        assert meta.current_page == 100
        assert meta.page_size == 100


class TestApplyPaginationToArray:
    """Test cases for apply_pagination_to_array function."""

    def test_apply_pagination_first_page(self):
        """Test applying pagination to first page."""
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = apply_pagination_to_array(items, current_page=1, page_size=3)

        assert result == [1, 2, 3]

    def test_apply_pagination_second_page(self):
        """Test applying pagination to second page."""
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = apply_pagination_to_array(items, current_page=2, page_size=3)

        assert result == [4, 5, 6]

    def test_apply_pagination_last_page(self):
        """Test applying pagination to last page."""
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = apply_pagination_to_array(items, current_page=4, page_size=3)

        assert result == [10]  # Only one item remains

    def test_apply_pagination_empty_array(self):
        """Test applying pagination to empty array."""
        items = []
        result = apply_pagination_to_array(items, current_page=1, page_size=25)

        assert result == []

    def test_apply_pagination_out_of_range(self):
        """Test applying pagination beyond array length."""
        items = [1, 2, 3]
        result = apply_pagination_to_array(items, current_page=10, page_size=25)

        assert result == []  # Empty when out of range

    def test_apply_pagination_negative_page(self):
        """Test applying pagination with negative page."""
        items = [1, 2, 3, 4, 5]
        result = apply_pagination_to_array(items, current_page=-1, page_size=2)

        assert result == [1, 2]  # Treated as page 1

    def test_apply_pagination_zero_page(self):
        """Test applying pagination with zero page."""
        items = [1, 2, 3, 4, 5]
        result = apply_pagination_to_array(items, current_page=0, page_size=2)

        assert result == [1, 2]  # Treated as page 1

    def test_apply_pagination_negative_page_size(self):
        """Test applying pagination with negative page_size."""
        items = [1, 2, 3, 4, 5]
        result = apply_pagination_to_array(items, current_page=1, page_size=-10)

        assert result == [1, 2, 3, 4, 5]  # Default page_size of 25, but only 5 items

    def test_apply_pagination_zero_page_size(self):
        """Test applying pagination with zero page_size."""
        items = [1, 2, 3, 4, 5]
        result = apply_pagination_to_array(items, current_page=1, page_size=0)

        assert len(result) <= 25  # Default page_size

    def test_apply_pagination_dict_items(self):
        """Test applying pagination to array of dictionaries."""
        items = [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2"},
            {"id": 3, "name": "Item 3"},
            {"id": 4, "name": "Item 4"},
        ]
        result = apply_pagination_to_array(items, current_page=2, page_size=2)

        assert result == [{"id": 3, "name": "Item 3"}, {"id": 4, "name": "Item 4"}]


class TestCreatePaginatedListResponse:
    """Test cases for create_paginated_list_response function."""

    def test_create_paginated_response_basic(self):
        """Test creating basic paginated response."""
        items = [{"id": 1}, {"id": 2}]
        response = create_paginated_list_response(
            items, total_items=10, current_page=1, page_size=2, type="item"
        )

        assert response.meta.total_items == 10
        assert response.meta.current_page == 1
        assert response.meta.page_size == 2
        assert response.meta.type == "item"
        assert len(response.data) == 2
        assert response.data == items

    def test_create_paginated_response_empty(self):
        """Test creating paginated response with empty data."""
        items = []
        response = create_paginated_list_response(
            items, total_items=0, current_page=1, page_size=25, type="item"
        )

        assert response.meta.total_items == 0
        assert response.meta.current_page == 1
        assert len(response.data) == 0

    def test_create_paginated_response_type_safety(self):
        """Test that paginated response preserves generic type."""
        items = ["string1", "string2", "string3"]
        response = create_paginated_list_response(
            items, total_items=3, current_page=1, page_size=3, type="string"
        )

        assert isinstance(response.data, list)
        assert all(isinstance(item, str) for item in response.data)

    def test_create_paginated_response_with_meta_aliases(self):
        """Test that paginated response supports camelCase meta aliases."""
        items = [{"id": 1}]
        response = create_paginated_list_response(
            items, total_items=1, current_page=1, page_size=1, type="item"
        )

        # Test camelCase access
        assert response.meta.totalItems == 1
        assert response.meta.currentPage == 1
        assert response.meta.pageSize == 1
