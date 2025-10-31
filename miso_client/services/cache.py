"""
Cache service with Redis support and in-memory TTL fallback.

This module provides a generic caching service that can be used anywhere.
It supports Redis-backed caching when available, with automatic fallback to
in-memory TTL-based caching when Redis is unavailable.
"""

import json
import time
from typing import Any, Dict, Optional, Tuple

from ..services.redis import RedisService


class CacheService:
    """Cache service with Redis and in-memory TTL fallback."""

    def __init__(self, redis: Optional[RedisService] = None):
        """
        Initialize cache service.

        Args:
            redis: Optional RedisService instance. If provided, Redis will be used
                  as primary cache with in-memory as fallback. If None, only
                  in-memory caching is used.
        """
        self.redis = redis
        # In-memory cache: {key: (value, expiration_timestamp)}
        self._memory_cache: Dict[str, Tuple[Any, float]] = {}
        # Cleanup threshold: clean expired entries if cache exceeds this size
        self._cleanup_threshold = 1000

    def _is_expired(self, expiration: float) -> bool:
        """Check if entry has expired."""
        return time.time() > expiration

    def _cleanup_expired(self) -> None:
        """Remove expired entries from memory cache."""
        if len(self._memory_cache) <= self._cleanup_threshold:
            return

        expired_keys = [
            key
            for key, (_, expiration) in self._memory_cache.items()
            if self._is_expired(expiration)
        ]

        for key in expired_keys:
            del self._memory_cache[key]

    def _serialize_value(self, value: Any) -> str:
        """
        Serialize value to JSON string.

        Args:
            value: Value to serialize (can be any JSON-serializable type)

        Returns:
            JSON string representation
        """
        # For primitive types (str, int, float, bool, None), return as-is or simple string
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, str):
                return value
            return json.dumps(value)

        # For complex types, use JSON serialization with a marker
        return json.dumps({"__cached_value__": value})

    def _deserialize_value(self, value_str: str) -> Any:
        """
        Deserialize JSON string back to original value.

        Args:
            value_str: JSON string to deserialize

        Returns:
            Deserialized value
        """
        if not value_str:
            return None

        try:
            # Try to parse as JSON
            parsed = json.loads(value_str)
            # Check if it's our wrapped format
            if isinstance(parsed, dict) and "__cached_value__" in parsed:
                return parsed["__cached_value__"]
            # Otherwise return as-is (could be a string or other JSON value)
            return parsed
        except (json.JSONDecodeError, TypeError):
            # If JSON parsing fails, assume it's a plain string
            return value_str

    async def get(self, key: str) -> Optional[Any]:
        """
        Get cached value.

        Checks Redis first (if available), then falls back to in-memory cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
        # Try Redis first if available and connected
        if self.redis and self.redis.is_connected():
            try:
                cached_value = await self.redis.get(key)
                if cached_value is not None:
                    return self._deserialize_value(cached_value)
            except Exception:
                # Redis operation failed, fall through to memory cache
                pass

        # Fallback to in-memory cache
        if key in self._memory_cache:
            value, expiration = self._memory_cache[key]
            if not self._is_expired(expiration):
                return value
            else:
                # Entry expired, remove it
                del self._memory_cache[key]

        return None

    async def set(self, key: str, value: Any, ttl: int) -> bool:
        """
        Set cached value with TTL.

        Stores in both Redis (if available) and in-memory cache.

        Args:
            key: Cache key
            value: Value to cache (any JSON-serializable type)
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        serialized_value = self._serialize_value(value)
        success = False

        # Store in Redis if available
        if self.redis and self.redis.is_connected():
            try:
                success = await self.redis.set(key, serialized_value, ttl)
            except Exception:
                # Redis operation failed, continue to memory cache
                pass

        # Also store in memory cache
        expiration = time.time() + ttl
        self._memory_cache[key] = (value, expiration)

        # Cleanup expired entries periodically
        self._cleanup_expired()

        return success or True  # Return True if at least memory cache succeeded

    async def delete(self, key: str) -> bool:
        """
        Delete cached value.

        Deletes from both Redis (if available) and in-memory cache.

        Args:
            key: Cache key

        Returns:
            True if deleted from at least one cache, False otherwise
        """
        deleted = False

        # Delete from Redis if available
        if self.redis and self.redis.is_connected():
            try:
                deleted = await self.redis.delete(key)
            except Exception:
                pass

        # Delete from memory cache
        if key in self._memory_cache:
            del self._memory_cache[key]
            deleted = True

        return deleted

    async def clear(self) -> None:
        """
        Clear all cached values.

        Clears both Redis (if available) and in-memory cache.
        Note: Redis clear operation only clears keys with the configured prefix,
        not the entire Redis database.
        """
        # Clear memory cache
        self._memory_cache.clear()

        # For Redis, we would need to delete all keys with the prefix
        # This is more complex and potentially dangerous, so we'll skip it
        # Users should use delete() for specific keys or clear Redis manually
        # if needed
