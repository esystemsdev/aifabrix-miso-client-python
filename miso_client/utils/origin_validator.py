"""Origin validation utility for CORS security.

This module provides utilities for validating request origins against
a list of allowed origins, with support for wildcard port matching.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def _result(valid: bool, error: Optional[str] = None) -> Dict[str, Any]:
    """Build normalized origin validation result payload."""
    return {"valid": valid, "error": error}


def _extract_headers_dict(headers: Any) -> Optional[Dict[str, Any]]:
    """Extract dictionary-like headers from supported request/header objects."""
    if isinstance(headers, dict):
        return headers
    if hasattr(headers, "headers"):
        headers_obj = getattr(headers, "headers")
        if isinstance(headers_obj, dict):
            return headers_obj
        if hasattr(headers_obj, "get"):
            return dict(headers_obj)
    if hasattr(headers, "get"):
        return dict(headers)
    return None


def _extract_non_empty_value(headers_dict: Dict[str, Any], keys: List[str]) -> Optional[str]:
    """Extract first non-empty string value from case-variant header keys."""
    for key in keys:
        value = headers_dict.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _origin_from_referer(referer_value: str) -> Optional[str]:
    """Extract origin part from referer URL string."""
    try:
        parsed = urlparse(referer_value)
    except Exception:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _resolve_origin(headers_dict: Dict[str, Any]) -> Optional[str]:
    """Resolve request origin from Origin or Referer headers."""
    origin = _extract_non_empty_value(headers_dict, ["origin", "Origin", "ORIGIN"])
    if origin:
        return origin
    referer = _extract_non_empty_value(
        headers_dict, ["referer", "Referer", "REFERER", "referrer", "Referrer", "REFERRER"]
    )
    if not referer:
        return None
    return _origin_from_referer(referer)


def _normalize_origin(origin: str) -> Optional[str]:
    """Normalize origin URL as lower-case scheme://host[:port] string."""
    try:
        parsed_origin = urlparse(origin)
    except Exception:
        return None
    if not parsed_origin.scheme or not parsed_origin.netloc:
        return None
    return f"{parsed_origin.scheme.lower()}://{parsed_origin.netloc.lower()}"


def _allowed_origin_matches(origin_normalized: str, allowed: str) -> bool:
    """Check whether a normalized request origin matches allowed origin pattern."""
    parsed_allowed = urlparse(allowed)
    allowed_scheme = parsed_allowed.scheme.lower()
    allowed_netloc = parsed_allowed.netloc.lower()
    allowed_normalized = f"{allowed_scheme}://{allowed_netloc}"
    if origin_normalized == allowed_normalized:
        return True
    if "*" not in allowed_netloc:
        return False
    origin_netloc = urlparse(origin_normalized).netloc
    origin_host = origin_netloc.split(":")[0]
    allowed_host = allowed_netloc.split(":")[0]
    allowed_port = allowed_netloc.split(":")[1] if ":" in allowed_netloc else None
    origin_scheme = urlparse(origin_normalized).scheme
    return bool(
        origin_host == allowed_host and allowed_port == "*" and origin_scheme == allowed_scheme
    )


def _is_allowed_origin(origin_normalized: str, allowed_origins: List[str]) -> bool:
    """Check normalized request origin against configured allowed origins."""
    for allowed in allowed_origins:
        if not allowed or not isinstance(allowed, str):
            continue
        try:
            if _allowed_origin_matches(origin_normalized, allowed):
                return True
        except Exception:
            continue
    return False


def validate_origin(headers: Any, allowed_origins: List[str]) -> Dict[str, Any]:
    """Validate request origin against an allowed-origins list."""
    if not allowed_origins:
        return _result(True)

    headers_dict = _extract_headers_dict(headers)
    if headers_dict is None:
        return _result(False, "Unable to extract headers from request")

    origin = _resolve_origin(headers_dict)
    if not origin:
        return _result(False, "No origin or referer header found")

    origin_normalized = _normalize_origin(origin)
    if not origin_normalized:
        return _result(False, f"Invalid origin format: {origin}")

    if _is_allowed_origin(origin_normalized, allowed_origins):
        return _result(True)
    return _result(False, f"Origin '{origin}' is not in allowed origins list")
