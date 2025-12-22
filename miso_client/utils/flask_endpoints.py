"""
Flask endpoint utilities for client token endpoint.

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


def create_flask_client_token_endpoint(
    miso_client: Any, options: Optional[ClientTokenEndpointOptions] = None
) -> Callable[[], Any]:
    """
    Create Flask route handler for client-token endpoint.

    Automatically enriches response with DataClient configuration including
    controllerPublicUrl for frontend client initialization.

    Args:
        miso_client: MisoClient instance (must be initialized)
        options: Optional configuration for endpoint

    Returns:
        Flask route handler function

    Example:
        >>> from flask import Flask
        >>> from miso_client import MisoClient, create_flask_client_token_endpoint, load_config
        >>>
        >>> app = Flask(__name__)
        >>> client = MisoClient(load_config())
        >>> await client.initialize()
        >>>
        >>> app.post('/api/v1/auth/client-token')(create_flask_client_token_endpoint(client))
    """
    opts = ClientTokenEndpointOptions(
        clientTokenUri=options.clientTokenUri if options else "/api/v1/auth/client-token",
        expiresIn=options.expiresIn if options else 1800,
        includeConfig=options.includeConfig if options else True,
    )

    def handler() -> tuple[dict[str, Any], int]:
        """
        Flask route handler for client token endpoint.

        Returns:
            Tuple of (response_dict, status_code)
        """
        try:
            # Check if misoClient is initialized
            if not miso_client.is_initialized():
                return (
                    {
                        "error": "Service Unavailable",
                        "message": "MisoClient is not initialized",
                    },
                    503,
                )

            # Get Flask request object
            try:
                from flask import request
            except ImportError:
                return (
                    {
                        "error": "Internal Server Error",
                        "message": "Flask is not installed",
                    },
                    500,
                )

            # Get token with origin validation (raises AuthenticationError if validation fails)
            # Run async function in sync context
            # Handle both sync and async Flask contexts
            try:
                # Try to get existing event loop
                _ = asyncio.get_running_loop()
                # If we get here, we're in an async context (Flask 2.0+ async handler)
                # In this case, we need to await, but Flask async handlers handle this
                # For now, create a new event loop in a thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, get_environment_token(miso_client, request.headers)
                    )
                    token = future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                token = asyncio.run(get_environment_token(miso_client, request.headers))

            # Build response
            response: ClientTokenEndpointResponse = ClientTokenEndpointResponse(
                token=token, expiresIn=opts.expiresIn or 1800
            )

            # Include config if requested
            if opts.includeConfig:
                config: MisoClientConfig = miso_client.config

                # Derive baseUrl from request
                base_url = f"{request.scheme}://{request.host or 'localhost'}"

                # Get controller URL (prefer controllerPublicUrl for browser, fallback to controller_url)
                controller_url = config.controllerPublicUrl or config.controller_url

                if not controller_url:
                    return (
                        {
                            "error": "Internal Server Error",
                            "message": "Controller URL not configured",
                        },
                        500,
                    )

                response.config = DataClientConfigResponse(
                    baseUrl=base_url,
                    controllerUrl=controller_url,
                    controllerPublicUrl=config.controllerPublicUrl,
                    clientId=config.client_id,
                    clientTokenUri=opts.clientTokenUri or "/api/v1/auth/client-token",
                )

            return response.model_dump(exclude_none=True), 200

        except AuthenticationError as error:
            # Origin validation failed (403)
            error_message = str(error)
            if "Origin validation failed" in error_message:
                return (
                    {
                        "error": "Forbidden",
                        "message": error_message,
                    },
                    403,
                )

            # Other authentication errors (500)
            return (
                {
                    "error": "Internal Server Error",
                    "message": error_message,
                },
                500,
            )

        except Exception as error:
            # Other errors (500)
            error_message = str(error) if error else "Unknown error"
            return (
                {
                    "error": "Internal Server Error",
                    "message": error_message,
                },
                500,
            )

    return handler
