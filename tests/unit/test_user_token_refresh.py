"""
Unit tests for UserTokenRefreshManager.

This module contains comprehensive tests for automatic user token refresh functionality.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miso_client.utils.user_token_refresh import (
    UserTokenRefreshManager,
    clear_stored_access_token,
    clear_stored_refresh_token,
    clear_stored_session_tokens,
    get_effective_user_token_refresh_buffer,
    get_jwt_expires_at,
    get_stored_refresh_token,
    get_user_token_expires_at,
    get_user_token_refresh_due_at,
    is_user_token_expired,
    is_user_token_refresh_due,
    normalize_expires_at,
    store_access_token,
    store_refresh_token,
)


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


class TestUserTokenLifecycleContracts:
    """Contract-level tests for extracted user token lifecycle helpers."""

    def test_normalize_expires_at_supports_seconds_milliseconds_and_iso(self):
        """Normalizes all expected expiration formats."""
        now = datetime.now(timezone.utc)
        seconds_value = int(now.timestamp())
        milliseconds_value = seconds_value * 1000
        iso_value = now.isoformat()

        parsed_seconds = normalize_expires_at(seconds_value)
        parsed_milliseconds = normalize_expires_at(milliseconds_value)
        parsed_iso = normalize_expires_at(iso_value)

        assert parsed_seconds is not None
        assert parsed_milliseconds is not None
        assert parsed_iso is not None
        assert parsed_seconds.tzinfo is not None
        assert parsed_milliseconds.tzinfo is not None
        assert parsed_iso.tzinfo is not None

    def test_normalize_expires_at_invalid_values_return_none(self):
        """Returns None for invalid expiration inputs."""
        assert normalize_expires_at(None) is None
        assert normalize_expires_at("") is None
        assert normalize_expires_at("not-a-date") is None
        assert normalize_expires_at(-10) is None

    def test_get_jwt_expires_at_reads_exp_claim(self):
        """Extracts expiration from JWT claim aliases."""
        future = int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())
        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = {"exp": future}
            expires_at = get_jwt_expires_at("token")
            assert expires_at is not None
            assert expires_at.tzinfo is not None

    def test_get_jwt_expires_at_returns_none_for_invalid_claims(self):
        """Returns None when token decode or expiration claims are invalid."""
        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = None
            assert get_jwt_expires_at("token") is None

        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = {"exp": "not-a-timestamp"}
            assert get_jwt_expires_at("token") is None

    def test_get_effective_user_token_refresh_buffer_is_adaptive(self):
        """Uses lifetime-aware buffer and never falls below default."""
        issued = datetime.now(timezone.utc)
        short_expiry = issued + timedelta(minutes=2)
        long_expiry = issued + timedelta(hours=4)

        short_buffer = get_effective_user_token_refresh_buffer(short_expiry, issued_at=issued)
        long_buffer = get_effective_user_token_refresh_buffer(long_expiry, issued_at=issued)

        assert short_buffer >= 60
        assert long_buffer >= short_buffer

    def test_get_effective_user_token_refresh_buffer_falls_back_for_invalid_inputs(self):
        """Falls back to normalized default for invalid expiration/lifetime values."""
        assert get_effective_user_token_refresh_buffer("invalid", default_buffer_seconds=45) == 45
        assert (
            get_effective_user_token_refresh_buffer(
                datetime.now(timezone.utc) - timedelta(minutes=1),
                issued_at=datetime.now(timezone.utc),
                default_buffer_seconds=-10,
            )
            == 0
        )

    def test_refresh_due_and_expired_state_transitions(self):
        """Tracks due and expired state for given timestamps."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=10)
        due_at = get_user_token_refresh_due_at(expires_at, issued_at=now, refresh_buffer_seconds=60)

        assert due_at is not None
        assert is_user_token_refresh_due(
            expires_at,
            issued_at=now,
            now=due_at + timedelta(seconds=1),
            refresh_buffer_seconds=60,
        )
        assert not is_user_token_expired(expires_at, now=now)
        assert is_user_token_expired(expires_at, now=expires_at + timedelta(seconds=1))

    def test_refresh_due_and_expired_helpers_return_safe_defaults_for_invalid_inputs(self):
        """Returns safe defaults for invalid due/expired inputs."""
        assert get_user_token_refresh_due_at("invalid") is None
        assert is_user_token_refresh_due("invalid") is False
        assert is_user_token_expired("invalid") is False

    def test_storage_lifecycle_and_compatibility_keys(self):
        """Stores and clears session tokens through compatibility aliases."""
        storage = {}
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        store_access_token(storage, "access-1", expires_at=expires_at)
        store_refresh_token(storage, "refresh-1")

        assert storage["miso_token"] == "access-1"
        assert storage["token"] == "access-1"
        assert storage["accessToken"] == "access-1"
        assert storage["authToken"] == "access-1"
        assert storage["miso:user-refresh-token"] == "refresh-1"
        assert storage["refreshToken"] == "refresh-1"
        assert get_stored_refresh_token(storage) == "refresh-1"
        assert get_user_token_expires_at(storage) is not None

        clear_stored_access_token(storage)
        assert "miso_token" not in storage
        assert "token" not in storage
        assert "accessToken" not in storage
        assert "authToken" not in storage

        clear_stored_refresh_token(storage)
        assert "miso:user-refresh-token" not in storage
        assert "refreshToken" not in storage

    def test_store_access_token_preserves_expiry_when_value_unchanged(self):
        """Keeps existing expiration metadata if token value is unchanged."""
        storage = {}
        first_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        store_access_token(storage, "access-1", expires_at=first_expires_at)

        second_expires_at = get_user_token_expires_at(storage)
        assert second_expires_at is not None

        store_access_token(storage, "access-1")
        preserved_expires_at = get_user_token_expires_at(storage)

        assert preserved_expires_at is not None
        assert int(preserved_expires_at.timestamp()) == int(second_expires_at.timestamp())

    def test_store_access_token_clears_old_expiry_when_token_changes_without_expiry(self):
        """Clears stale expiry metadata when token changes and no expiry is provided."""
        storage = {}
        store_access_token(
            storage, "access-1", expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)
        )
        assert get_user_token_expires_at(storage) is not None

        store_access_token(storage, "access-2")
        assert get_user_token_expires_at(storage) is None

    def test_store_refresh_token_overwrites_existing_aliases(self):
        """Overwrites all refresh token aliases with latest value."""
        storage = {}
        store_refresh_token(storage, "refresh-1")
        store_refresh_token(storage, "refresh-2")

        assert storage["miso:user-refresh-token"] == "refresh-2"
        assert storage["refreshToken"] == "refresh-2"
        assert get_stored_refresh_token(storage) == "refresh-2"

    def test_clear_stored_session_tokens_clears_both_token_types(self):
        """Clears both access and refresh data together."""
        storage = {}
        store_access_token(storage, "access-1")
        store_refresh_token(storage, "refresh-1")

        clear_stored_session_tokens(storage)

        assert get_stored_refresh_token(storage) is None
        assert get_user_token_expires_at(storage) is None

    def test_clear_helpers_are_idempotent_with_missing_keys(self):
        """Handles repeated clear operations safely on empty storage."""
        storage = {}

        clear_stored_access_token(storage)
        clear_stored_refresh_token(storage)
        clear_stored_session_tokens(storage)

        clear_stored_access_token(storage)
        clear_stored_refresh_token(storage)
        clear_stored_session_tokens(storage)

        assert storage == {}

    def test_get_stored_refresh_token_returns_none_for_blank_or_missing_values(self):
        """Returns None when refresh aliases are missing or blank."""
        storage = {"miso:user-refresh-token": "   ", "refreshToken": ""}
        assert get_stored_refresh_token(storage) is None

        storage.clear()
        assert get_stored_refresh_token(storage) is None

    def test_get_user_token_expires_at_uses_jwt_fallback_when_metadata_missing(self):
        """Falls back to JWT claims if explicit expiration metadata is absent."""
        future = int((datetime.now(timezone.utc) + timedelta(minutes=20)).timestamp())
        storage = {"miso_token": "access-token"}

        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = {"exp": future}
            expires_at = get_user_token_expires_at(storage)
            assert expires_at is not None

    def test_get_user_token_expires_at_returns_none_for_invalid_storage_and_jwt(self):
        """Returns None when neither metadata nor JWT claims provide valid expiration."""
        storage = {"miso_token": "access-token", "expiresAt": "invalid"}

        with patch("miso_client.utils.user_token_refresh.decode_token") as mock_decode:
            mock_decode.return_value = {"exp": "invalid"}
            assert get_user_token_expires_at(storage) is None
