"""Controller URL resolver with environment detection.

Automatically selects appropriate controller URL based on environment
(public for browser, private for server) with fallback support.
"""

from typing import NoReturn, Optional

from ..errors import ConfigurationError
from ..models.config import MisoClientConfig
from .url_validator import validate_url


def is_browser() -> bool:
    """Check if running in browser environment.

    For Python SDK (server-side only), always returns False.

    Returns:
        False (Python SDK is server-side only)

    """
    return False


def _resolve_configured_url(config: MisoClientConfig) -> Optional[str]:
    """Resolve preferred controller URL by runtime environment."""
    if is_browser():
        return config.controllerPublicUrl or config.controller_url
    return config.controllerPrivateUrl or config.controller_url


def _raise_missing_url_config() -> NoReturn:
    """Raise standardized missing URL configuration error."""
    raise ConfigurationError(
        "No controller URL configured. Set controller_url, controllerPrivateUrl, "
        "or controllerPublicUrl in MisoClientConfig."
    )


def _validate_resolved_url(resolved_url: str) -> None:
    """Validate resolved URL and raise configuration error when invalid."""
    if validate_url(resolved_url):
        return
    raise ConfigurationError(
        f"Invalid controller URL format: {resolved_url}. "
        "URL must start with http:// or https:// and have a valid hostname."
    )


def resolve_controller_url(config: MisoClientConfig) -> str:
    """Resolve controller URL from config and validate it."""
    resolved_url = _resolve_configured_url(config)
    if not resolved_url:
        _raise_missing_url_config()
    assert resolved_url is not None
    _validate_resolved_url(resolved_url)
    return resolved_url
