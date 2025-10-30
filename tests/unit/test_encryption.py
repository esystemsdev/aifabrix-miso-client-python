"""
Unit tests for EncryptionService.
"""

import pytest
import os
from unittest.mock import patch
from cryptography.fernet import Fernet
from miso_client.services.encryption import EncryptionService
from miso_client.errors import ConfigurationError


class TestEncryptionService:
    """Test cases for EncryptionService."""
    
    def test_init_with_env_var(self):
        """Test initialization with ENCRYPTION_KEY from environment."""
        # Generate a valid Fernet key
        key = Fernet.generate_key().decode()
        
        with patch.dict(os.environ, {"ENCRYPTION_KEY": key}, clear=False):
            service = EncryptionService()
            assert service.fernet is not None
    
    def test_init_with_constructor_param(self):
        """Test initialization with encryption key passed as parameter."""
        # Generate a valid Fernet key
        key = Fernet.generate_key().decode()
        
        # Remove env var if it exists
        with patch.dict(os.environ, {}, clear=False):
            if "ENCRYPTION_KEY" in os.environ:
                del os.environ["ENCRYPTION_KEY"]
            
            service = EncryptionService(encryption_key=key)
            assert service.fernet is not None
    
    def test_init_constructor_overrides_env(self):
        """Test that constructor parameter overrides environment variable."""
        env_key = Fernet.generate_key().decode()
        constructor_key = Fernet.generate_key().decode()
        
        with patch.dict(os.environ, {"ENCRYPTION_KEY": env_key}, clear=False):
            service = EncryptionService(encryption_key=constructor_key)
            # Verify it uses constructor key by encrypting with this service
            # and trying to decrypt with env key - should fail
            encrypted = service.encrypt("test")
            
            # Create service with env key
            env_service = EncryptionService()
            # Should fail to decrypt
            with pytest.raises(Exception):
                env_service.decrypt(encrypted)
    
    def test_init_no_key(self):
        """Test initialization fails when no key is provided."""
        with patch.dict(os.environ, {}, clear=False):
            if "ENCRYPTION_KEY" in os.environ:
                del os.environ["ENCRYPTION_KEY"]
            
            with pytest.raises(ConfigurationError, match="ENCRYPTION_KEY not found"):
                EncryptionService()
    
    def test_init_invalid_key(self):
        """Test initialization fails with invalid key."""
        with pytest.raises(ConfigurationError, match="Failed to initialize"):
            EncryptionService(encryption_key="invalid-key-format")
    
    def test_encrypt_decrypt_string(self):
        """Test encrypting and decrypting a string."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)
        
        plaintext = "Hello, World!"
        encrypted = service.encrypt(plaintext)
        
        assert encrypted != plaintext
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0
        
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_sensitive_data(self):
        """Test encrypting sensitive data like passwords and tokens."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)
        
        sensitive_data = [
            "my_secret_password_123",
            "api_key_abc123xyz",
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "client_secret:super_secret_value_here"
        ]
        
        for data in sensitive_data:
            encrypted = service.encrypt(data)
            decrypted = service.decrypt(encrypted)
            assert decrypted == data
    
    def test_encrypt_decrypt_unicode(self):
        """Test encrypting Unicode strings."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)
        
        unicode_strings = [
            "Hello 世界",
            "Привет мир",
            "🎉 Test with emoji 🚀",
            "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        ]
        
        for text in unicode_strings:
            encrypted = service.encrypt(text)
            decrypted = service.decrypt(encrypted)
            assert decrypted == text
    
    def test_encrypt_decrypt_long_string(self):
        """Test encrypting long strings."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)
        
        long_string = "A" * 10000
        encrypted = service.encrypt(long_string)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == long_string
    
    def test_encrypt_empty_string(self):
        """Test encrypting empty string returns empty string."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)
        
        encrypted = service.encrypt("")
        assert encrypted == ""
    
    def test_decrypt_empty_string(self):
        """Test decrypting empty string returns empty string."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)
        
        decrypted = service.decrypt("")
        assert decrypted == ""
    
    def test_decrypt_invalid_data(self):
        """Test decrypting invalid/corrupted data raises error."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)
        
        with pytest.raises(ValueError, match="Failed to decrypt"):
            service.decrypt("invalid-encrypted-data")
    
    def test_decrypt_wrong_key(self):
        """Test decrypting with wrong key fails."""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()
        
        service1 = EncryptionService(encryption_key=key1)
        service2 = EncryptionService(encryption_key=key2)
        
        encrypted = service1.encrypt("test data")
        
        with pytest.raises(Exception):  # Should raise ValueError or similar
            service2.decrypt(encrypted)
    
    def test_encrypt_returns_base64(self):
        """Test encrypted output is base64 encoded."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)
        
        encrypted = service.encrypt("test")
        
        # Base64 encoded strings should only contain alphanumeric + / + = chars
        import re
        base64_pattern = re.compile(r'^[A-Za-z0-9+/=]+$')
        assert base64_pattern.match(encrypted)
    
    def test_multiple_encrypts_different_output(self):
        """Test that encrypting same string multiple times produces different output (due to timestamp)."""
        key = Fernet.generate_key().decode()
        service = EncryptionService(encryption_key=key)
        
        plaintext = "same text"
        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)
        
        # Outputs should be different (Fernet includes timestamp)
        assert encrypted1 != encrypted2
        
        # But both should decrypt to same value
        assert service.decrypt(encrypted1) == plaintext
        assert service.decrypt(encrypted2) == plaintext

