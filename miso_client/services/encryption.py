"""
Encryption service for sensitive data using Fernet symmetric encryption.

This module provides encryption/decryption functionality that can be used anywhere
in the application. It supports reading the encryption key from environment variables
or accepting it as a constructor parameter.
"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet

from ..errors import ConfigurationError


class EncryptionService:
    """Service for encrypting/decrypting sensitive data using Fernet encryption."""

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption service with key from environment or parameter.

        Args:
            encryption_key: Optional encryption key. If not provided, reads from EXTENSION_KEY env var.
                           If provided, overrides environment variable.

        Raises:
            ConfigurationError: If encryption key is not found or invalid
        """
        # Use provided key, or fall back to environment variable
        key = encryption_key or os.environ.get("ENCRYPTION_KEY")

        if not key:
            raise ConfigurationError(
                "ENCRYPTION_KEY not found. Either set ENCRYPTION_KEY environment variable "
                "or pass encryption_key parameter to EncryptionService constructor."
            )

        try:
            # Fernet.generate_key() returns bytes, but env vars are strings
            # Convert string to bytes if needed
            key_bytes = key.encode() if isinstance(key, str) else key
            self.fernet = Fernet(key_bytes)
        except Exception as e:
            raise ConfigurationError(
                f"Failed to initialize encryption service with provided key: {str(e)}"
            ) from e

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt sensitive data.

        Args:
            plaintext: Plain text string to encrypt

        Returns:
            Base64-encoded encrypted string

        Raises:
            ValueError: If encryption fails
        """
        if not plaintext:
            return ""

        try:
            encrypted = self.fernet.encrypt(plaintext.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            raise ValueError(f"Failed to encrypt data: {str(e)}") from e

    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt sensitive data.

        Args:
            encrypted_text: Base64-encoded encrypted string

        Returns:
            Decrypted plain text string

        Raises:
            ValueError: If decryption fails or data is invalid
        """
        if not encrypted_text:
            return ""

        try:
            decoded = base64.b64decode(encrypted_text.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {str(e)}") from e
