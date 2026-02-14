# Encryption Service

The MisoClient SDK provides encryption and decryption functionality for sensitive data via the miso-controller. This enables secure storage of secrets using Azure Key Vault (production) or local AES-256-GCM encryption (development).

## Overview

The encryption service calls miso-controller API endpoints to:

- **Encrypt** plaintext values and return storage references
- **Decrypt** storage references back to plaintext

The storage backend (Key Vault or local) is determined by the controller's configuration, not by the client.

## Configuration

### Encryption key requirement

The encryption key is **required** for encrypt/decrypt operations. Set **either** `MISO_ENCRYPTION_KEY` or `ENCRYPTION_KEY` in your environment. This key provides a second factor of authorization beyond client credentials.

### Where to Obtain the Key

- Contact your environment administrator or DevOps team
- The key is environment-specific (different for production, staging, development)
- The key may be stored in:
  - **Azure Key Vault** (production) - administrator retrieves from Key Vault
  - **Environment configuration** (development) - administrator provides directly

### Security Model

- SDK reads the key from `MISO_ENCRYPTION_KEY` or `ENCRYPTION_KEY` in your `.env`
- SDK sends `encryptionKey` parameter to miso-controller with each request
- Controller validates against its configured source (Key Vault or .env)
- Provides two-level authorization: client credentials alone are insufficient
- `encryptionKey` is never logged, stored, or returned

### Example .env

```env
MISO_CONTROLLER_URL=https://controller.example.com
MISO_CLIENTID=your-client-id
MISO_CLIENTSECRET=your-client-secret
MISO_ENCRYPTION_KEY=obtain-from-your-environment-administrator
# or: ENCRYPTION_KEY=obtain-from-your-environment-administrator
```

## Usage

### Encrypting Data

```python
from miso_client import MisoClient, EncryptResult, EncryptionError

# Initialize client (MISO_ENCRYPTION_KEY required in .env)
client = MisoClient(config)
await client.initialize()

# Encrypt a secret
result = await client.encryption.encrypt("my-secret-api-key", "external-api-key")

# Result contains the encrypted reference and storage type
print(result.value)    # "kv://external-api-key" (Key Vault) or "enc://v1:..." (local)
print(result.storage)  # "keyvault" or "local"

# Store result.value in your database (never store plaintext)
await db.settings.update({"apiKeyRef": result.value})
```

### Decrypting Data

```python
# Retrieve the stored reference
setting = await db.settings.find_one()

# Decrypt to get the original value
plaintext = await client.encryption.decrypt(setting["apiKeyRef"], "external-api-key")

# Use the decrypted value
api_key = plaintext
```

### Convenience Methods on MisoClient

The `MisoClient` class provides convenience methods that delegate to the encryption service:

```python
# These are equivalent:
result = await client.encryption.encrypt("secret", "my-param")
result = await client.encrypt("secret", "my-param")

plaintext = await client.encryption.decrypt(result.value, "my-param")
plaintext = await client.decrypt(result.value, "my-param")
```

## Error Handling

```python
from miso_client import EncryptionError

try:
    await client.encryption.encrypt("secret", "invalid name!")
except EncryptionError as e:
    print(f"Error: {e}")
    print(f"Code: {e.code}")              # INVALID_PARAMETER_NAME
    print(f"Parameter: {e.parameter_name}")  # invalid name!
    print(f"Status: {e.status_code}")     # None (client-side validation)
```

## Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `ENCRYPTION_KEY_REQUIRED` | `MISO_ENCRYPTION_KEY` / `ENCRYPTION_KEY` not set | N/A (client-side) |
| `INVALID_PARAMETER_NAME` | Parameter name doesn't match pattern `^[a-zA-Z0-9._-]{1,128}$` | N/A (client-side) |
| `ENCRYPTION_FAILED` | Controller encryption failed | 500 |
| `DECRYPTION_FAILED` | Controller decryption failed (general) | 500 |
| `ACCESS_DENIED` | App doesn't have access or invalid encryption key | 401 or 403 |
| `PARAMETER_NOT_FOUND` | Parameter doesn't exist (Key Vault mode) | 404 |

## Parameter Naming

Parameter names must match the pattern: `^[a-zA-Z0-9._-]{1,128}$`

### Valid Names

- `my-api-key` - Alphanumeric with dashes
- `db.password` - Alphanumeric with dots
- `service_token` - Alphanumeric with underscores
- `OAuth2ClientSecret` - Mixed case alphanumeric
- `a` - Single character (minimum)
- `a` * 128 - Maximum length (128 characters)

### Invalid Names

- `my api key` - Contains spaces
- `key@123` - Contains special characters (@)
- `path/to/key` - Contains slashes
- `` (empty) - Empty string
- `a` * 129 - Exceeds maximum length

## Storage Types

The `EncryptResult.storage` field indicates which backend was used:

| Storage | Value Format | Description |
|---------|--------------|-------------|
| `keyvault` | `kv://<parameterName>` | Secret stored in Azure Key Vault |
| `local` | `enc://v1:<base64>` | AES-256-GCM encrypted locally |

The storage backend is determined by the controller's configuration:

- **Production**: Typically uses Azure Key Vault (`keyvault`)
- **Development**: Typically uses local encryption (`local`)

## Manual Testing

A manual test script is provided to verify encrypt/decrypt against a real miso-controller.

### Prerequisites

- SDK and dependencies installed (e.g. `pip install -e .` or use the project venv).
- `.env` in the project root with:
  - `MISO_CONTROLLER_URL` – controller base URL
  - `MISO_CLIENTID` / `MISO_CLIENTSECRET` – client credentials
  - `MISO_ENCRYPTION_KEY` or `ENCRYPTION_KEY` – encryption key (from your environment administrator)
- miso-controller running and configured for encryption (local or Key Vault)

### Run round-trip test (encrypt → decrypt)

From the project root:

```bash
python tests/integration/manual_test_encryption.py
```

This will:

1. Initialize `MisoClient` from `.env`
2. Encrypt a test value with a fixed parameter name
3. Decrypt the returned reference
4. Assert decrypted value equals the original

Success: script exits 0 and prints `round-trip OK`. Failure: exits 1 with error details.

### Run validation-only (no controller required for some checks)

To exercise client-side validation only (e.g. missing `MISO_ENCRYPTION_KEY`, invalid parameter name):

```bash
python tests/integration/manual_test_encryption.py --validate-only
```

With `MISO_ENCRYPTION_KEY` unset, this verifies `ENCRYPTION_KEY_REQUIRED`. With it set, this verifies `INVALID_PARAMETER_NAME` for an invalid parameter name.

### What to verify manually

- **Round-trip**: Encrypted reference format matches storage (`kv://...` or `enc://v1:...`), and decrypted value matches the plaintext you encrypted.
- **Errors**: For invalid controller config or key, you should see `EncryptionError` with an appropriate `code` (e.g. `ACCESS_DENIED`, `ENCRYPTION_FAILED`). See [Error Codes](#error-codes) in this document.

**Note:** The manual test script (and the SDK) accept the key from either `MISO_ENCRYPTION_KEY` or `ENCRYPTION_KEY` in `.env`.

## API Reference

### EncryptionService

#### `encrypt(plaintext: str, parameter_name: str) -> EncryptResult`

Encrypts a plaintext value via miso-controller.

**Parameters:**

- `plaintext` - Value to encrypt (max 32KB)
- `parameter_name` - Name identifier (1-128 chars, alphanumeric with `._-`)

**Returns:** `EncryptResult` with `value` and `storage` fields

**Raises:** `EncryptionError` if validation fails or encryption fails

#### `decrypt(value: str, parameter_name: str) -> str`

Decrypts an encrypted reference via miso-controller.

**Parameters:**

- `value` - Encrypted reference (`kv://...` or `enc://v1:...`)
- `parameter_name` - Name identifier (must match the name used during encryption)

**Returns:** Decrypted plaintext string

**Raises:** `EncryptionError` if validation fails or decryption fails

### EncryptResult

Pydantic model for encryption response:

```python
class EncryptResult(BaseModel):
    value: str       # Encrypted reference (kv://... or enc://v1:...)
    storage: StorageType  # "keyvault" or "local"
```

### EncryptionError

Exception raised for encryption/decryption failures:

```python
class EncryptionError(MisoClientError):
    code: Optional[EncryptionErrorCode]  # Error code for programmatic handling
    parameter_name: Optional[str]        # The parameter name that caused the error
    status_code: Optional[int]           # HTTP status code if applicable
```

## Migration from v3.x

If you were using local Fernet encryption in v3.x, you need to migrate to the new server-side encryption:

### Before (v3.x)

```python
# Required ENCRYPTION_KEY environment variable
import os
os.environ["ENCRYPTION_KEY"] = "your-fernet-key"

client = MisoClient(config)

# Sync methods with single argument
encrypted = client.encrypt("secret")  # Returns base64 string
decrypted = client.decrypt(encrypted)
```

### After (v4.0.0+)

```python
# MISO_ENCRYPTION_KEY required in .env for encryption operations
client = MisoClient(config)
await client.initialize()

# Async methods with parameter_name
result = await client.encrypt("secret", "my-param")  # Returns EncryptResult
decrypted = await client.decrypt(result.value, "my-param")
```

### Migration Steps

1. Replace `ENCRYPTION_KEY` with `MISO_ENCRYPTION_KEY` (obtain from your environment administrator)
2. Update all `encrypt()` calls to be async and add `parameter_name`
3. Update all `decrypt()` calls to be async and add `parameter_name`
4. Update code to handle `EncryptResult` object instead of string
5. Add error handling for `EncryptionError`

**Note:** Existing encrypted values using local Fernet encryption are NOT compatible with the new server-side encryption. You'll need to decrypt existing values with the old method and re-encrypt them with the new method during migration.
