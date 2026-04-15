"""JWT token utilities for safe decoding without verification.

This module provides utilities for extracting information from JWT tokens
without verification, used for cache optimization and context extraction.
Includes JWT token caching for performance optimization.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, cast

import jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Safely decode JWT token without verification.

    This is used for extracting user information (like userId) from tokens
    for cache optimization. The token is NOT verified - it should only be
    used for cache key generation, not for authentication decisions.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload as dictionary, or None if decoding fails

    """
    try:
        # Decode without verification (no secret key needed)
        decoded = cast(Dict[str, Any], jwt.decode(token, options={"verify_signature": False}))
        return decoded
    except Exception:
        # Token is invalid or malformed
        return None


def extract_user_id(token: str) -> Optional[str]:
    """Extract user ID from JWT token.

    Tries common JWT claim fields: sub, userId, user_id, id

    Args:
        token: JWT token string

    Returns:
        User ID string if found, None otherwise

    """
    decoded = decode_token(token)
    if not decoded:
        return None

    # Try common JWT claim fields for user ID
    user_id = (
        decoded.get("sub") or decoded.get("userId") or decoded.get("user_id") or decoded.get("id")
    )

    return str(user_id) if user_id else None


def extract_session_id(token: str) -> Optional[str]:
    """Extract session ID from JWT token.

    Args:
        token: JWT token string

    Returns:
        Session ID string if found, None otherwise

    """
    decoded = decode_token(token)
    if not decoded:
        return None

    value = decoded.get("sid") or decoded.get("sessionId")
    return value if isinstance(value, str) else None


class JwtTokenCache:
    """JWT token cache with expiration tracking.

    Caches decoded JWT tokens to avoid repeated decoding operations.
    """

    def __init__(self, max_size: int = 1000):
        """Initialize JWT token cache.

        Args:
            max_size: Maximum cache size to prevent memory leaks

        """
        self._cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}
        self._max_size = max_size

    def _get_cached_token(self, token: str, now: datetime) -> Optional[Dict[str, Any]]:
        """Return cached token when still valid, else remove expired cache entry."""
        cached = self._cache.get(token)
        if not cached:
            return None
        cached_decoded, expires_at = cached
        if expires_at > now:
            return cached_decoded
        del self._cache[token]
        return None

    def _resolve_cache_expiration(self, decoded: Dict[str, Any], now: datetime) -> datetime:
        """Resolve cache expiration timestamp from JWT claims."""
        default_exp = now + timedelta(hours=1)
        exp = decoded.get("exp")
        if isinstance(exp, (int, float)):
            token_exp = datetime.fromtimestamp(exp)
            return min(token_exp - timedelta(minutes=5), default_exp)
        return default_exp

    def _evict_cache_entries(self) -> None:
        """Evict oldest cache entries to maintain max cache size bound."""
        if len(self._cache) < self._max_size:
            return
        keys_to_remove = list(self._cache.keys())[: self._max_size // 10]
        for key in keys_to_remove:
            del self._cache[key]

    def _decode_and_cache_token(self, token: str, now: datetime) -> Optional[Dict[str, Any]]:
        """Decode token and cache the decoded payload with expiration."""
        decoded = decode_token(token)
        if not decoded:
            return None
        self._evict_cache_entries()
        self._cache[token] = (decoded, self._resolve_cache_expiration(decoded, now))
        return decoded

    def get_decoded_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Get decoded JWT token with cache and expiration handling."""
        now = datetime.now()
        cached = self._get_cached_token(token, now)
        if cached is not None:
            return cached
        try:
            return self._decode_and_cache_token(token, now)
        except Exception:
            return None

    def extract_user_id_from_headers(self, headers: Dict[str, Any]) -> Optional[str]:
        """Extract user ID from JWT token in Authorization header with caching.

        Args:
            headers: Request headers dictionary

        Returns:
            User ID if found, None otherwise

        """
        auth_header = headers.get("authorization") or headers.get("Authorization")
        if not auth_header or not isinstance(auth_header, str):
            return None

        # Extract token (Bearer <token> format)
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header

        try:
            decoded = self.get_decoded_token(token)
            if decoded:
                return decoded.get("sub") or decoded.get("userId") or decoded.get("user_id")
        except Exception:
            pass

        return None

    def clear_token(self, token: str) -> None:
        """Clear a specific token from cache.

        Args:
            token: JWT token string to remove from cache

        """
        if token in self._cache:
            del self._cache[token]
