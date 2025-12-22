"""
Controller URL resolver with environment detection.

Automatically selects appropriate controller URL based on environment
(public for browser, private for server) with fallback support.
"""

from typing import Optional

from ..errors import ConfigurationError
from ..models.config import MisoClientConfig
from .url_validator import validate_url


def is_browser() -> bool:
    """
    Check if running in browser environment.

    For Python SDK (server-side only), always returns False.

    Returns:
        False (Python SDK is server-side only)
    """
    return False


def resolve_controller_url(config: MisoClientConfig) -> str:
    """
    Resolve controller URL based on environment and configuration.

    For server environment:
    - Uses controllerPrivateUrl if set
    - Falls back to controller_url if controllerPrivateUrl not set
    - Validates resolved URL
    - Raises ConfigurationError if no valid URL found

    Args:
        config: MisoClient configuration

    Returns:
        Resolved controller URL string

    Raises:
        ConfigurationError: If no valid URL is configured

    Example:
        >>> config = MisoClientConfig(
        ...     controller_url="https://controller.example.com",
        ...     controllerPrivateUrl="https://controller-private.example.com",
        ...     client_id="test",
        ...     client_secret="secret"
        ... )
        >>> url = resolve_controller_url(config)
        >>> url
        'https://controller-private.example.com'
    """
    # Server environment: prefer controllerPrivateUrl, fallback to controller_url
    resolved_url: Optional[str] = None

    if is_browser():
        # Browser environment (not applicable for Python SDK, but included for completeness)
        resolved_url = config.controllerPublicUrl or config.controller_url
    else:
        # Server environment
        resolved_url = config.controllerPrivateUrl or config.controller_url

    if not resolved_url:
        raise ConfigurationError(
            "No controller URL configured. Set controller_url, controllerPrivateUrl, "
            "or controllerPublicUrl in MisoClientConfig."
        )

    # Validate URL
    if not validate_url(resolved_url):
        raise ConfigurationError(
            f"Invalid controller URL format: {resolved_url}. "
            "URL must start with http:// or https:// and have a valid hostname."
        )

    return resolved_url
