---
name: 44 sdk auth cutover
overview: Create a Python SDK hard-cutover plan that removes migration-phase token compatibility behavior, aligned with Dataplane 393.4 and TypeScript SDK plan 58, after validating current code/docs reality.
todos:
  - id: freeze-final-contract
    content: Define canonical final no-migration token storage contract and legacy-key policy for Python SDK.
    status: completed
  - id: remove-helper-api-surface
    content: Remove token storage helper API surface from implementation and public exports as an intentional hard breaking cutover.
    status: completed
  - id: preserve-manager-behavior
    content: Keep UserTokenRefreshManager refresh/retry behavior stable under final-only storage semantics.
    status: completed
  - id: update-tests-final-only
    content: Update unit tests for hard cutover: remove helper-API assertions and enforce final manager-only behavior with legacy-key negative cases.
    status: completed
  - id: expected-automated-tests-implementation
    content: Implement all automated tests listed in `## Expected Automated Tests` exactly as specified and verify they pass locally before final validation gates.
    status: completed
  - id: update-docs-and-changelog
    content: Revise README and CHANGELOG from migration compatibility language to final cutover contract.
    status: completed
  - id: create-consumer-migration-doc
    content: Create a migration-instruction document in project `.temp` for the SDK consumer project, describing required consumer-side changes after helper API removal.
    status: completed
  - id: run-validation-gates
    content: Run silent format/lint/type-check/test gates and collect evidence.
    status: completed
  - id: final-dod-closure
    content: Perform final Definition of Done closure check, ensuring all required plan phases and deliverables are complete and statuses are synchronized.
    status: completed
isProject: false
---

# 44 Final Auth Cutover (Python SDK, No Migration Phase)

## Goal
Ship final auth/token behavior in `aifabrix-miso-client-python` by removing migration-only compatibility semantics and fully removing token storage helper API surface as an intentional hard breaking cutover, while preserving core manager refresh/retry behavior and updating tests/docs/changelog accordingly.

## Source Alignment and Reality Check
- Consumer source plan: `/workspace/aifabrix-dataplane/.cursor/plans/393.4-final-auth-cutover-no-migration_3a35d9c5.plan.md`.
- Parallel SDK reference: `/workspace/aifabrix-miso-client/.cursor/plans/58-final-auth-cutover-ts-sdk_059e1351.plan.md`.
- Verified in current Python SDK:
  - Migration alias behavior is active in `/workspace/aifabrix-miso-client-python/miso_client/utils/user_token_refresh.py` (`ACCESS_TOKEN_KEYS`, `REFRESH_TOKEN_KEYS`, alias fan-out and alias lookup helpers).
  - Alias-driven behavior is asserted by tests in `/workspace/aifabrix-miso-client-python/tests/unit/test_user_token_refresh.py`.
  - Migration alias guidance is documented in `/workspace/aifabrix-miso-client-python/README.md`.
  - Release notes still describe compatibility-key semantics in `/workspace/aifabrix-miso-client-python/CHANGELOG.md`.

## Rules and Standards
This plan must comply with:

- **[Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns)** - preserve service/runtime behavior while removing migration-only helper surface.
- **[Code Style](.cursor/rules/project-rules.mdc#code-style)** - keep Python typing, naming, and error-handling standards in all touched code.
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - enforce deterministic pytest coverage for final-only behavior.
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - avoid token leakage and keep ISO-27001-safe behavior.
- **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** - maintain file/method size constraints in touched modules.
- **[Documentation](.cursor/rules/project-rules.mdc#documentation)** - keep README/CHANGELOG contract messaging accurate.
- **[Critical Rules](.cursor/rules/project-rules.mdc#critical-rules)** - apply required do/don't constraints consistently.
- **[Workspace Baseline Rules](.cursorrules)** - follow repository-level quality and implementation constraints.

Key requirements applied:

- Preserve safe error handling (`try/except`, `exc_info`, deterministic defaults).
- Keep manager behavior resilient after helper API removal.
- Treat this as explicit breaking change and document consumer impact clearly.
- Keep validation order strict: FORMAT -> LINT -> TYPE-CHECK -> TEST.

## Scope
### In scope
- Remove migration-phase alias compatibility from Python SDK token-lifecycle contract.
- Remove token storage helper API surface (`store_*`, `clear_*`, `get_stored_*`) from implementation and top-level exports.
- Keep final manager behavior for refresh flow and robust expiry handling.
- Update/replace tests to enforce hard-cutover semantics and remove helper-API dependencies.
- Update README and changelog to final cutover language, including explicit breaking-change notice.
- Create consumer-facing migration instruction doc under project `.temp` with concrete upgrade steps for post-cutover integration.

### Out of scope
- Changes in Dataplane repo or TypeScript SDK repo.
- Infrastructure/container work.
- Publishing workflow execution (separate release action).
- Direct code modifications in consumer repo (only migration instructions are produced here).

## Before Development
- [x] Re-read `.cursor/rules/project-rules.mdc` sections listed in `Rules and Standards`.
- [x] Re-read `.cursorrules` and confirm no conflict with this hard-cutover scope.
- [x] Confirm removed public symbols list (see `Removal Inventory`) before edits.
- [x] Confirm consumer update ownership and expected immediate cutover window.
- [x] Confirm docs targets: `README.md`, `CHANGELOG.md`.
- [x] Confirm test targets: `tests/unit/test_user_token_refresh.py`.

## Final Contract Target (derived from TS SDK plan 58)
- Remove token storage helper API surface from public SDK contract.
- Remove migration alias fan-out, fallback lookup, and compatibility cleanup semantics.
- Keep only final contract behavior needed by manager/runtime (refresh/retry orchestration + expiry computations).
- Treat legacy alias keys as fully unsupported after cutover.

## Removal Inventory (Public Surface)
The following exported helper API is intended to be removed from public contract in this plan:

- `store_access_token`
- `store_refresh_token`
- `clear_stored_access_token`
- `clear_stored_refresh_token`
- `clear_stored_session_tokens`
- `get_stored_refresh_token`
- `get_user_token_expires_at`

If additional helper exports are discovered as migration-only during implementation, they must be added to this list before removal.

## Primary File Touchpoints
- `/workspace/aifabrix-miso-client-python/miso_client/utils/user_token_refresh.py`
- `/workspace/aifabrix-miso-client-python/tests/unit/test_user_token_refresh.py`
- `/workspace/aifabrix-miso-client-python/miso_client/__init__.py` (remove helper exports)
- `/workspace/aifabrix-miso-client-python/README.md`
- `/workspace/aifabrix-miso-client-python/CHANGELOG.md`
- `/workspace/aifabrix-miso-client-python/.temp/NN-consumer-sdk-migration-instruction.md` (exact numeric prefix determined at execution time)

## Implementation Plan
1. Freeze no-migration contract
- Document hard-cutover policy: helper API removal is intentional breaking change.
- Record consumer migration expectation (consumer will be updated immediately by owner).

2. Remove helper API and migration storage semantics
- Remove storage helper functions/constants that implement migration compatibility semantics from `user_token_refresh.py`.
- Remove related manager coupling to removed helper API where not needed for final behavior.
- Ensure no fallback path depends on legacy keys.

3. Preserve final refresh/retry behavior
- Ensure `UserTokenRefreshManager` still supports callback refresh, refresh-token path, JWT expiry extraction, and deterministic cleanup.
- Keep resilient behavior for invalid/missing values without reintroducing alias fallback.

4. Update tests for final-only behavior
- Remove helper API contract tests and replace with manager-level/final-behavior tests.
- Add negative assertions that legacy keys (`miso_token`, `token`, `authToken`, etc.) are unsupported and do not influence behavior.
- Keep/expand coverage for refresh due/expired transitions and manager flow where still valid.

5. Update docs and release notes
- Remove helper API usage/docs and migration alias claims from README token lifecycle section.
- Add explicit hard-cutover notes and consumer impact (helper API removal + legacy key removal).
- Add changelog entry describing helper API removal and migration compatibility removal as breaking contract changes.

6. Create consumer migration instruction doc
- Create a temporary handoff document in project `.temp` with:
  - removed helper API list and replacement guidance,
  - required import/code changes for consumer,
  - rollout order and validation checklist for consumer migration,
  - known breaking points and quick verification commands.
- Use next sequential numeric prefix in `.temp` folder filename.

7. Validation and evidence
- Run required validation gates in order:
  - `make format-silent`
  - `make lint-silent`
  - `make type-check-silent`
  - `make test-silent`
- Use fallback commands only if silent targets are unavailable:
  - `make format`
  - `make lint`
  - `make type-check`
  - `make test`
- Capture evidence from `.temp/validation/` and update validation section in plan if used.

## Validation Gates
- Mandatory order: **FORMAT -> LINT -> TYPE-CHECK -> TEST**.
- Preferred silent commands:
  - `make format-silent`
  - `make lint-silent`
  - `make type-check-silent`
  - `make test-silent`
- Fallback only if needed:
  - `make format`
  - `make lint`
  - `make type-check`
  - `make test`
- Logs source: `.temp/validation/`.
- Gate policy: zero blocking errors/warnings on mandatory quality gates.

## Execution Status Tracking
- Allowed todo statuses: `pending`, `in_progress`, `completed`, `cancelled`.
- Move todo to `in_progress` at start and `completed` immediately after completion.
- Keep frontmatter todos and checklist state synchronized.
- Do not leave stale `in_progress` todos when implementation is complete.

## Expected Automated Tests
- Unit tests proving helper API is no longer exported/used and manager final flow remains valid.
- Negative tests proving legacy compatibility keys are unsupported and ignored.
- Regression tests for:
  - `normalize_expires_at` / `get_jwt_expires_at`
  - refresh buffer and due/expired calculations
  - manager refresh callback/service paths and failure handling

## Definition of Done
- Migration alias semantics are removed.
- Token storage helper API is removed from implementation and public exports.
- Final manager token lifecycle behavior remains stable and test-covered.
- README and changelog reflect final (no-migration) contract.
- Consumer migration instruction doc is created in `.temp` with actionable post-cutover steps.
- Validation gates pass in required silent order.
- Test coverage requirement is met: >=80% for new/changed code.
- Breaking consumer impact is explicitly documented (helper API removal + required consumer update).
- Type hints are present for all new/changed functions.
- Public method/class docstrings remain valid and Google-style.
- File/method size constraints are respected for touched files.
- All plan todos are resolved (`completed` or explicitly `cancelled` with rationale).

## Plan Validation Report

**Date**: 2026-05-15 (today is 2026-05-15)  
**Plan**: `.cursor/plans/44_sdk_auth_cutover_5d2ed6a9.plan.md`  
**Status**: ✅ VALIDATED

### Plan Purpose

Define a hard-cutover SDK plan that removes migration-phase helper API/storage compatibility semantics and keeps final manager runtime behavior stable with explicit breaking-change communication.

### Applicable Rules

- ✅ [Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns) - applies to manager/runtime behavior preservation.
- ✅ [Code Style](.cursor/rules/project-rules.mdc#code-style) - applies to typing/error-handling quality in touched Python modules.
- ✅ [Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions) - applies to required final-only and edge-case test coverage.
- ✅ [Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines) - applies to token handling and safe fallback behavior.
- ✅ [Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines) - applies to touched file/method size constraints.
- ✅ [Documentation](.cursor/rules/project-rules.mdc#documentation) - applies to README/CHANGELOG updates.
- ✅ [Critical Rules](.cursor/rules/project-rules.mdc#critical-rules) - applies to mandatory do/don't policies.
- ✅ [.cursorrules](.cursorrules) - applies as workspace-level baseline guidance.

### Rule Compliance

- ✅ DoD contains required silent validation commands and strict order (FORMAT -> LINT -> TYPE-CHECK -> TEST).
- ✅ DoD includes coverage, typing, docstring, security, and completion requirements.
- ✅ Plan includes `Rules and Standards`, `Before Development`, `Expected Automated Tests`, `Validation Gates`, and `Execution Status Tracking`.
- ✅ Frontmatter `todos` are present and use valid status set (`pending|in_progress|completed|cancelled`).

### Plan Updates Made

- ✅ Upgraded `Rules and Standards` to explicit anchor-linked rule references.
- ✅ Added missing explicit `>=80%` coverage requirement to DoD.
- ✅ Attached this `Plan Validation Report` with dynamic-date format.

### Recommendations

- Keep removal inventory in sync with actual export removals discovered during implementation.
- Keep breaking-change notes explicit in README and CHANGELOG to support immediate consumer cutover.

## Implementation Validation Report

**Date**: 2026-05-15

Executed in required order with silent targets:

- `make format-silent` -> `.temp/validation/01-format` ✅
- `make lint-silent` -> `.temp/validation/02-lint` ✅
- `make type-check-silent` -> `.temp/validation/03-type-check` ✅
- `make test-silent` -> `.temp/validation/04-test` ✅ (`1367 passed`)

Implementation closure:

- Storage helper API removed from implementation and top-level exports.
- `UserTokenRefreshManager` refresh/retry behavior preserved without alias storage semantics.
- Unit tests updated to final manager-only contract and pass.
- README and CHANGELOG updated with hard-cutover/breaking-change messaging.
- Consumer migration instruction created: `.temp/03-sdk-auth-cutover-consumer-migration.md`.

## Validation

**Date**: 2026-05-19 (today is 2026-05-19)  
**Status**: ✅ COMPLETE

### Executive Summary

Implementation is complete and backed by code, tests, and validation-gate evidence, including explicit negative proof that legacy compatibility keys are ignored.

### File Existence Validation

- ✅ `miso_client/utils/user_token_refresh.py` - exists and helper API definitions were removed.
- ✅ `tests/unit/test_user_token_refresh.py` - exists and manager-only contract tests are present.
- ✅ `miso_client/__init__.py` - exists and removed helper exports are absent.
- ✅ `README.md` - exists and helper API usage docs removed.
- ✅ `CHANGELOG.md` - exists and breaking cutover note added in `Unreleased`.
- ✅ `.temp/03-sdk-auth-cutover-consumer-migration.md` - exists.

### Test Coverage

- ✅ Unit tests exist.
- ✅ Regression tests for refresh/lifecycle helpers and manager paths exist.
- ✅ Legacy-key negative case is covered by `test_refresh_token_ignores_legacy_storage_alias_keys`.
- ✅ Coverage evidence (`make test-cov-silent`): `TOTAL ... 94%`.

### Code Quality Validation

**STEP 1 - FORMAT**: ✅ PASSED (`make format-silent`)  
**STEP 2 - LINT**: ✅ PASSED (`make lint-silent`)  
**STEP 3 - TYPE CHECK**: ✅ PASSED (`make type-check-silent`)  
**STEP 4 - TEST**: ✅ PASSED (`make test-silent`, `1368 passed`)

### Cursor Rules Compliance

- ✅ Code reuse
- ✅ Error handling
- ✅ Logging / no secret exposure
- ✅ Type safety
- ✅ Async patterns
- ✅ HTTP/token management patterns
- ✅ Redis/service-layer constraints (no new violations introduced)
- ✅ Security / ISO-oriented constraints
- ✅ API data conventions
- ✅ File/method size constraints in touched files

### Implementation Completeness

- ✅ Services/manager behavior: complete.
- ✅ Utilities/export/doc updates: complete.
- ✅ Expected automated tests: complete evidence, including legacy-key negative behavior.
- ✅ Final DoD closure: complete.

### Issues and Recommendations

- No blocking issues found.

### Final Validation Checklist

- [x] All tasks completed
- [x] All files exist
- [x] Tests exist and pass
- [x] Code quality validation passes
- [x] Cursor rules compliance verified
- [x] Implementation complete

**Result**: ✅ **VALIDATION PASSED** - all plan requirements are implemented and evidenced.