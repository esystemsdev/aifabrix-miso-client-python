---
name: restore-warn-log-level-python
overview: Restore `warn` as a first-class logging level across the Python SDK pipeline so it is preserved from public API to transport payloads and tests/docs remain consistent.
todos:
  - id: align-log-level-contracts
    content: Align all log level types/contracts to include warn end-to-end
    status: completed
  - id: implement-core-warn
    content: Add first-class warn method in LoggerService and wire through _log/_build_log_entry paths
    status: completed
  - id: unified-and-chain-parity
    content: Update UnifiedLogger and LoggerChain to call warn directly without remapping
    status: completed
  - id: request-helper-parity
    content: Update logger request helper level literals and tests to support warn
    status: completed
  - id: transport-and-api-consistency
    content: Ensure transform and API request models preserve warn unchanged
    status: completed
  - id: tests-regression-coverage
    content: Add/update unit tests and regression guards for warn-to-info remap
    status: completed
  - id: add-contract-guardrails
    content: Add maintainability guardrails to reduce future log-level contract drift
    status: completed
  - id: docs-and-changelog-sync
    content: Update README/CHANGELOG to match runtime warn behavior
    status: completed
  - id: ci-gate-for-warn
    content: Define CI gates so warn contract regressions cannot be merged
    status: completed
isProject: false
---

# Restore Warn as First-Class (Python SDK)

## Goal

Ensure `warn` survives end-to-end without conversion to `info`: public logger API -> internal `LogEntry` -> request transformation -> logs API payload/contracts -> tests/docs.

## Rules and Standards

This plan must comply with `.cursorrules` and `.cursor/rules/project-rules.mdc`, especially:

- **Architecture Patterns**: logging service and transport flow updates must stay consistent with current SDK architecture.
- **Code Style**: type hints and public contract consistency across model/service/helper layers.
- **Testing Conventions**: add unit/regression coverage for warn behavior at service and transformation boundaries.
- **Security Guidelines**: preserve masking and do not leak sensitive data in logs.
- **Documentation**: public behavior changes must be reflected in README/changelog.

### Key Requirements Applied Here

- Keep service behavior stable except warn parity scope.
- Preserve ISO 27001 masking behavior and silent-fail logging safety patterns.
- Keep Python type contracts explicit and synchronized across all log-level literals.
- Add regression tests that fail if warn is remapped to info again.

## Before Development

- Re-check all logger level contract points (model, service, helpers, transport, docs).
- Confirm this change is warn parity only (no unrelated logging redesign).
- Confirm required tests include helper-level warn coverage, not only service-level tests.

## Current Mismatch to Fix

- `[miso_client/models/config.py](miso_client/models/config.py)`: `MisoClientConfig.log_level` includes `"warn"`, but `LogEntry.level` excludes it.
- `[miso_client/services/logger.py](miso_client/services/logger.py)`: no public `warn()` method; internal level literals exclude `warn`.
- `[miso_client/services/unified_logger.py](miso_client/services/unified_logger.py)`: `warn()` currently calls `logger_service.info()` and prefixes message with `"WARNING: "`.
- `[miso_client/services/logger_chain.py](miso_client/services/logger_chain.py)`: no chain-level `.warn(...)` method.
- `[miso_client/utils/logger_request_helpers.py](miso_client/utils/logger_request_helpers.py)`: helper level literals exclude `warn`.
- `[README.md](README.md)`: documents warn usage, currently inconsistent with runtime behavior.

## Scope (Recommended)

- **Recommended option: Full contract alignment (same as TypeScript path intent)** because it prevents drift between config, runtime behavior, transport payload, and docs.
- In scope:
  - Add first-class `warn` support in core logger.
  - Preserve `warn` unchanged in transformation and transport payloads.
  - Add parity in `UnifiedLogger`, `LoggerChain`, and request helper pathways.
  - Add regression tests to block warn->info remapping.
  - Align docs/changelog with implemented behavior.
- Out of scope:
  - Broad logger architecture refactors unrelated to warn parity.
  - New logging features beyond warn-level support.

## Planned File-Level Changes

- `[miso_client/models/config.py](miso_client/models/config.py)`
  - Extend `LogEntry.level` literal to include `"warn"`.
- `[miso_client/services/logger.py](miso_client/services/logger.py)`
  - Add `async def warn(...)` and route to `_log("warn", ...)`.
  - Extend all relevant internal `Literal[...]` level annotations (`_build_log_entry`, `_log`, and public `get_*` methods) to include `warn`.
  - Keep existing debug gating unchanged unless warn gating is explicitly required.
- `[miso_client/services/unified_logger.py](miso_client/services/unified_logger.py)`
  - Change `warn()` to call `logger_service.warn(...)` directly.
  - Remove warn message prefix remapping behavior.
- `[miso_client/services/logger_chain.py](miso_client/services/logger_chain.py)`
  - Add fluent `.warn(message: str)` method for parity with `.info/.debug/.error/.audit`.
- `[miso_client/utils/logger_request_helpers.py](miso_client/utils/logger_request_helpers.py)`
  - Extend helper function level literals to include `warn`.
  - Ensure helper-built `LogEntry` preserves `warn` unchanged.
- `[miso_client/utils/logger_helpers.py](miso_client/utils/logger_helpers.py)`
  - Extend `build_log_entry()` level literal to include `warn`.
  - Verify `transform_log_entry_to_request()` keeps `GeneralLogData.level="warn"` unchanged for warn entries.
- `[tests/unit/test_unified_logger.py](tests/unit/test_unified_logger.py)`
  - Replace current expectation (`info("WARNING: ...")`) with direct `warn(...)` forwarding assertions.
- `[tests/unit/test_logger.py](tests/unit/test_logger.py)`
  - Add tests for `LoggerService.warn()` entry creation and transform behavior.
  - Add explicit regression test ensuring no warn->info conversion.
- `[tests/unit/test_logger_chain.py](tests/unit/test_logger_chain.py)`
  - Add `.warn()` chain method tests.
- `[tests/unit/test_logger_request_helpers.py](tests/unit/test_logger_request_helpers.py)` (or equivalent additions in existing logger tests)
  - Add helper-level tests for warn support in `get_log_with_request`, `get_with_context`, and `get_for_request`.
- `[tests/unit/test_logger_helpers.py](tests/unit/test_logger_helpers.py)`
  - Add helper-level tests validating `warn` produces valid `LogEntry` and preserved request payload.
- `[README.md](README.md)` and `[CHANGELOG.md](CHANGELOG.md)`
  - Align examples/contract notes with first-class warn behavior.

## Best-Practice Guardrails (Applicable from TypeScript Plan)

- Use a single source of truth for logger levels where practical (for example, shared type alias/import pattern) to reduce type drift.
- Add boundary contract tests for exact level preservation (`warn` must remain `warn` in transformed payloads).
- Add explicit regression checks that fail on warn remapping or warn message prefixing behavior.
- Keep changes localized to warn parity; avoid unrelated logger refactors in the same change.

## Test and Validation Plan

- Unit tests (minimum):
  - Unified logger warn delegation path.
  - Core logger warn creation path.
  - Logger chain warn parity path.
  - Logger request helper warn parity path.
  - Helper transform payload level-preservation path.
- Regression guard:
  - Dedicated assertion that warn entries are never prefixed/remapped to info.
- Validation commands (in this repo’s Python toolchain):
  - `python -m ruff check miso_client tests`
  - `python -m mypy miso_client`
  - `python -m pytest tests/unit/test_unified_logger.py tests/unit/test_logger.py tests/unit/test_logger_chain.py tests/unit/test_logger_helpers.py`
  - `python -m pytest tests/unit/test_logger_request_helpers.py` (if file exists or is newly added)
  - `python -m pytest`

## CI Gate Template (Warn Contract)

- Required checks before merge:
  - `python -m ruff check miso_client tests`
  - `python -m mypy miso_client`
  - targeted warn logger unit tests
  - full `python -m pytest`
- Block merge if any warn contract test fails.

## Definition of Done

1. `warn` is part of all internal/public log-level contracts where `info/debug/error/audit` are used for general logging.
2. `UnifiedLogger.warn()` and `LoggerChain.warn()` use native warn path (no info remap, no message prefixing).
3. `logger_request_helpers` supports `warn` in all helper entry points.
4. Transform/payload keeps `warn` unchanged in `GeneralLogData.level`.
5. Targeted warn tests and full unit suite pass.
6. README/changelog entries match runtime behavior.
7. No regression to masking, audit queue behavior, or HTTP/Redis fallback behavior.
8. Validation order is completed: **RUFF -> MYPY -> TARGETED TESTS -> FULL PYTEST**.

## Risks and Guardrails

- Risk: type drift between model/service/helper literals.
  - Guardrail: update all logger-level `Literal` declarations in the same change and add regression tests at service + transform boundaries.
- Risk: accidental behavior change for existing warn consumers expecting prefixed info messages.
  - Guardrail: document behavior change in changelog as a compatibility note.

## Execution Status

- Completed: warn-level contract alignment across model/service/helper layers.
- Completed: native `warn` behavior in `UnifiedLogger` and `LoggerChain` (no remap/prefix).
- Completed: request helper warn pathway coverage.
- Completed: docs/changelog updates.
- Validation run (using project virtualenv): `ruff` passed, `mypy` passed, targeted warn tests passed, full `pytest` passed.

## Validation

**Date**: 2026-02-19  
**Status**: ✅ COMPLETE

### Executive Summary

Implementation is complete and validated against the plan scope. All plan todos are marked completed, all referenced files exist, warn-level behavior is implemented end-to-end, and quality gates passed in required order.

### File Existence Validation

- ✅ `miso_client/models/config.py` - exists and updated
- ✅ `miso_client/services/logger.py` - exists and updated
- ✅ `miso_client/services/unified_logger.py` - exists and updated
- ✅ `miso_client/services/logger_chain.py` - exists and updated
- ✅ `miso_client/utils/logger_request_helpers.py` - exists and updated
- ✅ `miso_client/utils/logger_helpers.py` - exists and updated
- ✅ `tests/unit/test_unified_logger.py` - exists and updated
- ✅ `tests/unit/test_logger.py` - exists and updated
- ✅ `tests/unit/test_logger_chain.py` - exists and updated
- ✅ `tests/unit/test_logger_request_helpers.py` - exists and created
- ✅ `tests/unit/test_logger_helpers.py` - exists and updated
- ✅ `README.md` - exists and updated
- ✅ `CHANGELOG.md` - exists and updated

### Test Coverage

- ✅ Unit tests exist for modified logger services/helpers.
- ✅ New helper-path test file exists: `tests/unit/test_logger_request_helpers.py`.
- ✅ Regression checks included for warn-remap/prefix behavior.
- ✅ Full suite result: `1289 passed` with overall coverage `93%`.

### Code Quality Validation

**STEP 1 - FORMAT**: ✅ PASSED  
- Ran `black` and `isort` on `miso_client/` and `tests/` (1 file reformatted).

**STEP 2 - LINT**: ✅ PASSED  
- Ran `ruff check` on `miso_client/` and `tests/` (`All checks passed`).

**STEP 3 - TYPE CHECK**: ✅ PASSED  
- Ran `mypy miso_client --ignore-missing-imports` (`Success: no issues found in 83 source files`).
- Informational mypy notes only (no errors).

**STEP 4 - TEST**: ✅ PASSED  
- Ran `pytest tests -v` (`1289 passed`).

### Cursor Rules Compliance

- ✅ Code reuse: PASSED (used shared `LogLevel` type alias across layers)
- ✅ Error handling: PASSED (existing safe/silent logging flows preserved)
- ✅ Logging: PASSED (`warn` now first-class, no remap to `info`)
- ✅ Type safety: PASSED (type hints updated across model/service/helper boundaries)
- ✅ Async patterns: PASSED (async logger methods and tests preserved)
- ✅ HTTP client patterns: PASSED (no regressions in logging transport paths)
- ✅ Token management: PASSED (no changes violating JWT/token rules)
- ✅ Redis caching: PASSED (no regressions in logger queue/fallback behavior)
- ✅ Service layer patterns: PASSED (service structure and dependency patterns maintained)
- ✅ Security: PASSED (masking and sensitive-data handling unchanged)
- ✅ API data conventions: PASSED (outgoing log payload level keeps `warn`)
- ✅ File size guidelines: PASSED (no introduced oversized modules)

### Implementation Completeness

- ✅ Services: COMPLETE
- ✅ Models: COMPLETE
- ✅ Utilities: COMPLETE
- ✅ Documentation: COMPLETE
- ✅ Exports: COMPLETE

### Issues and Recommendations

- No blocking issues found.
- Optional improvement: enable `mypy --check-untyped-defs` gradually to reduce annotation-unchecked notes in unrelated modules.

### Final Validation Checklist

- [x] All tasks completed
- [x] All files exist
- [x] Tests exist and pass
- [x] Code quality validation passes
- [x] Cursor rules compliance verified
- [x] Implementation complete

**Result**: ✅ **VALIDATION PASSED** - Warn-level implementation is complete, tested, and compliant with plan requirements.
