# Fix and Improve Code - Utils - Internal HTTP Client

## Overview

This plan addresses file size violations in `miso_client/utils/internal_http_client.py` (666 lines, exceeds 500-line limit). The file handles core HTTP functionality with automatic client token management.

## Modules Analyzed

- `miso_client/utils/internal_http_client.py` (666 lines) - **VIOLATION: Exceeds 500-line limit**

## Key Issues Identified

### 1. File Size Violation - Critical

- **Issue**: `internal_http_client.py` has 666 lines, exceeding the 500-line limit by 166 lines (33% over limit)
- **Location**: `miso_client/utils/internal_http_client.py`
- **Impact**: Violates code size guidelines
- **Rule Violated**: Code Size Guidelines - "Keep source files under 500 lines"

### 2. Multiple Responsibilities

- **Issue**: The file contains:

1. Client token management
2. HTTP request execution
3. Error handling and transformation
4. Auth strategy handling
5. Correlation ID extraction

- **Impact**: Could be split into focused modules

## Implementation Tasks

### Task 1: Extract Client Token Management

**Priority**: High (Reduces file size by ~100 lines)

**Description**:
Extract client token management logic to `miso_client/utils/client_token_manager.py`.

**Methods to Extract**:

- `_get_client_token()` - Token retrieval with caching
- `_fetch_client_token()` - Token fetching logic
- `_extract_correlation_id()` - Correlation ID extraction

**Files to Create**:

- `miso_client/utils/client_token_manager.py` (new file)

**Files to Modify**:

- `miso_client/utils/internal_http_client.py`

**Estimated Reduction**: ~100 lines

### Task 2: Extract Error Handling Utilities

**Priority**: Medium (Reduces file size by ~50 lines)

**Description**:
Extract error handling and transformation logic to `miso_client/utils/http_error_handler.py`.

**Methods to Extract**:

- Error response parsing
- Error transformation logic
- HTTP status error handling

**Files to Create**:

- `miso_client/utils/http_error_handler.py` (new file)

**Files to Modify**:

- `miso_client/utils/internal_http_client.py`

**Estimated Reduction**: ~50 lines

## Testing Requirements

- Test that `InternalHttpClient` still works correctly after refactoring
- Test client token management independently
- Test error handling paths
- Test backward compatibility

## Code Quality Metrics

### Before

- **File Size**: 666 lines (exceeds 500-line limit)

### After

- **File Size**: ~500-550 lines (within or close to limit)
- **Maintainability**: Improved (focused modules)

## Priority

**Medium Priority** - File size violation should be addressed, but the file is well-organized and may be acceptable as a utility file.

## Notes

- This is a core utility file - refactoring must be careful to maintain functionality
- Consider if 666 lines is acceptable for a utility file (may be exception case)
- Focus on extracting clearly separable concerns (token management, error handling)

## Validation

**Date**: 2025-01-09
**Status**: ✅ COMPLETE

### Executive Summary

All implementation tasks have been completed successfully. The file size violation has been resolved by extracting client token management and error handling into separate modules. The main file (`internal_http_client.py`) is now 435 lines (under the 500-line limit), representing a 35% reduction from the original 666 lines. All tests pass and code quality validation succeeds.

**Completion**: 100% (2/2 tasks completed)

### File Existence Validation

- ✅ `miso_client/utils/internal_http_client.py` - EXISTS (435 lines, reduced from 666)
- ✅ `miso_client/utils/client_token_manager.py` - EXISTS (222 lines, new file)
- ✅ `miso_client/utils/http_error_handler.py` - EXISTS (92 lines, new file)
- ✅ `tests/unit/test_http_client.py` - EXISTS (updated with new structure)

### Implementation Completeness

**Task 1: Extract Client Token Management** - ✅ COMPLETE
- ✅ `ClientTokenManager` class created with all required methods:
  - ✅ `get_client_token()` - Token retrieval with caching
  - ✅ `fetch_client_token()` - Token fetching logic
  - ✅ `extract_correlation_id()` - Correlation ID extraction
  - ✅ `clear_token()` - Token clearing method
- ✅ `InternalHttpClient` updated to use `ClientTokenManager`
- ✅ All token management logic extracted (~100 lines)

**Task 2: Extract Error Handling Utilities** - ✅ COMPLETE
- ✅ `parse_error_response()` function created
- ✅ `extract_correlation_id_from_response()` helper function created
- ✅ `InternalHttpClient` updated to use `parse_error_response()`
- ✅ All error handling logic extracted (~50 lines)

### Code Quality Validation

**STEP 1 - FORMAT**: ✅ PASSED
- Files formatted with `black`
- 2 files reformatted (http_error_handler.py, test_http_client.py)
- All files now properly formatted

**STEP 2 - LINT**: ✅ PASSED (0 errors, 0 warnings)
- `ruff check` passed with no errors or warnings
- All code follows linting standards

**STEP 3 - TYPE CHECK**: ✅ PASSED
- `mypy` type checking passed for modified files
- Type errors found in other files (auth.py) are unrelated to this refactoring
- All new code has proper type hints

**STEP 4 - TEST**: ✅ PASSED (46 tests passing)
- All 46 `TestInternalHttpClient` tests pass
- Test execution time: 1.17s (fast, properly mocked)
- Test coverage:
  - `client_token_manager.py`: 84% coverage
  - `http_error_handler.py`: 93% coverage
  - `internal_http_client.py`: 89% coverage

### Code Size Validation

**Before**:
- `internal_http_client.py`: 666 lines ❌ (exceeds 500-line limit)

**After**:
- `internal_http_client.py`: 435 lines ✅ (under 500-line limit)
- `client_token_manager.py`: 222 lines ✅ (under 500-line limit)
- `http_error_handler.py`: 92 lines ✅ (under 500-line limit)

**Reduction**: 231 lines extracted (35% reduction in main file)

### Cursor Rules Compliance

- ✅ **Code reuse**: PASSED - Extracted common functionality into reusable modules
- ✅ **Error handling**: PASSED - Error handling properly extracted and maintained
- ✅ **Logging**: PASSED - No logging changes required
- ✅ **Type safety**: PASSED - All code has proper type hints
- ✅ **Async patterns**: PASSED - All async/await patterns maintained correctly
- ✅ **HTTP client patterns**: PASSED - HTTP client functionality preserved
- ✅ **Token management**: PASSED - Token management properly extracted and maintained
- ✅ **Service layer patterns**: PASSED - Proper dependency injection maintained
- ✅ **Security**: PASSED - No security issues introduced
- ✅ **API data conventions**: PASSED - No API changes
- ✅ **File size guidelines**: PASSED - All files under 500-line limit

### Test Coverage

- ✅ Unit tests exist and updated: `tests/unit/test_http_client.py`
- ✅ All test references updated to use new structure:
  - `http_client.token_manager.*` instead of `http_client._*`
  - `parse_error_response()` imported from module
- ✅ Test coverage: 84-93% for new modules
- ✅ All 46 tests passing
- ✅ Tests properly mock dependencies (httpx, redis, JWT)
- ✅ Tests use async patterns correctly (`@pytest.mark.asyncio`)

### Backward Compatibility

- ✅ Public API unchanged - `InternalHttpClient` interface preserved
- ✅ All existing functionality maintained
- ✅ No breaking changes to method signatures
- ✅ Internal refactoring only (private methods extracted)

### Issues and Recommendations

**None** - Implementation is complete and all validations pass.

### Final Validation Checklist

- [x] All tasks completed (2/2)
- [x] All files exist and are implemented correctly
- [x] Tests exist, updated, and pass (46/46)
- [x] Code quality validation passes (format, lint, type-check, test)
- [x] Cursor rules compliance verified
- [x] File size guidelines met (all files < 500 lines)
- [x] Implementation complete
- [x] Backward compatibility maintained

**Result**: ✅ **VALIDATION PASSED** - All implementation tasks completed successfully. File size violation resolved. Code properly refactored into focused modules with comprehensive test coverage. All code quality checks pass.