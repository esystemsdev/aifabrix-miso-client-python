"""Configuration loader utility.

Automatically loads environment variables with sensible defaults.
"""

import os
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

from ..errors import ConfigurationError
from ..models.config import AuthMethod, AuthStrategy, MisoClientConfig, RedisConfig

VALID_LOG_LEVELS = ("debug", "info", "warn", "error")
VALID_AUTH_METHODS: List[AuthMethod] = ["bearer", "client-token", "client-credentials", "api-key"]


def _load_dotenv_if_available() -> None:
    """Load `.env` file when python-dotenv is installed."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def _get_required_env(primary_key: str, secondary_key: str, error_message: str) -> str:
    """Read required environment variable from primary/secondary keys."""
    value = os.environ.get(primary_key) or os.environ.get(secondary_key) or ""
    if not value:
        raise ConfigurationError(error_message)
    return value


def _parse_log_level() -> Literal["debug", "info", "warn", "error"]:
    """Parse and normalize configured log level."""
    log_level_str = os.environ.get("MISO_LOG_LEVEL", "info")
    if log_level_str not in VALID_LOG_LEVELS:
        log_level_str = "info"
    return cast(Literal["debug", "info", "warn", "error"], log_level_str)


def _parse_auth_strategy(api_key: Optional[str]) -> Optional[AuthStrategy]:
    """Parse optional auth strategy from environment."""
    auth_strategy_str = os.environ.get("MISO_AUTH_STRATEGY")
    if not auth_strategy_str:
        return None

    try:
        methods: List[AuthMethod] = []
        for method in [item.strip() for item in auth_strategy_str.split(",")]:
            if method in VALID_AUTH_METHODS:
                methods.append(cast(AuthMethod, method))
            else:
                raise ConfigurationError(
                    f"Invalid auth method '{method}' in MISO_AUTH_STRATEGY. "
                    f"Valid methods: {', '.join(VALID_AUTH_METHODS)}"
                )
        return AuthStrategy(methods=methods, apiKey=api_key) if methods else None
    except ConfigurationError:
        raise
    except Exception as error:
        raise ConfigurationError(f"Failed to parse MISO_AUTH_STRATEGY: {str(error)}")


def _parse_allowed_origins() -> Optional[List[str]]:
    """Parse optional comma-separated allowed origins list."""
    allowed_origins_str = os.environ.get("MISO_ALLOWED_ORIGINS")
    if not allowed_origins_str:
        return None

    origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
    return origins if origins else None


def _build_redis_config() -> Optional[RedisConfig]:
    """Build optional Redis config from environment variables."""
    redis_host = os.environ.get("REDIS_HOST")
    if not redis_host:
        return None

    redis_password = os.environ.get("REDIS_PASSWORD")
    if redis_password == "":
        redis_password = None

    redis_db = int(os.environ.get("REDIS_DB", "0")) if os.environ.get("REDIS_DB") else 0
    return RedisConfig(
        host=redis_host,
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=redis_password,
        db=redis_db,
        key_prefix=os.environ.get("REDIS_KEY_PREFIX", "miso:"),
    )


def _resolve_controller_urls() -> Tuple[str, Optional[str], Optional[str]]:
    """Resolve controller URLs for server and browser contexts."""
    controller_url = os.environ.get("MISO_CONTROLLER_URL") or "https://controller.aifabrix.ai"
    controller_private_url = os.environ.get("MISO_CONTROLLER_URL")
    controller_public_url = os.environ.get("MISO_WEB_SERVER_URL")
    return controller_url, controller_private_url, controller_public_url


def _build_base_config(
    controller_url: str,
    controller_private_url: Optional[str],
    controller_public_url: Optional[str],
    client_id: str,
    client_secret: str,
    log_level: Literal["debug", "info", "warn", "error"],
    api_key: Optional[str],
    encryption_key: Optional[str],
    auth_strategy: Optional[AuthStrategy],
    client_token_uri: Optional[str],
    allowed_origins: Optional[List[str]],
) -> MisoClientConfig:
    """Build base MisoClientConfig without optional Redis section."""
    return MisoClientConfig(
        controller_url=controller_url,
        client_id=client_id,
        client_secret=client_secret,
        log_level=log_level,
        api_key=api_key,
        encryption_key=encryption_key,
        authStrategy=auth_strategy,
        clientTokenUri=client_token_uri,
        allowedOrigins=allowed_origins,
        controllerPrivateUrl=controller_private_url,
        controllerPublicUrl=controller_public_url,
    )


def _read_core_config_values() -> Dict[str, Any]:
    """Read and normalize core config values from environment."""
    controller_url, controller_private_url, controller_public_url = _resolve_controller_urls()
    client_id = _get_required_env(
        "MISO_CLIENTID", "MISO_CLIENT_ID", "MISO_CLIENTID environment variable is required"
    )
    client_secret = _get_required_env(
        "MISO_CLIENTSECRET",
        "MISO_CLIENT_SECRET",
        "MISO_CLIENTSECRET environment variable is required",
    )
    api_key = os.environ.get("API_KEY") or os.environ.get("MISO_API_KEY")
    return {
        "controller_url": controller_url,
        "controller_private_url": controller_private_url,
        "controller_public_url": controller_public_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "log_level": _parse_log_level(),
        "api_key": api_key,
        "encryption_key": os.environ.get("MISO_ENCRYPTION_KEY") or os.environ.get("ENCRYPTION_KEY"),
        "auth_strategy": _parse_auth_strategy(api_key),
        "client_token_uri": os.environ.get("MISO_CLIENT_TOKEN_URI"),
        "allowed_origins": _parse_allowed_origins(),
    }


def load_config() -> MisoClientConfig:
    """Load SDK configuration from environment variables."""
    _load_dotenv_if_available()
    values = _read_core_config_values()

    config = _build_base_config(
        controller_url=values["controller_url"],
        controller_private_url=values["controller_private_url"],
        controller_public_url=values["controller_public_url"],
        client_id=values["client_id"],
        client_secret=values["client_secret"],
        log_level=values["log_level"],
        api_key=values["api_key"],
        encryption_key=values["encryption_key"],
        auth_strategy=values["auth_strategy"],
        client_token_uri=values["client_token_uri"],
        allowed_origins=values["allowed_origins"],
    )

    redis_config = _build_redis_config()
    if redis_config:
        config.redis = redis_config

    return config
