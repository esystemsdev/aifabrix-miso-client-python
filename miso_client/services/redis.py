"""Redis service for caching and log queuing.

This module provides Redis connectivity with graceful degradation when Redis
is unavailable. It handles caching of roles and permissions, and log queuing.
"""

import logging
from inspect import isawaitable
from typing import Awaitable, Optional, Protocol, TypeVar, cast

import redis.asyncio as redis

from ..models.config import RedisConfig
from ..utils.error_utils import extract_correlation_id_from_error

logger = logging.getLogger(__name__)
T = TypeVar("T")


class RedisClientLike(Protocol):
    """Minimal Redis client surface used by this service."""

    def ping(self) -> Awaitable[bool] | bool: ...

    def get(self, key: str) -> Awaitable[object | None] | object | None: ...

    def setex(self, key: str, ttl: int, value: str) -> Awaitable[object] | object: ...

    def delete(self, key: str) -> Awaitable[object] | object: ...

    def rpush(self, queue: str, value: str) -> Awaitable[object] | object: ...

    async def aclose(self) -> None: ...


def _error_extra(error: Exception) -> Optional[dict[str, str]]:
    """Build structured logger extra fields from exception context."""
    correlation_id = extract_correlation_id_from_error(error)
    return {"correlationId": correlation_id} if correlation_id else None


class RedisService:
    """Redis service for caching and log queuing."""

    def __init__(self, config: Optional[RedisConfig] = None):
        """Initialize Redis service.

        Args:
            config: Optional Redis configuration

        """
        self.config = config
        self.redis: Optional[RedisClientLike] = None
        self.connected = False

    def _build_redis_client(self) -> RedisClientLike:
        """Create configured Redis client instance."""
        assert self.config is not None
        return cast(
            RedisClientLike,
            redis.Redis(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                db=self.config.db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            ),
        )

    async def _resolve_maybe_awaitable(self, value: T | Awaitable[T]) -> T:
        """Return value directly or await it when needed."""
        if isawaitable(value):
            return await cast(Awaitable[T], value)
        return cast(T, value)

    async def connect(self) -> None:
        """Connect to Redis.

        Raises:
            Exception: If connection fails and config is provided

        """
        if not self.config:
            logger.info("Redis not configured, using controller fallback")
            return
        try:
            self.redis = self._build_redis_client()
            await self._resolve_maybe_awaitable(self.redis.ping())
            self.connected = True
            logger.info("Connected to Redis")
        except Exception as error:
            logger.error(
                f"Failed to connect to Redis: {error}",
                exc_info=error,
                extra=_error_extra(error),
            )
            self.connected = False
            if self.config:
                raise error

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.aclose()
            self.connected = False
            logger.info("Disconnected from Redis")

    def is_connected(self) -> bool:
        """Check if Redis is connected.

        Returns:
            True if connected, False otherwise

        """
        return self.connected and self.redis is not None

    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis.

        Args:
            key: Redis key

        Returns:
            Value if found, None otherwise

        """
        if not self.is_connected():
            return None

        try:
            assert self.redis is not None
            prefixed_key = f"{self.config.key_prefix}{key}" if self.config else key
            result = await self._resolve_maybe_awaitable(self.redis.get(prefixed_key))
            return None if result is None else str(result)
        except Exception as error:
            logger.error("Redis get error", exc_info=error, extra=_error_extra(error))
            return None

    async def set(self, key: str, value: str, ttl: int) -> bool:
        """Set value in Redis with TTL.

        Args:
            key: Redis key
            value: Value to store
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise

        """
        if not self.is_connected():
            return False

        try:
            assert self.redis is not None
            prefixed_key = f"{self.config.key_prefix}{key}" if self.config else key
            await self._resolve_maybe_awaitable(self.redis.setex(prefixed_key, ttl, value))
            return True
        except Exception as error:
            logger.error("Redis set error", exc_info=error, extra=_error_extra(error))
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from Redis.

        Args:
            key: Redis key

        Returns:
            True if successful, False otherwise

        """
        if not self.is_connected():
            return False

        try:
            assert self.redis is not None
            prefixed_key = f"{self.config.key_prefix}{key}" if self.config else key
            await self._resolve_maybe_awaitable(self.redis.delete(prefixed_key))
            return True
        except Exception as error:
            logger.error("Redis delete error", exc_info=error, extra=_error_extra(error))
            return False

    async def rpush(self, queue: str, value: str) -> bool:
        """Push value to Redis list (for log queuing).

        Args:
            queue: Queue name
            value: Value to push

        Returns:
            True if successful, False otherwise

        """
        if not self.is_connected():
            return False

        try:
            assert self.redis is not None
            prefixed_queue = f"{self.config.key_prefix}{queue}" if self.config else queue
            await self._resolve_maybe_awaitable(self.redis.rpush(prefixed_queue, value))
            return True
        except Exception as error:
            logger.error("Redis rpush error", exc_info=error, extra=_error_extra(error))
            return False
