---
name: Fix and Improve Core Code
overview: New unified snapshot of all unfinished core-code fixes for services/utils/models and exports.
todos:
  - id: split-auth-service-file
    content: Refactor miso_client/services/auth.py (592 lines) to <= 500 lines without API regressions
    status: completed
  - id: split-http-client-file
    content: Refactor miso_client/utils/http_client.py (508 lines) to <= 500 lines while preserving auth/logging behavior
    status: completed
  - id: reduce-method-size-critical-utils
    content: Break down utility methods over 30 lines in critical modules (token/filter/http/logging paths)
    status: completed
  - id: reduce-method-size-services
    content: Break down service methods over 30 lines in auth/application/encryption/permission areas
    status: completed
  - id: validate-after-refactor
    content: Run ruff, mypy, and targeted/full pytest after each refactor chunk
    status: completed
isProject: false
---

# Fix and Improve Code - New Unified Plan

## Scope

This plan is a **new snapshot** and includes all currently unfinished fixes for:

- `miso_client/services/`
- `miso_client/utils/`
- `miso_client/models/`
- `miso_client/__init__.py`

Validation basis: `.cursorrules` and `.cursor/rules/project-rules.mdc`.

## Unfinished Fix Inventory

### A) File Size Violations (Must Fix First)

1. `miso_client/services/auth.py` - 592 lines (>500)
2. `miso_client/utils/http_client.py` - 508 lines (>500)

### B) Method Size Violations (High Priority)

Representative unresolved methods over 30 lines that should be decomposed:

- `miso_client/utils/filter_applier.py`: `apply_filters`
- `miso_client/utils/client_token_manager.py`: `fetch_client_token`
- `miso_client/utils/origin_validator.py`: `validate_origin`
- `miso_client/utils/environment_token.py`: `get_environment_token`
- `miso_client/utils/token_utils.py`: `extract_client_token_info`
- `miso_client/utils/http_client_logging.py`: `log_http_request_audit`, `log_http_request_debug`
- `miso_client/utils/filter_parser.py`: `parse_filter_params`
- `miso_client/utils/filter.py`: `build_query_string`, `query_string_to_json_filter`, `validate_json_filter`
- `miso_client/utils/filter_schema.py`: `validate_filter`, `compile_filter`, `create_filter_schema`
- `miso_client/utils/user_token_refresh.py`: `_refresh_token`
- `miso_client/utils/audit_log_queue.py`: `flush`
- `miso_client/utils/pagination.py`: `parse_pagination_params`
- `miso_client/utils/sort.py`: `parse_sort_params`
- `miso_client/utils/http_client.py`: `authenticated_request`
- `miso_client/utils/internal_http_client.py`: `_create_error_from_http_status`, `post`, `put`
- `miso_client/services/auth.py`: `exchange_token`
- `miso_client/services/application_context.py`: `get_application_context_sync`, `get_application_context`, `_build_context_with_overwrites`
- `miso_client/services/encryption.py`: `encrypt`, `decrypt`
- `miso_client/services/permission.py`: `get_permissions`

## Execution Plan

### Step 1 - Split Oversized Files

1. Extract private helper units from `auth.py`:
  - token exchange/validation branches
  - repeated response normalization/error handling
2. Extract private helper units from `http_client.py`:
  - request parameter preparation
  - response conversion/error normalization
  - duplicated auth/request option handling

**Acceptance criteria:**

- both files `<= 500` lines,
- public API signatures unchanged,
- behavior-compatible with existing tests.

### Step 2 - Reduce Method Size in Core Hot Paths

Refactor long methods into focused helpers while preserving behavior and naming conventions:

- prioritize auth/token/http/filter/logging paths first,
- keep snake_case in Python internals,
- keep camelCase only for API payloads/params.

### Step 3 - Safety and Compliance Review

- ensure no client credentials are exposed in logs,
- confirm error handling in services still returns `[]`/`None` defaults,
- keep `x-client-token` and `Authorization` behavior unchanged.

### Step 4 - Validation Sequence

Run after each major refactor chunk:

1. `python -m ruff check <changed-files>`
2. `python -m mypy <changed-files-or-packages>`
3. `python -m pytest tests/unit/test_auth.py tests/unit/test_http_client.py tests/unit/test_internal_http_client.py`
4. Full unit test run when all refactors complete

## Definition of Done

- No core files exceed 500 lines (`services/utils/models/__init_`_ scope).
- Refactored long methods are decomposed with clear single responsibility.
- Lint and type checks pass for changed code.
- Relevant tests pass with no regressions in auth/token/http/logging flows.
- No breaking API changes unless explicitly approved.

## Execution Progress

- Completed:
  - `miso_client/services/auth.py` reduced to 477 lines
  - `miso_client/utils/http_client.py` reduced to 465 lines
  - `miso_client/services/application_context.py` method decomposition
  - `miso_client/services/encryption.py` method decomposition helpers
  - `miso_client/services/permission.py` method decomposition helpers
  - `miso_client/utils/filter.py` + `filter_parser.py` + `filter_schema.py` method decomposition pass
  - `miso_client/utils/http_client_logging.py` + `http_client_logging_helpers.py` method decomposition pass
  - `miso_client/utils/token_utils.py` + `environment_token.py` + `client_token_manager.py` method decomposition pass
  - `miso_client/utils/filter_applier.py` `apply_filters()` decomposition
  - `miso_client/utils/flask_endpoints.py` + `fastapi_endpoints.py` method decomposition pass
  - `miso_client/utils/flask_logger_middleware.py` + `fastapi_logger_middleware.py` method decomposition pass
  - `miso_client/utils/request_context.py` method decomposition pass
  - `miso_client/utils/origin_validator.py` method decomposition pass
  - `miso_client/utils/pagination.py` + `sort.py` method decomposition pass
  - `miso_client/utils/user_token_refresh.py` method decomposition pass
  - `miso_client/utils/audit_log_queue.py` method decomposition pass
  - `miso_client/utils/logger_request_helpers.py` method decomposition pass
  - `miso_client/utils/logger_helpers.py` method decomposition pass
  - `miso_client/utils/log_request_transformer.py` method decomposition pass
  - `miso_client/utils/url_validator.py` method decomposition pass
  - `miso_client/utils/internal_http_client.py` + `http_client_auth_helpers.py` + `controller_url_resolver.py` method decomposition pass
  - `miso_client/utils/jwt_tools.py` + `error_utils.py` + `http_error_handler.py` decomposition pass
  - `miso_client/services/logger_chain.py` + `utils/http_log_formatter.py` + `logging_helpers.py` + `auth_strategy.py` decomposition pass
  - `miso_client/utils/http_client.py` + `auth_utils.py` + `http_log_masker.py` decomposition pass
  - `miso_client/services/role.py` decomposition pass
  - `miso_client/utils/sensitive_fields_loader.py` + `data_masker.py` decomposition pass
  - `miso_client/services/redis.py` + `permission.py` + `encryption.py` decomposition pass
  - `miso_client/utils/filter_coercion.py` + `http_client_runtime_helpers.py` decomposition pass
  - `miso_client/services/auth.py` + `cache.py` + `application_context.py` decomposition pass
  - `miso_client/services/logger.py` + `unified_logger.py` + `utils/unified_logger_factory.py` decomposition pass
  - `miso_client/utils/http_client_logging.py` + `http_client_logging_helpers.py` final decomposition pass
- Validation executed on changed modules:
  - `ruff` passed (virtualenv)
  - `mypy` passed (virtualenv)
  - `pytest` passed for:
    - `tests/unit/test_auth_service_caching.py`
    - `tests/unit/test_http_client.py`
    - `tests/unit/test_http_client_filters.py`
    - `tests/unit/test_application_context.py`
    - `tests/unit/test_encryption_service.py`
    - `tests/unit/test_miso_client.py`
    - `tests/unit/test_filter.py`
    - `tests/unit/test_filter_schema.py`
    - `tests/unit/test_http_client_logging_helpers.py`
    - `tests/unit/test_token_utils.py`
    - `tests/unit/test_environment_token.py`
    - `tests/unit/test_user_token_refresh.py`
    - targeted regression set:
      - `tests/unit/test_http_client.py`
      - `tests/unit/test_http_error_handler.py`
      - `tests/unit/test_pagination.py`
    - full suite:
      - `1353 passed`
  - Current phase environment note:
    - global interpreter has no `pytest`/`ruff`/`mypy`; validation was executed using repo virtualenv:
      - `venv/bin/python -m ruff check miso_client`
      - `venv/bin/python -m mypy miso_client`
      - `venv/bin/python -m pytest`
    - Full package syntax verification also completed with `python -m compileall miso_client`.
- Current inventory snapshot:
  - Remaining methods > 30 lines in core scope: **0**

