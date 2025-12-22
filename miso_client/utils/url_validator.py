"""
URL validation utility for controller URLs.

This module provides utilities for validating HTTP/HTTPS URLs with comprehensive
checks to prevent dangerous protocols and ensure valid URL structure.
"""

from urllib.parse import urlparse


def validate_url(url: str) -> bool:
    """
    Validate HTTP/HTTPS URL with comprehensive checks.

    Validates that the URL:
    - Starts with http:// or https://
    - Has a valid hostname
    - Does not use dangerous protocols (javascript:, data:, etc.)

    Args:
        url: URL string to validate

    Returns:
        True if URL is valid, False otherwise

    Example:
        >>> validate_url("https://controller.example.com")
        True
        >>> validate_url("javascript:alert('xss')")
        False
        >>> validate_url("http://localhost:3000")
        True
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    if not url:
        return False

    # Check for dangerous protocols
    dangerous_protocols = ["javascript:", "data:", "vbscript:", "file:", "about:"]
    url_lower = url.lower()
    for protocol in dangerous_protocols:
        if url_lower.startswith(protocol):
            return False

    # Must start with http:// or https://
    if not url_lower.startswith(("http://", "https://")):
        return False

    try:
        parsed = urlparse(url)
        # Must have a valid hostname (netloc)
        if not parsed.netloc:
            return False

        # Hostname must not be empty
        hostname = parsed.netloc.split(":")[0]  # Remove port if present
        if not hostname:
            return False

        return True
    except Exception:
        # URL parsing failed
        return False
