"""Authentication utilities for shared use across services.

This module provides shared authentication utilities to avoid code duplication
across service classes.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from ..models.config import AuthStrategy
from ..utils.http_client import HttpClient

if TYPE_CHECKING:
    from ..api import ApiClient


def _validation_result_from_api_response(response: Any) -> Dict[str, Any]:
    """Convert typed API response to shared validation result shape."""
    return {
        "data": {
            "authenticated": response.data.authenticated,
            "user": response.data.user.model_dump() if response.data.user else None,
            "expiresAt": response.data.expiresAt,
        },
    }


async def _validate_with_http_client(
    token: str, http_client: HttpClient, auth_strategy: Optional[AuthStrategy]
) -> Dict[str, Any]:
    """Validate token using HttpClient fallback path."""
    if auth_strategy is not None:
        result = await http_client.authenticated_request(
            "POST",
            "/api/v1/auth/validate",
            token,
            {"token": token},
            auth_strategy=auth_strategy,
        )
        return result  # type: ignore[no-any-return]
    result = await http_client.authenticated_request(
        "POST", "/api/v1/auth/validate", token, {"token": token}
    )
    return result  # type: ignore[no-any-return]


async def validate_token_request(
    token: str,
    http_client: HttpClient,
    api_client: Optional["ApiClient"] = None,
    auth_strategy: Optional[AuthStrategy] = None,
) -> Dict[str, Any]:
    """Call `/api/v1/auth/validate` with shared response normalization."""
    if api_client:
        response = await api_client.auth.validate_token(token, auth_strategy=auth_strategy)
        return _validation_result_from_api_response(response)
    return await _validate_with_http_client(token, http_client, auth_strategy)
