"""
Encryption API request and response type definitions.

This module defines Pydantic models for the encryption/decryption API endpoints
provided by miso-controller. All field names use camelCase to match API conventions.
"""

from typing import Literal

from pydantic import BaseModel, Field

# Storage backend type for encrypted parameters
StorageType = Literal["keyvault", "local"]


class EncryptRequest(BaseModel):
    """Encrypt request parameters sent to miso-controller."""

    plaintext: str = Field(..., description="The plaintext value to encrypt (max 32KB)")
    parameterName: str = Field(
        ..., description="Name identifier for the parameter (1-128 chars, alphanumeric with ._-)"
    )


class EncryptResult(BaseModel):
    """Encrypt response with storage reference from miso-controller."""

    value: str = Field(..., description="Encrypted reference (kv://paramName or enc://v1:base64)")
    storage: StorageType = Field(..., description="Storage backend used (keyvault or local)")


class DecryptRequest(BaseModel):
    """Decrypt request parameters sent to miso-controller."""

    value: str = Field(..., description="Encrypted reference (kv:// or enc://v1:)")
    parameterName: str = Field(
        ..., description="Name identifier for the parameter (must match encryption)"
    )


class DecryptResult(BaseModel):
    """Decrypt response with plaintext value from miso-controller."""

    plaintext: str = Field(..., description="The decrypted plaintext value")
