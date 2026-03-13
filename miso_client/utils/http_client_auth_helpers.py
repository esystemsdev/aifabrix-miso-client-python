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
    **kwargs: Any,
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


def _apply_authorization_header(kwargs: Dict[str, Any], token: str) -> Dict[str, Any]:
    """Return kwargs with Authorization header applied."""
    headers = kwargs.get("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    kwargs["headers"] = headers
    return kwargs


async def _refresh_token_for_401(
    user_token_refresh: "UserTokenRefreshManager", token: str
) -> Optional[str]:
    """Refresh token after 401 response using user id hint."""
    user_id = extract_user_id(token)
    return await user_token_refresh._refresh_token(token, user_id)


async def _retry_with_refreshed_token(
    internal_client: "InternalHttpClient",
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    refreshed_token: str,
    data: Optional[Dict[str, Any]],
    auth_strategy: Optional["AuthStrategy"],
    kwargs: Dict[str, Any],
    original_error: httpx.HTTPStatusError,
) -> Any:
    """Retry authenticated request with refreshed token or raise original error."""
    try:
        return await internal_client.authenticated_request(
            method, url, refreshed_token, data, auth_strategy, **kwargs
        )
    except httpx.HTTPStatusError:
        raise original_error


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
    **kwargs: Any,
) -> Any:
    """Handle 401 by refreshing user token and retrying once."""
    if not auto_refresh:
        raise error
    refreshed_token = await _refresh_token_for_401(user_token_refresh, token)
    if not refreshed_token:
        raise error
    retry_kwargs = _apply_authorization_header(kwargs, refreshed_token)
    return await _retry_with_refreshed_token(
        internal_client,
        method,
        url,
        refreshed_token,
        data,
        auth_strategy,
        retry_kwargs,
        error,
    )


async def execute_authenticated_call(
    internal_client: "InternalHttpClient",
    user_token_refresh: "UserTokenRefreshManager",
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    valid_token: str,
    data: Optional[Dict[str, Any]],
    auth_strategy: Optional["AuthStrategy"],
    auto_refresh: bool,
    request_kwargs: Dict[str, Any],
) -> Any:
    try:
        return await _call_authenticated(
            internal_client, method, url, valid_token, data, auth_strategy, request_kwargs
        )
    except httpx.HTTPStatusError as error:
        if error.response.status_code != 401:
            raise
        return await handle_401_refresh(
            internal_client,
            user_token_refresh,
            method,
            url,
            valid_token,
            data,
            auth_strategy,
            error,
            auto_refresh,
            **request_kwargs,
        )


async def _call_authenticated(
    internal_client: "InternalHttpClient",
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    token: str,
    data: Optional[Dict[str, Any]],
    auth_strategy: Optional["AuthStrategy"],
    request_kwargs: Dict[str, Any],
) -> Any:
    """Invoke internal authenticated request with prepared kwargs."""
    return await internal_client.authenticated_request(
        method, url, token, data, auth_strategy, **request_kwargs
    )
