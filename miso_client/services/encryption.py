"""
Encryption service for security parameter management via miso-controller.

This service provides encryption and decryption functionality by calling
miso-controller API endpoints. It supports Azure Key Vault and local
storage modes, with the storage backend determined by server configuration.
"""

import logging
import re
from typing import TYPE_CHECKING, cast

from ..errors import EncryptionError, MisoClientError
from ..models.encryption import EncryptResult

if TYPE_CHECKING:
    from ..utils.http_client import HttpClient

logger = logging.getLogger(__name__)

# Centralize endpoint URLs as constants (aligned with TypeScript SDK)
ENCRYPT_ENDPOINT = "/api/security/parameters/encrypt"
DECRYPT_ENDPOINT = "/api/security/parameters/decrypt"

# Parameter name validation regex (matches controller validation)
PARAMETER_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,128}$")


class EncryptionService:
    """
    Encryption service calling miso-controller for server-side encryption.

    This service provides encrypt/decrypt methods with client-side parameter
    validation before calling the controller API endpoints.
    """

    def __init__(self, http_client: "HttpClient"):
        """
        Initialize encryption service with HTTP client.

        Args:
            http_client: HTTP client instance for controller API calls
        """
        self.http_client = http_client

    def _validate_parameter_name(self, parameter_name: str) -> None:
        """
        Validate parameter name against allowed pattern.

        Args:
            parameter_name: Name to validate

        Raises:
            EncryptionError: If name doesn't match pattern
        """
        if not parameter_name or not PARAMETER_NAME_PATTERN.match(parameter_name):
            raise EncryptionError(
                f"Invalid parameter name: '{parameter_name}'. "
                "Must be 1-128 chars, alphanumeric with ._-",
                code="INVALID_PARAMETER_NAME",
                parameter_name=parameter_name,
            )

    async def encrypt(self, plaintext: str, parameter_name: str) -> EncryptResult:
        """
        Encrypt a plaintext value via miso-controller.

        The storage backend (Key Vault or local encryption) is determined
        by the controller's configuration.

        Args:
            plaintext: Value to encrypt (max 32KB)
            parameter_name: Name identifier (1-128 chars, alphanumeric with ._-)

        Returns:
            EncryptResult with value reference (kv:// or enc://v1:) and storage type

        Raises:
            EncryptionError: If validation fails or encryption fails
        """
        self._validate_parameter_name(parameter_name)
        try:
            response = await self.http_client.post(
                ENCRYPT_ENDPOINT,
                data={"plaintext": plaintext, "parameterName": parameter_name},
            )
            return EncryptResult(value=response["value"], storage=response["storage"])
        except MisoClientError as e:
            logger.error(f"Encryption failed for parameter '{parameter_name}'")
            raise EncryptionError(
                str(e),
                code="ENCRYPTION_FAILED",
                parameter_name=parameter_name,
                status_code=e.status_code,
            ) from e

    async def decrypt(self, value: str, parameter_name: str) -> str:
        """
        Decrypt an encrypted reference via miso-controller.

        The storage provider is auto-detected from the value prefix
        (kv:// for Key Vault, enc://v1: for local).

        Args:
            value: Encrypted reference (kv:// or enc://v1:)
            parameter_name: Name identifier (must match encryption)

        Returns:
            Decrypted plaintext string

        Raises:
            EncryptionError: If validation fails or decryption fails
        """
        self._validate_parameter_name(parameter_name)
        try:
            response = await self.http_client.post(
                DECRYPT_ENDPOINT,
                data={"value": value, "parameterName": parameter_name},
            )
            return cast(str, response["plaintext"])
        except MisoClientError as e:
            # Map specific error codes from controller response
            from ..errors import EncryptionErrorCode

            code: EncryptionErrorCode = "DECRYPTION_FAILED"
            if e.status_code == 404:
                code = "PARAMETER_NOT_FOUND"
            elif e.status_code == 403:
                code = "ACCESS_DENIED"
            logger.error(f"Decryption failed for parameter '{parameter_name}'")
            raise EncryptionError(
                str(e),
                code=code,
                parameter_name=parameter_name,
                status_code=e.status_code,
            ) from e
