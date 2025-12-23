"""
JWT token utilities for safe decoding without verification.

This module provides utilities for extracting information from JWT tokens
without verification, used for cache optimization and context extraction.
Includes JWT token caching for performance optimization.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, cast

import jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Safely decode JWT token without verification.

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
    """
    Extract user ID from JWT token.

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
    """
    Extract session ID from JWT token.

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
    """
    JWT token cache with expiration tracking.

    Caches decoded JWT tokens to avoid repeated decoding operations.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize JWT token cache.

        Args:
            max_size: Maximum cache size to prevent memory leaks
        """
        self._cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}
        self._max_size = max_size

    def get_decoded_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get decoded JWT token with caching for performance optimization.

        Tokens are cached with expiration tracking to avoid repeated decoding.

        Args:
            token: JWT token string

        Returns:
            Decoded token payload as dictionary, or None if decoding fails
        """
        now = datetime.now()

        # Check cache first
        if token in self._cache:
            cached_decoded, expires_at = self._cache[token]
            # If not expired, return cached value
            if expires_at > now:
                return cached_decoded
            # Expired, remove from cache
            del self._cache[token]

        # Decode token
        try:
            decoded = decode_token(token)
            if not decoded:
                return None

            # Extract expiration from token (if available)
            expires_at = now + timedelta(hours=1)  # Default: 1 hour cache
            if "exp" in decoded and isinstance(decoded["exp"], (int, float)):
                # Use token expiration minus 5 minutes buffer
                token_exp = datetime.fromtimestamp(decoded["exp"])
                expires_at = min(token_exp - timedelta(minutes=5), now + timedelta(hours=1))
            elif "iat" in decoded and "exp" not in decoded:
                # Estimate expiration if only issued_at is present
                expires_at = now + timedelta(hours=1)

            # Cache the decoded token
            # Limit cache size to prevent memory leaks
            if len(self._cache) >= self._max_size:
                # Remove oldest entries (simple FIFO - remove first 10%)
                keys_to_remove = list(self._cache.keys())[: self._max_size // 10]
                for key in keys_to_remove:
                    del self._cache[key]

            self._cache[token] = (decoded, expires_at)
            return decoded

        except Exception:
            return None

    def extract_user_id_from_headers(self, headers: Dict[str, Any]) -> Optional[str]:
        """
        Extract user ID from JWT token in Authorization header with caching.

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
        """
        Clear a specific token from cache.

        Args:
            token: JWT token string to remove from cache
        """
        if token in self._cache:
            del self._cache[token]
