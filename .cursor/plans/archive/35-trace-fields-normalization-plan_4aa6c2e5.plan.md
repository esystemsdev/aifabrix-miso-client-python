---
name: trace-fields-normalization-plan
overview: Introduce deterministic non-empty normalization and precedence rules for key traceability fields in miso-client logging paths, starting with shared helper integration and regression safety.
todos:
  - id: define-trace-helper
    content: Add shared non-empty trace field helper and integrate in logger_helpers.
    status: completed
  - id: apply-precedence-matrix
    content: Apply deterministic precedence matrix across logger entry construction paths.
    status: completed
  - id: add-regression-tests
    content: Add regression tests for audit/general paths and empty-value clobber protection.
    status: completed
  - id: payload-snapshot-tests
    content: Add serialized payload assertions for resolved traceability fields.
    status: completed
  - id: transport-boundary-evidence
    content: Capture miso-client transport-boundary serialized payload evidence via tests/mocks for audit, with_context, and for_request paths.
    status: completed
  - id: run-validation-gates
    content: Run formatting, lint, type checks, and targeted tests for changed modules.
    status: completed
isProject: false
---

# Shared Traceability Normalization Plan

## Decision and Rationale

Use a shared normalization strategy, not `applicationId`-only. This is justified because current behavior is partly field-specific and can drift across paths; centralizing non-empty clobber protection reduces recurring incidents for `requestId/userId/correlationId` while preserving existing payload contracts.

## Scope

In scope:

- Deterministic precedence + non-empty normalization for: `applicationId`, `correlationId`, `requestId`, `userId`, `application`, `environment`.
- Logger entry construction and payload serialization paths.
- Regression tests for `audit` and `general/error` flows.
- Focused verification of `applicationId` retention in `miso-client` serialized transport payload (in-repo test/mock evidence only).

Out of scope:

- Changes outside the current `miso-client` repository.
- Breaking changes to public SDK method signatures.
- External system validation and cross-repository evidence correlation.

## Rules and Standards

This plan follows the project rules in:

- `[/workspace/aifabrix-miso-client-python/.cursorrules](/workspace/aifabrix-miso-client-python/.cursorrules)`
- `[/workspace/aifabrix-miso-client-python/.cursor/rules/project-rules.mdc](/workspace/aifabrix-miso-client-python/.cursor/rules/project-rules.mdc)`

Applicable sections from `project-rules.mdc`:

- **[Architecture Patterns](/workspace/aifabrix-miso-client-python/.cursor/rules/project-rules.mdc#architecture-patterns)** - applies because the plan changes logger/service payload construction and context propagation behavior.
- **[Code Style](/workspace/aifabrix-miso-client-python/.cursor/rules/project-rules.mdc#code-style)** - applies for type hints, defensive error handling, and docstring expectations.
- **[Testing Conventions](/workspace/aifabrix-miso-client-python/.cursor/rules/project-rules.mdc#testing-conventions)** - applies because this plan is regression-test heavy and path-parity focused.
- **[Common Patterns](/workspace/aifabrix-miso-client-python/.cursor/rules/project-rules.mdc#common-patterns)** - applies for logger chain and service method consistency.
- **[Security Guidelines](/workspace/aifabrix-miso-client-python/.cursor/rules/project-rules.mdc#security-guidelines)** - mandatory because logging changes must preserve masking and avoid sensitive-data leakage.
- **[Code Size Guidelines](/workspace/aifabrix-miso-client-python/.cursor/rules/project-rules.mdc#code-size-guidelines)** - mandatory because helper extraction and method-size constraints apply.
- **[Documentation](/workspace/aifabrix-miso-client-python/.cursor/rules/project-rules.mdc#documentation)** - applies because consumer/handoff artifacts and changelog impact must stay aligned.

Required constraints for execution:

- Preserve public SDK contracts (no signature/type breaking changes).
- Keep service methods defensive and preserve RFC 7807-related error/log behavior.
- Keep outgoing payload naming conventions intact (camelCase for API payload fields).
- Apply normalization only to the six traceability keys in this plan.
- Add regression coverage for both success and error/audit paths.
- Do not add runtime tracing/instrumentation code to production paths.

## Target Files

- [miso_client/utils/logger_helpers.py](/workspace/aifabrix-miso-client-python/miso_client/utils/logger_helpers.py)
- [miso_client/services/logger.py](/workspace/aifabrix-miso-client-python/miso_client/services/logger.py)
- [miso_client/services/logger_chain.py](/workspace/aifabrix-miso-client-python/miso_client/services/logger_chain.py)
- [miso_client/services/unified_logger.py](/workspace/aifabrix-miso-client-python/miso_client/services/unified_logger.py)
- [miso_client/utils/logger_request_helpers.py](/workspace/aifabrix-miso-client-python/miso_client/utils/logger_request_helpers.py)
- [tests/unit/test_logger.py](/workspace/aifabrix-miso-client-python/tests/unit/test_logger.py)

Evidence artifacts (in scope):

- `miso-client` unit/integration test outputs.
- Serialized payload assertions captured in tests/mocks at transport boundary.

## Implementation Steps

1. Define a shared helper for scalar trace fields (e.g., `pick_first_non_empty(...)`) in `logger_helpers` with strict non-empty semantics (`None`, empty string, whitespace-only are treated as missing).
2. Implement and document a precedence matrix per field in `build_log_entry()` (field-specific source order, common normalization).
3. Apply helper-backed resolution consistently in logger entry creation paths (`LoggerService`/request helper/chain/unified) to prevent path-specific clobbering.
4. Preserve payload compatibility: keep top-level fields as today; keep context behavior stable except for preventing empty overwrites.
5. Add regression tests for both flow families (`audit`, `general/error`) including explicit clobber scenarios.
6. Add serialized payload assertions to verify final outbound request data keeps resolved non-empty values.
7. Verify parity for all required serializer entry paths:
   - `log.audit(...)`
   - chain path `with_context(...).info/error/audit`
   - request-bound path `for_request(...)` (where serializer path applies)
8. Produce transport-boundary evidence only through tests/mocks and serialized payload assertions (no runtime debug snapshots).

## Regression Test Checklist (Mandatory)

1. Path parity test for identical input context across:
   - `log.audit(...)`
   - `with_context(...).info/error/audit`
   - `for_request(...)` (where serializer path applies)
   Expected: same resolved values for `applicationId`, `context.applicationId`, `correlationId`, `requestId`, `userId`, `application`, `environment`.

2. Empty-clobber matrix tests for each traceability key:
   - inputs: `None`, `""`, whitespace-only, valid value
   - expected: empty values never overwrite a non-empty resolved value.

3. Top-level vs nested `applicationId` conflict tests:
   - top-level non-empty + nested empty -> nested resolved non-empty
   - nested non-empty + top-level empty -> top-level resolved non-empty
   - both non-empty and different -> deterministic precedence per matrix.

4. Context merge stability tests:
   - normalization applies only to the six traceability keys;
   - unrelated business context keys remain unchanged.

5. Serialized payload contract (wire-level) tests:
   - assert exact payload handed to transport/mock sender preserves resolved top-level and nested `applicationId`.

6. Audit vs general/error parity tests:
   - for equivalent traceability input, key fields remain present and consistent in both payload families.

7. Request-derived fallback tests:
   - explicit empty `requestId/correlationId` uses request-derived values;
   - explicit non-empty values keep precedence.

8. Production-safety guard check:
   - ensure no temporary runtime tracing markers/debug instrumentation are introduced in SDK source.

## Precedence Matrix (Initial)

- `applicationId`: explicit context value -> application context service value -> JWT-derived fallback.
- `correlationId`: explicit context value -> stored logger context -> generated UUID fallback (where generation is current behavior).
- `requestId`: explicit context value -> request-derived context value -> fallback none.
- `userId`: explicit context value -> JWT-derived value.
- `application`: options/context value -> application context service -> configured client id/default.
- `environment`: options/context value -> application context service -> configured/default.

## Validation

- Mandatory order:
  1. `black` + `isort` (format gate)
  2. `ruff check` (lint gate)
  3. `mypy` (type-check gate)
  4. `pytest` (test gate)
- Confirm no contract break in `CHANGELOG` impact notes (behavior hardening only).
- Confirm required output package is complete:
  - file-level diff summary,
  - test list and pass output.
- Confirm no temporary runtime tracing code is introduced in SDK source.
- Confirm all items in `Regression Test Checklist (Mandatory)` are implemented and passing.
- Confirm documentation is updated where needed (`CHANGELOG.md` and consumer-impact notes in plan artifacts).

### Implementation Validation Report

**Date**: 2026-03-04  
**Status**: ✅ COMPLETE

#### Executive Summary

Implementation is complete for current-repository scope. Code quality gates pass, required tests exist and pass, and evidence requirements are satisfied using in-repo test/mock transport payload assertions.

#### File Existence Validation

- ✅ All linked plan file paths exist (`8/8`).
- ✅ Planned implementation files exist and were updated:
  - `miso_client/utils/logger_helpers.py`
  - `miso_client/services/logger.py`
  - `miso_client/api/types/logs_types.py`
  - `tests/unit/test_logger_helpers.py`
  - `tests/unit/test_logger.py`
  - `tests/unit/test_logger_request_helpers.py`

#### Test Coverage Validation

- ✅ Unit tests exist for modified/new behavior.
- ✅ Regression test additions cover:
  - traceability non-empty clobber protection,
  - top-level + nested `applicationId` payload preservation,
  - audit/chain/for_request parity checks,
  - request-derived fallback for empty request IDs.
- ✅ Full test suite pass confirmed: `1317 passed`, coverage `93%`.

#### Code Quality Validation

**STEP 1 - FORMAT**: ✅ PASSED  
- `black /workspace/aifabrix-miso-client-python/miso_client /workspace/aifabrix-miso-client-python/tests`  
- `isort /workspace/aifabrix-miso-client-python/miso_client /workspace/aifabrix-miso-client-python/tests`

**STEP 2 - LINT**: ✅ PASSED  
- `ruff check /workspace/aifabrix-miso-client-python/miso_client /workspace/aifabrix-miso-client-python/tests`

**STEP 3 - TYPE CHECK**: ✅ PASSED  
- `mypy /workspace/aifabrix-miso-client-python/miso_client --ignore-missing-imports`

**STEP 4 - TEST**: ✅ PASSED  
- `pytest /workspace/aifabrix-miso-client-python/tests -v`

#### Cursor Rules Compliance

- ✅ Code reuse and helper extraction: PASSED
- ✅ Error handling behavior preserved: PASSED
- ✅ Logging/traceability hardening without runtime incident tracing: PASSED
- ✅ Type safety (type hints + mypy): PASSED
- ✅ Async/test mocking patterns: PASSED
- ✅ API data conventions (camelCase payload fields): PASSED
- ✅ Security/masking expectations preserved: PASSED
- ✅ File size guideline relevant changes: PASSED

#### Implementation Completeness

- ✅ Services: COMPLETE
- ✅ Models/types: COMPLETE
- ✅ Utilities: COMPLETE
- ✅ Tests: COMPLETE
- ✅ Documentation/evidence package: COMPLETE (in-repo scope)

#### Issues and Recommendations

- No open implementation blockers remain within current-repository scope.
- Recommended next step: keep this plan scoped to `miso-client`; if needed, handle cross-repository verification in a separate plan.

#### Final Validation Checklist

- [x] Core implementation tasks completed
- [x] Referenced files exist
- [x] Tests added and passing
- [x] Format/lint/type-check/test gates passing
- [x] Rule compliance reviewed
- [x] All plan todos completed
- [x] Full in-repo evidence bundle completed

**Result**: ✅ **VALIDATION PASSED** - Implementation is complete and validated within current project scope.

## Risks and Mitigations

- Risk: over-normalizing business context fields.
  - Mitigation: apply strict normalization only to the six traceability keys.
- Risk: behavior drift between `audit` and chain paths.
  - Mitigation: add paired tests asserting same resolution outcome across both paths.

## Before Development

- Re-read applicable sections in `project-rules.mdc` (Architecture, Testing, Security, Code Size, Documentation).
- Confirm exact source order for each field from current implementation before changing precedence.
- Confirm whether any downstream consumer depends on empty-string traceability values.
- Prepare targeted fixture/mocks for logger service, unified logger, and chain path tests.
- Identify any docs/changelog surfaces that must be updated after implementation.

## Definition of Done

- Shared non-empty helper implemented and used for all six traceability keys.
- Precedence matrix implemented exactly as documented.
- No public API signature/type changes introduced.
- Regression tests added for audit and general/error paths, including clobber scenarios.
- Serialized payload evidence from `miso-client` is captured for required paths (audit + chain + request-bound where applicable).
- Validation commands pass in required order (`FORMAT -> LINT -> TYPE-CHECK -> TEST`) with zero lint/type/test failures.
- No temporary runtime debug/instrumentation code exists in final codebase.
- All mandatory regression checklist items are implemented, executed, and passing.
- File and method size constraints remain compliant (files <=500 lines; methods within guideline or justified).
- Public/modified methods keep type hints and Google-style docstrings as required.
- Documentation/changelog impact is updated if behavior changes are introduced.

## Required Output Back

1. Changed files with short rationale.
2. Test list and pass output.
3. Serialized payload evidence summary (from tests/mocks) with columns:
   - `correlationId`
   - `miso_client_serialized_topLevel_applicationId`
   - `miso_client_serialized_context_applicationId`
   - `status` (`fixed` / `not fixed`)
4. Final in-repo statement:
   - `miso-client serialization fix confirmed`
   - or `further investigation required`

## Execution Progress

- Completed implementation:
  - Added shared traceability normalization helpers in `logger_helpers`:
    - non-empty detection
    - first-non-empty selection
    - context merge with empty-value clobber protection
  - Applied helper-backed precedence in `build_log_entry()` for:
    - `applicationId`, `correlationId`, `requestId`, `userId`, `application`, `environment`
  - Preserved `context.applicationId` in final serialized payload when top-level `applicationId` resolves non-empty.
  - Extended API-layer log request serialization to carry traceability fields for both `general/error` and `audit` payloads.

- Completed regression coverage additions:
  - Added/updated tests for:
    - empty-value clobber prevention,
    - top-level and nested `applicationId` preservation,
    - wire-level serialization assertions,
    - path parity across `audit`, `with_context`, and `for_request`,
    - request-derived fallback precedence for empty explicit request IDs.

- Validation evidence (executed):
  - `black` + `isort` on source + tests: passed
  - `ruff check` on source + tests: passed
  - `mypy` on source files: passed (`Success: no issues found in 84 source files`)
  - `pytest` full test suite: passed (`1317 passed in 9.88s`, coverage `93%`)

- Scope note:
  - Plan evidence is limited to current repository artifacts (tests/mocks/serialized payload assertions).

## Plan Validation Report

**Date**: 2026-03-04  
**Plan**: `/workspace/aifabrix-miso-client-python/.cursor/plans/35-trace-fields-normalization-plan_4aa6c2e5.plan.md`  
**Status**: ✅ VALIDATED

### Validation Summary

- Scope is clear and bounded to `miso-client` logging paths.
- Change strategy is low-risk (shared helper + deterministic precedence) and contract-preserving.
- Test strategy is sufficient for regression protection if implemented as written.
- Risk controls are adequate and specific to incident class (empty-value clobbering).
- Mandatory rule sections are now referenced explicitly with rationale.
- DoD now includes strict `LINT -> FORMAT -> TEST` sequencing and documentation update expectations.

### Minor Improvements Applied

- Added explicit rules/compliance section.
- Added pre-development checklist and concrete Definition of Done.
- Clarified mandatory validation command order and documentation obligations.

### Recommendation

Proceed with implementation as planned. Keep normalization strictly limited to the six traceability keys to avoid accidental mutation of business context fields.