"""
Unit tests for JWT tools.
"""

import jwt

from miso_client.utils.jwt_tools import (
    JwtTokenCache,
    decode_token,
    extract_session_id,
    extract_user_id,
)


class TestJwtTools:
    """Test cases for JWT tools."""

    def test_decode_token_valid(self):
        """Test decoding valid JWT token."""
        # Create a valid JWT token
        payload = {"sub": "user-123", "exp": 9999999999}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        decoded = decode_token(token)

        assert decoded is not None
        assert decoded["sub"] == "user-123"

    def test_decode_token_invalid(self):
        """Test decoding invalid token."""
        decoded = decode_token("invalid.token.here")

        assert decoded is None

    def test_decode_token_empty(self):
        """Test decoding empty token."""
        decoded = decode_token("")

        assert decoded is None

    def test_extract_user_id_from_sub(self):
        """Test extracting user ID from 'sub' claim."""
        payload = {"sub": "user-123"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        user_id = extract_user_id(token)

        assert user_id == "user-123"

    def test_extract_user_id_from_user_id(self):
        """Test extracting user ID from 'userId' claim."""
        payload = {"userId": "user-456"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        user_id = extract_user_id(token)

        assert user_id == "user-456"

    def test_extract_user_id_from_user_id_field(self):
        """Test extracting user ID from 'user_id' claim."""
        payload = {"user_id": "user-789"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        user_id = extract_user_id(token)

        assert user_id == "user-789"

    def test_extract_user_id_from_id(self):
        """Test extracting user ID from 'id' claim."""
        payload = {"id": "user-999"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        user_id = extract_user_id(token)

        assert user_id == "user-999"

    def test_extract_user_id_priority(self):
        """Test that 'sub' has priority over other fields."""
        payload = {"sub": "user-sub", "userId": "user-id", "id": "user-id-value"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        user_id = extract_user_id(token)

        assert user_id == "user-sub"

    def test_extract_user_id_not_found(self):
        """Test extracting user ID when not present."""
        payload = {"name": "test"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        user_id = extract_user_id(token)

        assert user_id is None

    def test_extract_user_id_invalid_token(self):
        """Test extracting user ID from invalid token."""
        user_id = extract_user_id("invalid.token")

        assert user_id is None

    def test_extract_session_id_from_sid(self):
        """Test extracting session ID from 'sid' claim."""
        payload = {"sid": "session-123"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        session_id = extract_session_id(token)

        assert session_id == "session-123"

    def test_extract_session_id_from_session_id(self):
        """Test extracting session ID from 'sessionId' claim."""
        payload = {"sessionId": "session-456"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        session_id = extract_session_id(token)

        assert session_id == "session-456"

    def test_extract_session_id_not_found(self):
        """Test extracting session ID when not present."""
        payload = {"sub": "user-123"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        session_id = extract_session_id(token)

        assert session_id is None

    def test_extract_session_id_invalid_token(self):
        """Test extracting session ID from invalid token."""
        session_id = extract_session_id("invalid.token")

        assert session_id is None


class TestJwtTokenCache:
    """Test cases for JwtTokenCache."""

    def test_clear_token_existing(self):
        """Test clearing existing token from cache."""
        cache = JwtTokenCache()
        payload = {"sub": "user-123"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        # Add token to cache by decoding it
        cache.get_decoded_token(token)

        # Verify token is in cache
        assert token in cache._cache

        # Clear token
        cache.clear_token(token)

        # Verify token is removed from cache
        assert token not in cache._cache

    def test_clear_token_non_existent(self):
        """Test clearing non-existent token (idempotent operation)."""
        cache = JwtTokenCache()
        payload = {"sub": "user-123"}
        token = jwt.encode(payload, "secret", algorithm="HS256")

        # Token not in cache
        assert token not in cache._cache

        # Clear token (should not raise exception)
        cache.clear_token(token)

        # Verify token still not in cache
        assert token not in cache._cache

    def test_clear_token_reduces_cache_size(self):
        """Test that clearing token reduces cache size."""
        cache = JwtTokenCache()
        token1 = jwt.encode({"sub": "user-1"}, "secret", algorithm="HS256")
        token2 = jwt.encode({"sub": "user-2"}, "secret", algorithm="HS256")

        # Add tokens to cache
        cache.get_decoded_token(token1)
        cache.get_decoded_token(token2)

        # Verify both tokens are in cache
        assert len(cache._cache) == 2

        # Clear one token
        cache.clear_token(token1)

        # Verify cache size reduced
        assert len(cache._cache) == 1
        assert token1 not in cache._cache
        assert token2 in cache._cache
