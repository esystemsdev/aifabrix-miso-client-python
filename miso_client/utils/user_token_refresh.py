"""User token refresh manager and internal token lifecycle helpers."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional, Sequence

from .jwt_tools import decode_token, extract_user_id

logger = logging.getLogger(__name__)

JWT_EXPIRATION_CLAIMS: Sequence[str] = ("exp", "expiresAt", "expires_at")
JWT_ISSUED_AT_CLAIMS: Sequence[str] = ("iat", "issuedAt", "issued_at")
DEFAULT_USER_TOKEN_REFRESH_BUFFER_SECONDS = 60
MIN_USER_TOKEN_REFRESH_BUFFER_SECONDS = 15
MAX_USER_TOKEN_REFRESH_BUFFER_SECONDS = 300


def _normalize_str(value: Any) -> Optional[str]:
    """Return stripped string value or None for empty/non-string input."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _normalize_positive_int(value: int) -> int:
    """Normalize possibly negative integer into non-negative integer."""
    return value if value >= 0 else 0


def _parse_timestamp_number(value: float) -> Optional[datetime]:
    """Parse epoch seconds or epoch milliseconds into UTC datetime."""
    if value <= 0:
        return None
    if value > 1_000_000_000_000:
        value = value / 1000.0
    return datetime.fromtimestamp(value, tz=timezone.utc)


def normalize_expires_at(value: Any) -> Optional[datetime]:
    """Normalize expiration value to UTC datetime.

    Supports:
    - datetime
    - epoch seconds
    - epoch milliseconds
    - numeric strings
    - ISO datetime strings
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        return _parse_timestamp_number(float(value))

    normalized_str = _normalize_str(value)
    if normalized_str is None:
        return None

    try:
        return _parse_timestamp_number(float(normalized_str))
    except ValueError:
        pass

    normalized_iso = normalized_str
    if normalized_iso.endswith("Z"):
        normalized_iso = f"{normalized_iso[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized_iso)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_claim_datetime(decoded: Dict[str, Any], claims: Sequence[str]) -> Optional[datetime]:
    """Extract first parseable datetime value from claim aliases."""
    for claim in claims:
        parsed = normalize_expires_at(decoded.get(claim))
        if parsed is not None:
            return parsed
    return None


def get_jwt_expires_at(token: str) -> Optional[datetime]:
    """Extract normalized expiration datetime from JWT token claims."""
    decoded = decode_token(token)
    if not decoded:
        return None
    return _extract_claim_datetime(decoded, JWT_EXPIRATION_CLAIMS)


def _get_jwt_issued_at(decoded: Dict[str, Any]) -> Optional[datetime]:
    """Extract normalized issued-at datetime from JWT claims."""
    return _extract_claim_datetime(decoded, JWT_ISSUED_AT_CLAIMS)


def get_effective_user_token_refresh_buffer(
    expires_at: Any,
    issued_at: Any = None,
    *,
    default_buffer_seconds: int = DEFAULT_USER_TOKEN_REFRESH_BUFFER_SECONDS,
) -> int:
    """Calculate adaptive refresh buffer using token lifetime when available."""
    normalized_default = _normalize_positive_int(default_buffer_seconds)
    normalized_expires_at = normalize_expires_at(expires_at)
    if normalized_expires_at is None:
        return normalized_default

    normalized_issued_at = normalize_expires_at(issued_at) or datetime.now(timezone.utc)
    lifetime_seconds = int((normalized_expires_at - normalized_issued_at).total_seconds())
    if lifetime_seconds <= 0:
        return normalized_default

    adaptive_buffer = int(lifetime_seconds * 0.1)
    bounded_buffer = max(
        MIN_USER_TOKEN_REFRESH_BUFFER_SECONDS,
        min(adaptive_buffer, MAX_USER_TOKEN_REFRESH_BUFFER_SECONDS),
    )
    return max(normalized_default, bounded_buffer)


def get_user_token_refresh_due_at(
    expires_at: Any,
    *,
    issued_at: Any = None,
    refresh_buffer_seconds: int = DEFAULT_USER_TOKEN_REFRESH_BUFFER_SECONDS,
) -> Optional[datetime]:
    """Calculate the datetime when user token should be proactively refreshed."""
    normalized_expires_at = normalize_expires_at(expires_at)
    if normalized_expires_at is None:
        return None
    effective_buffer = get_effective_user_token_refresh_buffer(
        normalized_expires_at,
        issued_at,
        default_buffer_seconds=refresh_buffer_seconds,
    )
    return normalized_expires_at - timedelta(seconds=effective_buffer)


def is_user_token_refresh_due(
    expires_at: Any,
    *,
    issued_at: Any = None,
    now: Optional[datetime] = None,
    refresh_buffer_seconds: int = DEFAULT_USER_TOKEN_REFRESH_BUFFER_SECONDS,
) -> bool:
    """Return True when token should be refreshed according to due-at strategy."""
    due_at = get_user_token_refresh_due_at(
        expires_at,
        issued_at=issued_at,
        refresh_buffer_seconds=refresh_buffer_seconds,
    )
    if due_at is None:
        return False
    comparison_now = now or datetime.now(timezone.utc)
    if comparison_now.tzinfo is None:
        comparison_now = comparison_now.replace(tzinfo=timezone.utc)
    return comparison_now >= due_at


def is_user_token_expired(expires_at: Any, *, now: Optional[datetime] = None) -> bool:
    """Return True when token is already expired."""
    normalized_expires_at = normalize_expires_at(expires_at)
    if normalized_expires_at is None:
        return False
    comparison_now = now or datetime.now(timezone.utc)
    if comparison_now.tzinfo is None:
        comparison_now = comparison_now.replace(tzinfo=timezone.utc)
    return comparison_now >= normalized_expires_at


class UserTokenRefreshManager:
    """Manages user token refresh with proactive refresh and 401 retry."""

    def __init__(self) -> None:
        """Initialize user token refresh manager."""
        self._refresh_callbacks: Dict[str, Callable[[str], Awaitable[Any]]] = {}
        self._refresh_tokens: Dict[str, str] = {}
        self._token_expirations: Dict[str, datetime] = {}
        self._refresh_locks: Dict[str, asyncio.Lock] = {}
        self._refreshed_tokens: Dict[str, str] = {}
        self._auth_service: Optional[Any] = None

    def register_refresh_callback(
        self, user_id: str, callback: Callable[[str], Awaitable[Any]]
    ) -> None:
        """Register refresh callback for a user.

        Args:
            user_id: User ID
            callback: Async function that takes old token and returns new token

        """
        self._refresh_callbacks[user_id] = callback

    def register_refresh_token(self, user_id: str, refresh_token: str) -> None:
        """Register refresh token for a user.

        Args:
            user_id: User ID
            refresh_token: Refresh token string

        """
        self._refresh_tokens[user_id] = refresh_token

    def set_auth_service(self, auth_service: Any) -> None:
        """Set AuthService instance for refresh endpoint calls.

        Args:
            auth_service: AuthService instance

        """
        self._auth_service = auth_service

    def _get_user_id(self, token: str) -> Optional[str]:
        """Extract user ID from token."""
        return extract_user_id(token)

    def _is_token_expired(self, token: str, buffer_seconds: int = 60) -> bool:
        """Check if token is expired or will expire soon.

        Args:
            token: JWT token string
            buffer_seconds: Buffer time before expiration (default: 60 seconds)

        Returns:
            True if token is expired or will expire within buffer time

        """
        if token in self._token_expirations:
            return is_user_token_refresh_due(
                self._token_expirations[token], refresh_buffer_seconds=buffer_seconds
            )
        decoded = decode_token(token)
        if not decoded:
            return True
        token_exp = self._extract_expiration(decoded)
        if token_exp is None:
            return False
        self._token_expirations[token] = token_exp
        token_issued_at = _get_jwt_issued_at(decoded)
        return is_user_token_refresh_due(
            token_exp,
            issued_at=token_issued_at,
            refresh_buffer_seconds=buffer_seconds,
        )

    def _is_expired_by_time(self, expires_at: datetime, buffer_seconds: int) -> bool:
        """Check if expiration timestamp is within configured buffer window."""
        return is_user_token_refresh_due(expires_at, refresh_buffer_seconds=buffer_seconds)

    def _extract_expiration(self, decoded: Dict[str, Any]) -> Optional[datetime]:
        """Extract expiration datetime from decoded JWT payload."""
        return _extract_claim_datetime(decoded, JWT_EXPIRATION_CLAIMS)

    def _get_tokens_for_user(self, token_map: Dict[str, Any], user_id: str) -> list[str]:
        """Return map keys whose token belongs to given user."""
        return [
            old_token for old_token in token_map.keys() if self._get_user_id(old_token) == user_id
        ]

    def _remove_user_token_entries(self, token_map: Dict[str, Any], user_id: str) -> None:
        """Remove all token entries mapped to a specific user id."""
        for old_token in self._get_tokens_for_user(token_map, user_id):
            token_map.pop(old_token, None)

    def _clear_user_registrations(self, user_id: str) -> None:
        """Clear user refresh callback, token and lock registrations."""
        self._refresh_callbacks.pop(user_id, None)
        self._refresh_tokens.pop(user_id, None)
        self._refresh_locks.pop(user_id, None)

    def clear_user_tokens(self, user_id: str) -> None:
        """Clear all tokens and refresh data for a user."""
        self._clear_user_registrations(user_id)
        self._remove_user_token_entries(self._refreshed_tokens, user_id)
        self._remove_user_token_entries(self._token_expirations, user_id)

    async def get_valid_token(self, token: str, refresh_if_needed: bool = True) -> Optional[str]:
        """Get valid token, refreshing if expired."""
        if refresh_if_needed and self._is_token_expired(token):
            user_id = self._get_user_id(token)
            refreshed = await self._refresh_token(token, user_id)
            if refreshed:
                return refreshed
        return token

    def _get_refresh_token_from_jwt(self, token: str) -> Optional[str]:
        """Extract refresh token from JWT claims.

        Checks common refresh token claim names: refreshToken, refresh_token, rt
        """
        decoded = decode_token(token)
        if not decoded:
            return None

        # Try common refresh token claim names
        refresh_token = (
            decoded.get("refreshToken") or decoded.get("refresh_token") or decoded.get("rt")
        )
        return str(refresh_token) if refresh_token else None

    def _get_refresh_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create per-user refresh lock."""
        if user_id not in self._refresh_locks:
            self._refresh_locks[user_id] = asyncio.Lock()
        return self._refresh_locks[user_id]

    def _token_to_str(self, token_value: Any) -> str:
        """Normalize token value to string."""
        return token_value if isinstance(token_value, str) else str(token_value)

    def _cache_refreshed_token(self, old_token: str, refreshed_token: str) -> str:
        """Cache refreshed token mapping for concurrent requests."""
        self._refreshed_tokens[old_token] = refreshed_token
        return refreshed_token

    async def _refresh_via_callback(self, user_id: str, token: str) -> Optional[str]:
        """Refresh token via registered callback."""
        callback = self._refresh_callbacks.get(user_id)
        if callback is None:
            return None
        new_token = await callback(token)
        if not new_token:
            return None
        return self._cache_refreshed_token(token, self._token_to_str(new_token))

    def _update_refresh_token(self, user_id: str, refresh_response: Dict[str, Any]) -> None:
        """Update stored refresh token from refresh response payload."""
        refresh_token = refresh_response.get("refreshToken")
        if refresh_token:
            self._refresh_tokens[user_id] = str(refresh_token)

    def _cache_token_expiration(self, token: str, expires_at: Any) -> None:
        """Cache parsed token expiration when refresh response provides it."""
        parsed_expires_at = normalize_expires_at(expires_at)
        if parsed_expires_at is not None:
            self._token_expirations[token] = parsed_expires_at

    async def _refresh_with_refresh_token(
        self, user_id: str, token: str, refresh_token: Optional[str]
    ) -> Optional[str]:
        """Refresh token via AuthService using provided refresh token."""
        if not refresh_token or not self._auth_service:
            return None
        refresh_response = await self._auth_service.refresh_user_token(refresh_token)
        if not refresh_response or not refresh_response.get("token"):
            return None
        refreshed_token = self._token_to_str(refresh_response["token"])
        refreshed = self._cache_refreshed_token(token, refreshed_token)
        self._cache_token_expiration(refreshed_token, refresh_response.get("expiresAt"))
        self._update_refresh_token(user_id, refresh_response)
        return refreshed

    async def _try_refresh_mechanisms(self, token: str, user_id: str) -> Optional[str]:
        """Try all available refresh mechanisms in priority order."""
        callback_token = await self._refresh_via_callback(user_id, token)
        if callback_token:
            logger.info("Token refreshed successfully for user %s via callback", user_id)
            return callback_token

        stored_refresh = self._refresh_tokens.get(user_id)
        stored_token_result = await self._refresh_with_refresh_token(user_id, token, stored_refresh)
        if stored_token_result:
            logger.info("Token refreshed successfully for user %s via refresh token", user_id)
            return stored_token_result

        jwt_refresh = self._get_refresh_token_from_jwt(token)
        jwt_token_result = await self._refresh_with_refresh_token(user_id, token, jwt_refresh)
        if jwt_token_result:
            logger.info("Token refreshed successfully for user %s via JWT refresh token", user_id)
            return jwt_token_result
        return None

    async def _refresh_token(self, token: str, user_id: Optional[str] = None) -> Optional[str]:
        """Refresh user token using available refresh mechanisms."""
        if not user_id:
            user_id = self._get_user_id(token)
            if not user_id:
                logger.warning("Cannot refresh token: user ID not found")
                return None

        async with self._get_refresh_lock(user_id):
            if token in self._refreshed_tokens:
                return self._refreshed_tokens[token]
            try:
                refreshed = await self._try_refresh_mechanisms(token, user_id)
                if refreshed:
                    return refreshed
                logger.warning(f"No refresh mechanism available for user {user_id}")
                return None
            except Exception as error:
                logger.error(f"Token refresh failed for user {user_id}", exc_info=error)
                return None
