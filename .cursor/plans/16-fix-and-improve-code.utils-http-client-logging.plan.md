# Fix and Improve Code - Utils - HTTP Client Logging

## Overview

This plan addresses file size violations in `miso_client/utils/http_client_logging.py` (646 lines, exceeds 500-line limit). The file provides ISO 27001 compliant audit and debug logging utilities.

## Modules Analyzed

- `miso_client/utils/http_client_logging.py` (646 lines) - **VIOLATION: Exceeds 500-line limit**

## Key Issues Identified

### 1. File Size Violation - Critical

- **Issue**: `http_client_logging.py` has 646 lines, exceeding the 500-line limit by 146 lines (29% over limit)
- **Location**: `miso_client/utils/http_client_logging.py`
- **Impact**: Violates code size guidelines
- **Rule Violated**: Code Size Guidelines - "Keep source files under 500 lines"

### 2. Multiple Responsibilities

- **Issue**: The file contains:

1. Logging skip logic
2. Data masking for logging
3. Audit log formatting
4. Debug log formatting
5. Request/response parsing

- **Impact**: Could be split into focused modules

## Implementation Tasks

### Task 1: Extract Data Masking Helpers

**Priority**: Medium (Reduces file size by ~80 lines)

**Description**:
Extract data masking logic specific to HTTP logging to a separate helper module.

**Methods to Extract**:

- Request/response masking logic
- Header masking logic
- Query parameter masking logic

**Files to Create**:

- `miso_client/utils/http_log_masker.py` (new file)

**Files to Modify**:

- `miso_client/utils/http_client_logging.py`

**Estimated Reduction**: ~80 lines

### Task 2: Extract Log Formatting Helpers

**Priority**: Low (Reduces file size by ~60 lines)

**Description**:
Extract audit and debug log formatting logic to separate helpers.

**Methods to Extract**:

- Audit log entry building
- Debug log entry building
- Request/response formatting

**Files to Create**:

- `miso_client/utils/http_log_formatter.py` (new file)

**Files to Modify**:

- `miso_client/utils/http_client_logging.py`

**Estimated Reduction**: ~60 lines

## Testing Requirements

- Test that logging functions still work correctly after refactoring
- Test data masking independently
- Test log formatting independently
- Test backward compatibility

## Code Quality Metrics

### Before

- **File Size**: 646 lines (exceeds 500-line limit)

### After

- **File Size**: ~500-550 lines (within or close to limit)
- **Maintainability**: Improved (focused modules)

## Priority

**Medium Priority** - File size violation should be addressed, but the file is well-organized and may be acceptable as a utility file.

## Notes

- This is a utility file - refactoring must maintain functionality
- Consider if 646 lines is acceptable for a utility file (may be exception case)
- Focus on extracting clearly separable concerns (masking, formatting)