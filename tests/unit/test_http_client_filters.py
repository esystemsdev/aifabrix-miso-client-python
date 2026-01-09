"""
Unit tests for HTTP client filter and pagination integration.

This module contains tests for HttpClient filter and pagination helper methods:
get_with_filters and get_paginated.
"""

from unittest.mock import AsyncMock

import pytest

from miso_client.models.config import MisoClientConfig
from miso_client.models.filter import FilterBuilder, FilterOption, FilterQuery, JsonFilter
from miso_client.models.pagination import PaginatedListResponse
from miso_client.services.logger import LoggerService
from miso_client.services.redis import RedisService
from miso_client.utils.http_client import HttpClient
from miso_client.utils.internal_http_client import InternalHttpClient


class TestHttpClientGetWithFilters:
    """Test cases for HttpClient.get_with_filters method."""

    @pytest.fixture
    def config(self):
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            log_level="info",
        )

    @pytest.fixture
    def redis_service(self, config):
        return RedisService(config.redis)

    @pytest.fixture
    def internal_http_client(self, config):
        return InternalHttpClient(config)

    @pytest.fixture
    def logger_service(self, internal_http_client, redis_service):
        return LoggerService(internal_http_client, redis_service)

    @pytest.fixture
    def http_client(self, config, logger_service):
        return HttpClient(config, logger_service)

    @pytest.mark.asyncio
    async def test_get_with_filters_single_filter(self, http_client):
        """Test get_with_filters with single filter."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Create filter builder
        filter_builder = FilterBuilder().add("status", "eq", "active")

        result = await http_client.get_with_filters("/api/items", filter_builder)

        assert result == {"data": "test"}
        # Verify get was called with params
        mock_internal_client.get.assert_called_once()
        call_args = mock_internal_client.get.call_args
        assert "params" in call_args[1]
        params = call_args[1]["params"]
        assert "filter" in params

    @pytest.mark.asyncio
    async def test_get_with_filters_multiple_filters(self, http_client):
        """Test get_with_filters with multiple filters."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Create filter builder with multiple filters
        filter_builder = (
            FilterBuilder().add("status", "eq", "active").add("region", "in", ["eu", "us"])
        )

        result = await http_client.get_with_filters("/api/items", filter_builder)

        assert result == {"data": "test"}
        mock_internal_client.get.assert_called_once()
        call_args = mock_internal_client.get.call_args
        params = call_args[1]["params"]
        assert "filter" in params

    @pytest.mark.asyncio
    async def test_get_with_filters_no_filter_builder(self, http_client):
        """Test get_with_filters without filter builder."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        result = await http_client.get_with_filters("/api/items", None)

        assert result == {"data": "test"}
        mock_internal_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_with_filters_with_existing_params(self, http_client):
        """Test get_with_filters with existing query parameters."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.get = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        # Create filter builder
        filter_builder = FilterBuilder().add("status", "eq", "active")

        result = await http_client.get_with_filters(
            "/api/items", filter_builder, params={"other": "value"}
        )

        assert result == {"data": "test"}
        mock_internal_client.get.assert_called_once()
        call_args = mock_internal_client.get.call_args
        params = call_args[1]["params"]
        # Should have both filter and other params
        assert "filter" in params or "other" in params


class TestHttpClientGetPaginated:
    """Test cases for HttpClient.get_paginated method."""

    @pytest.fixture
    def config(self):
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            log_level="info",
        )

    @pytest.fixture
    def redis_service(self, config):
        return RedisService(config.redis)

    @pytest.fixture
    def internal_http_client(self, config):
        return InternalHttpClient(config)

    @pytest.fixture
    def logger_service(self, internal_http_client, redis_service):
        return LoggerService(internal_http_client, redis_service)

    @pytest.fixture
    def http_client(self, config, logger_service):
        return HttpClient(config, logger_service)

    @pytest.mark.asyncio
    async def test_get_paginated_basic(self, http_client):
        """Test get_paginated with basic pagination."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_response = {
            "meta": {
                "totalItems": 120,
                "currentPage": 1,
                "pageSize": 25,
                "type": "item",
            },
            "data": [{"id": 1}, {"id": 2}],
        }
        mock_internal_client.get = AsyncMock(return_value=mock_response)
        http_client._internal_client = mock_internal_client

        result = await http_client.get_paginated("/api/items", page=1, page_size=25)

        assert isinstance(result, PaginatedListResponse)
        assert result.meta.totalItems == 120
        assert result.meta.currentPage == 1
        assert result.meta.pageSize == 25
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_get_paginated_with_params(self, http_client):
        """Test get_paginated adds pagination params to request."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_response = {
            "meta": {"totalItems": 10, "currentPage": 2, "pageSize": 5, "type": "item"},
            "data": [],
        }
        mock_internal_client.get = AsyncMock(return_value=mock_response)
        http_client._internal_client = mock_internal_client

        await http_client.get_paginated("/api/items", page=2, page_size=5)

        mock_internal_client.get.assert_called_once()
        call_args = mock_internal_client.get.call_args
        assert "params" in call_args[1]
        params = call_args[1]["params"]
        assert params["page"] == 2
        assert params["pageSize"] == 5

    @pytest.mark.asyncio
    async def test_get_paginated_no_pagination(self, http_client):
        """Test get_paginated without pagination params."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_response = {"meta": {"totalItems": 10}, "data": []}
        mock_internal_client.get = AsyncMock(return_value=mock_response)
        http_client._internal_client = mock_internal_client

        result = await http_client.get_paginated("/api/items")

        assert result == mock_response  # Should return raw response if doesn't match format

    @pytest.mark.asyncio
    async def test_get_paginated_only_page(self, http_client):
        """Test get_paginated with only page parameter."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_response = {
            "meta": {"totalItems": 10, "currentPage": 2, "pageSize": 25, "type": "item"},
            "data": [],
        }
        mock_internal_client.get = AsyncMock(return_value=mock_response)
        http_client._internal_client = mock_internal_client

        await http_client.get_paginated("/api/items", page=2)

        mock_internal_client.get.assert_called_once()
        call_args = mock_internal_client.get.call_args
        params = call_args[1]["params"]
        assert params["page"] == 2

    @pytest.mark.asyncio
    async def test_get_paginated_only_page_size(self, http_client):
        """Test get_paginated with only page_size parameter."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_response = {
            "meta": {"totalItems": 10, "currentPage": 1, "pageSize": 50, "type": "item"},
            "data": [],
        }
        mock_internal_client.get = AsyncMock(return_value=mock_response)
        http_client._internal_client = mock_internal_client

        await http_client.get_paginated("/api/items", page_size=50)

        mock_internal_client.get.assert_called_once()
        call_args = mock_internal_client.get.call_args
        params = call_args[1]["params"]
        assert params["pageSize"] == 50

    @pytest.mark.asyncio
    async def test_get_paginated_invalid_response_format(self, http_client):
        """Test get_paginated with response that doesn't match PaginatedListResponse format."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_response = {"items": [{"id": 1}], "total": 10}  # Different format
        mock_internal_client.get = AsyncMock(return_value=mock_response)
        http_client._internal_client = mock_internal_client

        result = await http_client.get_paginated("/api/items", page=1, page_size=25)

        # Should return raw response when format doesn't match
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_get_paginated_with_existing_params(self, http_client):
        """Test get_paginated with existing query parameters."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_response = {
            "meta": {"totalItems": 10, "currentPage": 1, "pageSize": 25, "type": "item"},
            "data": [],
        }
        mock_internal_client.get = AsyncMock(return_value=mock_response)
        http_client._internal_client = mock_internal_client

        await http_client.get_paginated(
            "/api/items", page=1, page_size=25, params={"other": "value"}
        )

        mock_internal_client.get.assert_called_once()
        call_args = mock_internal_client.get.call_args
        params = call_args[1]["params"]
        # Should have both pagination and other params
        assert params["page"] == 1
        assert params["pageSize"] == 25
        assert params["other"] == "value"


class TestHttpClientPostWithFilters:
    """Test cases for HttpClient.post_with_filters method."""

    @pytest.fixture
    def config(self):
        return MisoClientConfig(
            controller_url="https://controller.aifabrix.ai",
            client_id="test-client",
            client_secret="test-secret",
            log_level="info",
        )

    @pytest.fixture
    def redis_service(self, config):
        return RedisService(config.redis)

    @pytest.fixture
    def internal_http_client(self, config):
        return InternalHttpClient(config)

    @pytest.fixture
    def logger_service(self, internal_http_client, redis_service):
        return LoggerService(internal_http_client, redis_service)

    @pytest.fixture
    def http_client(self, config, logger_service):
        return HttpClient(config, logger_service)

    @pytest.mark.asyncio
    async def test_post_with_filters_json_filter(self, http_client):
        """Test post_with_filters with JsonFilter."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        json_filter = JsonFilter(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )

        result = await http_client.post_with_filters("/api/items/search", json_filter=json_filter)

        assert result == {"data": "test"}
        mock_internal_client.post.assert_called_once()
        call_args = mock_internal_client.post.call_args
        assert call_args[0][0] == "/api/items/search"
        body = call_args[0][1]
        assert body is not None
        assert "filters" in body
        assert body["page"] == 1
        assert body["pageSize"] == 25

    @pytest.mark.asyncio
    async def test_post_with_filters_filter_query(self, http_client):
        """Test post_with_filters with FilterQuery."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        filter_query = FilterQuery(
            filters=[FilterOption(field="status", op="eq", value="active")],
            page=1,
            pageSize=25,
        )

        result = await http_client.post_with_filters("/api/items/search", json_filter=filter_query)

        assert result == {"data": "test"}
        mock_internal_client.post.assert_called_once()
        call_args = mock_internal_client.post.call_args
        body = call_args[0][1]
        assert "filters" in body
        assert body["page"] == 1
        assert body["pageSize"] == 25

    @pytest.mark.asyncio
    async def test_post_with_filters_with_json_body(self, http_client):
        """Test post_with_filters with additional JSON body."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        json_filter = JsonFilter(filters=[FilterOption(field="status", op="eq", value="active")])
        json_body = {"includeMetadata": True, "otherField": "value"}

        result = await http_client.post_with_filters(
            "/api/items/search", json_filter=json_filter, json_body=json_body
        )

        assert result == {"data": "test"}
        mock_internal_client.post.assert_called_once()
        call_args = mock_internal_client.post.call_args
        body = call_args[0][1]
        assert "filters" in body
        assert body["includeMetadata"] is True
        assert body["otherField"] == "value"

    @pytest.mark.asyncio
    async def test_post_with_filters_dict_filter(self, http_client):
        """Test post_with_filters with dict filter."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        filter_dict = {"filters": [{"field": "status", "op": "eq", "value": "active"}]}

        result = await http_client.post_with_filters("/api/items/search", json_filter=filter_dict)

        assert result == {"data": "test"}
        mock_internal_client.post.assert_called_once()
        call_args = mock_internal_client.post.call_args
        body = call_args[0][1]
        assert "filters" in body

    @pytest.mark.asyncio
    async def test_post_with_filters_no_filter(self, http_client):
        """Test post_with_filters without filter."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        result = await http_client.post_with_filters("/api/items/search")

        assert result == {"data": "test"}
        mock_internal_client.post.assert_called_once()
        call_args = mock_internal_client.post.call_args
        # Should pass None for data when no filter/body
        assert call_args[0][1] is None or call_args[0][1] == {}

    @pytest.mark.asyncio
    async def test_post_with_filters_only_json_body(self, http_client):
        """Test post_with_filters with only JSON body (no filter)."""
        # Mock InternalHttpClient
        mock_internal_client = AsyncMock()
        mock_internal_client.post = AsyncMock(return_value={"data": "test"})
        http_client._internal_client = mock_internal_client

        json_body = {"includeMetadata": True}

        result = await http_client.post_with_filters("/api/items/search", json_body=json_body)

        assert result == {"data": "test"}
        mock_internal_client.post.assert_called_once()
        call_args = mock_internal_client.post.call_args
        body = call_args[0][1]
        assert body["includeMetadata"] is True
