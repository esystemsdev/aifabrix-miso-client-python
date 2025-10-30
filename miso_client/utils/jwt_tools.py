"""
JWT token utilities for safe decoding without verification.

This module provides utilities for extracting information from JWT tokens
without verification, used for cache optimization and context extraction.
"""

import jwt
from typing import Optional, Dict, Any, cast


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
        decoded.get("sub") or
        decoded.get("userId") or
        decoded.get("user_id") or
        decoded.get("id")
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

