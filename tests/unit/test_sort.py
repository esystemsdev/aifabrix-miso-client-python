"""
Unit tests for sort utilities.

This module contains comprehensive tests for sort utilities including
parse_sort_params and build_sort_string.
"""

from miso_client.models.sort import SortOption
from miso_client.utils.sort import build_sort_string, parse_sort_params


class TestParseSortParams:
    """Test cases for parse_sort_params function."""

    def test_parse_single_sort_string_ascending(self):
        """Test parsing single sort string (ascending)."""
        params = {"sort": "created_at"}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 1
        assert sort_options[0].field == "created_at"
        assert sort_options[0].order == "asc"

    def test_parse_single_sort_string_descending(self):
        """Test parsing single sort string (descending with '-' prefix)."""
        params = {"sort": "-updated_at"}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 1
        assert sort_options[0].field == "updated_at"
        assert sort_options[0].order == "desc"

    def test_parse_multiple_sort_list(self):
        """Test parsing multiple sort strings as list."""
        params = {"sort": ["-updated_at", "created_at"]}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 2
        assert sort_options[0].field == "updated_at"
        assert sort_options[0].order == "desc"
        assert sort_options[1].field == "created_at"
        assert sort_options[1].order == "asc"

    def test_parse_sort_empty_params(self):
        """Test parsing empty params."""
        params = {}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 0

    def test_parse_sort_none_value(self):
        """Test parsing None sort value."""
        params = {"sort": None}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 0

    def test_parse_sort_empty_string(self):
        """Test parsing empty sort string."""
        params = {"sort": ""}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 0

    def test_parse_sort_whitespace_only(self):
        """Test parsing sort string with only whitespace."""
        params = {"sort": "   "}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 0

    def test_parse_sort_multiple_descending(self):
        """Test parsing multiple descending sorts."""
        params = {"sort": ["-updated_at", "-created_at"]}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 2
        assert all(option.order == "desc" for option in sort_options)

    def test_parse_sort_multiple_ascending(self):
        """Test parsing multiple ascending sorts."""
        params = {"sort": ["name", "email"]}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 2
        assert all(option.order == "asc" for option in sort_options)

    def test_parse_sort_mixed_asc_desc(self):
        """Test parsing mixed ascending and descending sorts."""
        params = {"sort": ["-updated_at", "created_at", "-name", "email"]}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 4
        assert sort_options[0].order == "desc"
        assert sort_options[1].order == "asc"
        assert sort_options[2].order == "desc"
        assert sort_options[3].order == "asc"

    def test_parse_sort_with_spaces(self):
        """Test parsing sort string with spaces (should be trimmed)."""
        params = {"sort": "  -updated_at  "}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 1
        assert sort_options[0].field == "updated_at"
        assert sort_options[0].order == "desc"

    def test_parse_sort_invalid_type(self):
        """Test parsing sort with invalid type (not string or list)."""
        params = {"sort": 123}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 0

    def test_parse_sort_mixed_valid_invalid(self):
        """Test parsing sort list with mix of valid and invalid entries."""
        params = {"sort": ["-updated_at", 123, "created_at", None, "name"]}
        sort_options = parse_sort_params(params)

        assert len(sort_options) == 3
        assert sort_options[0].field == "updated_at"
        assert sort_options[1].field == "created_at"
        assert sort_options[2].field == "name"


class TestBuildSortString:
    """Test cases for build_sort_string function."""

    def test_build_sort_string_single_ascending(self):
        """Test building sort string with single ascending sort."""
        sort_options = [SortOption(field="created_at", order="asc")]
        sort_string = build_sort_string(sort_options)

        assert sort_string == "created_at"

    def test_build_sort_string_single_descending(self):
        """Test building sort string with single descending sort."""
        sort_options = [SortOption(field="updated_at", order="desc")]
        sort_string = build_sort_string(sort_options)

        assert sort_string == "-updated_at"

    def test_build_sort_string_multiple(self):
        """Test building sort string with multiple sorts."""
        sort_options = [
            SortOption(field="updated_at", order="desc"),
            SortOption(field="created_at", order="asc"),
        ]
        sort_string = build_sort_string(sort_options)

        assert sort_string == "-updated_at,created_at"

    def test_build_sort_string_empty_list(self):
        """Test building sort string with empty list."""
        sort_options = []
        sort_string = build_sort_string(sort_options)

        assert sort_string == ""

    def test_build_sort_string_all_descending(self):
        """Test building sort string with all descending."""
        sort_options = [
            SortOption(field="updated_at", order="desc"),
            SortOption(field="created_at", order="desc"),
            SortOption(field="name", order="desc"),
        ]
        sort_string = build_sort_string(sort_options)

        assert sort_string == "-updated_at,-created_at,-name"

    def test_build_sort_string_all_ascending(self):
        """Test building sort string with all ascending."""
        sort_options = [
            SortOption(field="name", order="asc"),
            SortOption(field="email", order="asc"),
        ]
        sort_string = build_sort_string(sort_options)

        assert sort_string == "name,email"

    def test_build_sort_string_mixed(self):
        """Test building sort string with mixed ascending and descending."""
        sort_options = [
            SortOption(field="updated_at", order="desc"),
            SortOption(field="created_at", order="asc"),
            SortOption(field="name", order="desc"),
        ]
        sort_string = build_sort_string(sort_options)

        assert sort_string == "-updated_at,created_at,-name"

    def test_build_sort_string_url_encoding(self):
        """Test that sort string properly URL encodes field names."""
        sort_options = [SortOption(field="user name", order="asc")]
        sort_string = build_sort_string(sort_options)

        # Should URL encode spaces
        assert "%20" in sort_string or "user%20name" in sort_string

    def test_build_sort_string_complex_field_name(self):
        """Test building sort string with complex field name."""
        sort_options = [SortOption(field="created_at", order="desc")]
        sort_string = build_sort_string(sort_options)

        assert sort_string == "-created_at"

    def test_build_sort_string_special_characters(self):
        """Test building sort string with special characters in field name."""
        sort_options = [SortOption(field="user-id", order="asc")]
        sort_string = build_sort_string(sort_options)

        assert "user-id" in sort_string or "%2D" in sort_string  # URL encoded hyphen
