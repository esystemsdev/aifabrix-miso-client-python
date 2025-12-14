"""
Client token utilities for extracting information from JWT tokens.

This module provides utilities for decoding client tokens and extracting
application/environment information without verification.
"""

from typing import Dict, Optional

from .jwt_tools import decode_token


def extract_client_token_info(client_token: str) -> Dict[str, Optional[str]]:
    """
    Extract application and environment information from client token.

    Decodes JWT token without verification (no secret available) and extracts
    fields with fallback support for multiple field name variations.

    Args:
        client_token: JWT client token string

    Returns:
        Dictionary with optional fields:
            - application: Optional[str] - Application name
            - environment: Optional[str] - Environment name
            - applicationId: Optional[str] - Application ID
            - clientId: Optional[str] - Client ID

    Example:
        >>> token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        >>> info = extract_client_token_info(token)
        >>> info.get("application")
        'my-app'
    """
    if not client_token or not isinstance(client_token, str):
        return {
            "application": None,
            "environment": None,
            "applicationId": None,
            "clientId": None,
        }

    try:
        decoded = decode_token(client_token)
        if not decoded or not isinstance(decoded, dict):
            return {
                "application": None,
                "environment": None,
                "applicationId": None,
                "clientId": None,
            }

        # Extract fields with fallback support
        application = (
            decoded.get("application")
            or decoded.get("app")
            or decoded.get("Application")
            or decoded.get("App")
        )
        if isinstance(application, str):
            application = application.strip() if application.strip() else None
        else:
            application = None

        environment = (
            decoded.get("environment")
            or decoded.get("env")
            or decoded.get("Environment")
            or decoded.get("Env")
        )
        if isinstance(environment, str):
            environment = environment.strip() if environment.strip() else None
        else:
            environment = None

        application_id = (
            decoded.get("applicationId")
            or decoded.get("app_id")
            or decoded.get("application_id")
            or decoded.get("ApplicationId")
            or decoded.get("AppId")
        )
        if isinstance(application_id, str):
            application_id = application_id.strip() if application_id.strip() else None
        else:
            application_id = None

        client_id = (
            decoded.get("clientId")
            or decoded.get("client_id")
            or decoded.get("ClientId")
            or decoded.get("Client_Id")
        )
        if isinstance(client_id, str):
            client_id = client_id.strip() if client_id.strip() else None
        else:
            client_id = None

        return {
            "application": application,
            "environment": environment,
            "applicationId": application_id,
            "clientId": client_id,
        }

    except Exception:
        # Decode failed, return empty dict
        return {
            "application": None,
            "environment": None,
            "applicationId": None,
            "clientId": None,
        }
