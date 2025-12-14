"""
Origin validation utility for CORS security.

This module provides utilities for validating request origins against
a list of allowed origins, with support for wildcard port matching.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def validate_origin(headers: Any, allowed_origins: List[str]) -> Dict[str, Any]:
    """
    Validate request origin against allowed origins list.

    Checks the 'origin' header first, then falls back to 'referer' header.
    Supports wildcard ports (e.g., 'http://localhost:*' matches any port).

    Args:
        headers: Request headers dict or object with headers attribute
        allowed_origins: List of allowed origin URLs (supports wildcard ports)

    Returns:
        Dictionary with:
            - valid: bool - Whether origin is valid
            - error: Optional[str] - Error message if invalid, None if valid

    Example:
        >>> headers = {"origin": "http://localhost:3000"}
        >>> result = validate_origin(headers, ["http://localhost:*"])
        >>> result["valid"]
        True
    """
    if not allowed_origins:
        # If no allowed origins configured, allow all (backward compatibility)
        return {"valid": True, "error": None}

    # Extract headers dict from various request object types
    headers_dict: Optional[Dict[str, Any]] = None
    if isinstance(headers, dict):
        headers_dict = headers
    elif hasattr(headers, "headers"):
        # FastAPI, Flask style: request.headers
        headers_obj = getattr(headers, "headers")
        if isinstance(headers_obj, dict):
            headers_dict = headers_obj
        elif hasattr(headers_obj, "get"):
            # Headers object with get method (like Starlette headers)
            headers_dict = dict(headers_obj)
    elif hasattr(headers, "get"):
        # Already a dict-like object
        headers_dict = dict(headers)

    if headers_dict is None:
        return {"valid": False, "error": "Unable to extract headers from request"}

    # Extract origin from headers (case-insensitive)
    origin = None
    for key in ["origin", "Origin", "ORIGIN"]:
        if key in headers_dict:
            origin_value = headers_dict[key]
            if isinstance(origin_value, str) and origin_value.strip():
                origin = origin_value.strip()
                break

    # Fallback to referer header if origin not found
    if not origin:
        for key in ["referer", "Referer", "REFERER", "referrer", "Referrer", "REFERRER"]:
            if key in headers_dict:
                referer_value = headers_dict[key]
                if isinstance(referer_value, str) and referer_value.strip():
                    # Extract origin from referer URL
                    try:
                        parsed = urlparse(referer_value.strip())
                        if parsed.scheme and parsed.netloc:
                            origin = f"{parsed.scheme}://{parsed.netloc}"
                            break
                    except Exception:
                        pass

    if not origin:
        return {"valid": False, "error": "No origin or referer header found"}

    # Normalize origin (remove trailing slash, lowercase scheme/host)
    try:
        parsed_origin = urlparse(origin)
        if not parsed_origin.scheme or not parsed_origin.netloc:
            return {"valid": False, "error": f"Invalid origin format: {origin}"}
        origin_scheme = parsed_origin.scheme.lower()
        origin_netloc = parsed_origin.netloc.lower()
        origin_normalized = f"{origin_scheme}://{origin_netloc}"
    except Exception:
        return {"valid": False, "error": f"Invalid origin format: {origin}"}

    # Check against allowed origins
    for allowed in allowed_origins:
        if not allowed or not isinstance(allowed, str):
            continue

        try:
            parsed_allowed = urlparse(allowed)
            allowed_scheme = parsed_allowed.scheme.lower()
            allowed_netloc = parsed_allowed.netloc.lower()
            allowed_normalized = f"{allowed_scheme}://{allowed_netloc}"

            # Check for exact match
            if origin_normalized == allowed_normalized:
                return {"valid": True, "error": None}

            # Check for wildcard port match (e.g., localhost:* matches localhost:3000)
            if "*" in allowed_netloc:
                # Extract host from origin
                origin_host = origin_netloc.split(":")[0]

                # Extract host from allowed (may have wildcard port)
                allowed_host = allowed_netloc.split(":")[0]
                allowed_port = allowed_netloc.split(":")[1] if ":" in allowed_netloc else None

                # Match if host matches and allowed has wildcard port
                if origin_host == allowed_host and allowed_port == "*":
                    if origin_scheme == allowed_scheme:
                        return {"valid": True, "error": None}

        except Exception:
            # Skip invalid allowed origin format
            continue

    return {"valid": False, "error": f"Origin '{origin}' is not in allowed origins list"}
