# Add parse_pagination_params Function to Miso Client SDK

## Problem

The `miso-client` package currently has `parsePaginationParams` (camelCase) that returns a dictionary `{"currentPage": int, "pageSize": int}`, but the dataplane codebase needs `parse_pagination_params` (snake_case) that returns a tuple `(page, page_size)` to match the pattern of other parsing functions like `parse_filter_params` and `parse_sort_params`.

## Solution

Add a new `parse_pagination_params` function to `miso_client/utils/pagination.py` that:

- Uses snake_case naming (Python convention)
- Returns `tuple[int, int] `with `(page, page_size)` 
- Follows the same validation logic as `parsePaginationParams` but with tuple return
- Is exported from `miso_client/__init__.py`

## Implementation

### 1. Add Function to `miso_client/utils/pagination.py`

Add the new function after the existing `parsePaginationParams` function:

```python
from typing import Any

def parse_pagination_params(params: dict[str, Any]) -> tuple[int, int]:
    """
    Parse pagination parameters from a dictionary.

    This function normalizes pagination parameters, ensuring they are valid integers
    and enforcing minimum values. It follows the same pattern as parse_filter_params
    and parse_sort_params.

    Args:
        params: Dictionary with "page" and "page_size" keys.
                Values can be int, str, or None.

    Returns:
        Tuple of (page, page_size) as integers.

    Defaults:
        - page: 1 if not provided or invalid
        - page_size: 20 if not provided or invalid

    Validation:
        - page must be >= 1 (enforced via max(1, page))
        - page_size must be >= 1 (enforced via max(1, page_size))
        - Invalid values (non-numeric strings, None) default to safe values

    Examples:
        >>> parse_pagination_params({"page": 2, "page_size": 50})
        (2, 50)
        >>> parse_pagination_params({"page": "3", "page_size": "25"})
        (3, 25)
        >>> parse_pagination_params({"page": 1})
        (1, 20)
        >>> parse_pagination_params({})
        (1, 20)
        >>> parse_pagination_params({"page": 0, "page_size": -5})
        (1, 1)
        >>> parse_pagination_params({"page": None, "page_size": "invalid"})
        (1, 20)
    """
    page = params.get("page", 1)
    page_size = params.get("page_size", 20)

    # Convert to int if needed (handles string inputs from query params)
    try:
        page = int(page) if page is not None else 1
    except (ValueError, TypeError):
        page = 1

    try:
        page_size = int(page_size) if page_size is not None else 20
    except (ValueError, TypeError):
        page_size = 20

    # Ensure minimum values (page and page_size must be >= 1)
    page = max(1, page)
    page_size = max(1, page_size)

    return page, page_size
```

### 2. Export Function in `miso_client/__init__.py`

Add to imports from `miso_client/utils/pagination`:

- Line 112: Add `parse_pagination_params` to the import list
- Line 863: Add `"parse_pagination_params"` to `__all__` list (after `"parsePaginationParams"`)

### 3. Add Unit Tests to `tests/unit/test_pagination.py`

Add a new test class `TestParsePaginationParamsSnakeCase` with comprehensive test cases:

```python
class TestParsePaginationParamsSnakeCase:
    """Test cases for parse_pagination_params function (snake_case version)."""

    def test_parse_basic_params(self):
        """Test parsing basic pagination parameters."""
        page, page_size = parse_pagination_params({"page": 2, "page_size": 50})
        assert page == 2
        assert page_size == 50

    def test_parse_string_params(self):
        """Test parsing string parameters."""
        page, page_size = parse_pagination_params({"page": "3", "page_size": "25"})
        assert page == 3
        assert page_size == 25

    def test_parse_with_defaults(self):
        """Test parsing with missing parameters (uses defaults)."""
        page, page_size = parse_pagination_params({})
        assert page == 1
        assert page_size == 20

    def test_parse_with_only_page(self):
        """Test parsing with only page parameter."""
        page, page_size = parse_pagination_params({"page": 2})
        assert page == 2
        assert page_size == 20

    def test_parse_with_only_page_size(self):
        """Test parsing with only page_size parameter."""
        page, page_size = parse_pagination_params({"page_size": 50})
        assert page == 1
        assert page_size == 50

    def test_parse_minimum_values(self):
        """Test parsing with zero and negative values (clamped to 1)."""
        page, page_size = parse_pagination_params({"page": 0, "page_size": -5})
        assert page == 1
        assert page_size == 1

    def test_parse_invalid_values(self):
        """Test parsing with invalid values (defaults applied)."""
        page, page_size = parse_pagination_params({"page": None, "page_size": "invalid"})
        assert page == 1
        assert page_size == 20

    def test_parse_returns_tuple(self):
        """Test that function returns a tuple."""
        result = parse_pagination_params({"page": 1, "page_size": 25})
        assert isinstance(result, tuple)
        assert len(result) == 2
```

### 4. Update Documentation

- Update `README.md` to document the new function alongside `parsePaginationParams`
- Update `CHANGELOG.md` with the new function addition

## Files to Modify

1. **`miso_client/utils/pagination.py`** - Add `parse_pagination_params` function
2. **`miso_client/__init__.py`** - Export `parse_pagination_params` in imports and `__all__`
3. **`tests/unit/test_pagination.py`** - Add comprehensive test cases
4. **`README.md`** - Document the new function
5. **`CHANGELOG.md`** - Add changelog entry

## Rules and Standards

This plan must comply with the following rules from [Project Rules](.cursor/rules/project-rules.mdc):

- **[Code Style](.cursor/rules/project-rules.mdc#code-style)** - Python conventions, type hints, docstrings, snake_case naming
- **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** - File size limits (≤500 lines), method size limits (≤20-30 lines)
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - pytest patterns, test structure, coverage requirements (≥80%)
- **[File Organization](.cursor/rules/project-rules.mdc#file-organization)** - Export strategy, import order, `__all__` usage
- **[Documentation](.cursor/rules/project-rules.mdc#documentation)** - Google-style docstrings for all public methods
- **[Common Patterns](.cursor/rules/project-rules.mdc#common-patterns)** - Pagination pattern, utility function patterns
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - No hardcoded secrets, data masking (not applicable for this utility function)

**Key Requirements**:

- Use snake_case for function names (Python convention)
- Add type hints for all function parameters and return types (`tuple[int, int]`)
- Add Google-style docstrings with Args, Returns, and Examples sections
- Keep function under 20-30 lines (extract helper methods if needed)
- Write comprehensive tests with ≥80% coverage
- Export function in `__init__.py` using `__all__`
- Follow the same pattern as `parse_filter_params` and `parse_sort_params`
- Update README.md and CHANGELOG.md with documentation

## Before Development

- [ ] Read Code Style section from project-rules.mdc (type hints, docstrings, naming conventions)
- [ ] Review existing `parse_filter_params` and `parse_sort_params` functions for pattern consistency
- [ ] Review existing `parsePaginationParams` function to understand validation logic
- [ ] Review existing test patterns in `tests/unit/test_pagination.py`
- [ ] Understand export strategy in `miso_client/__init__.py` (imports and `__all__`)
- [ ] Review Google-style docstring patterns from existing functions

## Definition of Done

Before marking this plan as complete, ensure:

1. **Lint**: Run `ruff check` and `mypy` (must pass with zero errors/warnings)
2. **Format**: Run `black` and `isort` (code must be formatted)
3. **Test**: Run `pytest` AFTER lint/format (all tests must pass, ≥80% coverage for new code)
4. **Validation Order**: LINT → FORMAT → TEST (mandatory sequence, never skip steps)
5. **File Size Limits**: Files ≤500 lines, methods ≤20-30 lines
6. **Type Hints**: All functions have type hints (`dict[str, Any]` → `tuple[int, int]`)
7. **Docstrings**: All public methods have Google-style docstrings with Args, Returns, Examples
8. **Code Quality**: All rule requirements met
9. **Security**: No hardcoded secrets (not applicable for this utility function)
10. **Documentation**: Update README.md and CHANGELOG.md with the new function
11. **Export**: Function exported in `miso_client/__init__.py` (imports and `__all__`)
12. **Tests**: Comprehensive test coverage (≥80%) with edge cases (None, invalid values, defaults)
13. **Pattern Consistency**: Function follows same pattern as `parse_filter_params` and `parse_sort_params`
14. All tasks completed

## Notes

- The existing `parsePaginationParams` (camelCase) function remains unchanged for backward compatibility
- The new function uses snake_case naming to match Python conventions and other parsing functions
- The function returns a tuple `(page, page_size)` which is more Pythonic than returning a dictionary
- Both functions can coexist - `parsePaginationParams` returns dict for API responses, `parse_pagination_params` returns tuple for Python code

## Plan Validation Report

**Date**: 2025-01-27

**Plan**: `.cursor/plans/24-add_parse_pagination_params_function.plan.md`

**Status**: ✅ VALIDATED

### Plan Purpose

Add a snake_case `parse_pagination_params` function that returns a tuple `(page, page_size)` to match the pattern of `parse_filter_params` and `parse_sort_params`. This addresses the ImportError in the dataplane codebase where 21+ files are trying to import this function.

**Plan Type**: Development (Utility Function Addition)

**Affected Areas**: Utils (pagination), Public API exports, Tests, Documentation

### Applicable Rules

- ✅ **[Code Style](.cursor/rules/project-rules.mdc#code-style)** - Python conventions, type hints, docstrings, snake_case naming
- ✅ **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** - File size limits, method size limits (mandatory)
- ✅ **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - pytest patterns, test structure, coverage requirements (mandatory)
- ✅ **[File Organization](.cursor/rules/project-rules.mdc#file-organization)** - Export strategy, import order, `__all__` usage
- ✅ **[Documentation](.cursor/rules/project-rules.mdc#documentation)** - Google-style docstrings for all public methods
- ✅ **[Common Patterns](.cursor/rules/project-rules.mdc#common-patterns)** - Pagination pattern, utility function patterns
- ✅ **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - No hardcoded secrets (mandatory, not applicable for this utility)

### Rule Compliance

- ✅ DoD Requirements: Documented (LINT → FORMAT → TEST sequence, coverage ≥80%, type hints, docstrings)
- ✅ Code Style: Compliant (snake_case naming, type hints, Google-style docstrings)
- ✅ Code Size Guidelines: Compliant (function is under 30 lines, file size limits respected)
- ✅ Testing Conventions: Compliant (comprehensive test cases with edge cases)
- ✅ File Organization: Compliant (export strategy documented)
- ✅ Documentation: Compliant (README.md and CHANGELOG.md updates documented)
- ✅ Common Patterns: Compliant (follows same pattern as `parse_filter_params` and `parse_sort_params`)

### Plan Updates Made

- ✅ Added Rules and Standards section with applicable rule references
- ✅ Added Before Development checklist with prerequisites
- ✅ Added Definition of Done section with mandatory validation steps (LINT → FORMAT → TEST)
- ✅ Added rule references: Code Style, Code Size Guidelines, Testing Conventions, File Organization, Documentation, Common Patterns, Security Guidelines
- ✅ Updated documentation requirements: README.md and CHANGELOG.md updates documented
- ✅ Added validation report with compliance status

### Recommendations

- ✅ Plan is production-ready and compliant with all applicable rules
- ✅ Function implementation follows existing patterns (`parse_filter_params`, `parse_sort_params`)
- ✅ Test coverage is comprehensive with edge cases (None, invalid values, defaults, tuple return type)
- ✅ Documentation updates are clearly specified (README.md and CHANGELOG.md)
- ✅ Export strategy is documented (imports and `__all__` in `__init__.py`)
- ✅ Type hints and docstrings are properly specified in the implementation example