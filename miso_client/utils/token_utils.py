"""Client token utilities for extracting information from JWT tokens.

This module provides utilities for decoding client tokens and extracting
application/environment information without verification.
"""

from typing import Dict, Optional

from .jwt_tools import decode_token

EMPTY_TOKEN_INFO = {
    "application": None,
    "environment": None,
    "applicationId": None,
    "clientId": None,
}


def _normalized_str(value: Optional[object]) -> Optional[str]:
    """Normalize possible string token value."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def _pick_field(decoded: Dict[str, object], keys: list[str]) -> Optional[str]:
    """Pick first non-empty string field from claim aliases."""
    for key in keys:
        normalized = _normalized_str(decoded.get(key))
        if normalized is not None:
            return normalized
    return None


def extract_client_token_info(client_token: str) -> Dict[str, Optional[str]]:
    """Extract application/environment identity info from client token."""
    if not client_token or not isinstance(client_token, str):
        return dict(EMPTY_TOKEN_INFO)

    try:
        decoded = decode_token(client_token)
        if not decoded or not isinstance(decoded, dict):
            return dict(EMPTY_TOKEN_INFO)

        return {
            "application": _pick_field(decoded, ["application", "app", "Application", "App"]),
            "environment": _pick_field(decoded, ["environment", "env", "Environment", "Env"]),
            "applicationId": _pick_field(
                decoded,
                ["applicationId", "app_id", "application_id", "ApplicationId", "AppId"],
            ),
            "clientId": _pick_field(decoded, ["clientId", "client_id", "ClientId", "Client_Id"]),
        }

    except Exception:
        return dict(EMPTY_TOKEN_INFO)
