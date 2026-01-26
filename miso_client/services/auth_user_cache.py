"""
User info caching helpers for AuthService.

This module provides caching functionality for user information
to reduce API calls to the controller.
"""

import logging
import time
from typing import TYPE_CHECKING, Optional

from ..models.config import UserInfo
from ..utils.jwt_tools import extract_user_id

if TYPE_CHECKING:
    from ..services.cache import CacheService

logger = logging.getLogger(__name__)


def get_user_cache_key(user_id: str) -> str:
    """
    Generate cache key for user info.

    Args:
        user_id: User ID string

    Returns:
        Cache key string in format: user:{userId}
    """
    return f"user:{user_id}"


async def check_user_info_cache(cache: Optional["CacheService"], token: str) -> Optional[UserInfo]:
    """
    Check cache for user info.

    Args:
        cache: CacheService instance (may be None)
        token: JWT token to extract userId from

    Returns:
        Cached UserInfo if found, None otherwise
    """
    if not cache:
        return None

    user_id = extract_user_id(token)
    if not user_id:
        return None

    cache_key = get_user_cache_key(user_id)
    cached_data = await cache.get(cache_key)
    if cached_data and isinstance(cached_data, dict) and "user" in cached_data:
        logger.debug("User info cache hit")
        return UserInfo(**cached_data["user"])

    return None


async def cache_user_info(
    cache: Optional["CacheService"], token: str, user_info: UserInfo, ttl: int
) -> None:
    """
    Cache user info result.

    Args:
        cache: CacheService instance (may be None)
        token: JWT token to extract userId from
        user_info: UserInfo to cache
        ttl: Time to live in seconds
    """
    if not cache:
        return

    user_id = extract_user_id(token)
    if not user_id:
        return

    cache_key = get_user_cache_key(user_id)
    try:
        cache_data = {
            "user": user_info.model_dump(),
            "timestamp": int(time.time() * 1000),
        }
        await cache.set(cache_key, cache_data, ttl)
        logger.debug(f"User info cached with TTL: {ttl}s")
    except Exception as error:
        logger.warning("Failed to cache user info", exc_info=error)


async def clear_user_cache(cache: Optional["CacheService"], token: str) -> None:
    """
    Clear cached user info for a user.

    Args:
        cache: CacheService instance (may be None)
        token: JWT token to extract userId from
    """
    if not cache:
        return

    user_id = extract_user_id(token)
    if user_id:
        try:
            await cache.delete(get_user_cache_key(user_id))
            logger.debug("User info cache cleared")
        except Exception as error:
            logger.warning("Failed to clear user cache", exc_info=error)
