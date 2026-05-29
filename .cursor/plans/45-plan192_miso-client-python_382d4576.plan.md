---
name: Plan192 miso-client-python
overview: "Execution-ready plan for the miso-client-python scope from plan 192: define explicit auth-boundary behavior per endpoint, preserve device refresh compatibility, and ship test + docs evidence for migration safety."
todos:
  - id: verify-rules-before-dev
    content: Confirm all applicable sections from project-rules.mdc are reviewed before implementation starts.
    status: completed
  - id: freeze-plan192-python-mapping
    content: Lock exact plan 192 scope mapping for Python SDK, including explicit N/A browser-only items.
    status: completed
  - id: lock-cross-sdk-contract-parity
    content: Lock shared exposed contract parity with miso-client for common auth endpoints, payload fields, and boundary rules.
    status: completed
  - id: align-refresh-contract-surface
    content: Refactor Python SDK refresh API/service surfaces to match plan 192 contract boundaries where impacted.
    status: completed
  - id: preserve-device-refresh-contract
    content: Keep /api/v1/auth/login/device/refresh request-body refreshToken contract unchanged and guarded by tests.
    status: completed
  - id: enforce-auth-path-separation
    content: Ensure user, M2M/client-token, and device auth flows remain explicitly separated in code paths.
    status: completed
  - id: update-python-tests
    content: Implement/update unit and integration tests for new contract boundaries and non-regression behavior.
    status: completed
  - id: update-python-docs
    content: Update README/CHANGELOG/examples for behavior and migration notes.
    status: completed
  - id: publish-compatibility-matrix
    content: Publish an endpoint-method compatibility matrix that distinguishes browser-session vs device vs M2M behaviors for Python SDK users.
    status: completed
  - id: add-manual-smoke-checklist
    content: Add and execute a manual smoke checklist that covers happy path, negative paths, boundary conditions, config variants, integration contracts, and regressions.
    status: in_progress
  - id: run-python-validation-gates
    content: Run pytest, formatting/lint/type checks in required order and confirm pass.
    status: in_progress
  - id: final-dod-verification
    content: Verify Definition of Done checklist and task state sync before closure.
    status: pending
isProject: false
---

# Plan192 Miso-Client-Python Auth Contract Alignment

## Goal
Implement the `miso-client-python` portion of [192 unified token providers](/workspace/aifabrix-miso/.cursor/plans/192-unified-token-providers.plan.md) in a standalone, executable SDK plan.

## Source Scope (From Plan 192)
From `Cross-Project Follow-up` in plan 192, this repo must:
- assess actual impact for Python SDK (server-side usage);
- verify device refresh and service-to-service contracts remain compatible with controller hard cut;
- update documentation if behavior/contract usage changes.

## Rules and Standards
This plan must follow [project rules](.cursor/rules/project-rules.mdc) with emphasis on the sections below:

- **[Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns)** - Applies because this plan changes auth API/service contract boundaries and flow separation behavior.
- **[Code Style](.cursor/rules/project-rules.mdc#code-style)** - Applies because auth/service refactors must preserve type hints, async/await, and RFC 7807-aligned error handling conventions.
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - Applies because this plan requires unit + integration non-regression coverage for refresh/device/M2M paths.
- **[Common Patterns](.cursor/rules/project-rules.mdc#common-patterns)** - Applies because refresh behavior touches service method, error handling, and token refresh helper patterns.
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - Applies because auth token handling must preserve ISO 27001-safe logging and avoid leaking credentials/secrets.
- **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** - Mandatory for all plans; refactors must keep file/method size within project limits.
- **[Documentation](.cursor/rules/project-rules.mdc#documentation)** - Applies because public auth contract behavior and migration notes change.

### Key Requirements
- Keep auth flows explicitly separated (user/session, device refresh, and client-token/M2M).
- Use type hints on all functions and Google-style docstrings for public APIs affected by the change.
- Keep API payload conventions camelCase on wire contracts and snake_case in Python code.
- Enforce robust try-except behavior and structured error handling without exposing internal details.
- Maintain file size and method size limits (`<=500` lines per source file and `<=20-30` lines per method where feasible).
- Ensure tests cover success, error, cache/refresh fallback, and contract compatibility paths.

## Before Development
- [x] Re-read [project-rules.mdc](.cursor/rules/project-rules.mdc) sections listed in this plan.
- [x] Confirm baseline behavior in current auth refresh/device/M2M code paths and list impacted symbols.
- [x] Confirm which browser-oriented requirements are N/A for Python SDK and document rationale.
- [x] Confirm documentation touchpoints (`README.md`, `CHANGELOG.md`, auth usage examples) before code edits.
- [x] Prepare unit + integration test updates for all changed contract boundaries before implementation.
- [x] Confirm validation command flow and log locations (`make *-silent`, `.temp/validation/`).

## Cross-SDK Contract Parity (Python + TypeScript)

The following exposed contracts must match `miso-client` for equivalent controller APIs:

- **Browser session restore/refresh boundary**
  - Shared browser-oriented contract is cookie-first `/api/v1/auth/session` + `/api/v1/auth/refresh`.
  - Browser refresh contract does not require frontend `refreshToken` JSON payload.
  - Python SDK marks activity-listener/browser-runtime mechanics as N/A (implementation-language specific), but preserves API boundary consistency.
- **Device refresh boundary**
  - `/api/v1/auth/login/device/refresh` keeps request-body `refreshToken` contract.
  - Device refresh may return rotated `refreshToken`; this behavior remains aligned with TypeScript SDK.
- **M2M vs user auth separation**
  - `x-client-token` flow remains separate from user bearer/session flow.
  - No contract blending between client-token APIs and browser session APIs.
- **Shared payload contract expectations**
  - Common auth response fields remain compatible (`accessToken`, `expiresIn`, optional metadata).
  - API-facing field naming remains camelCase for wire contracts.
- **Error/behavior semantics**
  - Expired/invalid session behavior is explicit and non-ambiguous.
  - Device refresh failure semantics remain documented and tested.

## Scope Decision (Needed vs Not Needed)
This plan is **needed** because current Python SDK auth flow still models `/api/v1/auth/refresh` with request-body `refreshToken` in:
- [auth_api.py](/workspace/aifabrix-miso-client-python/miso_client/api/auth_api.py)
- [auth_flow_helpers.py](/workspace/aifabrix-miso-client-python/miso_client/services/auth_flow_helpers.py)
- [auth.py](/workspace/aifabrix-miso-client-python/miso_client/services/auth.py)
- [user_token_refresh.py](/workspace/aifabrix-miso-client-python/miso_client/utils/user_token_refresh.py)

Plan 192 hard-cut introduces cookie-first browser refresh semantics and strict browser/device separation, so Python SDK contract boundaries must be explicitly aligned and documented.

## Scope
### In scope
- Align Python SDK auth API/service behavior with plan 192 contract boundaries.
- Preserve and verify unchanged device refresh flow:
  - `/api/v1/auth/login/device/refresh` with request-body `refreshToken`.
- Remove or redesign assumptions that browser `/auth/refresh` always accepts body `refreshToken` for SDK paths that must follow plan 192 semantics.
- Keep M2M/client-token and delegated-token flows stable.
- Update tests and docs/changelog for any changed behavior.

### Out of scope
- Backend implementation changes in `miso-controller`.
- Frontend/browser listener implementation (`miso-client` TypeScript scope).
- `miso-ui` / `dataplane` application code changes.
- Infra/container/deployment operations.

## Current Baseline (Verified)
- Python Auth API defines:
  - `/api/v1/auth/refresh`
  - `/api/v1/auth/login/device/refresh`
  in [auth_api.py](/workspace/aifabrix-miso-client-python/miso_client/api/auth_api.py).
- `refresh_token()` currently sends `RefreshTokenRequest(refreshToken=...)` to `/api/v1/auth/refresh` in [auth_api.py](/workspace/aifabrix-miso-client-python/miso_client/api/auth_api.py).
- Service helper fallback calls `/api/v1/auth/refresh` with JSON body containing `refreshToken` in [auth_flow_helpers.py](/workspace/aifabrix-miso-client-python/miso_client/services/auth_flow_helpers.py).
- Internal refresh manager stores per-user refresh tokens and attempts refresh-token-based renewal in [user_token_refresh.py](/workspace/aifabrix-miso-client-python/miso_client/utils/user_token_refresh.py).

## Contract Targets
1. **Browser session contract boundary**
   - Treat browser cookie-first `/auth/session` + `/auth/refresh` behavior as non-primary for server-side Python SDK unless explicit server-mediated session contract is added.
   - Avoid forcing browser-style cookie assumptions into server-side token-refresh paths without explicit opt-in API.

2. **Device refresh contract**
   - Keep `/api/v1/auth/login/device/refresh` request-body `refreshToken` behavior unchanged and explicitly validated.

3. **Auth-path separation**
   - Keep user bearer/delegated flows, client-token/M2M flows, and device flow clearly separated in API/service contracts.

4. **Compatibility visibility**
   - Expose a concise matrix in docs that shows, for each relevant endpoint, whether Python SDK uses body tokens, cookie/session semantics, or client-token headers.
   - Make unsupported/Not Applicable behavior explicit instead of implicit.

## Implementation Plan
1. **Freeze plan 192 mapping for Python SDK**
   - Document exact affected endpoints and methods in auth API/service layers.
   - Mark which plan 192 browser-only requirements are N/A for Python SDK and why.

2. **Refactor refresh contract surfaces where required**
   - Review and adjust `refresh_token()` and helper flows so Python SDK does not implicitly depend on deprecated browser refresh-token request-body semantics where incompatible with plan 192.
   - Introduce explicit path handling to prevent accidental cross-use of browser and device contracts.

3. **Preserve device refresh behavior**
   - Keep request/response contract for `/api/v1/auth/login/device/refresh` intact.
   - Ensure no side effects from browser/session contract alignment work.

4. **Harden auth separation and caching semantics**
   - Verify user-token refresh manager and auth service do not blend browser session assumptions with device or M2M flows.
   - Keep token exchange and client-token validation behavior unchanged unless required by controller contract updates.

5. **Update tests and docs**
   - Add/update unit and integration tests for refreshed contract boundaries and non-regression behavior.
   - Update [README.md](/workspace/aifabrix-miso-client-python/README.md) and [CHANGELOG.md](/workspace/aifabrix-miso-client-python/CHANGELOG.md) for contract changes and migration notes.
   - Add explicit cross-SDK parity notes for teams using both SDK languages.
   - Add endpoint compatibility matrix and migration examples for old refresh-token-body assumptions.

## Expected Automated Tests
### Unit
- `AuthApi.refresh_token` behavior aligned with updated contract expectations.
- `AuthApi.refresh_device_code_token` remains unchanged (request-body `refreshToken`).
- `auth_flow_helpers.refresh_user_access_token` respects auth-path separation.
- `UserTokenRefreshManager` does not rely on invalid browser refresh assumptions.

### Integration
- `/api/v1/auth/refresh` compatibility behavior (as applicable to Python SDK usage) is explicit and tested.
- `/api/v1/auth/login/device/refresh` non-regression tests remain passing.
- Client-token validation and delegated token exchange remain unaffected.
- Contract parity checks for shared endpoints against TypeScript SDK expectations (documented assertions).

## Documentation Updates
- [README.md](/workspace/aifabrix-miso-client-python/README.md)
- [CHANGELOG.md](/workspace/aifabrix-miso-client-python/CHANGELOG.md)
- Any auth API usage examples affected by contract changes.
- Endpoint compatibility matrix (browser session vs device refresh vs M2M/client-token behavior).

## Manual Testing
Manual verification is executed locally against a reachable controller environment after implementation and automated checks, with results captured as pass/fail evidence for each case.

- [ ] **Happy path / baseline:** Execute primary user-token refresh flow used by Python SDK and confirm access token renewal succeeds with expected response fields.
- [ ] **Negative/error path:** Send invalid or expired refresh context and confirm structured failure behavior is returned and documented (no ambiguous fallback).
- [ ] **Boundary/edge condition:** Validate handling for empty/missing optional auth metadata and unusual-but-valid token payload combinations without contract drift.
- [ ] **Configuration variant:** Verify behavior under at least two auth configuration modes relevant to SDK usage (for example explicit user token vs client-token-only path) and confirm path separation is preserved.
- [ ] **Integration/contract check:** Confirm request/response shape and required headers/parameters for `/api/v1/auth/refresh` and `/api/v1/auth/login/device/refresh` match documented SDK contracts.
- [ ] **Regression check:** Re-run previously passing auth scenarios adjacent to refresh changes (device refresh and M2M/client-token flows) and confirm no unintended behavior change.

## Definition of Done
- Python SDK auth contract boundaries are explicitly aligned with plan 192.
- Device refresh flow remains unchanged and covered by non-regression tests.
- User/M2M/device auth-path separation is enforced in code and tests.
- Cross-SDK parity checklist is satisfied for shared exposed auth contracts with `miso-client`.
- Docs/changelog are updated to reflect final behavior and migration impact.
- Endpoint compatibility matrix is published and consistent with implementation.
- Manual testing checklist is fully completed with recorded outcomes.
- Format runs first with `make format-silent` (fallback: `make format`) and passes.
- Lint runs after format with `make lint-silent` (fallback: `make lint`) and passes with zero errors/warnings.
- Type check runs after lint with `make type-check-silent` (fallback: `make type-check`) and passes.
- Tests run after type-check with `make test-silent` (fallback: `make test`) and pass; new code maintains >=80% coverage.
- Mandatory validation order `FORMAT -> LINT -> TYPE CHECK -> TEST` is followed with no skipped steps.
- File size and method size rules are satisfied (`<=500` lines per file, `<=20-30` lines per method guideline).
- All changed functions include type hints.
- All affected public methods include Google-style docstrings.
- Security constraints are preserved (no hardcoded secrets, ISO 27001-safe logging/masking).
- Markdown checklists and frontmatter `todos` remain synchronized and accurately reflect status.
- All plan tasks are completed before closure.

## Validation
Run from `aifabrix-miso-client-python` root in this order:
1. `make format-silent` (fallback: `make format`)
2. `make lint-silent` (fallback: `make lint`)
3. `make type-check-silent` (fallback: `make type-check`)
4. `make test-silent` (fallback: `make test`)
5. If integration contract checks are required for endpoint behavior: `make test-integration-silent` (fallback: `make test-integration`)
6. Review logs in `.temp/validation/` and surface detailed output only for failing steps.

## Risks and Mitigations
- **Risk:** Over-applying browser cookie-first semantics to server-side SDK paths.
  - **Mitigation:** Explicitly mark browser-only requirements as N/A in Python SDK and enforce endpoint separation.
- **Risk:** Breaking device refresh while refactoring refresh paths.
  - **Mitigation:** Dedicated device refresh non-regression tests and explicit contract assertions.
- **Risk:** Hidden downstream usage of old refresh assumptions.
  - **Mitigation:** Changelog migration notes and focused integration tests for affected entry points.

## Plan Validation Report

**Date**: 2026-05-29 (today is 2026-05-29)
**Plan**: `/workspace/aifabrix-miso-client-python/.cursor/plans/45-plan192_miso-client-python_382d4576.plan.md`
**Status**: ✅ VALIDATED

### Plan Purpose

This plan aligns the Python SDK auth contract boundaries with plan 192 while keeping device refresh compatibility and explicit auth-path separation.  
Affected areas: auth API/service layers, token refresh helpers, tests, and public documentation.

### Applicable Rules

- ✅ [Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns) - Auth API/service boundary changes must follow service and HTTP client patterns.
- ✅ [Code Style](.cursor/rules/project-rules.mdc#code-style) - Type hints, async conventions, and structured error handling are required for touched code.
- ✅ [Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions) - Unit/integration coverage and mock strategy requirements apply to refresh-flow changes.
- ✅ [Common Patterns](.cursor/rules/project-rules.mdc#common-patterns) - Existing refresh/service/error patterns must be preserved or explicitly refactored.
- ✅ [Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines) - Token/credential handling and logging constraints are mandatory.
- ✅ [Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines) - File and method size limits must be enforced.
- ✅ [Documentation](.cursor/rules/project-rules.mdc#documentation) - Public usage and migration behavior updates are required.

### Rule Compliance

- ✅ DoD requirements: documented with mandatory `FORMAT -> LINT -> TYPE CHECK -> TEST` sequence.
- ✅ Quiet validation policy: documented via `make *-silent` commands and `.temp/validation/` logs.
- ✅ Security, type hints, docstrings, and size constraints: explicitly captured in DoD.
- ✅ Task-state synchronization requirement: explicitly captured in DoD.

### Plan Updates Made

- ✅ Added `Rules and Standards` section with applicable rule links and why each applies.
- ✅ Added `Before Development` checklist with rule/prerequisite gates.
- ✅ Strengthened `Definition of Done` with mandatory silent validation gates and quality requirements.
- ✅ Updated `Validation` section to quiet-first `make` commands with fallback and logging guidance.
- ✅ Added frontmatter todos for pre-dev rule verification and final DoD closure.
- ✅ Appended this validation report to the plan file.

### Recommendations

- Keep endpoint compatibility matrix authoritative and update it immediately if implementation scope changes.
- During execution, treat any behavior that blends device and browser/session contracts as a blocker and resolve before merge.
- If integration tests require environment prerequisites, capture prerequisite checks near the test task to keep execution deterministic.