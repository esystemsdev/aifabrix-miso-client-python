"""
Unit tests for pagination utilities.

This module contains comprehensive tests for pagination utilities including
parsePaginationParams, createMetaObject, applyPaginationToArray,
and createPaginatedListResponse.
"""

from miso_client.utils.pagination import (
    applyPaginationToArray,
    createMetaObject,
    createPaginatedListResponse,
    parsePaginationParams,
)


class TestParsePaginationParams:
    """Test cases for parsePaginationParams function."""

    def test_parse_basic_params(self):
        """Test parsing basic pagination parameters."""
        params = {"page": "1", "page_size": "25"}
        result = parsePaginationParams(params)
        current_page = result["currentPage"]
        page_size = result["pageSize"]

        assert current_page == 1
        assert page_size == 25

    def test_parse_with_defaults(self):
        """Test parsing with missing parameters (uses defaults)."""
        params = {}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 1  # Default page
        assert result["pageSize"] == 20  # Default pageSize

    def test_parse_with_only_page(self):
        """Test parsing with only page parameter."""
        params = {"page": "2"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 2
        assert result["pageSize"] == 20  # Default pageSize

    def test_parse_with_only_page_size(self):
        """Test parsing with only page_size parameter."""
        params = {"page_size": "50"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 1  # Default page
        assert result["pageSize"] == 50

    def test_parse_with_alternative_names(self):
        """Test parsing with alternative parameter names."""
        params = {"current_page": "2", "pageSize": "30"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 2
        assert result["pageSize"] == 30

    def test_parse_invalid_page(self):
        """Test parsing with invalid page value."""
        params = {"page": "invalid", "page_size": "25"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 1  # Default on invalid
        assert result["pageSize"] == 25

    def test_parse_negative_page(self):
        """Test parsing with negative page value."""
        params = {"page": "-1", "page_size": "25"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 1  # Default on negative
        assert result["pageSize"] == 25

    def test_parse_zero_page(self):
        """Test parsing with zero page value."""
        params = {"page": "0", "page_size": "25"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 1  # Default on zero
        assert result["pageSize"] == 25

    def test_parse_invalid_page_size(self):
        """Test parsing with invalid page_size value."""
        params = {"page": "1", "page_size": "invalid"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 1
        assert result["pageSize"] == 20  # Default on invalid

    def test_parse_negative_page_size(self):
        """Test parsing with negative page_size value."""
        params = {"page": "1", "page_size": "-10"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 1
        assert result["pageSize"] == 20  # Default on negative

    def test_parse_zero_page_size(self):
        """Test parsing with zero page_size value."""
        params = {"page": "1", "page_size": "0"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 1
        assert result["pageSize"] == 20  # Default on zero

    def test_parse_large_values(self):
        """Test parsing with large values."""
        params = {"page": "100", "page_size": "1000"}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 100
        assert result["pageSize"] == 1000

    def test_parse_none_values(self):
        """Test parsing with None values."""
        params = {"page": None, "page_size": None}
        result = parsePaginationParams(params)

        assert result["currentPage"] == 1  # Default
        assert result["pageSize"] == 20  # Default


class TestCreateMetaObject:
    """Test cases for createMetaObject function."""

    def test_create_meta_basic(self):
        """Test creating basic meta object."""
        meta = createMetaObject(totalItems=120, currentPage=1, pageSize=25, type="item")

        assert meta.totalItems == 120
        assert meta.currentPage == 1
        assert meta.pageSize == 25
        assert meta.type == "item"

    def test_create_meta_with_camel_case(self):
        """Test creating meta object with camelCase field names."""
        meta = createMetaObject(totalItems=120, currentPage=1, pageSize=25, type="item")

        # Test camelCase access
        assert meta.totalItems == 120
        assert meta.currentPage == 1
        assert meta.pageSize == 25

    def test_create_meta_different_type(self):
        """Test creating meta object with different type."""
        meta = createMetaObject(totalItems=50, currentPage=2, pageSize=10, type="user")

        assert meta.type == "user"
        assert meta.totalItems == 50

    def test_create_meta_large_values(self):
        """Test creating meta object with large values."""
        meta = createMetaObject(totalItems=10000, currentPage=100, pageSize=100, type="item")

        assert meta.totalItems == 10000
        assert meta.currentPage == 100
        assert meta.pageSize == 100


class TestApplyPaginationToArray:
    """Test cases for applyPaginationToArray function."""

    def test_apply_pagination_first_page(self):
        """Test applying pagination to first page."""
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = applyPaginationToArray(items, currentPage=1, pageSize=3)

        assert result == [1, 2, 3]

    def test_apply_pagination_second_page(self):
        """Test applying pagination to second page."""
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = applyPaginationToArray(items, currentPage=2, pageSize=3)

        assert result == [4, 5, 6]

    def test_apply_pagination_last_page(self):
        """Test applying pagination to last page."""
        items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = applyPaginationToArray(items, currentPage=4, pageSize=3)

        assert result == [10]  # Only one item remains

    def test_apply_pagination_empty_array(self):
        """Test applying pagination to empty array."""
        items = []
        result = applyPaginationToArray(items, currentPage=1, pageSize=25)

        assert result == []

    def test_apply_pagination_out_of_range(self):
        """Test applying pagination beyond array length."""
        items = [1, 2, 3]
        result = applyPaginationToArray(items, currentPage=10, pageSize=25)

        assert result == []  # Empty when out of range

    def test_apply_pagination_negative_page(self):
        """Test applying pagination with negative page."""
        items = [1, 2, 3, 4, 5]
        result = applyPaginationToArray(items, currentPage=-1, pageSize=2)

        assert result == [1, 2]  # Treated as page 1

    def test_apply_pagination_zero_page(self):
        """Test applying pagination with zero page."""
        items = [1, 2, 3, 4, 5]
        result = applyPaginationToArray(items, currentPage=0, pageSize=2)

        assert result == [1, 2]  # Treated as page 1

    def test_apply_pagination_negative_page_size(self):
        """Test applying pagination with negative pageSize."""
        items = [1, 2, 3, 4, 5]
        result = applyPaginationToArray(items, currentPage=1, pageSize=-10)

        assert result == [1, 2, 3, 4, 5]  # Default pageSize of 25, but only 5 items

    def test_apply_pagination_zero_page_size(self):
        """Test applying pagination with zero pageSize."""
        items = [1, 2, 3, 4, 5]
        result = applyPaginationToArray(items, currentPage=1, pageSize=0)

        assert len(result) <= 25  # Default pageSize

    def test_apply_pagination_dict_items(self):
        """Test applying pagination to array of dictionaries."""
        items = [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2"},
            {"id": 3, "name": "Item 3"},
            {"id": 4, "name": "Item 4"},
        ]
        result = applyPaginationToArray(items, currentPage=2, pageSize=2)

        assert result == [{"id": 3, "name": "Item 3"}, {"id": 4, "name": "Item 4"}]


class TestCreatePaginatedListResponse:
    """Test cases for createPaginatedListResponse function."""

    def test_create_paginated_response_basic(self):
        """Test creating basic paginated response."""
        items = [{"id": 1}, {"id": 2}]
        response = createPaginatedListResponse(
            items, totalItems=10, currentPage=1, pageSize=2, type="item"
        )

        assert response.meta.totalItems == 10
        assert response.meta.currentPage == 1
        assert response.meta.pageSize == 2
        assert response.meta.type == "item"
        assert len(response.data) == 2
        assert response.data == items

    def test_create_paginated_response_empty(self):
        """Test creating paginated response with empty data."""
        items = []
        response = createPaginatedListResponse(
            items, totalItems=0, currentPage=1, pageSize=25, type="item"
        )

        assert response.meta.totalItems == 0
        assert response.meta.currentPage == 1
        assert len(response.data) == 0

    def test_create_paginated_response_type_safety(self):
        """Test that paginated response preserves generic type."""
        items = ["string1", "string2", "string3"]
        response = createPaginatedListResponse(
            items, totalItems=3, currentPage=1, pageSize=3, type="string"
        )

        assert isinstance(response.data, list)
        assert all(isinstance(item, str) for item in response.data)

    def test_create_paginated_response_with_camel_case(self):
        """Test that paginated response uses camelCase field names."""
        items = [{"id": 1}]
        response = createPaginatedListResponse(
            items, totalItems=1, currentPage=1, pageSize=1, type="item"
        )

        # Test camelCase access
        assert response.meta.totalItems == 1
        assert response.meta.currentPage == 1
        assert response.meta.pageSize == 1
