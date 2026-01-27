"""HTTP client authentication helper functions.

This module provides helper functions for handling authentication in HTTP requests,
including token refresh and 401 error handling.
"""

from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

import httpx

if TYPE_CHECKING:
    from ..models.config import AuthStrategy
    from ..utils.internal_http_client import InternalHttpClient
    from ..utils.user_token_refresh import UserTokenRefreshManager

from ..utils.jwt_tools import extract_user_id


async def prepare_authenticated_request(
    user_token_refresh: "UserTokenRefreshManager",
    token: str,
    auto_refresh: bool,
    **kwargs,
) -> str:
    """Prepare authenticated request by getting valid token and setting headers.

    Args:
        user_token_refresh: UserTokenRefreshManager instance
        token: User authentication token
        auto_refresh: Whether to refresh token if expired
        **kwargs: Request kwargs (headers will be modified)

    Returns:
        Valid token to use for request

    """
    # Get valid token (refresh if expired)
    valid_token = await user_token_refresh.get_valid_token(token, refresh_if_needed=auto_refresh)
    if not valid_token:
        valid_token = token  # Fallback to original token

    # Add Bearer token to headers for logging context
    headers = kwargs.get("headers", {})
    headers["Authorization"] = f"Bearer {valid_token}"
    kwargs["headers"] = headers

    return valid_token


async def handle_401_refresh(
    internal_client: "InternalHttpClient",
    user_token_refresh: "UserTokenRefreshManager",
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    token: str,
    data: Optional[Dict[str, Any]],
    auth_strategy: Optional["AuthStrategy"],
    error: httpx.HTTPStatusError,
    auto_refresh: bool,
    **kwargs,
) -> Any:
    """Handle 401 error by refreshing token and retrying request.

    Args:
        internal_client: InternalHttpClient instance
        user_token_refresh: UserTokenRefreshManager instance
        method: HTTP method
        url: Request URL
        token: Current token
        data: Request data
        auth_strategy: Authentication strategy
        error: HTTPStatusError with 401 status
        auto_refresh: Whether to refresh token
        **kwargs: Request kwargs

    Returns:
        Response data from retried request

    Raises:
        httpx.HTTPStatusError: If refresh fails or retry fails

    """
    if not auto_refresh:
        raise error

    user_id = extract_user_id(token)
    refreshed_token = await user_token_refresh._refresh_token(token, user_id)

    if not refreshed_token:
        raise error

    # Retry request with refreshed token
    headers = kwargs.get("headers", {})
    headers["Authorization"] = f"Bearer {refreshed_token}"
    kwargs["headers"] = headers

    try:
        return await internal_client.authenticated_request(
            method, url, refreshed_token, data, auth_strategy, **kwargs
        )
    except httpx.HTTPStatusError:
        # Retry failed, raise original error
        raise error
