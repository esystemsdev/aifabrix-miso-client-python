---
name: JSON Document Masking Interface
overview: Expose the existing DataMasker as a public interface for other projects to mask JSON documents. The SDK already has masking for error/logging internally; this plan adds a clean public API and optionally a convenience function for raw JSON strings.
todos: []
isProject: false
---

# JSON Document Masking Interface for External Projects

## Current State

- **DataMasker** ([miso_client/utils/data_masker.py](miso_client/utils/data_masker.py)): Static class with `mask_sensitive_data(data)`, `mask_value()`, `is_sensitive_field()`, `contains_sensitive_data()`, `set_config_path()`
- Used internally for: logger context masking, HTTP audit logging (headers, bodies, query params)
- **Not exported** in [miso_client/**init**.py](miso_client/__init__.py) - other projects must import from internal path `miso_client.utils.data_masker`

## Proposed Interface

### 1. Export DataMasker in Public API

Add to [miso_client/**init**.py](miso_client/__init__.py):

```python
from .utils.data_masker import DataMasker
# Add "DataMasker" to __all__
```

**Usage for other projects:**

```python
from miso_client import DataMasker

doc = {"user": "john", "password": "secret123", "email": "john@example.com"}
masked = DataMasker.mask_sensitive_data(doc)
# {"user": "john", "password": "***MASKED***", "email": "john@example.com"}
```

### 2. Add Convenience Function for Raw JSON Strings (Optional)

Create `mask_json_string(json_str: str) -> str` for projects that have JSON as a string (e.g. from HTTP body, file, or external API):

- Location: Add to [miso_client/utils/data_masker.py](miso_client/utils/data_masker.py) or a thin wrapper in `miso_client/__init__.py`
- Behavior: `json.loads()` -> `DataMasker.mask_sensitive_data()` -> `json.dumps()`
- Handles invalid JSON gracefully (return original string or raise, per project conventions)

### 3. Public API Surface


| Symbol                                                | Type     | Purpose                                             |
| ----------------------------------------------------- | -------- | --------------------------------------------------- |
| `DataMasker`                                          | Class    | Main masking interface                              |
| `DataMasker.mask_sensitive_data(data)`                | Method   | Mask dict/list recursively (returns copy)           |
| `DataMasker.mask_value(value, show_first, show_last)` | Method   | Mask individual string                              |
| `DataMasker.is_sensitive_field(key)`                  | Method   | Check if field name is sensitive                    |
| `DataMasker.contains_sensitive_data(data)`            | Method   | Check if data has sensitive fields                  |
| `DataMasker.set_config_path(path)`                    | Method   | Custom sensitive fields config                      |
| `DataMasker.MASKED_VALUE`                             | Constant | `"***MASKED***"`                                    |
| `mask_json(data)`                                     | Function | Optional alias for `DataMasker.mask_sensitive_data` |
| `mask_json_string(json_str)`                          | Function | Optional: mask raw JSON string                      |


### 4. Documentation

- Add a short section to README under "Data Masking" or "Utilities" describing how external projects can use `DataMasker` for JSON masking
- Document `MISO_SENSITIVE_FIELDS_CONFIG` and `DataMasker.set_config_path()` for custom sensitive fields
- Example: masking before logging, before sending to external systems, audit trails

### 5. Testing

- Existing [tests/unit/test_data_masker.py](tests/unit/test_data_masker.py) already covers DataMasker
- Add unit test that imports `DataMasker` from `miso_client` (validates public export)
- If `mask_json_string` is added: add tests for valid JSON, invalid JSON, empty string

## Implementation Options

**Option A (Minimal):** Export only `DataMasker` in `__init__.py`. No new functions.

**Option B (Recommended):** Export `DataMasker` + add `mask_json(data)` as a simple alias for discoverability. No JSON string helper.

**Option C (Full):** Export `DataMasker`, `mask_json`, and `mask_json_string` for both dict/list and raw string use cases.

## Design Notes

- **No breaking changes**: DataMasker stays internal; we only add exports
- **Config**: Same `sensitive_fields_config.json` and `MISO_SENSITIVE_FIELDS_CONFIG` already used for audit logging
- **Return copy**: `mask_sensitive_data` already returns a copy, does not mutate input
- **Input types**: Accepts `dict`, `list`, or primitives; primitives pass through unchanged

---

## Rules and Standards

This plan must comply with [Project Rules](.cursor/rules/project-rules.mdc):

- **[Data Masking (ISO 27001 Compliance)](.cursor/rules/project-rules.mdc#data-masking-iso-27001-compliance)** - Plan exposes DataMasker for masking sensitive fields; uses existing sensitive_fields_config.json and MISO_SENSITIVE_FIELDS_CONFIG
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - Mask sensitive data in logs; DataMasker is the canonical utility
- **[File Organization / Export Strategy](.cursor/rules/project-rules.mdc#file-organization)** - Update `miso_client/__init__.py` and `__all_`_ for public exports
- **[Code Style](.cursor/rules/project-rules.mdc#code-style)** - Any new functions (e.g. `mask_json_string`) require type hints and Google-style docstrings
- **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** - Files ≤500 lines, methods ≤20-30 lines
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - Add test for public import; if `mask_json_string` added, test valid JSON, invalid JSON, edge cases; maintain 80%+ coverage
- **[When Adding New Features](.cursor/rules/project-rules.mdc#when-adding-new-features)** - Update `__init__.py`, write tests, update docs
- **[Documentation](.cursor/rules/project-rules.mdc#documentation)** - Add README section for Data Masking / JSON document masking usage

**Key Requirements:**

- Use DataMasker for all sensitive data masking
- Any new functions: full type hints, Google-style docstrings
- Test public import: `from miso_client import DataMasker`
- If `mask_json_string` added: handle invalid JSON per project conventions (return original or raise)
- Update README with usage examples for external projects

---

## Before Development

- Read Data Masking and Export Strategy sections from project-rules.mdc
- Review existing DataMasker implementation in `miso_client/utils/data_masker.py`
- Review README Data Masking section (lines ~555-568) for consistency
- Decide implementation option (A, B, or C) before coding

---

## Definition of Done

Before marking this plan complete:

1. **Lint**: Run `ruff check` and `mypy` (must pass with zero errors/warnings)
2. **Format**: Run `black` and `isort` (code must be formatted)
3. **Test**: Run `pytest` **after** lint/format (all tests pass, ≥80% coverage for new code)
4. **Validation order**: LINT → FORMAT → TEST (mandatory sequence; never skip steps)
5. **File size**: Files ≤500 lines, methods ≤20-30 lines
6. **Type hints**: All new functions have type hints
7. **Docstrings**: All new public methods have Google-style docstrings
8. **Security**: DataMasker used for masking; no sensitive data exposed
9. **Documentation**: README updated with Data Masking / JSON masking usage
10. All plan tasks completed
11. Test added that imports `DataMasker` from `miso_client`

---

## Plan Validation Report

**Date**: 2025-02-27  
**Plan**: .cursor/plans/34-json_document_masking_interface.plan.md  
**Status**: VALIDATED

### Plan Purpose

Expose the existing DataMasker as a public interface for masking JSON documents in other projects. The SDK uses DataMasker internally for error/logging; this plan adds a public API and optionally a convenience function for raw JSON strings. **Type**: Security (data masking, ISO 27001) + Development (public API).

### Applicable Rules

- [Data Masking (ISO 27001 Compliance)](.cursor/rules/project-rules.mdc#data-masking-iso-27001-compliance) - Plan exposes DataMasker
- [Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines) - Sensitive data masking
- [File Organization](.cursor/rules/project-rules.mdc#file-organization) - Export strategy
- [Code Style](.cursor/rules/project-rules.mdc#code-style) - Type hints, docstrings
- [Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines) - File/method limits
- [Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions) - pytest, coverage
- [When Adding New Features](.cursor/rules/project-rules.mdc#when-adding-new-features) - Update **init**.py, tests, docs
- [Documentation](.cursor/rules/project-rules.mdc#documentation) - README updates

### Rule Compliance

- DoD Requirements: Documented (LINT → FORMAT → TEST, coverage, file size, type hints, docstrings)
- Data Masking: Compliant (uses existing DataMasker)
- Security: Compliant (no new sensitive data exposure)
- Export Strategy: Compliant (add to **init**.py and **all**)
- Testing: Compliant (existing tests + public import test)

### Plan Updates Made

- Added Rules and Standards section with links to project-rules.mdc
- Added Before Development checklist
- Added Definition of Done with LINT → FORMAT → TEST and coverage
- Appended Plan Validation Report

### Recommendations

- Confirm Option A, B, or C before implementation
- If Option C: add `mask_json_string` to `data_masker.py` (keeps masking logic together)
- If adding `mask_json_string`: document invalid-JSON behavior (return original vs raise) in docstring

