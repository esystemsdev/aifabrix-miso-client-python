"""
Token validation caching helpers for AuthService.

This module provides caching functionality for token validation results
to reduce API calls to the controller.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

if TYPE_CHECKING:
    from ..services.cache import CacheService

logger = logging.getLogger(__name__)


async def check_cache_for_token(
    cache: Optional["CacheService"], cache_key: str
) -> Optional[Dict[str, Any]]:
    """
    Check cache for token validation result.

    Args:
        cache: CacheService instance (may be None)
        cache_key: Cache key for the token

    Returns:
        Cached validation result if found, None otherwise
    """
    if not cache:
        return None

    cached_result = await cache.get(cache_key)
    if cached_result and isinstance(cached_result, dict):
        logger.debug("Token validation cache hit")
        return cast(Dict[str, Any], cached_result)

    return None


async def cache_validation_result(
    cache: Optional["CacheService"],
    cache_key: str,
    result: Dict[str, Any],
    ttl: int,
) -> None:
    """
    Cache successful validation results.

    Args:
        cache: CacheService instance (may be None)
        cache_key: Cache key for the token
        result: Validation result dictionary
        ttl: Time to live in seconds
    """
    if not cache:
        return

    result_dict: Dict[str, Any] = result
    if result_dict.get("data", {}).get("authenticated") is not True:
        return

    try:
        await cache.set(cache_key, result_dict, ttl)
        logger.debug(f"Token validation cached with TTL: {ttl}s")
    except Exception as error:
        logger.warning("Failed to cache validation result", exc_info=error)
