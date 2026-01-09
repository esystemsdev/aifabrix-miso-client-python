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