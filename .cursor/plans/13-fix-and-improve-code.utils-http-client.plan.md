# Fix and Improve Code - Utils - HTTP Client

## Overview

This plan addresses file size violations in `miso_client/utils/http_client.py` (751 lines, exceeds 500-line limit). The file needs to be split into smaller, focused modules while maintaining the same public API.

## Modules Analyzed

- `miso_client/utils/http_client.py` (751 lines) - **VIOLATION: Exceeds 500-line limit**

## Key Issues Identified

### 1. File Size Violation - Critical

- **Issue**: `http_client.py` has 751 lines, exceeding the 500-line limit by 251 lines (50% over limit)
- **Location**: `miso_client/utils/http_client.py`
- **Impact**: Violates code size guidelines, reduces maintainability, makes code harder to navigate
- **Rule Violated**: Code Size Guidelines - "Keep source files under 500 lines"

### 2. Multiple Responsibilities

- **Issue**: The file contains multiple logical sections:

  1. Logging helpers (lines 74-232)
  2. Request execution helpers (lines 234-288)
  3. HTTP method implementations (lines 290-405)
  4. Token refresh management (lines 406-434)
  5. Authenticated request handling (lines 435-598)
  6. Filter and pagination helpers (lines 599-685)
  7. Filter POST helpers (lines 696-751)

- **Impact**: Violates single responsibility principle, makes testing harder

### 3. Method Size Analysis

- Most methods are appropriately sized (under 20-30 lines)
- Some helper methods could be extracted for better organization

## Implementation Tasks

### Task 1: Extract Logging Helpers to Separate Module

**Priority**: High (Reduces file size by ~160 lines)

**Description**:

Extract logging-related helper methods to `miso_client/utils/http_client_logging_helpers.py` (or similar name to avoid conflict with existing `http_client_logging.py`).

**Methods to Extract**:

- `_handle_logging_task_error()` (lines 74-90)
- `_wait_for_logging_tasks()` (lines 92-110)
- `_calculate_status_code()` (lines 111-132)
- `_extract_user_id_from_headers()` (lines 134-148)
- `_log_debug_if_enabled()` (lines 150-191)
- `_log_http_request()` (lines 193-232)

**Implementation Steps**:

1. Create `miso_client/utils/http_client_logging_helpers.py`:
```python
"""
HTTP client logging helper functions.

Extracted from http_client.py to reduce file size and improve maintainability.
"""

import asyncio
import time
from typing import Any, Dict, Optional

from ..models.config import MisoClientConfig
from ..services.logger import LoggerService
from ..utils.jwt_tools import JwtTokenCache
from .http_client_logging import log_http_request_audit, log_http_request_debug


def handle_logging_task_error(task: asyncio.Task) -> None:
    """
    Handle errors in background logging tasks.

    Silently swallows all exceptions to prevent logging errors from breaking requests.

    Args:
        task: The completed logging task
    """
    try:
        exception = task.exception()
        if exception:
            # Silently swallow logging errors - never break HTTP requests
            pass
    except Exception:
        # Task might not be done yet or other error - ignore
        pass


async def wait_for_logging_tasks(
    logging_tasks: set[asyncio.Task], timeout: float = 0.5
) -> None:
    """
    Wait for all pending logging tasks to complete.

    Useful for tests to ensure logging has finished before assertions.

    Args:
        logging_tasks: Set of logging tasks
        timeout: Maximum time to wait in seconds
    """
    if logging_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*logging_tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # Some tasks might still be running, that's okay
            pass


def calculate_status_code(
    response: Optional[Any], error: Optional[Exception]
) -> Optional[int]:
    """
    Calculate HTTP status code from response or error.

    Args:
        response: Response data (if successful)
        error: Exception (if request failed)

    Returns:
        HTTP status code, or None if cannot determine
    """
    if response is not None:
        return 200
    if error is not None:
        if hasattr(error, "status_code"):
            status_code = getattr(error, "status_code", None)
            if isinstance(status_code, int):
                return status_code
        return 500
    return None


def extract_user_id_from_headers(
    request_headers: Optional[Dict[str, Any]], jwt_cache: JwtTokenCache
) -> Optional[str]:
    """
    Extract user ID from request headers.

    Args:
        request_headers: Request headers dictionary
        jwt_cache: JWT token cache instance

    Returns:
        User ID if found, None otherwise
    """
    if request_headers:
        return jwt_cache.extract_user_id_from_headers(request_headers)
    return None


async def log_debug_if_enabled(
    logger: LoggerService,
    config: MisoClientConfig,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
) -> None:
    """
    Log debug details if debug logging is enabled.

    Args:
        logger: LoggerService instance
        config: MisoClientConfig instance
        method: HTTP method
        url: Request URL
        response: Response data (if successful)
        error: Exception (if request failed)
        start_time: Request start time
        user_id: User ID if available
        request_data: Request body data
        request_headers: Request headers
    """
    if config.log_level != "debug":
        return

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    status_code = calculate_status_code(response, error)
    await log_http_request_debug(
        logger=logger,
        method=method,
        url=url,
        response=response,
        duration_ms=duration_ms,
        status_code=status_code,
        user_id=user_id,
        request_data=request_data,
        request_headers=request_headers,
        base_url=config.controller_url,
        config=config,
    )


async def log_http_request(
    logger: LoggerService,
    config: MisoClientConfig,
    jwt_cache: JwtTokenCache,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
) -> None:
    """
    Log HTTP request with audit and optional debug logging.

    Args:
        logger: LoggerService instance
        config: MisoClientConfig instance
        jwt_cache: JWT token cache instance
        method: HTTP method
        url: Request URL
        response: Response data (if successful)
        error: Exception (if request failed)
        start_time: Request start time
        request_data: Request body data
        request_headers: Request headers
    """
    user_id = extract_user_id_from_headers(request_headers, jwt_cache)

    await log_http_request_audit(
        logger=logger,
        method=method,
        url=url,
        response=response,
        error=error,
        start_time=start_time,
        request_data=request_data,
        user_id=user_id,
        log_level=config.log_level,
        config=config,
    )

    await log_debug_if_enabled(
        logger,
        config,
        method,
        url,
        response,
        error,
        start_time,
        user_id,
        request_data,
        request_headers,
    )
```

2. Update `miso_client/utils/http_client.py`:

   - Remove extracted methods
   - Import helpers: `from .http_client_logging_helpers import ...`
   - Update method calls to use helper functions
   - Pass required dependencies (logger, config, jwt_cache) to helper functions

**Files to Modify**:

- `miso_client/utils/http_client_logging_helpers.py` (new file)
- `miso_client/utils/http_client.py`

**Estimated Reduction**: ~160 lines

### Task 2: Extract Filter and Pagination Helpers

**Priority**: High (Reduces file size by ~90 lines)

**Description**:

Extract filter and pagination helper methods to `miso_client/utils/http_client_query_helpers.py`.

**Methods to Extract**:

- `_parse_filter_query_string()` (if exists)
- `_merge_filter_params()` (if exists)
- `_add_pagination_params()` (lines 613-631)
- `_parse_paginated_response()` (lines 633-650)
- `get_with_filters()` (lines 580-611)
- `get_paginated()` (lines 652-685)
- `post_with_filters()` (lines 696-751)

**Implementation Steps**:

1. Create `miso_client/utils/http_client_query_helpers.py`:
```python
"""
HTTP client query helpers for filters and pagination.

Extracted from http_client.py to reduce file size and improve maintainability.
"""

from typing import Any, Dict, Optional, Union

from ..models.filter import FilterBuilder, FilterQuery, JsonFilter
from ..models.pagination import PaginatedListResponse
from ..utils.filter import build_query_string


def add_pagination_params(
    kwargs: Dict[str, Any], page: Optional[int], page_size: Optional[int]
) -> None:
    """
    Add pagination params to kwargs.

    Args:
        kwargs: Request kwargs dictionary
        page: Optional page number (1-based)
        page_size: Optional number of items per page
    """
    params = kwargs.get("params", {})
    if page is not None:
        params["page"] = page
    if page_size is not None:
        params["pageSize"] = page_size

    if params:
        kwargs["params"] = params


def parse_paginated_response(response_data: Any) -> Any:
    """
    Parse response as PaginatedListResponse if possible.

    Args:
        response_data: Response data from API

    Returns:
        PaginatedListResponse if format matches, otherwise raw response
    """
    try:
        return PaginatedListResponse(**response_data)
    except Exception:
        # If response doesn't match PaginatedListResponse format, return as-is
        # This allows flexibility for different response formats
        return response_data


def prepare_filter_params(filter_builder: Optional[FilterBuilder]) -> Optional[Dict[str, Any]]:
    """
    Prepare filter parameters from FilterBuilder.

    Args:
        filter_builder: Optional FilterBuilder instance

    Returns:
        Dictionary of filter parameters, or None if no filters
    """
    if not filter_builder:
        return None

    from ..models.filter import FilterQuery

    filter_query = FilterQuery(filters=filter_builder.build())
    query_string = build_query_string(filter_query)

    if query_string:
        # Parse query string into params dict
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(f"?{query_string}")
        params = parse_qs(parsed.query)
        # Convert lists to single values where appropriate
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}

    return None


def prepare_json_filter_body(
    json_filter: Optional[Union[JsonFilter, FilterQuery, Dict[str, Any]]],
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Prepare JSON body with filter data.

    Args:
        json_filter: Optional JsonFilter, FilterQuery, or dict
        json_body: Optional existing JSON body

    Returns:
        Dictionary with merged filter and body data
    """
    request_body: Dict[str, Any] = {}
    if json_body:
        request_body.update(json_body)

    if json_filter:
        if isinstance(json_filter, JsonFilter):
            filter_dict = json_filter.model_dump(exclude_none=True)
        elif isinstance(json_filter, FilterQuery):
            filter_dict = json_filter.to_json()
        else:
            filter_dict = json_filter

        request_body.update(filter_dict)

    return request_body
```

2. Update `miso_client/utils/http_client.py`:

   - Remove extracted methods
   - Import helpers: `from .http_client_query_helpers import ...`
   - Update method implementations to use helpers
   - Keep public methods (`get_with_filters`, `get_paginated`, `post_with_filters`) but delegate to helpers

**Files to Modify**:

- `miso_client/utils/http_client_query_helpers.py` (new file)
- `miso_client/utils/http_client.py`

**Estimated Reduction**: ~90 lines

### Task 3: Extract Request Execution Helper

**Priority**: Medium (Reduces file size by ~55 lines)

**Description**:

Extract `_execute_with_logging()` method to a helper module or keep it in `http_client.py` but simplify it.

**Current Status**:

The `_execute_with_logging()` method (lines 234-288) is tightly coupled to `HttpClient` instance state. Consider keeping it in the main file but simplifying it.

**Alternative Approach**:

Keep `_execute_with_logging()` in `http_client.py` but extract the logging task management logic to the logging helpers module.

**Estimated Reduction**: ~30 lines (if extracted)

### Task 4: Verify Method Sizes

**Priority**: Low

**Description**:

Review all methods in `http_client.py` to ensure they comply with the 20-30 line limit.

**Current Status**:

Most methods appear to be appropriately sized. Review `authenticated_request()` method (lines 435-598) - it's 163 lines and should be broken down.

**Implementation Steps**:

1. Break down `authenticated_request()` into smaller helper methods:

   - `_prepare_authenticated_request()` - Prepare headers and token
   - `_handle_401_refresh()` - Handle 401 errors with token refresh
   - `_execute_authenticated_request()` - Execute the actual request

**Estimated Reduction**: Better organization, easier to test

## Testing Requirements

### Unit Tests

- Test all extracted helper functions independently
- Test that `HttpClient` still works correctly after refactoring
- Test that logging helpers work correctly
- Test that filter/pagination helpers work correctly
- Test backward compatibility (public API unchanged)

### Integration Tests

- Test end-to-end HTTP requests with logging
- Test filter and pagination functionality
- Test authenticated requests with token refresh
- Test error handling paths

## Code Quality Metrics

### Before

- **File Size**: 751 lines (exceeds 500-line limit by 251 lines)
- **Responsibilities**: Multiple (logging, request execution, filters, pagination)
- **Maintainability**: Low (hard to navigate large file)

### After

- **File Size**: ~450-500 lines (within limit)
- **Responsibilities**: Single (HTTP client coordination)
- **Maintainability**: High (focused modules, easier to test)

## Priority

**High Priority** - File size violation is a critical code quality issue that should be addressed to improve maintainability.

## Notes

- All public API methods must remain unchanged
- Internal refactoring only - no breaking changes
- Helper modules should be private/internal (not exported in `__init__.py`)
- Consider adding `__all__` exports to control public API
- Test coverage must remain at 80%+ after refactoring