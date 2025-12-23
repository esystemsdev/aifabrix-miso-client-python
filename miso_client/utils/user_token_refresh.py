"""User token refresh manager for automatic token refresh."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from .jwt_tools import decode_token, extract_user_id

logger = logging.getLogger(__name__)


class UserTokenRefreshManager:
    """
    Manages user token refresh with proactive refresh and 401 retry.

    Similar to client token refresh but for user Bearer tokens.
    """

    def __init__(self):
        """Initialize user token refresh manager."""
        # Store refresh callbacks per user: {user_id: callback}
        self._refresh_callbacks: Dict[str, Callable[[str], Any]] = {}
        # Store refresh tokens per user: {user_id: refresh_token}
        self._refresh_tokens: Dict[str, str] = {}
        # Track token expiration: {token: expiration_datetime}
        self._token_expirations: Dict[str, datetime] = {}
        # Locks per user to prevent concurrent refreshes: {user_id: Lock}
        self._refresh_locks: Dict[str, asyncio.Lock] = {}
        # Cache refreshed tokens: {old_token: new_token}
        self._refreshed_tokens: Dict[str, str] = {}
        # AuthService instance for refresh endpoint calls
        self._auth_service: Optional[Any] = None

    def register_refresh_callback(self, user_id: str, callback: Callable[[str], Any]) -> None:
        """
        Register refresh callback for a user.

        Args:
            user_id: User ID
            callback: Async function that takes old token and returns new token
        """
        self._refresh_callbacks[user_id] = callback

    def register_refresh_token(self, user_id: str, refresh_token: str) -> None:
        """
        Register refresh token for a user.

        Args:
            user_id: User ID
            refresh_token: Refresh token string
        """
        self._refresh_tokens[user_id] = refresh_token

    def set_auth_service(self, auth_service: Any) -> None:
        """
        Set AuthService instance for refresh endpoint calls.

        Args:
            auth_service: AuthService instance
        """
        self._auth_service = auth_service

    def _get_user_id(self, token: str) -> Optional[str]:
        """Extract user ID from token."""
        return extract_user_id(token)

    def _is_token_expired(self, token: str, buffer_seconds: int = 60) -> bool:
        """
        Check if token is expired or will expire soon.

        Args:
            token: JWT token string
            buffer_seconds: Buffer time before expiration (default: 60 seconds)

        Returns:
            True if token is expired or will expire within buffer time
        """
        # Check cached expiration first
        if token in self._token_expirations:
            expires_at = self._token_expirations[token]
            return datetime.now() + timedelta(seconds=buffer_seconds) >= expires_at

        # Decode token to check expiration
        decoded = decode_token(token)
        if not decoded:
            return True  # Invalid token, consider expired

        # Check exp claim
        if "exp" in decoded and isinstance(decoded["exp"], (int, float)):
            token_exp = datetime.fromtimestamp(decoded["exp"])
            buffer_time = datetime.now() + timedelta(seconds=buffer_seconds)
            is_expired = buffer_time >= token_exp
            # Cache expiration for future checks
            self._token_expirations[token] = token_exp
            return is_expired

        # No expiration claim - assume not expired
        return False

    def _get_refresh_token_from_jwt(self, token: str) -> Optional[str]:
        """
        Extract refresh token from JWT claims.

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

    async def _refresh_token(self, token: str, user_id: Optional[str] = None) -> Optional[str]:
        """
        Refresh user token using available refresh mechanism.

        Args:
            token: Current user token
            user_id: Optional user ID (extracted from token if not provided)
            auth_service: Optional AuthService instance for refresh endpoint calls

        Returns:
            New token if refresh successful, None otherwise
        """
        if not user_id:
            user_id = self._get_user_id(token)
            if not user_id:
                logger.warning("Cannot refresh token: user ID not found")
                return None

        # Get or create lock for this user
        if user_id not in self._refresh_locks:
            self._refresh_locks[user_id] = asyncio.Lock()

        async with self._refresh_locks[user_id]:
            # Check if token was already refreshed (by another concurrent request)
            if token in self._refreshed_tokens:
                return self._refreshed_tokens[token]

            try:
                # Try refresh callback first
                if user_id in self._refresh_callbacks:
                    callback = self._refresh_callbacks[user_id]
                    new_token = await callback(token)
                    if new_token:
                        token_str = str(new_token) if not isinstance(new_token, str) else new_token
                        self._refreshed_tokens[token] = token_str
                        logger.info(f"Token refreshed successfully for user {user_id} via callback")
                        return token_str

                # Try stored refresh token
                if user_id in self._refresh_tokens and self._auth_service:
                    refresh_token = self._refresh_tokens[user_id]
                    refresh_response = await self._auth_service.refresh_user_token(refresh_token)
                    if refresh_response and refresh_response.get("token"):
                        new_token = refresh_response["token"]
                        token_str = str(new_token) if not isinstance(new_token, str) else new_token
                        self._refreshed_tokens[token] = token_str
                        # Update refresh token if new one provided
                        if refresh_response.get("refreshToken"):
                            self._refresh_tokens[user_id] = refresh_response["refreshToken"]
                        logger.info(
                            f"Token refreshed successfully for user {user_id} via refresh token"
                        )
                        return token_str

                # Try refresh token from JWT claims
                jwt_refresh_token = self._get_refresh_token_from_jwt(token)
                if jwt_refresh_token and self._auth_service:
                    refresh_response = await self._auth_service.refresh_user_token(
                        jwt_refresh_token
                    )
                    if refresh_response and refresh_response.get("token"):
                        new_token = refresh_response["token"]
                        token_str = str(new_token) if not isinstance(new_token, str) else new_token
                        self._refreshed_tokens[token] = token_str
                        # Update refresh token if new one provided
                        if refresh_response.get("refreshToken"):
                            self._refresh_tokens[user_id] = refresh_response["refreshToken"]
                        logger.info(
                            f"Token refreshed successfully for user {user_id} via JWT refresh token"
                        )
                        return token_str

                logger.warning(f"No refresh mechanism available for user {user_id}")
                return None

            except Exception as error:
                logger.error(f"Token refresh failed for user {user_id}", exc_info=error)
                return None

    async def get_valid_token(self, token: str, refresh_if_needed: bool = True) -> Optional[str]:
        """
        Get valid token, refreshing if expired.

        Args:
            token: Current user token
            refresh_if_needed: Whether to refresh if token is expired

        Returns:
            Valid token (original or refreshed), None if refresh failed
        """
        # Check if token is expired
        if refresh_if_needed and self._is_token_expired(token):
            user_id = self._get_user_id(token)
            refreshed = await self._refresh_token(token, user_id)
            if refreshed:
                return refreshed
            # Refresh failed, return original token (let request fail naturally)

        return token

    def clear_user_tokens(self, user_id: str) -> None:
        """
        Clear all tokens and refresh data for a user.

        Args:
            user_id: User ID
        """
        # Clear refresh callback
        self._refresh_callbacks.pop(user_id, None)
        # Clear refresh token
        self._refresh_tokens.pop(user_id, None)
        # Clear refresh lock
        self._refresh_locks.pop(user_id, None)
        # Clear cached refreshed tokens (find by user_id in old tokens)
        tokens_to_remove = [
            old_token
            for old_token in self._refreshed_tokens.keys()
            if self._get_user_id(old_token) == user_id
        ]
        for old_token in tokens_to_remove:
            self._refreshed_tokens.pop(old_token, None)
        # Clear token expirations
        expirations_to_remove = [
            old_token
            for old_token in self._token_expirations.keys()
            if self._get_user_id(old_token) == user_id
        ]
        for old_token in expirations_to_remove:
            self._token_expirations.pop(old_token, None)
