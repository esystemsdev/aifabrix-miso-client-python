"""Reusable auth service flow helpers."""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from ..api.types.auth_types import TokenExchangeResponse
from ..models.config import AuthStrategy, UserInfo
from ..utils.auth_cache_helpers import get_cache_ttl_from_token, get_token_exchange_cache_key
from ..utils.http_client import HttpClient

if TYPE_CHECKING:
    from ..api import ApiClient

logger = logging.getLogger(__name__)


def _extract_validation_data(response: Any) -> Dict[str, Any]:
    """Convert typed validation response to legacy dict payload."""
    return {
        "data": {
            "authenticated": response.data.authenticated,
            "user": response.data.user.model_dump() if response.data.user else None,
            "expiresAt": response.data.expiresAt,
        },
    }


def _normalize_exchange_response_payload(response: Any) -> Any:
    """Normalize legacy exchange endpoint response shape."""
    if isinstance(response, dict) and "data" in response and isinstance(response["data"], dict):
        return response["data"]
    return response


async def _read_cached_exchange_result(
    cache: Optional[Any], cache_key: str
) -> Optional[TokenExchangeResponse]:
    """Read cached token exchange result."""
    if not cache:
        return None
    cached = await cache.get(cache_key)
    if cached and isinstance(cached, dict):
        logger.debug("Token exchange cache hit")
        return TokenExchangeResponse(**cached)
    return None


async def _cache_exchange_result(
    cache: Optional[Any], cache_key: str, result: TokenExchangeResponse, validation_ttl: int
) -> None:
    """Cache token exchange result if possible."""
    if not cache or not result.accessToken:
        return
    ttl = get_cache_ttl_from_token(result.accessToken, validation_ttl)
    try:
        await cache.set(cache_key, result.model_dump(), ttl)
        logger.debug("Token exchange cached with TTL %ds", ttl)
    except Exception as error:
        logger.warning("Failed to cache token exchange result", exc_info=error)


async def fetch_validation_result(
    api_client: Optional["ApiClient"],
    http_client: HttpClient,
    token: str,
    auth_strategy: Optional[AuthStrategy],
) -> Dict[str, Any]:
    """Fetch token validation using ApiClient or HttpClient."""
    if api_client:
        response = await api_client.auth.validate_token(token, auth_strategy=auth_strategy)
        return _extract_validation_data(response)

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


async def fetch_user_info(
    api_client: Optional["ApiClient"],
    http_client: HttpClient,
    token: str,
    auth_strategy: Optional[AuthStrategy],
) -> Optional[UserInfo]:
    """Fetch user info from typed ApiClient or HttpClient fallback."""
    if api_client:
        response = await api_client.auth.get_user(token, auth_strategy=auth_strategy)
        return response.data.user

    user_data = await http_client.authenticated_request(
        "GET", "/api/v1/auth/user", token, auth_strategy=auth_strategy
    )
    return UserInfo(**user_data)


async def logout_user(
    api_client: Optional["ApiClient"], http_client: HttpClient, token: str
) -> Dict[str, Any]:
    """Logout user through ApiClient or HttpClient."""
    if api_client:
        await api_client.auth.logout(token)
        return {"data": None}

    result = await http_client.authenticated_request(
        "POST", "/api/v1/auth/logout", token, {"token": token}
    )
    return result if isinstance(result, dict) else {}


async def exchange_delegated_token(
    api_client: Optional["ApiClient"],
    http_client: HttpClient,
    cache: Optional[Any],
    validation_ttl: int,
    delegated_token: str,
) -> TokenExchangeResponse:
    """Exchange delegated token and cache result by delegated token hash."""
    cache_key = get_token_exchange_cache_key(delegated_token)
    cached_result = await _read_cached_exchange_result(cache, cache_key)
    if cached_result:
        return cached_result

    if api_client:
        result = await api_client.auth.exchange_token(delegated_token)
    else:
        response = await http_client.authenticated_request(
            "POST",
            "/api/v1/auth/token/exchange",
            delegated_token,
            data=None,
            auto_refresh=False,
        )
        response = _normalize_exchange_response_payload(response)
        result = TokenExchangeResponse(**response)

    await _cache_exchange_result(cache, cache_key, result, validation_ttl)
    return result


async def refresh_user_access_token(
    api_client: Optional["ApiClient"], http_client: HttpClient, refresh_token: str
) -> Optional[Dict[str, Any]]:
    """Refresh user access token via ApiClient or HttpClient fallback."""
    if api_client:
        response = await api_client.auth.refresh_token(refresh_token)
        return {
            "data": {
                "token": response.data.accessToken,
                "accessToken": response.data.accessToken,
                "refreshToken": response.data.refreshToken,
                "expiresIn": response.data.expiresIn,
            },
        }

    result = await http_client.request(
        "POST", "/api/v1/auth/refresh", {"refreshToken": refresh_token}
    )
    return result if isinstance(result, dict) else None
