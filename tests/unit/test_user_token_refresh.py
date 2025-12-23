"""
Unit tests for UserTokenRefreshManager.

This module contains comprehensive tests for automatic user token refresh functionality.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miso_client.utils.user_token_refresh import UserTokenRefreshManager


class TestUserTokenRefreshManager:
    """Test cases for UserTokenRefreshManager."""

    @pytest.fixture
    def refresh_manager(self):
        """Create a UserTokenRefreshManager instance."""
        return UserTokenRefreshManager()

    @pytest.fixture
    def mock_auth_service(self):
        """Create a mock AuthService."""
        mock_service = MagicMock()
        mock_service.refresh_user_token = AsyncMock()
        return mock_service

    @pytest.mark.asyncio
    async def test_register_refresh_callback(self, refresh_manager):
        """Test registering refresh callback."""

        async def refresh_callback(token: str) -> str:
            return "new-token"

        refresh_manager.register_refresh_callback("user-123", refresh_callback)

        assert "user-123" in refresh_manager._refresh_callbacks
        assert refresh_manager._refresh_callbacks["user-123"] == refresh_callback

    def test_register_refresh_token(self, refresh_manager):
        """Test registering refresh token."""
        refresh_manager.register_refresh_token("user-123", "refresh-token-abc")

        assert refresh_manager._refresh_tokens["user-123"] == "refresh-token-abc"

    def test_set_auth_service(self, refresh_manager, mock_auth_service):
        """Test setting auth service."""
        refresh_manager.set_auth_service(mock_auth_service)

        assert refresh_manager._auth_service == mock_auth_service

    @pytest.mark.asyncio
    async def test_get_user_id_from_token(self, refresh_manager):
        """Test extracting user ID from token."""
        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = "user-123"

            user_id = refresh_manager._get_user_id("test-token")

            assert user_id == "user-123"
            mock_extract.assert_called_once_with("test-token")

    @pytest.mark.asyncio
    async def test_is_token_expired_with_exp_claim(self, refresh_manager):
        """Test token expiration check with exp claim."""
        # Token expires in 30 seconds (within 60s buffer)
        exp_time = datetime.now() + timedelta(seconds=30)
        exp_timestamp = int(exp_time.timestamp())

        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = {"exp": exp_timestamp, "sub": "user-123"}

            is_expired = refresh_manager._is_token_expired("test-token", buffer_seconds=60)

            assert is_expired is True

    @pytest.mark.asyncio
    async def test_is_token_expired_not_expired(self, refresh_manager):
        """Test token expiration check when not expired."""
        # Token expires in 2 hours (well beyond buffer)
        exp_time = datetime.now() + timedelta(hours=2)
        exp_timestamp = int(exp_time.timestamp())

        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = {"exp": exp_timestamp, "sub": "user-123"}

            is_expired = refresh_manager._is_token_expired("test-token", buffer_seconds=60)

            assert is_expired is False

    @pytest.mark.asyncio
    async def test_is_token_expired_invalid_token(self, refresh_manager):
        """Test token expiration check with invalid token."""
        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = None

            is_expired = refresh_manager._is_token_expired("invalid-token")

            assert is_expired is True  # Invalid tokens considered expired

    @pytest.mark.asyncio
    async def test_get_refresh_token_from_jwt(self, refresh_manager):
        """Test extracting refresh token from JWT claims."""
        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = {"refreshToken": "rt-123", "sub": "user-123"}

            refresh_token = refresh_manager._get_refresh_token_from_jwt("test-token")

            assert refresh_token == "rt-123"

    @pytest.mark.asyncio
    async def test_get_refresh_token_from_jwt_alternative_claims(self, refresh_manager):
        """Test extracting refresh token from alternative claim names."""
        # Test refresh_token claim
        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = {"refresh_token": "rt-456", "sub": "user-123"}

            refresh_token = refresh_manager._get_refresh_token_from_jwt("test-token")

            assert refresh_token == "rt-456"

        # Test rt claim
        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = {"rt": "rt-789", "sub": "user-123"}

            refresh_token = refresh_manager._get_refresh_token_from_jwt("test-token")

            assert refresh_token == "rt-789"

    @pytest.mark.asyncio
    async def test_refresh_token_via_callback(self, refresh_manager):
        """Test token refresh via callback."""

        async def refresh_callback(token: str) -> str:
            return "new-token-from-callback"

        refresh_manager.register_refresh_callback("user-123", refresh_callback)

        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = "user-123"

            new_token = await refresh_manager._refresh_token("old-token", "user-123")

            assert new_token == "new-token-from-callback"
            assert refresh_manager._refreshed_tokens["old-token"] == "new-token-from-callback"

    @pytest.mark.asyncio
    async def test_refresh_token_via_stored_refresh_token(self, refresh_manager, mock_auth_service):
        """Test token refresh via stored refresh token."""
        refresh_manager.set_auth_service(mock_auth_service)
        refresh_manager.register_refresh_token("user-123", "stored-refresh-token")
        mock_auth_service.refresh_user_token.return_value = {
            "token": "new-access-token",
            "refreshToken": "new-refresh-token",
            "expiresIn": 3600,
        }

        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = "user-123"

            new_token = await refresh_manager._refresh_token("old-token", "user-123")

            assert new_token == "new-access-token"
            assert refresh_manager._refreshed_tokens["old-token"] == "new-access-token"
            # Verify refresh token was updated
            assert refresh_manager._refresh_tokens["user-123"] == "new-refresh-token"
            mock_auth_service.refresh_user_token.assert_called_once_with("stored-refresh-token")

    @pytest.mark.asyncio
    async def test_refresh_token_via_jwt_refresh_token(self, refresh_manager, mock_auth_service):
        """Test token refresh via JWT refresh token claim."""
        refresh_manager.set_auth_service(mock_auth_service)
        mock_auth_service.refresh_user_token.return_value = {
            "token": "new-access-token",
            "refreshToken": "new-refresh-token",
            "expiresIn": 3600,
        }

        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = "user-123"

        with patch.object(refresh_manager, "_get_refresh_token_from_jwt") as mock_get_jwt:
            mock_get_jwt.return_value = "jwt-refresh-token"

            new_token = await refresh_manager._refresh_token("old-token", "user-123")

            assert new_token == "new-access-token"
            mock_auth_service.refresh_user_token.assert_called_once_with("jwt-refresh-token")

    @pytest.mark.asyncio
    async def test_refresh_token_no_mechanism(self, refresh_manager):
        """Test refresh when no mechanism available."""
        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = "user-123"

            new_token = await refresh_manager._refresh_token("old-token", "user-123")

            assert new_token is None

    @pytest.mark.asyncio
    async def test_refresh_token_concurrent_requests(self, refresh_manager):
        """Test concurrent refresh requests use same token."""
        call_count = 0

        async def slow_callback(token: str) -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate slow refresh
            return f"new-token-{call_count}"

        refresh_manager.register_refresh_callback("user-123", slow_callback)

        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = "user-123"

            # Make concurrent refresh requests
            results = await asyncio.gather(
                refresh_manager._refresh_token("old-token", "user-123"),
                refresh_manager._refresh_token("old-token", "user-123"),
                refresh_manager._refresh_token("old-token", "user-123"),
            )

            # All should return the same token (from first call)
            assert all(token == "new-token-1" for token in results)
            # Callback should only be called once due to lock
            assert call_count == 1

    @pytest.mark.asyncio
    async def test_get_valid_token_not_expired(self, refresh_manager):
        """Test get_valid_token when token is not expired."""
        with patch.object(refresh_manager, "_is_token_expired") as mock_expired:
            mock_expired.return_value = False

            token = await refresh_manager.get_valid_token("valid-token")

            assert token == "valid-token"

    @pytest.mark.asyncio
    async def test_get_valid_token_expired_refresh_success(self, refresh_manager):
        """Test get_valid_token when token is expired and refresh succeeds."""
        with patch.object(refresh_manager, "_is_token_expired") as mock_expired:
            mock_expired.return_value = True

        async def refresh_callback(token: str) -> str:
            return "refreshed-token"

        refresh_manager.register_refresh_callback("user-123", refresh_callback)

        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = "user-123"

            token = await refresh_manager.get_valid_token("expired-token", refresh_if_needed=True)

            assert token == "refreshed-token"

    @pytest.mark.asyncio
    async def test_get_valid_token_expired_refresh_failed(self, refresh_manager):
        """Test get_valid_token when token is expired but refresh fails."""
        with patch.object(refresh_manager, "_is_token_expired") as mock_expired:
            mock_expired.return_value = True

        with patch.object(refresh_manager, "_refresh_token") as mock_refresh:
            mock_refresh.return_value = None  # Refresh failed

            token = await refresh_manager.get_valid_token("expired-token", refresh_if_needed=True)

            # Should return original token (let request fail naturally)
            assert token == "expired-token"

    @pytest.mark.asyncio
    async def test_get_valid_token_refresh_disabled(self, refresh_manager):
        """Test get_valid_token when refresh is disabled."""
        with patch.object(refresh_manager, "_is_token_expired") as mock_expired:
            mock_expired.return_value = True

        token = await refresh_manager.get_valid_token("expired-token", refresh_if_needed=False)

        # Should return original token without refresh attempt
        assert token == "expired-token"

    def test_clear_user_tokens(self, refresh_manager):
        """Test clearing all tokens for a user."""

        # Set up data
        async def callback(token: str) -> str:
            return "new-token"

        refresh_manager.register_refresh_callback("user-123", callback)
        refresh_manager.register_refresh_token("user-123", "refresh-token")
        refresh_manager._refreshed_tokens["old-token-1"] = "new-token-1"
        refresh_manager._refreshed_tokens["old-token-2"] = "new-token-2"

        # Mock user ID extraction for tokens
        with patch.object(refresh_manager, "_get_user_id") as mock_get_user_id:
            mock_get_user_id.side_effect = lambda token: (
                "user-123" if token.startswith("old-token") else None
            )

            refresh_manager.clear_user_tokens("user-123")

        # Verify all data cleared
        assert "user-123" not in refresh_manager._refresh_callbacks
        assert "user-123" not in refresh_manager._refresh_tokens
        assert "user-123" not in refresh_manager._refresh_locks
        assert "old-token-1" not in refresh_manager._refreshed_tokens
        assert "old-token-2" not in refresh_manager._refreshed_tokens

    @pytest.mark.asyncio
    async def test_refresh_token_callback_exception(self, refresh_manager):
        """Test refresh token when callback raises exception."""

        async def failing_callback(token: str) -> str:
            raise Exception("Callback failed")

        refresh_manager.register_refresh_callback("user-123", failing_callback)

        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = "user-123"

            new_token = await refresh_manager._refresh_token("old-token", "user-123")

            assert new_token is None

    @pytest.mark.asyncio
    async def test_refresh_token_auth_service_exception(self, refresh_manager, mock_auth_service):
        """Test refresh token when auth service raises exception."""
        refresh_manager.set_auth_service(mock_auth_service)
        refresh_manager.register_refresh_token("user-123", "refresh-token")
        mock_auth_service.refresh_user_token.side_effect = Exception("Service failed")

        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = "user-123"

            new_token = await refresh_manager._refresh_token("old-token", "user-123")

            assert new_token is None

    @pytest.mark.asyncio
    async def test_refresh_token_no_user_id(self, refresh_manager):
        """Test refresh token when user ID cannot be extracted."""
        with patch("miso_client.utils.user_token_refresh.extract_user_id") as mock_extract:
            mock_extract.return_value = None

            new_token = await refresh_manager._refresh_token("token-without-user-id")

            assert new_token is None
