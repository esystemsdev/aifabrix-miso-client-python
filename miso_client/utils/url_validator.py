"""URL validation utility for controller URLs.

This module provides utilities for validating HTTP/HTTPS URLs with comprehensive
checks to prevent dangerous protocols and ensure valid URL structure.
"""

from urllib.parse import urlparse

_DANGEROUS_PROTOCOLS = ("javascript:", "data:", "vbscript:", "file:", "about:")


def _is_invalid_input(url: str) -> bool:
    """Check whether input URL value is empty or not a string."""
    return not url or not isinstance(url, str)


def _normalize_url(url: str) -> str:
    """Normalize URL input for validation checks."""
    return url.strip()


def _has_dangerous_protocol(url: str) -> bool:
    """Return True when URL starts with dangerous protocol prefix."""
    lowered = url.lower()
    return any(lowered.startswith(protocol) for protocol in _DANGEROUS_PROTOCOLS)


def _has_http_scheme(url: str) -> bool:
    """Return True for HTTP/HTTPS URLs."""
    lowered = url.lower()
    return lowered.startswith(("http://", "https://"))


def _has_valid_hostname(url: str) -> bool:
    """Validate parsed URL hostname/netloc presence."""
    parsed = urlparse(url)
    if not parsed.netloc:
        return False
    hostname = parsed.netloc.split(":")[0]
    return bool(hostname)


def validate_url(url: str) -> bool:
    """Validate HTTP/HTTPS URL with protocol and hostname checks."""
    if _is_invalid_input(url):
        return False

    url = _normalize_url(url)
    if not url:
        return False

    if _has_dangerous_protocol(url):
        return False

    if not _has_http_scheme(url):
        return False
    try:
        return _has_valid_hostname(url)
    except Exception:
        return False
