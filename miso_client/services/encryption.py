"""Encryption service for security parameter management via miso-controller.

This service provides encryption and decryption functionality by calling
miso-controller API endpoints. It supports Azure Key Vault and local
storage modes, with the storage backend determined by server configuration.
Optional response caching reduces controller calls when the same value
is encrypted or decrypted repeatedly.
"""

import hashlib
import logging
import re
from typing import TYPE_CHECKING, Optional, cast

from ..errors import EncryptionError, MisoClientError
from ..models.encryption import EncryptResult
from ..utils.error_utils import extract_correlation_id_from_error

if TYPE_CHECKING:
    from ..models.config import MisoClientConfig
    from ..services.cache import CacheService
    from ..utils.http_client import HttpClient

logger = logging.getLogger(__name__)

# Centralize endpoint URLs as constants (aligned with TypeScript SDK)
ENCRYPT_ENDPOINT = "/api/security/parameters/encrypt"
DECRYPT_ENDPOINT = "/api/security/parameters/decrypt"

# Cache key prefixes (no plaintext in keys; encrypt key is hash of plaintext+param)
ENCRYPT_CACHE_PREFIX = "encryption:encrypt:"
DECRYPT_CACHE_PREFIX = "encryption:decrypt:"

# Parameter name validation regex (matches controller validation)
PARAMETER_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,128}$")


def _cache_key_encrypt(plaintext: str, parameter_name: str) -> str:
    """Build cache key for encrypt result. Uses hash only (no plaintext in key)."""
    raw = f"{plaintext}:{parameter_name}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{ENCRYPT_CACHE_PREFIX}{h}"


def _cache_key_decrypt(value: str, parameter_name: str) -> str:
    """Build cache key for decrypt result (value is encrypted reference)."""
    raw = f"{value}:{parameter_name}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{DECRYPT_CACHE_PREFIX}{h}"


class EncryptionService:
    """Encryption service calling miso-controller for server-side encryption.

    This service provides encrypt/decrypt methods with client-side parameter
    validation before calling the controller API endpoints. Optional
    CacheService and encryption_cache_ttl reduce controller calls by
    caching results (encrypt by hash of plaintext+param, decrypt by value+param).
    """

    def __init__(
        self,
        http_client: "HttpClient",
        config: "MisoClientConfig",
        cache: Optional["CacheService"] = None,
    ):
        """Initialize encryption service.

        Args:
            http_client: HTTP client for controller API calls
            config: Client configuration (encryption_key, encryption_cache_ttl)
            cache: Optional cache service for encrypt/decrypt results (TTL from config)

        """
        self.http_client = http_client
        self._config = config
        self._cache = cache
        self._encryption_key = config.encryption_key

    def _validate_parameter_name(self, parameter_name: str) -> None:
        """Validate parameter name against allowed pattern.

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

    def _validate_encryption_key(self) -> None:
        """Validate that encryption key is configured.

        Raises:
            EncryptionError: If encryption key is not configured

        """
        if not self._encryption_key:
            raise EncryptionError(
                "Encryption key is required. Set MISO_ENCRYPTION_KEY or ENCRYPTION_KEY "
                "environment variable or provide encryption_key in config.",
                code="ENCRYPTION_KEY_REQUIRED",
            )

    def _encryption_cache_ttl(self) -> int:
        """Return encryption cache TTL in seconds; 0 means disabled."""
        return getattr(self._config, "encryption_cache_ttl", 300) or 0

    async def encrypt(self, plaintext: str, parameter_name: str) -> EncryptResult:
        """Encrypt a plaintext value via miso-controller.

        The storage backend (Key Vault or local encryption) is determined
        by the controller's configuration. When cache is enabled, repeated
        encrypt of the same (plaintext, parameter_name) returns cached result.

        Args:
            plaintext: Value to encrypt (max 32KB)
            parameter_name: Name identifier (1-128 chars, alphanumeric with ._-)

        Returns:
            EncryptResult with value reference (kv:// or enc://v1:) and storage type

        Raises:
            EncryptionError: If validation fails or encryption fails

        """
        self._validate_parameter_name(parameter_name)
        self._validate_encryption_key()
        ttl = self._encryption_cache_ttl()
        cache_key = (
            _cache_key_encrypt(plaintext, parameter_name) if (self._cache and ttl > 0) else None
        )
        if cache_key is not None and self._cache is not None:
            try:
                cached = await self._cache.get(cache_key)
                if cached is not None and isinstance(cached, dict):
                    return EncryptResult(**cached)
            except Exception:
                pass  # Fallback to controller on cache failure
        try:
            response = await self.http_client.post(
                ENCRYPT_ENDPOINT,
                data={
                    "plaintext": plaintext,
                    "parameterName": parameter_name,
                    "encryptionKey": self._encryption_key,
                },
            )
            result = EncryptResult(value=response["value"], storage=response["storage"])
            if cache_key is not None and self._cache is not None:
                try:
                    await self._cache.set(cache_key, result.model_dump(), ttl)
                except Exception:
                    pass
            return result
        except MisoClientError as e:
            correlation_id = extract_correlation_id_from_error(e)
            extra = {"correlationId": correlation_id} if correlation_id else None
            logger.error(
                f"Encryption failed for parameter '{parameter_name}'",
                exc_info=e,
                extra=extra,
            )
            raise EncryptionError(
                str(e),
                code="ENCRYPTION_FAILED",
                parameter_name=parameter_name,
                status_code=e.status_code,
            ) from e

    async def decrypt(self, value: str, parameter_name: str) -> str:
        """Decrypt an encrypted reference via miso-controller.

        The storage provider is auto-detected from the value prefix
        (kv:// for Key Vault, enc://v1: for local). When cache is enabled,
        repeated decrypt of the same (value, parameter_name) returns cached plaintext.

        Args:
            value: Encrypted reference (kv:// or enc://v1:)
            parameter_name: Name identifier (must match encryption)

        Returns:
            Decrypted plaintext string

        Raises:
            EncryptionError: If validation fails or decryption fails

        """
        self._validate_parameter_name(parameter_name)
        self._validate_encryption_key()
        ttl = self._encryption_cache_ttl()
        cache_key = _cache_key_decrypt(value, parameter_name) if (self._cache and ttl > 0) else None
        if cache_key is not None and self._cache is not None:
            try:
                cached = await self._cache.get(cache_key)
                if cached is not None and isinstance(cached, str):
                    return cast(str, cached)
            except Exception:
                pass  # Fallback to controller on cache failure
        try:
            response = await self.http_client.post(
                DECRYPT_ENDPOINT,
                data={
                    "value": value,
                    "parameterName": parameter_name,
                    "encryptionKey": self._encryption_key,
                },
            )
            plaintext = cast(str, response["plaintext"])
            if cache_key is not None and self._cache is not None:
                try:
                    await self._cache.set(cache_key, plaintext, ttl)
                except Exception:
                    pass
            return plaintext
        except MisoClientError as e:
            # Map specific error codes from controller response
            from ..errors import EncryptionErrorCode

            code: EncryptionErrorCode = "DECRYPTION_FAILED"
            if e.status_code == 404:
                code = "PARAMETER_NOT_FOUND"
            elif e.status_code in (401, 403):
                code = "ACCESS_DENIED"
            correlation_id = extract_correlation_id_from_error(e)
            extra = {"correlationId": correlation_id} if correlation_id else None
            logger.error(
                f"Decryption failed for parameter '{parameter_name}'",
                exc_info=e,
                extra=extra,
            )
            raise EncryptionError(
                str(e),
                code=code,
                parameter_name=parameter_name,
                status_code=e.status_code,
            ) from e
