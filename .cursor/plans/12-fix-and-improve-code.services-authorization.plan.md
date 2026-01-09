# Fix and Improve Code - Services - Authorization

## Overview

This plan addresses code quality issues in the authorization services (`RoleService` and `PermissionService`), focusing on eliminating code duplication and improving maintainability.

## Modules Analyzed

- `miso_client/services/role.py` (299 lines)
- `miso_client/services/permission.py` (307 lines)

## Key Issues Identified

### 1. Code Duplication - Critical Violation

- **Issue**: `_validate_token_request()` method is duplicated identically in both `RoleService` and `PermissionService`
- **Location**: 
  - `miso_client/services/role.py:45-86`
  - `miso_client/services/permission.py:45-86`
- **Impact**: Violates DRY principle, makes maintenance harder, increases risk of inconsistencies
- **Rule Violated**: Code Reuse - "Verify use of reusable utilities from `miso_client/utils/`"

### 2. Similar Cache Pattern Duplication

- **Issue**: Both services have nearly identical cache key generation and cache checking patterns
- **Location**: Both services use `f"roles:{user_id}"` and `f"permissions:{user_id}"` patterns
- **Impact**: Minor duplication, but could be abstracted

### 3. Similar Error Handling Pattern

- **Issue**: Both services have identical error handling with correlation ID extraction
- **Location**: Multiple methods in both services
- **Impact**: Consistent but could be abstracted

## Implementation Tasks

### Task 1: Extract `_validate_token_request` to Shared Utility

**Priority**: High (Critical Code Duplication)

**Description**:

Create a shared utility function in `miso_client/utils/auth_utils.py` (or similar) that can be used by both `RoleService` and `PermissionService` to eliminate the duplicated `_validate_token_request` method.

**Implementation Steps**:

1. Create `miso_client/utils/auth_utils.py` with shared validation utility:
```python
"""
Authentication utilities for shared use across services.
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from ..models.config import AuthStrategy
from ..utils.http_client import HttpClient

if TYPE_CHECKING:
    from ..api import ApiClient


async def validate_token_request(
    token: str,
    http_client: HttpClient,
    api_client: Optional["ApiClient"] = None,
    auth_strategy: Optional[AuthStrategy] = None,
) -> Dict[str, Any]:
    """
    Helper function to call /api/v1/auth/validate endpoint with proper request body.

    Shared utility for RoleService and PermissionService to avoid code duplication.

    Args:
        token: JWT token to validate
        http_client: HTTP client instance (for backward compatibility)
        api_client: Optional API client instance (for typed API calls)
        auth_strategy: Optional authentication strategy

    Returns:
        Validation result dictionary
    """
    if api_client:
        # Use ApiClient for typed API calls
        response = await api_client.auth.validate_token(token, auth_strategy=auth_strategy)
        # Extract data from typed response
        return {
            "success": response.success,
            "data": {
                "authenticated": response.data.authenticated,
                "user": response.data.user.model_dump() if response.data.user else None,
                "expiresAt": response.data.expiresAt,
            },
            "timestamp": response.timestamp,
        }
    else:
        # Fallback to HttpClient for backward compatibility
        if auth_strategy is not None:
            result = await http_client.authenticated_request(
                "POST",
                "/api/v1/auth/validate",
                token,
                {"token": token},
                auth_strategy=auth_strategy,
            )
            return result  # type: ignore[no-any-return]
        else:
            result = await http_client.authenticated_request(
                "POST", "/api/v1/auth/validate", token, {"token": token}
            )
            return result  # type: ignore[no-any-return]
```

2. Update `miso_client/services/role.py`:

   - Remove `_validate_token_request` method (lines 45-86)
   - Import the shared utility: `from ..utils.auth_utils import validate_token_request`
   - Replace all calls to `self._validate_token_request(...)` with `await validate_token_request(..., self.http_client, self.api_client, auth_strategy)`

3. Update `miso_client/services/permission.py`:

   - Remove `_validate_token_request` method (lines 45-86)
   - Import the shared utility: `from ..utils.auth_utils import validate_token_request`
   - Replace all calls to `self._validate_token_request(...)` with `await validate_token_request(..., self.http_client, self.api_client, auth_strategy)`

**Files to Modify**:

- `miso_client/utils/auth_utils.py` (new file)
- `miso_client/services/role.py`
- `miso_client/services/permission.py`

**Testing Requirements**:

- Verify that `RoleService.get_roles()` still works correctly
- Verify that `RoleService.refresh_roles()` still works correctly
- Verify that `RoleService.clear_roles_cache()` still works correctly
- Verify that `PermissionService.get_permissions()` still works correctly
- Verify that `PermissionService.refresh_permissions()` still works correctly
- Verify that `PermissionService.clear_permissions_cache()` still works correctly
- Test with both `api_client` and `http_client` fallback paths
- Test with and without `auth_strategy` parameter

### Task 2: Add Type Hints and Docstrings (If Missing)

**Priority**: Medium

**Description**:

Ensure all methods have proper type hints and Google-style docstrings.

**Current Status**:

Both services already have good type hints and docstrings, but verify completeness.

**Implementation Steps**:

1. Review all methods in both services
2. Ensure all parameters have type hints
3. Ensure all return types are annotated
4. Ensure all methods have Google-style docstrings with Args, Returns, Raises sections

**Files to Modify**:

- `miso_client/services/role.py`
- `miso_client/services/permission.py`

### Task 3: Verify Error Handling Patterns

**Priority**: Low

**Description**:

Both services already follow the correct error handling pattern (return empty list `[]` on errors, use `exc_info=error` in logger.error(), extract correlation IDs). Verify consistency.

**Current Status**:

✅ Both services correctly:

- Return `[]` on errors for list-returning methods
- Use `exc_info=error` in logger.error()
- Extract correlation IDs from errors
- Handle exceptions gracefully

**No changes needed** - this is already correct.

## Testing Requirements

### Unit Tests

- Test `validate_token_request` utility function with both `api_client` and `http_client` paths
- Test `validate_token_request` with and without `auth_strategy`
- Test that RoleService methods still work after refactoring
- Test that PermissionService methods still work after refactoring
- Test error handling paths (API failures, network errors, etc.)

### Integration Tests

- Test end-to-end role retrieval with cache
- Test end-to-end permission retrieval with cache
- Test cache invalidation on refresh
- Test fallback behavior when Redis is unavailable

## Code Quality Metrics

### Before

- **Code Duplication**: 2 identical methods (42 lines duplicated)
- **Maintainability**: Low (changes must be made in 2 places)
- **Test Coverage**: Good (both services tested separately)

### After

- **Code Duplication**: 0 (shared utility)
- **Maintainability**: High (single source of truth)
- **Test Coverage**: Same or better (utility can be tested independently)

## Priority

**High Priority** - Code duplication is a critical maintainability issue that should be addressed immediately.

## Notes

- The shared utility approach maintains backward compatibility
- Both services can continue using their existing patterns
- The utility function can be reused by other services if needed in the future
- This refactoring does not change the public API of either service