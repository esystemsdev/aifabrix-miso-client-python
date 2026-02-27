# Server-Side Encryption SDK Implementation (Breaking Change)

**Aligned with**: TypeScript SDK `miso-client` v4.0.0

## Problem Statement

The miso-client Python SDK needs to call the miso-controller encryption endpoints instead of handling encryption locally. The existing `EncryptionService` class using local Fernet encryption will be **removed** in favor of controller-based encryption supporting Azure Key Vault and local storage modes.

## Breaking Changes

- **Removed**: Local Fernet encryption via `ENCRYPTION_KEY` environment variable
- **Removed**: `EncryptionService` constructor parameter `encryption_key`
- **Changed**: `encrypt()` method signature from `encrypt(plaintext) -> str` to `async encrypt(plaintext, parameter_name) -> EncryptResult`
- **Changed**: `decrypt()` method signature from `decrypt(encrypted) -> str` to `async decrypt(value, parameter_name) -> str`
- **Changed**: Methods are now async (were sync)
- **Added**: `EncryptionError` with error codes for better error handling
- **Added**: `EncryptResult` model with `value` and `storage` fields

## Target Interface

```python
from miso_client import MisoClient, EncryptResult, EncryptionError

client = MisoClient(config)  # No ENCRYPTION_KEY needed
await client.initialize()

# Server-side encryption
result = await client.encryption.encrypt('sensitive-data', 'my-parameter')
# Returns: EncryptResult(value='kv://my-parameter', storage='keyvault')

plaintext = await client.encryption.decrypt(result.value, 'my-parameter')

# Error handling
try:
    await client.encryption.encrypt('secret', 'invalid name!')
except EncryptionError as e:
    print(f"Code: {e.code}, Parameter: {e.parameter_name}")
```

## Rules and Standards

This plan must comply with the following rules from [Project Rules](.cursor/rules/project-rules.mdc):

- **[Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns)** - Service layer patterns, HTTP client usage with `http_client.post()`, automatic `x-client-token` handling
- **[Code Style](.cursor/rules/project-rules.mdc#code-style)** - Python conventions, type hints, async/await, Google-style docstrings
- **[Error Handling](.cursor/rules/project-rules.mdc#error-handling)** - Custom exception classes extending `MisoClientError`, error code mapping, logging with context
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - pytest with pytest-asyncio, mock HTTP client with `AsyncMock`, ≥80% coverage
- **[File Organization](.cursor/rules/project-rules.mdc#file-organization)** - Models in `miso_client/models/`, services in `miso_client/services/`, exports in `__init__.py`
- **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** - Files ≤500 lines, methods ≤20-30 lines
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - Never log sensitive data, use DataMasker, ISO 27001 compliance
- **[API Data Conventions](.cursor/rules/project-rules.mdc#api-data-conventions-camelcase)** - Request bodies use camelCase (`parameterName`, not `parameter_name`)

**Key Requirements**:

- Service receives `HttpClient` as dependency (not Redis - encryption doesn't cache)
- Use `http_client.post()` for API calls (x-client-token automatic)
- Wrap `MisoClientError` into `EncryptionError` with appropriate error codes
- Use try-except and log errors with `logger.error()`
- All public methods have type hints and Google-style docstrings
- Pydantic models for request/response types with camelCase field names
- Parameter validation uses regex pattern `^[a-zA-Z0-9._-]{1,128}$`

## Before Development

- [ ] Read Architecture Patterns section - service layer pattern, HTTP client usage
- [ ] Read Error Handling section - custom exception patterns, MisoClientError usage
- [ ] Review existing services (e.g., `role.py`, `permission.py`) for patterns
- [ ] Review existing error classes in `errors.py`
- [ ] Review existing models in `models/` for Pydantic patterns
- [ ] Review existing tests for mock patterns with `AsyncMock`

## Definition of Done

Before marking this plan as complete, ensure:

1. **Lint**: Run `ruff check miso_client/ tests/` - must pass with zero errors
2. **Type Check**: Run `mypy miso_client/` - must pass with zero errors
3. **Format**: Run `black miso_client/ tests/` and `isort miso_client/ tests/`
4. **Test**: Run `pytest tests/unit/test_encryption_service.py -v` - all tests must pass
5. **Coverage**: New code has ≥80% test coverage
6. **Validation Order**: LINT → TYPE CHECK → FORMAT → TEST (mandatory sequence)
7. **File Size**: All files ≤500 lines, all methods ≤20-30 lines
8. **Type Hints**: All functions have type hints
9. **Docstrings**: All public methods have Google-style docstrings
10. **Security**: No hardcoded secrets, no sensitive data in logs
11. **Documentation**: `docs/encryption.md` created, `CHANGELOG.md` updated
12. All tasks completed

## Controller API Endpoints

- **POST `/api/security/parameters/encrypt`** - Request: `{ plaintext, parameterName }` Response: `{ value, storage }`
- **POST `/api/security/parameters/decrypt`** - Request: `{ value, parameterName }` Response: `{ plaintext }`
- Auth: `x-client-token` header (automatic via HttpClient)

## Files to Create

- `miso_client/models/encryption.py` - Pydantic models (EncryptRequest, EncryptResult, etc.)
- `tests/unit/test_encryption_service.py` - Unit tests with mocked HTTP client
- `docs/encryption.md` - Encryption service documentation

## Files to Delete

- `tests/unit/test_encryption.py` - Old local Fernet encryption tests

## Files to Modify

- `miso_client/errors.py` - Add `EncryptionError` with error codes
- `miso_client/services/encryption.py` - Replace with server-side implementation
- `miso_client/__init__.py` - Update init, exports, convenience methods
- `miso_client/models/__init__.py` - Export encryption models
- `CHANGELOG.md` - Add breaking changes section with migration guide

## Implementation Details

### 1. Encryption Models (`miso_client/models/encryption.py`)

```python
"""Encryption API request and response type definitions."""
from typing import Literal
from pydantic import BaseModel, Field

StorageType = Literal["keyvault", "local"]

class EncryptRequest(BaseModel):
    """Encrypt request parameters."""
    plaintext: str = Field(..., description="Value to encrypt (max 32KB)")
    parameterName: str = Field(..., description="Name identifier (1-128 chars)")

class EncryptResult(BaseModel):
    """Encrypt response with storage reference."""
    value: str = Field(..., description="Encrypted reference (kv:// or enc://v1:)")
    storage: StorageType = Field(..., description="Storage backend used")

class DecryptRequest(BaseModel):
    """Decrypt request parameters."""
    value: str = Field(..., description="Encrypted reference")
    parameterName: str = Field(..., description="Name identifier")

class DecryptResult(BaseModel):
    """Decrypt response with plaintext value."""
    plaintext: str = Field(..., description="Decrypted value")
```

### 2. EncryptionError (`miso_client/errors.py`)

```python
from typing import Literal, Optional

EncryptionErrorCode = Literal[
    "ENCRYPTION_FAILED",
    "DECRYPTION_FAILED",
    "INVALID_PARAMETER_NAME",
    "ACCESS_DENIED",
    "PARAMETER_NOT_FOUND",
]

class EncryptionError(MisoClientError):
    """Raised when encryption/decryption operations fail."""

    def __init__(
        self,
        message: str,
        code: Optional[EncryptionErrorCode] = None,
        parameter_name: Optional[str] = None,
    ):
        super().__init__(message)
        self.code = code
        self.parameter_name = parameter_name
```

### 3. EncryptionService (`miso_client/services/encryption.py`)

```python
"""Encryption service for security parameter management via miso-controller."""
import logging
import re
from typing import TYPE_CHECKING

from ..errors import EncryptionError, MisoClientError
from ..models.encryption import EncryptResult

if TYPE_CHECKING:
    from ..utils.http_client import HttpClient

logger = logging.getLogger(__name__)

ENCRYPT_ENDPOINT = "/api/security/parameters/encrypt"
DECRYPT_ENDPOINT = "/api/security/parameters/decrypt"
PARAMETER_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,128}$")


class EncryptionService:
    """Encryption service calling miso-controller for server-side encryption."""

    def __init__(self, http_client: "HttpClient"):
        """Initialize with HTTP client for controller API calls."""
        self.http_client = http_client

    def _validate_parameter_name(self, parameter_name: str) -> None:
        """Validate parameter name against allowed pattern."""
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

        Args:
            plaintext: Value to encrypt (max 32KB)
            parameter_name: Name identifier (1-128 chars, alphanumeric with ._-)

        Returns:
            EncryptResult with value reference and storage type

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
            logger.error(f"Encryption failed for '{parameter_name}': {e}")
            raise EncryptionError(
                str(e), code="ENCRYPTION_FAILED", parameter_name=parameter_name
            ) from e

    async def decrypt(self, value: str, parameter_name: str) -> str:
        """
        Decrypt an encrypted reference via miso-controller.

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
            return response["plaintext"]
        except MisoClientError as e:
            code = "DECRYPTION_FAILED"
            if e.status_code == 404:
                code = "PARAMETER_NOT_FOUND"
            elif e.status_code == 403:
                code = "ACCESS_DENIED"
            logger.error(f"Decryption failed for '{parameter_name}': {e}")
            raise EncryptionError(str(e), code=code, parameter_name=parameter_name) from e
```

### 4. CHANGELOG.md Entry

````markdown
## [4.0.0] - 2026-01-XX

### Breaking Changes

- **Encryption Service Rewrite**: Local Fernet encryption replaced with server-side encryption via miso-controller
  - `encrypt()` now async: `await client.encryption.encrypt(plaintext, parameter_name)`
  - `decrypt()` now async: `await client.encryption.decrypt(value, parameter_name)`
  - `encrypt()` returns `EncryptResult` object (not string)
  - Both methods require `parameter_name` argument
  - `ENCRYPTION_KEY` environment variable no longer used

### Added

- `EncryptionError` exception with error codes
- `EncryptResult` model with `value` and `storage` fields
- `StorageType` type alias (`"keyvault"` | `"local"`)

### Migration Guide

**Before (v3.x):**
```python
client = MisoClient(config)  # Required ENCRYPTION_KEY
encrypted = client.encrypt("secret")  # Sync
````

**After (v4.0.0):**

```python
client = MisoClient(config)  # No ENCRYPTION_KEY needed
await client.initialize()
result = await client.encryption.encrypt("secret", "my-param")
decrypted = await client.encryption.decrypt(result.value, "my-param")
```
````

### 5. Documentation (`docs/encryption.md`)

See detailed documentation structure in original plan - includes:
- Usage examples for encrypt/decrypt
- Error handling with EncryptionError
- Error codes table
- Parameter naming rules

## Testing Strategy

### Unit Tests (`test_encryption_service.py`)

```python
@pytest.fixture
def mock_http_client(mocker):
    client = mocker.Mock(spec=HttpClient)
    client.post = AsyncMock()
    return client

class TestEncryptionService:
    # Parameter validation tests
    @pytest.mark.parametrize("name", ["simple", "with-dash", "with.dot", "a" * 128])
    async def test_valid_parameter_names(self, mock_http_client, name): ...

    @pytest.mark.parametrize("name", ["", "has space", "has/slash", "a" * 129])
    async def test_invalid_parameter_names(self, mock_http_client, name): ...

    # Encrypt tests
    async def test_encrypt_success(self, mock_http_client): ...
    async def test_encrypt_api_error(self, mock_http_client): ...

    # Decrypt tests
    async def test_decrypt_success(self, mock_http_client): ...
    async def test_decrypt_not_found_error(self, mock_http_client): ...
    async def test_decrypt_access_denied_error(self, mock_http_client): ...
````

## Version Bump

**Major version: 3.9.4 → 4.0.0** (breaking change)

---

## Plan Validation Report

**Date**: 2026-01-20

**Plan**: `.cursor/plans/server-side_encryption_sdk_b111304c.plan.md`

**Status**: ✅ VALIDATED

### Plan Purpose

Implement server-side encryption service that calls miso-controller API endpoints, replacing local Fernet encryption. Affects: services layer, models, error handling, exports, tests, documentation.

**Plan Type**: Service Layer / Breaking Change

### Applicable Rules

- ✅ **[Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns)** - Service receives HttpClient, uses `http_client.post()`
- ✅ **[Code Style](.cursor/rules/project-rules.mdc#code-style)** - Type hints, async/await, Google-style docstrings
- ✅ **[Error Handling](.cursor/rules/project-rules.mdc#error-handling)** - EncryptionError extends MisoClientError, error codes
- ✅ **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - pytest-asyncio, AsyncMock for HTTP client
- ✅ **[File Organization](.cursor/rules/project-rules.mdc#file-organization)** - Models in models/, services in services/
- ✅ **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** - Files ≤500 lines, methods ≤30 lines
- ✅ **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - No sensitive data logging
- ✅ **[API Data Conventions](.cursor/rules/project-rules.mdc#api-data-conventions-camelcase)** - camelCase for API fields

### Rule Compliance

- ✅ DoD Requirements: Documented (lint, type check, format, test, coverage)
- ✅ Architecture Patterns: Service pattern with HttpClient dependency
- ✅ Error Handling: Custom EncryptionError with error codes
- ✅ Testing: pytest-asyncio with AsyncMock patterns
- ✅ Code Size: Implementation fits within limits
- ✅ Security: No sensitive data exposure

### Plan Updates Made

- ✅ Added Rules and Standards section with applicable rule references
- ✅ Added Before Development checklist
- ✅ Added Definition of Done section with validation steps
- ✅ Added key requirements from rules
- ✅ Added validation report

### Recommendations

- None - plan is complete and ready for implementation