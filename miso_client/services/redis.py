"""
Redis service for caching and log queuing.

This module provides Redis connectivity with graceful degradation when Redis
is unavailable. It handles caching of roles and permissions, and log queuing.
"""

import logging
from typing import Optional

import redis.asyncio as redis

from ..models.config import RedisConfig

logger = logging.getLogger(__name__)


class RedisService:
    """Redis service for caching and log queuing."""

    def __init__(self, config: Optional[RedisConfig] = None):
        """
        Initialize Redis service.

        Args:
            config: Optional Redis configuration
        """
        self.config = config
        self.redis: Optional[redis.Redis] = None
        self.connected = False

    async def connect(self) -> None:
        """
        Connect to Redis.

        Raises:
            Exception: If connection fails and config is provided
        """
        if not self.config:
            logger.info("Redis not configured, using controller fallback")
            return

        try:
            self.redis = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                password=self.config.password,
                db=self.config.db,
                decode_responses=True,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )

            # Test connection
            # Some redis stubs type ping as possibly non-awaitable; support both
            resp = self.redis.ping()
            if hasattr(resp, "__await__"):
                await resp  # type: ignore[misc]
            self.connected = True
            logger.info("Connected to Redis")

        except Exception as error:
            logger.error(f"Failed to connect to Redis: {error}", exc_info=error)
            self.connected = False
            if self.config:  # Only raise if Redis was configured
                raise error

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.aclose()
            self.connected = False
            logger.info("Disconnected from Redis")

    def is_connected(self) -> bool:
        """
        Check if Redis is connected.

        Returns:
            True if connected, False otherwise
        """
        return self.connected and self.redis is not None

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from Redis.

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
            resp = self.redis.get(prefixed_key)
            if hasattr(resp, "__await__"):
                result = await resp  # type: ignore[misc]
            else:
                result = resp
            return None if result is None else str(result)
        except Exception as error:
            logger.error("Redis get error", exc_info=error)
            return None

    async def set(self, key: str, value: str, ttl: int) -> bool:
        """
        Set value in Redis with TTL.

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
            resp = self.redis.setex(prefixed_key, ttl, value)
            if hasattr(resp, "__await__"):
                await resp  # type: ignore[misc]
            return True
        except Exception as error:
            logger.error("Redis set error", exc_info=error)
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from Redis.

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
            resp = self.redis.delete(prefixed_key)
            if hasattr(resp, "__await__"):
                await resp  # type: ignore[misc]
            return True
        except Exception as error:
            logger.error("Redis delete error", exc_info=error)
            return False

    async def rpush(self, queue: str, value: str) -> bool:
        """
        Push value to Redis list (for log queuing).

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
            resp = self.redis.rpush(prefixed_queue, value)
            if hasattr(resp, "__await__"):
                await resp  # type: ignore[misc]
            return True
        except Exception as error:
            logger.error("Redis rpush error", exc_info=error)
            return False
