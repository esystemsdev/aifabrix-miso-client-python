"""Server-side environment token wrapper with origin validation and audit logging.

This module provides a secure server-side wrapper for fetching environment tokens
with origin validation and ISO 27001 compliant audit logging.
"""

from typing import Any

from ..errors import AuthenticationError
from ..services.logger import LoggerService
from .data_masker import DataMasker
from .origin_validator import validate_origin


def _masked_config(config: Any) -> dict[str, Any]:
    """Build masked config payload for secure logging."""
    return {
        "clientId": config.client_id,
        "clientSecret": DataMasker.mask_sensitive_data(config.client_secret),
    }


def _token_resource(config: Any) -> str:
    """Resolve effective token endpoint resource path."""
    return config.clientTokenUri or "/api/v1/auth/token"


async def _log_origin_validation_failure(
    logger: LoggerService, config: Any, error_message: str, allowed_origins: Any = None
) -> None:
    """Log origin validation failure before raising auth error."""
    masked_config = _masked_config(config)
    await logger.error(
        "Origin validation failed for environment token request",
        context={
            "error": error_message,
            "allowedOrigins": config.allowedOrigins if allowed_origins is None else allowed_origins,
            "clientId": config.client_id,
        },
    )
    await logger.audit(
        "auth.environment_token.origin_validation_failed",
        resource="/api/v1/auth/token",
        context={
            "error": error_message,
            "allowedOrigins": config.allowedOrigins if allowed_origins is None else allowed_origins,
            **masked_config,
        },
    )


async def _validate_request_origin(
    config: Any, logger: LoggerService, headers: Any, allowed_origins: Any = None
) -> None:
    """Validate request origin when allowedOrigins is configured."""
    effective_origins = config.allowedOrigins if allowed_origins is None else allowed_origins
    if not effective_origins:
        return
    validation_result = validate_origin(headers, effective_origins)
    if validation_result["valid"]:
        return
    error_message = validation_result.get("error", "Origin validation failed")
    await _log_origin_validation_failure(logger, config, error_message, effective_origins)
    raise AuthenticationError(f"Origin validation failed: {error_message}")


async def _resolve_allowed_origins(miso_client: Any, logger: LoggerService) -> Any:
    """Resolve logical public origins before the existing synchronous matcher runs."""
    configured = miso_client.config.allowedOrigins
    if not configured or not any("url://" in origin for origin in configured):
        return configured
    try:
        return await miso_client.resolve_allowed_origins(configured)
    except Exception as error:
        message = f"Origin validation failed: {str(error)}"
        await _log_origin_validation_failure(logger, miso_client.config, message)
        raise AuthenticationError(message) from error


async def _request_environment_token(miso_client: Any) -> str:
    """Request environment token from auth service."""
    token: str = await miso_client.auth.get_environment_token()
    return token


async def _log_environment_token_success(logger: LoggerService, config: Any, token: str) -> None:
    """Log successful environment token request."""
    await logger.audit(
        "auth.environment_token.success",
        resource=_token_resource(config),
        context={"clientId": config.client_id, "tokenLength": len(token) if token else 0},
    )


async def _log_environment_token_failure(
    logger: LoggerService, config: Any, error: Exception
) -> None:
    """Log failed environment token request."""
    masked_config = _masked_config(config)
    await logger.error(
        "Failed to get environment token",
        context={"error": str(error), "clientId": config.client_id},
    )
    await logger.audit(
        "auth.environment_token.failure",
        resource=_token_resource(config),
        context={"error": str(error), **masked_config},
    )


async def get_environment_token(miso_client: Any, headers: Any) -> str:
    """Get environment token with origin validation and audit logging."""
    config = miso_client.config
    logger: LoggerService = miso_client.logger

    allowed_origins = await _resolve_allowed_origins(miso_client, logger)
    await _validate_request_origin(config, logger, headers, allowed_origins)
    masked_config = _masked_config(config)

    await logger.audit(
        "auth.environment_token.request",
        resource=_token_resource(config),
        context=masked_config,
    )

    try:
        token = await _request_environment_token(miso_client)
        await _log_environment_token_success(logger, config, token)
        return token

    except Exception as error:
        await _log_environment_token_failure(logger, config, error)
        if isinstance(error, AuthenticationError):
            raise
        raise AuthenticationError(f"Failed to get environment token: {str(error)}") from error
