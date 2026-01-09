"""
Authentication utilities for shared use across services.

This module provides shared authentication utilities to avoid code duplication
across service classes.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from ..models.config import AuthStrategy
from ..utils.http_client import HttpClient

if TYPE_CHECKING:
    from ..api import ApiClient


async def validate_token_request(
    token: str,
    http_client: HttpClient,
    api_client: Optional["ApiClient"] = None,
    auth_strategy: Optional[AuthStrategy] = None,
) -> Dict[str, Any]:
    """
    Helper function to call /api/v1/auth/validate endpoint with proper request body.

    Shared utility for RoleService and PermissionService to avoid code duplication.

    Args:
        token: JWT token to validate
        http_client: HTTP client instance (for backward compatibility)
        api_client: Optional API client instance (for typed API calls)
        auth_strategy: Optional authentication strategy

    Returns:
        Validation result dictionary
    """
    if api_client:
        # Use ApiClient for typed API calls
        response = await api_client.auth.validate_token(token, auth_strategy=auth_strategy)
        # Extract data from typed response
        return {
            "success": response.success,
            "data": {
                "authenticated": response.data.authenticated,
                "user": response.data.user.model_dump() if response.data.user else None,
                "expiresAt": response.data.expiresAt,
            },
            "timestamp": response.timestamp,
        }
    else:
        # Fallback to HttpClient for backward compatibility
        if auth_strategy is not None:
            result = await http_client.authenticated_request(
                "POST",
                "/api/v1/auth/validate",
                token,
                {"token": token},
                auth_strategy=auth_strategy,
            )
            return result  # type: ignore[no-any-return]
        else:
            result = await http_client.authenticated_request(
                "POST", "/api/v1/auth/validate", token, {"token": token}
            )
            return result  # type: ignore[no-any-return]
