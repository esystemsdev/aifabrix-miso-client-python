"""
Unit tests for EncryptionService.

Tests server-side encryption via miso-controller API endpoints.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from miso_client.errors import EncryptionError, MisoClientError
from miso_client.models.encryption import EncryptResult
from miso_client.services.encryption import (
    DECRYPT_ENDPOINT,
    ENCRYPT_ENDPOINT,
    PARAMETER_NAME_PATTERN,
    EncryptionService,
)


class TestParameterNameValidation:
    """Test cases for parameter name validation."""

    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client."""
        client = MagicMock()
        client.post = AsyncMock()
        return client

    @pytest.fixture
    def mock_config(self):
        """Create mock config with encryption key."""
        config = MagicMock()
        config.encryption_key = "test-encryption-key"
        return config

    @pytest.fixture
    def encryption_service(self, mock_http_client, mock_config):
        """Create EncryptionService instance."""
        return EncryptionService(mock_http_client, mock_config)

    def test_parameter_name_pattern_valid_simple(self):
        """Test valid simple parameter name."""
        assert PARAMETER_NAME_PATTERN.match("simple")

    def test_parameter_name_pattern_valid_with_dash(self):
        """Test valid parameter name with dash."""
        assert PARAMETER_NAME_PATTERN.match("with-dash")

    def test_parameter_name_pattern_valid_with_underscore(self):
        """Test valid parameter name with underscore."""
        assert PARAMETER_NAME_PATTERN.match("with_underscore")

    def test_parameter_name_pattern_valid_with_dot(self):
        """Test valid parameter name with dot."""
        assert PARAMETER_NAME_PATTERN.match("with.dot")

    def test_parameter_name_pattern_valid_mixed(self):
        """Test valid parameter name with mixed characters."""
        assert PARAMETER_NAME_PATTERN.match("Mixed123._-test")

    def test_parameter_name_pattern_valid_single_char(self):
        """Test valid single character parameter name."""
        assert PARAMETER_NAME_PATTERN.match("a")

    def test_parameter_name_pattern_valid_max_length(self):
        """Test valid parameter name at max length (128 chars)."""
        assert PARAMETER_NAME_PATTERN.match("a" * 128)

    def test_parameter_name_pattern_invalid_empty(self):
        """Test empty parameter name is invalid."""
        assert not PARAMETER_NAME_PATTERN.match("")

    def test_parameter_name_pattern_invalid_space(self):
        """Test parameter name with space is invalid."""
        assert not PARAMETER_NAME_PATTERN.match("has space")

    def test_parameter_name_pattern_invalid_slash(self):
        """Test parameter name with slash is invalid."""
        assert not PARAMETER_NAME_PATTERN.match("has/slash")

    def test_parameter_name_pattern_invalid_backslash(self):
        """Test parameter name with backslash is invalid."""
        assert not PARAMETER_NAME_PATTERN.match("has\\backslash")

    def test_parameter_name_pattern_invalid_at(self):
        """Test parameter name with @ symbol is invalid."""
        assert not PARAMETER_NAME_PATTERN.match("has@symbol")

    def test_parameter_name_pattern_invalid_too_long(self):
        """Test parameter name exceeding 128 chars is invalid."""
        assert not PARAMETER_NAME_PATTERN.match("a" * 129)

    @pytest.mark.asyncio
    async def test_validate_empty_parameter_name_raises_error(self, encryption_service):
        """Test that empty parameter name raises EncryptionError."""
        with pytest.raises(EncryptionError) as exc_info:
            await encryption_service.encrypt("secret", "")

        assert exc_info.value.code == "INVALID_PARAMETER_NAME"
        assert exc_info.value.parameter_name == ""

    @pytest.mark.asyncio
    async def test_validate_invalid_parameter_name_raises_error(self, encryption_service):
        """Test that invalid parameter name raises EncryptionError."""
        with pytest.raises(EncryptionError) as exc_info:
            await encryption_service.encrypt("secret", "invalid name!")

        assert exc_info.value.code == "INVALID_PARAMETER_NAME"
        assert exc_info.value.parameter_name == "invalid name!"

    @pytest.mark.asyncio
    async def test_validate_too_long_parameter_name_raises_error(self, encryption_service):
        """Test that parameter name exceeding 128 chars raises EncryptionError."""
        long_name = "a" * 129
        with pytest.raises(EncryptionError) as exc_info:
            await encryption_service.encrypt("secret", long_name)

        assert exc_info.value.code == "INVALID_PARAMETER_NAME"
        assert exc_info.value.parameter_name == long_name


class TestEncrypt:
    """Test cases for encrypt method."""

    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client."""
        client = MagicMock()
        client.post = AsyncMock()
        return client

    @pytest.fixture
    def mock_config(self):
        """Create mock config with encryption key."""
        config = MagicMock()
        config.encryption_key = "test-encryption-key"
        return config

    @pytest.fixture
    def encryption_service(self, mock_http_client, mock_config):
        """Create EncryptionService instance."""
        return EncryptionService(mock_http_client, mock_config)

    @pytest.mark.asyncio
    async def test_encrypt_success_keyvault(self, encryption_service, mock_http_client):
        """Test successful encryption with Key Vault storage."""
        mock_http_client.post.return_value = {
            "value": "kv://my-param",
            "storage": "keyvault",
        }

        result = await encryption_service.encrypt("secret-data", "my-param")

        assert isinstance(result, EncryptResult)
        assert result.value == "kv://my-param"
        assert result.storage == "keyvault"
        mock_http_client.post.assert_called_once_with(
            ENCRYPT_ENDPOINT,
            data={
                "plaintext": "secret-data",
                "parameterName": "my-param",
                "encryptionKey": "test-encryption-key",
            },
        )

    @pytest.mark.asyncio
    async def test_encrypt_success_local(self, encryption_service, mock_http_client):
        """Test successful encryption with local storage."""
        mock_http_client.post.return_value = {
            "value": "enc://v1:YWJjZGVm",
            "storage": "local",
        }

        result = await encryption_service.encrypt("secret-data", "my-param")

        assert isinstance(result, EncryptResult)
        assert result.value == "enc://v1:YWJjZGVm"
        assert result.storage == "local"

    @pytest.mark.asyncio
    async def test_encrypt_api_error(self, encryption_service, mock_http_client):
        """Test encryption API error is wrapped in EncryptionError."""
        mock_http_client.post.side_effect = MisoClientError(
            "Internal server error", status_code=500
        )

        with pytest.raises(EncryptionError) as exc_info:
            await encryption_service.encrypt("secret", "my-param")

        assert exc_info.value.code == "ENCRYPTION_FAILED"
        assert exc_info.value.parameter_name == "my-param"
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_encrypt_with_special_characters_in_value(
        self, encryption_service, mock_http_client
    ):
        """Test encryption with special characters in plaintext."""
        mock_http_client.post.return_value = {
            "value": "kv://db.password",
            "storage": "keyvault",
        }

        result = await encryption_service.encrypt("p@ssw0rd!#$%^&*()", "db.password")

        assert result.value == "kv://db.password"
        mock_http_client.post.assert_called_once_with(
            ENCRYPT_ENDPOINT,
            data={
                "plaintext": "p@ssw0rd!#$%^&*()",
                "parameterName": "db.password",
                "encryptionKey": "test-encryption-key",
            },
        )

    @pytest.mark.asyncio
    async def test_encrypt_with_unicode(self, encryption_service, mock_http_client):
        """Test encryption with Unicode characters."""
        mock_http_client.post.return_value = {
            "value": "kv://unicode-test",
            "storage": "keyvault",
        }

        result = await encryption_service.encrypt("密码🔐", "unicode-test")

        assert result.value == "kv://unicode-test"


class TestDecrypt:
    """Test cases for decrypt method."""

    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client."""
        client = MagicMock()
        client.post = AsyncMock()
        return client

    @pytest.fixture
    def mock_config(self):
        """Create mock config with encryption key."""
        config = MagicMock()
        config.encryption_key = "test-encryption-key"
        return config

    @pytest.fixture
    def encryption_service(self, mock_http_client, mock_config):
        """Create EncryptionService instance."""
        return EncryptionService(mock_http_client, mock_config)

    @pytest.mark.asyncio
    async def test_decrypt_success_keyvault(self, encryption_service, mock_http_client):
        """Test successful decryption from Key Vault."""
        mock_http_client.post.return_value = {"plaintext": "secret-data"}

        result = await encryption_service.decrypt("kv://my-param", "my-param")

        assert result == "secret-data"
        mock_http_client.post.assert_called_once_with(
            DECRYPT_ENDPOINT,
            data={
                "value": "kv://my-param",
                "parameterName": "my-param",
                "encryptionKey": "test-encryption-key",
            },
        )

    @pytest.mark.asyncio
    async def test_decrypt_success_local(self, encryption_service, mock_http_client):
        """Test successful decryption from local storage."""
        mock_http_client.post.return_value = {"plaintext": "decrypted-value"}

        result = await encryption_service.decrypt("enc://v1:YWJjZGVm", "my-param")

        assert result == "decrypted-value"

    @pytest.mark.asyncio
    async def test_decrypt_not_found_error(self, encryption_service, mock_http_client):
        """Test decryption 404 error maps to PARAMETER_NOT_FOUND."""
        mock_http_client.post.side_effect = MisoClientError("Parameter not found", status_code=404)

        with pytest.raises(EncryptionError) as exc_info:
            await encryption_service.decrypt("kv://missing", "missing")

        assert exc_info.value.code == "PARAMETER_NOT_FOUND"
        assert exc_info.value.parameter_name == "missing"
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_decrypt_access_denied_error(self, encryption_service, mock_http_client):
        """Test decryption 403 error maps to ACCESS_DENIED."""
        mock_http_client.post.side_effect = MisoClientError("Access denied", status_code=403)

        with pytest.raises(EncryptionError) as exc_info:
            await encryption_service.decrypt("kv://forbidden", "forbidden")

        assert exc_info.value.code == "ACCESS_DENIED"
        assert exc_info.value.parameter_name == "forbidden"
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_decrypt_general_error(self, encryption_service, mock_http_client):
        """Test decryption general error maps to DECRYPTION_FAILED."""
        mock_http_client.post.side_effect = MisoClientError("Decryption failed", status_code=500)

        with pytest.raises(EncryptionError) as exc_info:
            await encryption_service.decrypt("kv://error", "error")

        assert exc_info.value.code == "DECRYPTION_FAILED"
        assert exc_info.value.parameter_name == "error"
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_decrypt_invalid_parameter_name(self, encryption_service):
        """Test decrypt with invalid parameter name raises error."""
        with pytest.raises(EncryptionError) as exc_info:
            await encryption_service.decrypt("kv://test", "invalid/name")

        assert exc_info.value.code == "INVALID_PARAMETER_NAME"


class TestEncryptionServiceInit:
    """Test cases for EncryptionService initialization."""

    def test_init_stores_http_client(self):
        """Test that init stores the HTTP client."""
        mock_client = MagicMock()
        mock_config = MagicMock()
        mock_config.encryption_key = "test-key"
        service = EncryptionService(mock_client, mock_config)

        assert service.http_client is mock_client

    def test_init_stores_encryption_key(self):
        """Test that init stores the encryption key from config."""
        mock_client = MagicMock()
        mock_config = MagicMock()
        mock_config.encryption_key = "my-encryption-key"
        service = EncryptionService(mock_client, mock_config)

        assert service._encryption_key == "my-encryption-key"

    def test_init_handles_none_encryption_key(self):
        """Test that init handles None encryption key."""
        mock_client = MagicMock()
        mock_config = MagicMock()
        mock_config.encryption_key = None
        service = EncryptionService(mock_client, mock_config)

        assert service._encryption_key is None


class TestEncryptionErrorModel:
    """Test cases for EncryptionError class."""

    def test_encryption_error_with_all_fields(self):
        """Test EncryptionError with all fields."""
        error = EncryptionError(
            "Test error",
            code="ENCRYPTION_FAILED",
            parameter_name="test-param",
            status_code=500,
        )

        assert str(error) == "Test error"
        assert error.code == "ENCRYPTION_FAILED"
        assert error.parameter_name == "test-param"
        assert error.status_code == 500

    def test_encryption_error_minimal(self):
        """Test EncryptionError with minimal fields."""
        error = EncryptionError("Simple error")

        assert str(error) == "Simple error"
        assert error.code is None
        assert error.parameter_name is None
        assert error.status_code is None

    def test_encryption_error_inherits_from_miso_client_error(self):
        """Test EncryptionError inherits from MisoClientError."""
        error = EncryptionError("Test")
        assert isinstance(error, MisoClientError)


class TestEncryptResultModel:
    """Test cases for EncryptResult model."""

    def test_encrypt_result_keyvault(self):
        """Test EncryptResult with keyvault storage."""
        result = EncryptResult(value="kv://test", storage="keyvault")

        assert result.value == "kv://test"
        assert result.storage == "keyvault"

    def test_encrypt_result_local(self):
        """Test EncryptResult with local storage."""
        result = EncryptResult(value="enc://v1:abc", storage="local")

        assert result.value == "enc://v1:abc"
        assert result.storage == "local"


class TestEncryptionKeyValidation:
    """Test cases for encryption key validation."""

    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client."""
        client = MagicMock()
        client.post = AsyncMock()
        return client

    @pytest.fixture
    def mock_config_no_key(self):
        """Create mock config without encryption key."""
        config = MagicMock()
        config.encryption_key = None
        return config

    @pytest.fixture
    def mock_config_with_key(self):
        """Create mock config with encryption key."""
        config = MagicMock()
        config.encryption_key = "test-encryption-key"
        return config

    @pytest.mark.asyncio
    async def test_encrypt_raises_error_when_key_missing(
        self, mock_http_client, mock_config_no_key
    ):
        """Test encrypt raises ENCRYPTION_KEY_REQUIRED when key is missing."""
        service = EncryptionService(mock_http_client, mock_config_no_key)

        with pytest.raises(EncryptionError) as exc_info:
            await service.encrypt("secret", "my-param")

        assert exc_info.value.code == "ENCRYPTION_KEY_REQUIRED"
        assert "MISO_ENCRYPTION_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_decrypt_raises_error_when_key_missing(
        self, mock_http_client, mock_config_no_key
    ):
        """Test decrypt raises ENCRYPTION_KEY_REQUIRED when key is missing."""
        service = EncryptionService(mock_http_client, mock_config_no_key)

        with pytest.raises(EncryptionError) as exc_info:
            await service.decrypt("kv://test", "my-param")

        assert exc_info.value.code == "ENCRYPTION_KEY_REQUIRED"
        assert "MISO_ENCRYPTION_KEY" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_encrypt_includes_encryption_key_in_request(
        self, mock_http_client, mock_config_with_key
    ):
        """Test encrypt includes encryptionKey in request body."""
        mock_http_client.post.return_value = {
            "value": "kv://my-param",
            "storage": "keyvault",
        }
        service = EncryptionService(mock_http_client, mock_config_with_key)

        await service.encrypt("secret-data", "my-param")

        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[1]["data"]["encryptionKey"] == "test-encryption-key"

    @pytest.mark.asyncio
    async def test_decrypt_includes_encryption_key_in_request(
        self, mock_http_client, mock_config_with_key
    ):
        """Test decrypt includes encryptionKey in request body."""
        mock_http_client.post.return_value = {"plaintext": "secret-data"}
        service = EncryptionService(mock_http_client, mock_config_with_key)

        await service.decrypt("kv://my-param", "my-param")

        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args[1]["data"]["encryptionKey"] == "test-encryption-key"

    @pytest.mark.asyncio
    async def test_decrypt_401_maps_to_access_denied(
        self, mock_http_client, mock_config_with_key
    ):
        """Test decryption 401 error maps to ACCESS_DENIED."""
        mock_http_client.post.side_effect = MisoClientError(
            "Unauthorized", status_code=401
        )
        service = EncryptionService(mock_http_client, mock_config_with_key)

        with pytest.raises(EncryptionError) as exc_info:
            await service.decrypt("kv://forbidden", "forbidden")

        assert exc_info.value.code == "ACCESS_DENIED"
        assert exc_info.value.status_code == 401
