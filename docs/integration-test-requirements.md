# Integration Test Requirements and Known Issues

This document summarizes what is required for `make test-integration` to pass and where problems may lie (SDK, tests, or miso-controller).

## Environment Variables

| Variable | Purpose | Required for |
|----------|---------|--------------|
| `MISO_CLIENTID`, `MISO_CLIENTSECRET`, `MISO_CONTROLLER_URL` | Controller auth | All tests |
| `MISO_ENCRYPTION_KEY` or `ENCRYPTION_KEY` | Encryption key (must match controller) | `test_encryption.py` |
| `TEST_USER_TOKEN` or `API_KEY` | User/auth token for protected endpoints | Most auth and logs tests |
| `TEST_REFRESH_TOKEN` or `REFRESH_TOKEN` or `MISO_REFRESH_TOKEN` or `TEST_REFRESH_TOKEN_FILE` | Refresh token for OAuth2 | `test_refresh_token` |
| `TEST_DEVICE_REFRESH_TOKEN` | Refresh token from device code flow | `test_refresh_device_code_token` |

Conftest loads `TEST_REFRESH_TOKEN` from `REFRESH_TOKEN` or `MISO_REFRESH_TOKEN` or from the file path in `TEST_REFRESH_TOKEN_FILE` if `TEST_REFRESH_TOKEN` is not set.

## SDK vs Controller Behavior

### 1. Device code flow (`test_initiate_device_code`, `test_poll_device_code_token`)

- **SDK:** Tries `POST /api/v1/auth/login/device` first; on 404, tries `POST /api/v1/auth/login` with body `{ environment?, scope?, grantType: "device_code" }`.
- **Observed:** 404 on `/api/v1/auth/login/device`; fallback to `POST /api/v1/auth/login` returns **400 Bad Request "Validation failed"**.
- **Conclusion:** Either:
  - **miso-controller** should implement `POST /api/v1/auth/login/device` for device code initiation (OpenAPI plan expected this path), or
  - **miso-controller** should accept `POST /api/v1/auth/login` for device code and document the exact request body (e.g. required fields, optional `grantType`).
- **Tests:** No skip; they fail with a clear message if the controller does not support the chosen contract.

### 2. Token refresh (`test_refresh_token`)

- **SDK:** `POST /api/v1/auth/refresh` with body `{ "refreshToken": "<token>" }` (client token in header).
- **Tests:** Fail if no refresh token is provided via env (see variables above). Set `REFRESH_TOKEN` or `TEST_REFRESH_TOKEN` (or file) so this test runs.

### 3. Get job log (`test_get_job_log`)

- **SDK:** `GET /api/v1/logs/jobs/{id}` after listing job logs.
- **Tests:** Fail if there are no job logs in the environment. Job logs are typically created by the system (e.g. jobs), not by `POST /api/v1/logs` (which only supports types `error`, `general`, `audit`).
- **Conclusion:** Environment or miso-controller must have at least one job log for this test to pass.

### 4. Export logs CSV (`test_export_logs_csv`)

- **SDK:** `GET /api/v1/logs/export?type=general&format=csv&limit=10` with Bearer token (user token or API_KEY).
- **Observed:** **401 Unauthorized** when using API_KEY as Bearer.
- **Conclusion:** Either:
  - **miso-controller** allows export with API_KEY (same as other log endpoints), or
  - Tests must use a JWT in `TEST_USER_TOKEN` for export. If export is restricted to JWT, document that and use a real user token for this test.

## Summary

| Failing test | Likely fix |
|--------------|------------|
| `test_refresh_token` | Set `REFRESH_TOKEN` or `TEST_REFRESH_TOKEN` (or file) in env. |
| `test_initiate_device_code` / `test_poll_device_code_token` | miso-controller: add `POST /api/v1/auth/login/device` or accept and document device code on `POST /api/v1/auth/login`. |
| `test_refresh_device_code_token` | Set `TEST_DEVICE_REFRESH_TOKEN` after completing device code flow once. |
| `test_get_job_log` | Ensure environment has job logs (or create via controller/jobs). |
| `test_export_logs_csv` | Use JWT in `TEST_USER_TOKEN` for export, or change controller to allow API_KEY for export. |

## Encryption integration tests (`tests/integration/test_encryption.py`)

- **Round-trip:** Encrypt then decrypt and assert plaintext matches; requires `MISO_ENCRYPTION_KEY` or `ENCRYPTION_KEY` in `.env` and the controller must be configured with the same key.
- **Skipped when:** No encryption key is set (tests skip so `make test-integration` passes without a key).
- **Note:** The test file loads `.env` with `override=True` so the project `.env` key is used instead of `tests/conftest.py`’s default.

## Refresh token from encrypted config.yaml

The refresh token may be stored encrypted in `.aifabrix/config.yaml` under `device.<controllerUrl>.refreshToken` (format `secure://...`). It is encrypted with the key in `secrets-encryption` in the same file. You can decrypt it using:

- **aifabrix-builder:** `/workspace/aifabrix-builder/lib/utils/secrets-encryption.js` (Node; AES-256-GCM).

Conftest will try to set `TEST_REFRESH_TOKEN` by:

1. Reading `.aifabrix/config.yaml` (from `AIFABRIX_HOME`, `/workspace/.aifabrix`, or `~/.aifabrix`).
2. Extracting `secrets-encryption` (hex key) and the first `refreshToken: 'secure://...'` value.
3. Calling the Node script above to decrypt (requires Node.js and the script path at `../aifabrix-builder` or `AIFABRIX_BUILDER_ROOT`).

If decryption fails (e.g. key/token mismatch or script not found), set the token manually:

- **Option A:** Run `python scripts/decrypt_refresh_token_from_config.py` and set `TEST_REFRESH_TOKEN` to its output (or `TEST_REFRESH_TOKEN_FILE` to a file containing that output).
- **Option B:** Set `REFRESH_TOKEN` or `TEST_REFRESH_TOKEN` (or `TEST_REFRESH_TOKEN_FILE`) in the environment.
