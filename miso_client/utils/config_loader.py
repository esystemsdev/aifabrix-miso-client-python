"""
Configuration loader utility.

Automatically loads environment variables with sensible defaults.
"""

import os
from typing import List, Literal, cast

from ..errors import ConfigurationError
from ..models.config import AuthMethod, AuthStrategy, MisoClientConfig, RedisConfig


def load_config() -> MisoClientConfig:
    """
    Load configuration from environment variables with defaults.

    Required environment variables:
    - MISO_CONTROLLER_URL (or default to https://controller.aifabrix.ai)
    - MISO_CLIENTID or MISO_CLIENT_ID
    - MISO_CLIENTSECRET or MISO_CLIENT_SECRET

    Optional environment variables:
    - MISO_LOG_LEVEL (debug, info, warn, error)
    - API_KEY (for testing - bypasses OAuth2 authentication)
    - MISO_API_KEY (alternative to API_KEY)
    - MISO_AUTH_STRATEGY (comma-separated list: bearer,client-token,api-key)
    - MISO_CLIENT_TOKEN_URI (custom client token endpoint URI)
    - MISO_ALLOWED_ORIGINS (comma-separated list of allowed origins, supports wildcard ports)
    - MISO_CONTROLLER_URL (maps to controllerPrivateUrl and controller_url for backward compatibility)
    - MISO_WEB_SERVER_URL (maps to controllerPublicUrl for browser/public access)
    - REDIS_HOST (if Redis is used)
    - REDIS_PORT (default: 6379)
    - REDIS_PASSWORD
    - REDIS_DB (default: 0)
    - REDIS_KEY_PREFIX (default: miso:)

    Returns:
        MisoClientConfig instance

    Raises:
        ConfigurationError: If required environment variables are missing
    """
    # Load dotenv if available (similar to TypeScript dotenv/config)
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass  # dotenv not installed, continue without it

    # MISO_CONTROLLER_URL maps to controllerPrivateUrl (server/internal) and controller_url (backward compatibility)
    controller_url = os.environ.get("MISO_CONTROLLER_URL") or "https://controller.aifabrix.ai"
    controller_private_url = os.environ.get(
        "MISO_CONTROLLER_URL"
    )  # Same as controller_url for server
    # MISO_WEB_SERVER_URL maps to controllerPublicUrl (browser/public)
    controller_public_url = os.environ.get("MISO_WEB_SERVER_URL")

    client_id = os.environ.get("MISO_CLIENTID") or os.environ.get("MISO_CLIENT_ID") or ""
    if not client_id:
        raise ConfigurationError("MISO_CLIENTID environment variable is required")

    client_secret = (
        os.environ.get("MISO_CLIENTSECRET") or os.environ.get("MISO_CLIENT_SECRET") or ""
    )
    if not client_secret:
        raise ConfigurationError("MISO_CLIENTSECRET environment variable is required")

    log_level_str = os.environ.get("MISO_LOG_LEVEL", "info")
    if log_level_str not in ["debug", "info", "warn", "error"]:
        log_level_str = "info"
    # Constrain to Literal for type-checker
    log_level: Literal["debug", "info", "warn", "error"] = cast(
        Literal["debug", "info", "warn", "error"], log_level_str
    )

    # Optional API_KEY for testing (support both API_KEY and MISO_API_KEY)
    api_key = os.environ.get("API_KEY") or os.environ.get("MISO_API_KEY")

    # Optional auth strategy
    auth_strategy = None
    auth_strategy_str = os.environ.get("MISO_AUTH_STRATEGY")
    if auth_strategy_str:
        try:
            methods_str = [m.strip() for m in auth_strategy_str.split(",")]
            # Validate methods
            valid_methods: List[AuthMethod] = [
                "bearer",
                "client-token",
                "client-credentials",
                "api-key",
            ]
            methods: List[AuthMethod] = []
            for method in methods_str:
                if method in valid_methods:
                    methods.append(method)  # type: ignore
                else:
                    raise ConfigurationError(
                        f"Invalid auth method '{method}' in MISO_AUTH_STRATEGY. "
                        f"Valid methods: {', '.join(valid_methods)}"
                    )
            if methods:
                auth_strategy = AuthStrategy(methods=methods, apiKey=api_key)
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to parse MISO_AUTH_STRATEGY: {str(e)}")

    # Optional client token URI
    client_token_uri = os.environ.get("MISO_CLIENT_TOKEN_URI")

    # Optional allowed origins
    allowed_origins = None
    allowed_origins_str = os.environ.get("MISO_ALLOWED_ORIGINS")
    if allowed_origins_str:
        # Split comma-separated list and trim whitespace
        origins_list = [
            origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()
        ]
        if origins_list:
            allowed_origins = origins_list

    config: MisoClientConfig = MisoClientConfig(
        controller_url=controller_url,
        client_id=client_id,
        client_secret=client_secret,
        log_level=log_level,
        api_key=api_key,
        authStrategy=auth_strategy,
        clientTokenUri=client_token_uri,
        allowedOrigins=allowed_origins,
        controllerPrivateUrl=controller_private_url,
        controllerPublicUrl=controller_public_url,
    )

    # Optional Redis configuration
    redis_host = os.environ.get("REDIS_HOST")
    if redis_host:
        redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        redis_password = os.environ.get("REDIS_PASSWORD")
        redis_db = int(os.environ.get("REDIS_DB", "0")) if os.environ.get("REDIS_DB") else 0
        redis_key_prefix = os.environ.get("REDIS_KEY_PREFIX", "miso:")

        redis_config = RedisConfig(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db,
            key_prefix=redis_key_prefix,
        )

        config.redis = redis_config

    return config
