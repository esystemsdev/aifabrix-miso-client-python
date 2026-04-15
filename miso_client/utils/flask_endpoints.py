"""Flask endpoint utilities for client token endpoint.

Provides server-side route handlers for creating client token endpoints
that return client token + DataClient configuration to frontend clients.
"""

import asyncio
from typing import Any, Callable, Optional

from ..errors import AuthenticationError
from ..models.config import (
    ClientTokenEndpointOptions,
    ClientTokenEndpointResponse,
    DataClientConfigResponse,
    MisoClientConfig,
)
from ..utils.environment_token import get_environment_token


def _build_options(options: Optional[ClientTokenEndpointOptions]) -> ClientTokenEndpointOptions:
    """Build endpoint options with defaults."""
    return ClientTokenEndpointOptions(
        clientTokenUri=options.clientTokenUri if options else "/api/v1/auth/client-token",
        expiresIn=options.expiresIn if options else 1800,
        includeConfig=options.includeConfig if options else True,
    )


def _error_response(message: str, status_code: int, error: str) -> tuple[dict[str, Any], int]:
    """Return normalized endpoint error response."""
    return ({"error": error, "message": message}, status_code)


def _import_flask_request() -> Optional[Any]:
    """Import Flask request object if Flask is available."""
    try:
        from flask import request
    except ImportError:
        return None
    return request


def _get_token_sync(miso_client: Any, headers: Any) -> str:
    """Resolve async token retrieval in sync Flask handler context."""
    try:
        _ = asyncio.get_running_loop()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, get_environment_token(miso_client, headers))
            return str(future.result())
    except RuntimeError:
        return str(asyncio.run(get_environment_token(miso_client, headers)))


def _build_data_client_config(
    request: Any, config: MisoClientConfig, opts: ClientTokenEndpointOptions
) -> Optional[DataClientConfigResponse]:
    """Build DataClient configuration section for response."""
    base_url = f"{request.scheme}://{request.host or 'localhost'}"
    controller_url = config.controllerPublicUrl or config.controller_url
    if not controller_url:
        return None
    return DataClientConfigResponse(
        baseUrl=base_url,
        controllerUrl=controller_url,
        controllerPublicUrl=config.controllerPublicUrl,
        clientId=config.client_id,
        clientTokenUri=opts.clientTokenUri or "/api/v1/auth/client-token",
    )


def _authentication_error_response(error: AuthenticationError) -> tuple[dict[str, Any], int]:
    """Map authentication errors to endpoint response."""
    error_message = str(error)
    if "Origin validation failed" in error_message:
        return _error_response(error_message, 403, "Forbidden")
    return _error_response(error_message, 500, "Internal Server Error")


def _append_config_or_error(
    response: ClientTokenEndpointResponse,
    miso_client: Any,
    request: Any,
    opts: ClientTokenEndpointOptions,
) -> Optional[tuple[dict[str, Any], int]]:
    """Append response config or return error response when config is invalid."""
    if not opts.includeConfig:
        return None
    config: MisoClientConfig = miso_client.config
    built_config = _build_data_client_config(request, config, opts)
    if built_config is None:
        return _error_response("Controller URL not configured", 500, "Internal Server Error")
    response.config = built_config
    return None


def create_flask_client_token_endpoint(
    miso_client: Any, options: Optional[ClientTokenEndpointOptions] = None
) -> Callable[[], Any]:
    opts = _build_options(options)
    return _build_flask_handler(miso_client, opts)


def _build_flask_handler(miso_client: Any, opts: ClientTokenEndpointOptions) -> Callable[[], Any]:
    """Build Flask endpoint handler with validated options."""

    def handler() -> tuple[dict[str, Any], int]:
        """Flask route handler for client token endpoint."""
        try:
            if not miso_client.is_initialized():
                return _error_response("MisoClient is not initialized", 503, "Service Unavailable")

            request = _import_flask_request()
            if request is None:
                return _error_response("Flask is not installed", 500, "Internal Server Error")

            token = _get_token_sync(miso_client, request.headers)
            response: ClientTokenEndpointResponse = ClientTokenEndpointResponse(
                token=token, expiresIn=opts.expiresIn or 1800
            )
            config_error = _append_config_or_error(response, miso_client, request, opts)
            if config_error:
                return config_error

            return response.model_dump(exclude_none=True), 200

        except AuthenticationError as error:
            return _authentication_error_response(error)

        except Exception as error:
            error_message = str(error) if error else "Unknown error"
            return _error_response(error_message, 500, "Internal Server Error")

    return handler
