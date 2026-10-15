"""FastAPI endpoint utilities for client token endpoint.

Provides server-side route handlers for creating client token endpoints
that return client token + DataClient configuration to frontend clients.
"""

import importlib
from typing import Any, Callable, NoReturn, Optional, Union

from ..errors import AuthenticationError
from ..models.config import (
    ClientTokenEndpointOptions,
    ClientTokenEndpointResponse,
    DataClientConfigResponse,
    MisoClientConfig,
)
from ..models.session_cookie import SessionCookieValidation
from ..utils.environment_token import get_environment_token


def _build_options(options: Optional[ClientTokenEndpointOptions]) -> ClientTokenEndpointOptions:
    """Build endpoint options with defaults."""
    return ClientTokenEndpointOptions(
        clientTokenUri=options.clientTokenUri if options else "/api/v1/auth/client-token",
        expiresIn=options.expiresIn if options else 1800,
        includeConfig=options.includeConfig if options else True,
    )


def _import_fastapi_http_exception() -> Any:
    """Import HTTPException from FastAPI, or raise RuntimeError if unavailable."""
    try:
        fastapi_module = importlib.import_module("fastapi")
        http_exception = getattr(fastapi_module, "HTTPException", None)
    except ImportError as error:
        raise RuntimeError("FastAPI is not installed") from error
    if http_exception is None:
        raise RuntimeError("FastAPI HTTPException class is unavailable")
    return http_exception


def _raise_http_error(status_code: int, message: str, error: str) -> NoReturn:
    """Raise FastAPI HTTPException with normalized payload."""
    HTTPException = _import_fastapi_http_exception()
    raise HTTPException(status_code=status_code, detail={"error": error, "message": message})


def _build_data_client_config(
    request: Any, config: MisoClientConfig, opts: ClientTokenEndpointOptions
) -> Optional[DataClientConfigResponse]:
    """Build DataClient configuration section for response."""
    controller_url = config.controllerPublicUrl or config.controller_url
    if not controller_url:
        return None
    return DataClientConfigResponse(
        baseUrl=str(request.base_url).rstrip("/"),
        controllerUrl=controller_url,
        controllerPublicUrl=config.controllerPublicUrl,
        clientId=config.client_id,
        clientTokenUri=opts.clientTokenUri or "/api/v1/auth/client-token",
    )


def _append_config_or_raise(
    response: ClientTokenEndpointResponse,
    request: Any,
    config: MisoClientConfig,
    opts: ClientTokenEndpointOptions,
) -> None:
    """Append response config or raise HTTP 500 when config is invalid."""
    if not opts.includeConfig:
        return
    built_config = _build_data_client_config(request, config, opts)
    if built_config is None:
        _raise_http_error(500, "Controller URL not configured", "Internal Server Error")
    response.config = built_config


def create_fastapi_client_token_endpoint(
    miso_client: Any, options: Optional[ClientTokenEndpointOptions] = None
) -> Callable[[Any], Any]:
    opts = _build_options(options)
    return _build_fastapi_handler(miso_client, opts)


def _build_fastapi_handler(
    miso_client: Any, opts: ClientTokenEndpointOptions
) -> Callable[[Any], Any]:
    async def handler(request: Any) -> ClientTokenEndpointResponse:
        try:
            if not miso_client.is_initialized():
                _raise_http_error(503, "MisoClient is not initialized", "Service Unavailable")

            token = await get_environment_token(miso_client, request.headers)
            response: ClientTokenEndpointResponse = ClientTokenEndpointResponse(
                token=token, expiresIn=opts.expiresIn or 1800
            )
            config: MisoClientConfig = miso_client.config
            _append_config_or_raise(response, request, config, opts)

            return response

        except AuthenticationError as error:
            error_message = str(error)
            if "Origin validation failed" in error_message:
                _raise_http_error(403, error_message, "Forbidden")
            _raise_http_error(500, error_message, "Internal Server Error")

        except Exception as error:
            if error.__class__.__name__ == "HTTPException":
                raise
            error_message = str(error) if error else "Unknown error"
            _raise_http_error(500, error_message, "Internal Server Error")

    return handler


def apply_session_cookie(
    response: Any, result: Optional[Union[SessionCookieValidation, str]]
) -> bool:
    """Add Miso's renewed session ``Set-Cookie`` to a FastAPI/Starlette response.

    The header is appended verbatim so Miso's cookie attributes (path,
    HttpOnly, SameSite, Secure) are kept.

    Args:
        response: FastAPI/Starlette response (``headers.append`` is used)
        result: Result of ``validate_or_refresh_session_cookie`` or a raw
            Set-Cookie value; None or a result without ``set_cookie`` is a no-op

    Returns:
        True when a cookie was added

    """
    set_cookie = result.set_cookie if isinstance(result, SessionCookieValidation) else result
    if not set_cookie:
        return False
    response.headers.append("set-cookie", set_cookie)
    return True
