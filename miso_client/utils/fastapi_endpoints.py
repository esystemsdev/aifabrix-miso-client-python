"""
FastAPI endpoint utilities for client token endpoint.

Provides server-side route handlers for creating client token endpoints
that return client token + DataClient configuration to frontend clients.
"""

from typing import Any, Callable, Optional

from ..errors import AuthenticationError
from ..models.config import (
    ClientTokenEndpointOptions,
    ClientTokenEndpointResponse,
    DataClientConfigResponse,
    MisoClientConfig,
)
from ..utils.environment_token import get_environment_token


def create_fastapi_client_token_endpoint(
    miso_client: Any, options: Optional[ClientTokenEndpointOptions] = None
) -> Callable[[Any], Any]:
    """
    Create FastAPI route handler for client-token endpoint.

    Automatically enriches response with DataClient configuration including
    controllerPublicUrl for frontend client initialization.

    Args:
        miso_client: MisoClient instance (must be initialized)
        options: Optional configuration for endpoint

    Returns:
        FastAPI route handler function

    Example:
        >>> from fastapi import FastAPI
        >>> from miso_client import MisoClient, create_fastapi_client_token_endpoint, load_config
        >>>
        >>> app = FastAPI()
        >>> client = MisoClient(load_config())
        >>> await client.initialize()
        >>>
        >>> app.post('/api/v1/auth/client-token')(create_fastapi_client_token_endpoint(client))
    """
    opts = ClientTokenEndpointOptions(
        clientTokenUri=options.clientTokenUri if options else "/api/v1/auth/client-token",
        expiresIn=options.expiresIn if options else 1800,
        includeConfig=options.includeConfig if options else True,
    )

    async def handler(request: Any) -> ClientTokenEndpointResponse:
        """
        FastAPI route handler for client token endpoint.

        Args:
            request: FastAPI Request object

        Returns:
            ClientTokenEndpointResponse with token and optional config

        Raises:
            HTTPException: With appropriate status code on errors
        """
        try:
            # Check if misoClient is initialized
            if not miso_client.is_initialized():
                try:
                    from fastapi import HTTPException

                    raise HTTPException(
                        status_code=503,
                        detail={
                            "error": "Service Unavailable",
                            "message": "MisoClient is not initialized",
                        },
                    )
                except ImportError:
                    raise RuntimeError("FastAPI is not installed")

            # Get token with origin validation (raises AuthenticationError if validation fails)
            token = await get_environment_token(miso_client, request.headers)

            # Build response
            response: ClientTokenEndpointResponse = ClientTokenEndpointResponse(
                token=token, expiresIn=opts.expiresIn or 1800
            )

            # Include config if requested
            if opts.includeConfig:
                config: MisoClientConfig = miso_client.config

                # Derive baseUrl from request
                # request.base_url is a URL object in FastAPI
                base_url = str(request.base_url).rstrip("/")

                # Get controller URL (prefer controllerPublicUrl for browser, fallback to controller_url)
                controller_url = config.controllerPublicUrl or config.controller_url

                if not controller_url:
                    try:
                        from fastapi import HTTPException

                        raise HTTPException(
                            status_code=500,
                            detail={
                                "error": "Internal Server Error",
                                "message": "Controller URL not configured",
                            },
                        )
                    except ImportError:
                        raise RuntimeError("FastAPI is not installed")

                response.config = DataClientConfigResponse(
                    baseUrl=base_url,
                    controllerUrl=controller_url,
                    controllerPublicUrl=config.controllerPublicUrl,
                    clientId=config.client_id,
                    clientTokenUri=opts.clientTokenUri or "/api/v1/auth/client-token",
                )

            return response

        except AuthenticationError as error:
            # Origin validation failed (403)
            error_message = str(error)
            try:
                from fastapi import HTTPException

                if "Origin validation failed" in error_message:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "error": "Forbidden",
                            "message": error_message,
                        },
                    )

                # Other authentication errors (500)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "Internal Server Error",
                        "message": error_message,
                    },
                )
            except ImportError:
                raise RuntimeError("FastAPI is not installed")

        except Exception as error:
            # Other errors (500)
            error_message = str(error) if error else "Unknown error"
            try:
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "Internal Server Error",
                        "message": error_message,
                    },
                )
            except ImportError:
                raise RuntimeError("FastAPI is not installed")

    return handler
