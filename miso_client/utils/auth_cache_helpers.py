"""Authentication cache helper functions.

This module provides helper functions for token validation caching,
including cache key generation and TTL calculation.
"""

import hashlib
import logging
import time

from ..utils.jwt_tools import decode_token

logger = logging.getLogger(__name__)


def get_token_cache_key(token: str) -> str:
    """Generate cache key for token validation using SHA-256 hash.

    Uses token hash instead of full token for security.

    Args:
        token: JWT token string

    Returns:
        Cache key string in format: token_validation:{sha256_hash}

    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return f"token_validation:{token_hash}"


def get_cache_ttl_from_token(token: str, validation_ttl: int) -> int:
    """Calculate smart TTL based on token expiration.

    If token has expiration claim, cache until token_exp - 30s buffer.
    Minimum: 60 seconds, Maximum: validation_ttl.

    Args:
        token: JWT token string
        validation_ttl: Default validation TTL in seconds

    Returns:
        TTL in seconds

    """
    try:
        decoded = decode_token(token)
        if decoded and "exp" in decoded:
            token_exp = decoded["exp"]
            if isinstance(token_exp, (int, float)):
                now = time.time()
                # Calculate TTL as token_exp - now - 30s buffer
                ttl = int(token_exp - now - 30)
                # Clamp between min (60s) and max (validation_ttl)
                return max(60, min(ttl, validation_ttl))
    except Exception:
        # If token expiration cannot be determined, use default TTL
        pass

    return validation_ttl
