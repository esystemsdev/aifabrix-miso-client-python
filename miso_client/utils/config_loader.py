"""
Configuration loader utility.

Automatically loads environment variables with sensible defaults.
"""

import os
from typing import Optional
from ..models.config import MisoClientConfig, RedisConfig
from ..errors import ConfigurationError


def load_config() -> MisoClientConfig:
    """
    Load configuration from environment variables with defaults.
    
    Required environment variables:
    - MISO_CONTROLLER_URL (or default to https://controller.aifabrix.ai)
    - MISO_CLIENTID or MISO_CLIENT_ID
    - MISO_CLIENTSECRET or MISO_CLIENT_SECRET
    
    Optional environment variables:
    - MISO_LOG_LEVEL (debug, info, warn, error)
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
    
    controller_url = os.environ.get("MISO_CONTROLLER_URL") or "https://controller.aifabrix.ai"
    
    client_id = os.environ.get("MISO_CLIENTID") or os.environ.get("MISO_CLIENT_ID") or ""
    if not client_id:
        raise ConfigurationError("MISO_CLIENTID environment variable is required")
    
    client_secret = os.environ.get("MISO_CLIENTSECRET") or os.environ.get("MISO_CLIENT_SECRET") or ""
    if not client_secret:
        raise ConfigurationError("MISO_CLIENTSECRET environment variable is required")
    
    log_level = os.environ.get("MISO_LOG_LEVEL", "info")
    if log_level not in ["debug", "info", "warn", "error"]:
        log_level = "info"
    
    config: MisoClientConfig = MisoClientConfig(
        controller_url=controller_url,
        client_id=client_id,
        client_secret=client_secret,
        log_level=log_level,
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

