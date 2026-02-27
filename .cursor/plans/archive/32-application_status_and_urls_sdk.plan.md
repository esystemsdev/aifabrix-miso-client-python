---
name: Application Status and URLs SDK
overview: Add server-side SDK support in miso-client-python for (1) updating the current application's status and URLs via POST self/status, and (2) fetching any application's status/URLs via GET application status, aligned with the TypeScript SDK implementation and miso-controller plan 138.
todos: []
isProject: false
---

# Application Status and URLs SDK - Python Plan

## Context

The [miso-controller plan 138](file:///workspace/aifabrix-miso/.cursor/plans/done/138-urls_keycloak_config_and_api.plan.md) defines two server-side APIs:

1. **POST self/status** - Update *own* application: status and optional `url`, `internalUrl`, `port`. Path: `POST /api/v1/environments/{envKey}/applications/self/status`. Auth: pipeline/client credentials (x-client-token).
2. **GET application status** - Return any application's metadata (id, key, displayName, url, internalUrl, port, status, runtimeStatus, etc.) **without** `configuration`. Path: `GET /api/v1/environments/{envKey}/applications/{appKey}/status`. Same auth (client credentials or bearer).

This plan adds the corresponding server-side interfaces in the **miso-client-python** SDK, mirroring the TypeScript implementation in [plan 49](file:///workspace/aifabrix-miso-client/.cursor/plans/49-application_status_and_urls_sdk.plan.md).

## Prerequisites

- Controller endpoints from plan 138 are implemented. TypeScript SDK uses `/api/v1/` for both endpoints.

## Rules and Standards

This plan must comply with [Project Rules](.cursorrules) and [project-rules.mdc](.cursor/rules/project-rules.mdc):

- **API Layer Pattern** - New `ApplicationsApi` with endpoint constants, `HttpClient` injection; use `post()`/`get()` for client credentials only, `authenticated_request()` or `request_with_auth_strategy()` when auth provided
- **Architecture Patterns** - Service layer; use `http_client.config`; dependency injection
- **API Data Conventions** - All Pydantic model fields use camelCase (e.g., `displayName`, `internalUrl`, `runtimeStatus`)
- **Code Style** - snake_case for Python; `Optional`, type hints; Google-style docstrings
- **Error Handling** - Services return empty list `[]` or `None` on errors; catch and log, don't propagate
- **Testing** - pytest, mock HttpClient; mirror `tests/unit/test_*_api.py`; ≥80% coverage

## Before Development

- Review [applications.api.ts](file:///workspace/aifabrix-miso-client/src/api/applications.api.ts) and [applications.types.ts](file:///workspace/aifabrix-miso-client/src/api/types/applications.types.ts) for TypeScript implementation
- Review [logs_api.py](miso_client/api/logs_api.py) for API layer pattern (POST with/without token, auth_strategy)
- Review [RoleService](miso_client/services/role.py) and [PermissionService](miso_client/services/permission.py) for ApplicationContextService usage (context for envKey/appKey)
- Review [application_context.py](miso_client/services/application_context.py) for `get_application_context_sync()` and `environment`/`application` fields

## 1. Types

**New file:** [miso_client/api/types/applications_types.py](miso_client/api/types/applications_types.py)

- **UpdateSelfStatusRequest** (Pydantic): optional `status` (str), `url` (str), `internalUrl` (str), `port` (int 1-65535). All fields optional; at least one typically sent. Use camelCase for API serialization.
- **UpdateSelfStatusResponse** (Pydantic): optional `success` (bool), `application` (ApplicationStatusResponse), `message` (str). camelCase.
- **ApplicationStatusResponse** (Pydantic): application without `configuration`. Fields: `id`, `key`, `displayName`, `url`, `internalUrl`, `port`, `status`, `runtimeStatus`, `environmentId`, `createdAt`, `updatedAt` (all optional). camelCase.

Follow pattern from [logs_types.py](miso_client/api/types/logs_types.py) - use `Field(..., description="...")` for optional fields.

## 2. API Layer

**New file:** [miso_client/api/applications_api.py](miso_client/api/applications_api.py)

- **ApplicationsApi** class (constructor: `HttpClient`)
- Endpoint constants (align with TypeScript):
  - `SELF_STATUS_ENDPOINT = "/api/v1/environments/{env_key}/applications/self/status"`
  - `APPLICATION_STATUS_ENDPOINT = "/api/v1/environments/{env_key}/applications/{app_key}/status"`
- **update_self_status(env_key, body, auth_strategy=None)**
  - `POST` to endpoint with `body` (UpdateSelfStatusRequest). Use `http_client.post()` when no auth_strategy (client credentials only). Use `http_client.authenticated_request()` when auth_strategy has bearer token; use `http_client.request_with_auth_strategy()` for other auth strategies.
- **get_application_status(env_key, app_key, auth_strategy=None)**
  - `GET` to endpoint. Same auth pattern.
- Build URL by replacing `{env_key}` / `{app_key}` in path template.
- Use `normalize_api_response()` from [response_utils.py](miso_client/api/response_utils.py) and return typed Pydantic models.

**Wire into ApiClient:** [miso_client/api/**init**.py](miso_client/api/__init__.py)

- Import `ApplicationsApi`
- Add `self.applications = ApplicationsApi(http_client)` in constructor
- Add `ApplicationsApi` to `__all__`

## 3. Application Context for "Own" App

- **update_my_application_status** should resolve `env_key` when caller does not pass it: use `ApplicationContextService.get_application_context_sync()` (same pattern as RoleService, PermissionService). Returns `environment` (envKey) and `application` (appKey).
- MisoClient must have access to ApplicationContextService. Currently RoleService and PermissionService create it via `_get_app_context_service()` which uses `InternalHttpClient`. For ApplicationsApi, we need envKey/appKey - either:
  - Add ApplicationContextService to MisoClient (if not already present) and pass to a thin wrapper, or
  - Create ApplicationContextService from `_internal_http_client` inside MisoClient methods (minimal change).
- **Recommended**: Use the same pattern as RoleService - create `ApplicationContextService` from `InternalHttpClient`. MisoClient already has `_internal_http_client`. Add `ApplicationContextService` instance or use lazy-initialization in `update_my_application_status` when `env_key` is omitted.

## 4. Public API on MisoClient

**In [miso_client/client.py](miso_client/client.py):**

- **update_my_application_status(body, env_key=None, auth_strategy=None)**
  - Body: `UpdateSelfStatusRequest`. If `env_key` omitted, use `ApplicationContextService.get_application_context_sync().environment` (return None or raise clear error if context missing).
  - Delegates to `api_client.applications.update_self_status(env_key, body, auth_strategy)`.
- **get_application_status(env_key, app_key, auth_strategy=None)**
  - Gets status/URLs for any application. Delegates to `api_client.applications.get_application_status(env_key, app_key, auth_strategy)`.
- **Optional overload**: `get_application_status(env_key=None, app_key=None, auth_strategy=None)` - when both omitted, use context for "current" app (`env_key=context.environment`, `app_key=context.application`).

Implementation: thin wrapper in MisoClient that reads context and calls `api_client.applications.*`. No need for separate ApplicationStatusService given only two methods.

## 5. Exports and Docs

- Export new types from [miso_client/**init**.py](miso_client/__init__.py): `UpdateSelfStatusRequest`, `UpdateSelfStatusResponse`, `ApplicationStatusResponse`
- Add to `__all__`
- Optional: short note in [docs/](docs/) (e.g., configuration or getting-started) for server-side URL/status self-service

## 6. Tests

- **Unit tests** for `ApplicationsApi`: [tests/unit/test_applications_api.py](tests/unit/test_applications_api.py) - mock `HttpClient`; assert correct method, path (with `:envKey`/`:appKey` replaced), and body for `update_self_status`; assert GET path for `get_application_status`; test with and without `auth_strategy` (similar to [test_logs_api.py](tests/unit/test_logs_api.py)).
- **Unit tests** for MisoClient: mock `ApiClient` and ApplicationContextService; assert `update_my_application_status` uses context when `env_key` not provided; assert `get_application_status(env_key, app_key)` forwards to API.

## 7. Auth Pattern Summary


| Scenario                                   | Python HTTP Client Method                                            |
| ------------------------------------------ | -------------------------------------------------------------------- |
| Client credentials only (no auth_strategy) | `http_client.post()` / `http_client.get()`                           |
| Bearer token in auth_strategy              | `http_client.authenticated_request(..., auth_strategy.bearer_token)` |
| Other auth_strategy (api-key, etc.)        | `http_client.request_with_auth_strategy(...)`                        |


## Files to Add or Modify


| Area                                                                                       | Action                                                                                                                   |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| [miso_client/api/types/applications_types.py](miso_client/api/types/applications_types.py) | New - Pydantic models (UpdateSelfStatusRequest, UpdateSelfStatusResponse, ApplicationStatusResponse)                     |
| [miso_client/api/types/**init**.py](miso_client/api/types/__init__.py)                     | Export new types if needed                                                                                               |
| [miso_client/api/applications_api.py](miso_client/api/applications_api.py)                 | New - ApplicationsApi with update_self_status, get_application_status                                                    |
| [miso_client/api/**init**.py](miso_client/api/__init__.py)                                 | Register ApplicationsApi on ApiClient                                                                                    |
| [miso_client/client.py](miso_client/client.py)                                             | Add update_my_application_status, get_application_status; use ApplicationContextService for default env_key when omitted |
| [miso_client/**init**.py](miso_client/__init__.py)                                         | Export new types                                                                                                         |
| [tests/unit/test_applications_api.py](tests/unit/test_applications_api.py)                 | New - ApplicationsApi unit tests                                                                                         |
| [tests/unit/test_miso_client.py](tests/unit/test_miso_client.py)                           | Add tests for update_my_application_status, get_application_status                                                       |
| [docs/](docs/)                                                                             | Optional short documentation                                                                                             |


## Definition of Done

- **Lint**: Run `ruff check` (must pass with zero errors/warnings)
- **Type Check**: Run `mypy` (must pass)
- **Test**: Run `pytest` (all tests pass; ≥80% coverage for new code)
- **Validation order**: LINT → TYPE CHECK → TEST (mandatory sequence)
- **File size**: Files ≤500 lines; methods ≤20-30 lines
- **Docstrings**: All public methods have Google-style docstrings
- Types and API layer implemented; ApplicationsApi registered in ApiClient
- MisoClient exposes update_my_application_status and get_application_status; env_key from context when omitted
- All public request/response use camelCase; JSDoc/docstrings present
- Unit tests added; existing tests and lint pass

## Out of Scope

- Controller implementation (plan 138)
- Browser/Data Client support for these endpoints
- Caching of application status in the SDK

## Validation

**Date**: 2026-02-09
**Status**: ✅ COMPLETE

### Executive Summary

Plan 32 (Application Status and URLs SDK) has been fully implemented and validated. All required files exist, ApplicationsApi and MisoClient methods are in place, types are exported, and unit tests pass. Code quality (format, lint, type-check) passes. One fix was applied during validation: the applications types import in miso_client/**init**.py was moved to after HttpClient and utils imports to resolve a circular import.

### File Existence Validation

- ✅ miso_client/api/types/applications_types.py - Exists
- ✅ miso_client/api/types/**init**.py - Exports new types
- ✅ miso_client/api/applications_api.py - ApplicationsApi, update_self_status, get_application_status
- ✅ miso_client/api/**init**.py - ApplicationsApi registered on ApiClient
- ✅ miso_client/client.py - update_my_application_status, get_application_status, _get_app_context_service
- ✅ miso_client/**init**.py - Exports new types
- ✅ tests/unit/test_applications_api.py - 7 tests
- ✅ tests/unit/test_miso_client.py - TestMisoClientApplicationStatus (6 tests)

### Test Coverage

- ✅ Unit tests for ApplicationsApi - 7 tests, mock HttpClient
- ✅ Unit tests for MisoClient application status - 6 tests
- ✅ Full unit suite: 1270 passed

### Code Quality Validation

**STEP 1 - FORMAT**: ✅ PASSED
**STEP 2 - LINT**: ✅ PASSED (0 errors, 0 warnings)
**STEP 3 - TYPE CHECK**: ✅ PASSED
**STEP 4 - TEST**: ✅ PASSED (1270 tests)

### Cursor Rules Compliance

- ✅ API layer pattern, camelCase, type hints, async, HttpClient usage, file size

### Implementation Completeness

- ✅ Types, API layer, ApiClient, MisoClient, context resolution, exports

### Final Validation Checklist

- All plan tasks completed
- All files exist
- Tests exist and pass
- Code quality validation passes
- Implementation complete

**Result**: ✅ **VALIDATION PASSED**