"""
Unit tests for CacheService.
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.services.cache import CacheService
from miso_client.services.redis import RedisService


class TestCacheService:
    """Test cases for CacheService."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis service."""
        redis = MagicMock(spec=RedisService)
        redis.is_connected = MagicMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def cache_with_redis(self, mock_redis):
        """Cache service with Redis."""
        return CacheService(redis=mock_redis)

    @pytest.fixture
    def cache_no_redis(self):
        """Cache service without Redis."""
        return CacheService(redis=None)

    @pytest.mark.asyncio
    async def test_get_from_redis(self, cache_with_redis, mock_redis):
        """Test getting value from Redis."""
        mock_redis.get = AsyncMock(return_value=json.dumps("cached_value"))

        value = await cache_with_redis.get("test_key")

        assert value == "cached_value"
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_from_memory_when_redis_unavailable(self, cache_with_redis, mock_redis):
        """Test fallback to memory cache when Redis is unavailable."""
        mock_redis.is_connected = MagicMock(return_value=False)
        mock_redis.get = AsyncMock(return_value=None)

        # Set in memory
        await cache_with_redis.set("test_key", "memory_value", 60)

        # Get should use memory
        value = await cache_with_redis.get("test_key")

        assert value == "memory_value"
        mock_redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_from_memory_only(self, cache_no_redis):
        """Test getting from memory-only cache."""
        await cache_no_redis.set("test_key", "value", 60)

        value = await cache_no_redis.get("test_key")

        assert value == "value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, cache_no_redis):
        """Test getting non-existent key returns None."""
        value = await cache_no_redis.get("nonexistent")

        assert value is None

    @pytest.mark.asyncio
    async def test_set_both_redis_and_memory(self, cache_with_redis, mock_redis):
        """Test setting value in both Redis and memory."""
        await cache_with_redis.set("test_key", "test_value", 60)

        # Verify Redis was called
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][2] == 60

        # Verify memory cache has it
        mock_redis.is_connected = MagicMock(return_value=False)
        value = await cache_with_redis.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_set_memory_only(self, cache_no_redis):
        """Test setting value in memory-only cache."""
        result = await cache_no_redis.set("test_key", "value", 60)

        assert result is True
        value = await cache_no_redis.get("test_key")
        assert value == "value"

    @pytest.mark.asyncio
    async def test_set_complex_object(self, cache_no_redis):
        """Test caching complex objects (dict, list)."""
        complex_obj = {"name": "test", "items": [1, 2, 3], "nested": {"key": "value"}}

        await cache_no_redis.set("complex", complex_obj, 60)
        retrieved = await cache_no_redis.get("complex")

        assert retrieved == complex_obj
        assert retrieved["name"] == "test"
        assert retrieved["items"] == [1, 2, 3]
        assert retrieved["nested"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_set_primitive_types(self, cache_no_redis):
        """Test caching primitive types."""
        test_cases = [
            ("string_key", "string_value"),
            ("int吃饭_key", 42),
            ("float_key", 3.14),
            ("bool_true", True),
            ("bool_false", False),
            ("none_key", None),
        ]

        for key, value in test_cases:
            await cache_no_redis.set(key, value, 60)
            retrieved = await cache_no_redis.get(key)
            assert retrieved == value

    @pytest.mark.asyncio
    async def test_ttl_expiration_memory(self, cache_no_redis):
        """Test TTL expiration in memory cache."""
        await cache_no_redis.set("expiring_key", "value", 1)  # 1 second TTL

        # Should be available immediately
        assert await cache_no_redis.get("expiring_key") == "value"

        # Wait for expiration
        time.sleep(1.1)

        # Should be None after expiration
        assert await cache_no_redis.get("expiring_key") is None

    @pytest.mark.asyncio
    async def test_delete_from_redis_and_memory(self, cache_with_redis, mock_redis):
        """Test deleting from both Redis and memory."""
        # Set in memory
        await cache_with_redis.set("test_key", "value", 60)

        # Delete
        result = await cache_with_redis.delete("test_key")

        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")

        # Verify memory cache is cleared
        assert await cache_with_redis.get("test_key") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache_no_redis):
        """Test deleting non-existent key."""
        result = await cache_no_redis.delete("nonexistent")

        # Should return False when nothing was deleted
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_memory_only(self, cache_no_redis):
        """Test deleting from memory-only cache."""
        await cache_no_redis.set("test_key", "value", 60)
        result = await cache_no_redis.delete("test_key")

        assert result is True
        assert await cache_no_redis.get("test_key") is None

    @pytest.mark.asyncio
    async def test_clear_memory(self, cache_no_redis):
        """Test clearing memory cache."""
        await cache_no_redis.set("key1", "value1", 60)
        await cache_no_redis.set("key2", "value2", 60)

        await cache_no_redis.clear()

        assert await cache_no_redis.get("key1") is None
        assert await cache_no_redis.get("key2") is None

    @pytest.mark.asyncio
    async def test_redis_failure_fallback(self, cache_with_redis, mock_redis):
        """Test fallback to memory when Redis operations fail."""
        mock_redis.is_connected = MagicMock(return_value=True)
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))

        # Set in memory first
        await cache_with_redis.set("test_key", "value", 60)

        # Get should fallback to memory when Redis fails
        mock_redis.is_connected = MagicMock(return_value=False)
        value = await cache_with_redis.get("test_key")

        assert value == "value"

    @pytest.mark.asyncio
    async def test_redis_set_failure_still_caches_memory(self, cache_with_redis, mock_redis):
        """Test that memory cache works even if Redis set fails."""
        mock_redis.set = AsyncMock(side_effect=Exception("Redis error"))

        # Should still succeed and cache in memory
        result = await cache_with_redis.set("test_key", "value", 60)

        assert result is True

        # Should be retrievable from memory
        mock_redis.is_connected = MagicMock(return_value=False)
        value = await cache_with_redis.get("test_key")
        assert value == "value"

    @pytest.mark.asyncio
    async def test_serialize_complex_nested_object(self, cache_no_redis):
        """Test serialization of complex nested objects."""
        complex_obj = {
            "users": [
                {"id": 1, "name": "Alice", "roles": ["admin", "user"]},
                {"id": 2, "name": "Bob", "roles": ["user"]},
            ],
            "metadata": {"timestamp": 1234567890, "version": "1.0.0"},
        }

        await cache_no_redis.set("complex_key", complex_obj, 60)
        value = await cache_no_redis.get("complex_key")

        assert value == complex_obj

    def test_serialize_primitive_types(self, cache_no_redis):
        """Test serialization of primitive types."""
        # Test integer
        serialized_int = cache_no_redis._serialize_value(123)
        assert serialized_int == "123"

        # Test float
        serialized_float = cache_no_redis._serialize_value(45.67)
        assert serialized_float == "45.67"

        # Test boolean
        serialized_bool = cache_no_redis._serialize_value(True)
        assert serialized_bool == "true"

        # Test None
        serialized_none = cache_no_redis._serialize_value(None)
        assert serialized_none == "null"

    def test_deserialize_with_cached_value_marker(self, cache_no_redis):
        """Test deserialization with __cached_value__ marker."""
        # Serialize complex object
        obj = {"key": "value", "nested": {"inner": 123}}
        serialized = cache_no_redis._serialize_value(obj)

        # Deserialize
        deserialized = cache_no_redis._deserialize_value(serialized)

        assert deserialized == obj

    def test_deserialize_plain_string_no_json(self, cache_no_redis):
        """Test deserialization of plain string that's not valid JSON."""
        # Plain string that's not JSON
        value = cache_no_redis._deserialize_value("just a string")

        assert value == "just a string"

    @pytest.mark.asyncio
    async def test_cleanup_expired_when_threshold_exceeded(self, cache_no_redis):
        """Test cleanup of expired entries when cache exceeds threshold."""
        # Set cleanup threshold to a small value for testing
        cache_no_redis._cleanup_threshold = 5

        # Add many entries, some expired
        for i in range(10):
            await cache_no_redis.set(f"key_{i}", f"value_{i}", -1 if i % 2 == 0 else 60)

        # Trigger cleanup by adding another entry
        await cache_no_redis.set("new_key", "new_value", 60)

        # Expired entries should be cleaned up
        # Check that expired keys are gone
        for i in range(10):
            if i % 2 == 0:
                value = await cache_no_redis.get(f"key_{i}")
                assert value is None
            else:
                value = await cache_no_redis.get(f"key_{i}")
                assert value == f"value_{i}"

    def test_is_expired(self, cache_no_redis):
        """Test expiration checking."""
        import time

        # Future expiration (not expired)
        future_exp = time.time() + 3600
        assert cache_no_redis._is_expired(future_exp) is False

        # Past expiration (expired)
        past_exp = time.time() - 3600
        assert cache_no_redis._is_expired(past_exp) is True

    @pytest.mark.asyncio
    async def test_clear_operation(self, cache_no_redis):
        """Test clear operation."""
        # Add some entries
        await cache_no_redis.set("key1", "value1", 60)
        await cache_no_redis.set("key2", "value2", 60)

        # Clear cache
        await cache_no_redis.clear()

        # Verify entries are gone
        assert await cache_no_redis.get("key1") is None
        assert await cache_no_redis.get("key2") is None

    @pytest.mark.asyncio
    async def test_get_when_redis_raises_exception(self, cache_with_redis, mock_redis):
        """Test get when Redis raises exception (should fallback to memory)."""
        mock_redis.is_connected.return_value = True
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))

        # Set in memory
        await cache_with_redis.set("test_key", "memory_value", 60)

        # Get should fallback to memory
        value = await cache_with_redis.get("test_key")

        assert value == "memory_value"

    @pytest.mark.asyncio
    async def test_set_when_redis_raises_exception(self, cache_with_redis, mock_redis):
        """Test set when Redis raises exception (should continue to memory)."""
        mock_redis.is_connected.return_value = True
        mock_redis.set = AsyncMock(side_effect=Exception("Redis error"))

        # Should still cache in memory
        result = await cache_with_redis.set("test_key", "value", 60)

        assert result is True
        # Verify memory cache has it
        value = await cache_with_redis.get("test_key")
        assert value == "value"

    @pytest.mark.asyncio
    async def test_cleanup_expired_entries(self, cache_no_redis):
        """Test automatic cleanup of expired entries."""
        # Set multiple keys with short TTL
        await cache_no_redis.set("expired_key1", "value1", 1)
        await cache_no_redis.set("expired_key2", "value2", 1)

        # Wait for expiration
        time.sleep(1.1)

        # Getting expired keys should return None and remove them
        assert await cache_no_redis.get("expired_key1") is None
        assert await cache_no_redis.get("expired_key2") is None

        # Verify they're removed from memory cache
        # (getting them again should still return None)
        assert await cache_no_redis.get("expired_key1") is None
        assert await cache_no_redis.get("expired_key2") is None

    @pytest.mark.asyncio
    async def test_serialization_deserialization(self, cache_no_redis):
        """Test proper serialization/deserialization of different types."""
        test_data = {
            "string": "text",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        await cache_no_redis.set("data", test_data, 60)
        retrieved = await cache_no_redis.get("data")

        assert retrieved == test_data
        assert isinstance(retrieved, dict)
        assert isinstance(retrieved["list"], list)
        assert isinstance(retrieved["dict"], dict)

    @pytest.mark.asyncio
    async def test_concurrent_access(self, cache_no_redis):
        """Test concurrent cache access."""
        import asyncio

        async def set_key(i):
            await cache_no_redis.set(f"key{i}", f"value{i}", 60)
            return await cache_no_redis.get(f"key{i}")

        # Set multiple keys concurrently
        results = await asyncio.gather(*[set_key(i) for i in range(10)])

        # All should succeed
        for i, value in enumerate(results):
            assert value == f"value{i}"

    @pytest.mark.asyncio
    async def test_unicode_keys_and_values(self, cache_no_redis):
        """Test caching with Unicode keys and values."""
        await cache_no_redis.set("测试", "值", 60)
        await cache_no_redis.set("emoji🎉", "🚀", 60)

        assert await cache_no_redis.get("测试") == "值"
        assert await cache_no_redis.get("emoji🎉") == "🚀"
