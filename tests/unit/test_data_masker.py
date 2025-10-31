"""
Unit tests for DataMasker.
"""

from miso_client.utils.data_masker import DataMasker


class TestDataMasker:
    """Test cases for DataMasker."""

    def test_is_sensitive_field_password(self):
        """Test detecting password field."""
        assert DataMasker.is_sensitive_field("password") is True
        assert DataMasker.is_sensitive_field("PASSWORD") is True
        assert DataMasker.is_sensitive_field("user_password") is True
        assert DataMasker.is_sensitive_field("password_hash") is True

    def test_is_sensitive_field_token(self):
        """Test detecting token fields."""
        assert DataMasker.is_sensitive_field("token") is True
        assert DataMasker.is_sensitive_field("access_token") is True
        assert DataMasker.is_sensitive_field("api_token") is True

    def test_is_sensitive_field_secret(self):
        """Test detecting secret fields."""
        assert DataMasker.is_sensitive_field("secret") is True
        assert DataMasker.is_sensitive_field("secret_key") is True
        assert DataMasker.is_sensitive_field("api_secret") is True

    def test_is_sensitive_field_not_sensitive(self):
        """Test non-sensitive fields."""
        assert DataMasker.is_sensitive_field("username") is False
        assert DataMasker.is_sensitive_field("email") is False
        assert DataMasker.is_sensitive_field("name") is False
        assert DataMasker.is_sensitive_field("id") is False

    def test_mask_sensitive_data_flat_dict(self):
        """Test masking sensitive data in flat dictionary."""
        data = {
            "username": "john_doe",
            "password": "secret123",
            "email": "john@example.com",
            "token": "abc123xyz",
        }

        masked = DataMasker.mask_sensitive_data(data)

        assert masked["username"] == "john_doe"
        assert masked["password"] == "***MASKED***"
        assert masked["email"] == "john@example.com"
        assert masked["token"] == "***MASKED***"

    def test_mask_sensitive_data_nested_dict(self):
        """Test masking sensitive data in nested dictionary."""
        data = {
            "user": {"name": "John", "password": "secret123", "settings": {"api_key": "key123"}},
            "token": "abc123",
        }

        masked = DataMasker.mask_sensitive_data(data)

        assert masked["user"]["name"] == "John"
        assert masked["user"]["password"] == "***MASKED***"
        assert masked["user"]["settings"]["api_key"] == "***MASKED***"
        assert masked["token"] == "***MASKED***"

    def test_mask_sensitive_data_array(self):
        """Test masking sensitive data in array."""
        data = [
            {"username": "user1", "password": "pass1"},
            {"username": "user2", "token": "token2"},
        ]

        masked = DataMasker.mask_sensitive_data(data)

        assert masked[0]["username"] == "user1"
        assert masked[0]["password"] == "***MASKED***"
        assert masked[1]["username"] == "user2"
        assert masked[1]["token"] == "***MASKED***"

    def test_mask_sensitive_data_primitives(self):
        """Test masking doesn't affect primitives."""
        assert DataMasker.mask_sensitive_data("string") == "string"
        assert DataMasker.mask_sensitive_data(123) == 123
        assert DataMasker.mask_sensitive_data(True) is True
        assert DataMasker.mask_sensitive_data(None) is None

    def test_mask_value_full(self):
        """Test masking value completely."""
        masked = DataMasker.mask_value("password123")

        assert masked == "***MASKED***" or len(masked.replace("*", "")) < len("password123")

    def test_mask_value_show_first(self):
        """Test masking value with show_first."""
        masked = DataMasker.mask_value("password123", show_first=3)

        assert masked.startswith("pas")
        assert "*" in masked

    def test_mask_value_show_last(self):
        """Test masking value with show_last."""
        masked = DataMasker.mask_value("password123", show_last=3)

        assert masked.endswith("123")
        assert "*" in masked

    def test_mask_value_short_string(self):
        """Test masking short string."""
        masked = DataMasker.mask_value("ab")

        # For very short strings, it returns asterisks instead of "***MASKED***"
        assert masked == "********" or masked == "***MASKED***"

    def test_contains_sensitive_data_true(self):
        """Test detecting sensitive data presence."""
        data = {"username": "john", "password": "secret"}

        assert DataMasker.contains_sensitive_data(data) is True

    def test_contains_sensitive_data_false(self):
        """Test not detecting sensitive data."""
        data = {"username": "john", "email": "john@example.com"}

        assert DataMasker.contains_sensitive_data(data) is False

    def test_contains_sensitive_data_nested(self):
        """Test detecting sensitive data in nested structure."""
        data = {"user": {"name": "John", "api_key": "secret123"}}

        assert DataMasker.contains_sensitive_data(data) is True

    def test_contains_sensitive_data_array(self):
        """Test detecting sensitive data in array."""
        data = [{"name": "John"}, {"token": "secret"}]

        assert DataMasker.contains_sensitive_data(data) is True

    def test_contains_sensitive_data_primitives(self):
        """Test with primitives."""
        assert DataMasker.contains_sensitive_data("string") is False
        assert DataMasker.contains_sensitive_data(123) is False
        assert DataMasker.contains_sensitive_data(None) is False
