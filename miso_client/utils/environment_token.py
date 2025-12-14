"""
Server-side environment token wrapper with origin validation and audit logging.

This module provides a secure server-side wrapper for fetching environment tokens
with origin validation and ISO 27001 compliant audit logging.
"""

from typing import Any

from ..errors import AuthenticationError
from ..services.logger import LoggerService
from .data_masker import DataMasker
from .origin_validator import validate_origin


async def get_environment_token(miso_client: Any, headers: Any) -> str:
    """
    Get environment token with origin validation and audit logging.

    This is a server-side wrapper that validates request origin before calling
    the controller, and logs audit events with ISO 27001 compliant data masking.

    Args:
        miso_client: MisoClient instance
        headers: Request headers dict or object with headers attribute

    Returns:
        Client token string

    Raises:
        AuthenticationError: If origin validation fails or token fetch fails

    Example:
        >>> from miso_client import MisoClient, MisoClientConfig
        >>> config = MisoClientConfig(...)
        >>> client = MisoClient(config)
        >>> headers = {"origin": "http://localhost:3000"}
        >>> token = await get_environment_token(client, headers)
    """
    config = miso_client.config
    logger: LoggerService = miso_client.logger

    # Validate origin if allowedOrigins is configured
    if config.allowedOrigins:
        validation_result = validate_origin(headers, config.allowedOrigins)
        if not validation_result["valid"]:
            error_message = validation_result.get("error", "Origin validation failed")

            # Log error and audit event before raising exception
            masked_config = {
                "clientId": config.client_id,
                "clientSecret": DataMasker.mask_sensitive_data(config.client_secret),
            }

            await logger.error(
                "Origin validation failed for environment token request",
                context={
                    "error": error_message,
                    "allowedOrigins": config.allowedOrigins,
                    "clientId": config.client_id,
                },
            )

            await logger.audit(
                "auth.environment_token.origin_validation_failed",
                resource="/api/v1/auth/token",
                context={
                    "error": error_message,
                    "allowedOrigins": config.allowedOrigins,
                    **masked_config,
                },
            )

            raise AuthenticationError(f"Origin validation failed: {error_message}")

    # Log audit event before calling controller (with masked credentials)
    masked_config = {
        "clientId": config.client_id,
        "clientSecret": DataMasker.mask_sensitive_data(config.client_secret),
    }

    await logger.audit(
        "auth.environment_token.request",
        resource=config.clientTokenUri or "/api/v1/auth/token",
        context=masked_config,
    )

    try:
        # Call auth service to get environment token
        token: str = await miso_client.auth.get_environment_token()

        # Log successful token fetch
        await logger.audit(
            "auth.environment_token.success",
            resource=config.clientTokenUri or "/api/v1/auth/token",
            context={
                "clientId": config.client_id,
                "tokenLength": len(token) if token else 0,
            },
        )

        return token

    except Exception as error:
        # Log error and audit event
        await logger.error(
            "Failed to get environment token",
            context={
                "error": str(error),
                "clientId": config.client_id,
            },
        )

        await logger.audit(
            "auth.environment_token.failure",
            resource=config.clientTokenUri or "/api/v1/auth/token",
            context={
                "error": str(error),
                **masked_config,
            },
        )

        # Re-raise as AuthenticationError
        if isinstance(error, AuthenticationError):
            raise
        raise AuthenticationError(f"Failed to get environment token: {str(error)}") from error
