# Fix and Improve Code - Utils - Filter

## Overview

This plan addresses file size violations in `miso_client/utils/filter.py` (576 lines, exceeds 500-line limit). The file provides filter utilities for parsing, building, and applying filters.

## Modules Analyzed

- `miso_client/utils/filter.py` (576 lines) - **VIOLATION: Exceeds 500-line limit**

## Key Issues Identified

### 1. File Size Violation - Critical

- **Issue**: `filter.py` has 576 lines, exceeding the 500-line limit by 76 lines (15% over limit)
- **Location**: `miso_client/utils/filter.py`
- **Impact**: Violates code size guidelines
- **Rule Violated**: Code Size Guidelines - "Keep source files under 500 lines"

### 2. Multiple Responsibilities

- **Issue**: The file contains:

1. Filter parameter parsing
2. Query string building
3. JSON filter conversion
4. Filter validation
5. Filter application to arrays

- **Impact**: Could be split into focused modules

## Implementation Tasks

### Task 1: Extract Filter Parsing Utilities

**Priority**: Medium (Reduces file size by ~100 lines)

**Description**:
Extract filter parsing logic to `miso_client/utils/filter_parser.py`.

**Methods to Extract**:

- `parse_filter_params()` - Parse query parameters
- `parse_filter_string()` - Parse individual filter strings
- Filter string parsing helpers

**Files to Create**:

- `miso_client/utils/filter_parser.py` (new file)

**Files to Modify**:

- `miso_client/utils/filter.py`

**Estimated Reduction**: ~100 lines

### Task 2: Extract Filter Application Utilities

**Priority**: Low (Reduces file size by ~50 lines)

**Description**:
Extract filter application logic to `miso_client/utils/filter_applier.py`.

**Methods to Extract**:

- `apply_filters()` - Apply filters to arrays
- Filter matching logic
- Operator evaluation

**Files to Create**:

- `miso_client/utils/filter_applier.py` (new file)

**Files to Modify**:

- `miso_client/utils/filter.py`

**Estimated Reduction**: ~50 lines

## Testing Requirements

- Test that filter utilities still work correctly after refactoring
- Test filter parsing independently
- Test filter application independently
- Test backward compatibility

## Code Quality Metrics

### Before

- **File Size**: 576 lines (exceeds 500-line limit)

### After

- **File Size**: ~400-450 lines (within limit)
- **Maintainability**: Improved (focused modules)

## Priority

**Medium Priority** - File size violation is minor (only 15% over limit), but should be addressed for consistency.

## Notes

- This is a utility file - refactoring must maintain functionality
- The file is close to the limit (only 76 lines over)
- Focus on extracting clearly separable concerns (parsing, application)