# OpenAPI Spec Validation

The SDK is aligned with the **miso-controller** API spec:

**Spec path:** `aifabrix-miso/packages/miso-controller/openapi/openapi-complete.yaml`

## Auth endpoints (validated)

| Operation | Spec path | SDK |
|-----------|-----------|-----|
| Initiate device code | **POST** `/api/v1/auth/login` (body: optional `environment`, `scope`) | `AuthApi.initiate_device_code(environment=..., scope=...)` → POST `/api/v1/auth/login` |
| Poll device code token | POST `/api/v1/auth/login/device/token` (body: `deviceCode`) | `AuthApi.poll_device_code_token(device_code)` |
| Refresh device code token | POST `/api/v1/auth/login/device/refresh` (body: `refreshToken`) | `AuthApi.refresh_device_code_token(refresh_token)` |
| Refresh user token | POST `/api/v1/auth/refresh` (body: `refreshToken`) | `AuthApi.refresh_token(refresh_token)` |

Note: The spec does **not** define `/api/v1/auth/login/device` for initiation; it is **POST /api/v1/auth/login** only. Integration tests pass `environment` (env `MISO_ENVIRONMENT` or `TEST_ENVIRONMENT` or default `miso`).

## Logs export

- Spec: GET `/api/v1/logs/export` with security **oauth2, scope logs:export**.
- 401 with API_KEY is expected if the key does not have `logs:export`; use a JWT with that scope for export.
