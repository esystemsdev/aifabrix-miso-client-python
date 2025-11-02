<!-- a821f3df-af0b-464c-8fb3-7a38c667f758 3e7501e0-f69f-4ecd-b2b4-ea7e253a7cd3 -->
# Add Reusable Pagination, Filter, Sort Utilities to Python Miso Client SDK

## Overview

Add reusable utilities for pagination, filtering, sorting, and error handling to the existing `miso-client` Python SDK. These utilities will be business-logic-free and reusable across other applications. All utilities use **snake_case** to match Miso/Dataplane API conventions.

## Implementation Details

### 1. Type Definitions (Pydantic Models - snake_case)

**File: `miso_client/models/pagination.py`**

- `Meta` class: `total_items`, `current_page`, `page_size`, `type` (all fields with snake_case aliases)
  - Note: `current_page` maps to `page` query parameter (1-based index)
  - `page_size` maps to `page_size` query parameter
- `PaginatedListResponse[T]` class: `meta`, `data` (generic type support)

**File: `miso_client/models/filter.py`**

- `FilterOperator` type: Literal type with `eq`, `neq`, `in`, `nin`, `gt`, `lt`, `gte`, `lte`, `contains`, `like`
- `FilterOption` class: `field`, `op`, `value` (supports lists/arrays)
- `FilterQuery` class: `filters` (optional list), `sort` (optional list), `page` (optional int), `page_size` (optional int), `fields` (optional list)
- `FilterBuilder` class: Builder pattern for dynamic filter construction

**File: `miso_client/models/sort.py`**

- `SortOption` class: `field`, `order` (Literal `asc` | `desc`)

**File: `miso_client/models/error_response.py`** (enhance existing)

- Keep existing `ErrorResponse` class (supports both camelCase and snake_case via `populate_by_name=True`)
- Add snake_case-specific fields: `status_code` alias for `statusCode`, `request_key` field (optional)
- Ensure all fields support snake_case aliases

### 2. Utility Functions

**File: `miso_client/utils/pagination.py`**

- `parse_pagination_params(params: dict) -> tuple[int, int]`: Parse query params (`page`, `page_size`) to `current_page`, `page_size` (1-based, returns tuple)
- `create_meta_object(total_items: int, current_page: int, page_size: int, type: str) -> Meta`: Construct `Meta` object
- `apply_pagination_to_array(items: list[T], current_page: int, page_size: int) -> list[T]`: Apply pagination to array (for testing/mocks)
- `create_paginated_list_response(items: list[T], total_items: int, current_page: int, page_size: int, type: str) -> PaginatedListResponse[T]`: Wrap array + meta into standard response

**File: `miso_client/utils/filter.py`**

- `parse_filter_params(params: dict) -> list[FilterOption]`: Parse `?filter=field:op:value` into `FilterOption[]`
- `build_query_string(filter_query: FilterQuery) -> str`: Convert `FilterQuery` object to query string
- `apply_filters(items: list[dict], filters: list[FilterOption]) -> list[dict]`: Apply filters to array locally (for testing/mocks)
- `FilterBuilder` class: Builder pattern for dynamic filter construction
  - Methods: `add(field: str, op: FilterOperator, value: Any) -> FilterBuilder`, `add_many(filters: list[FilterOption]) -> FilterBuilder`, `build() -> list[FilterOption]`, `to_query_string() -> str`

**File: `miso_client/utils/sort.py`**

- `parse_sort_params(params: dict) -> list[SortOption]`: Parse `?sort=-field` into `SortOption[]`
- `build_sort_string(sort_options: list[SortOption]) -> str`: Convert `SortOption[]` to query string format

**File: `miso_client/utils/error_utils.py`** (new file)

- `transform_error_to_snake_case(error_data: dict) -> ErrorResponse`: Transform errors to snake_case format
- `handle_api_error_snake_case(response_data: dict, status_code: int, instance: str | None = None) -> MisoClientError`: Handle errors with snake_case response format

### 3. HTTP Client Enhancement

**File: `miso_client/utils/http_client.py`** (enhance existing)

- Keep existing `HttpClient` with audit logging
- Add helper methods for filter builder integration:
  - `async def get_with_filters[T](self, url: str, filter_builder: FilterBuilder | None = None, **kwargs) -> T`: GET request with filter builder
  - `async def get_paginated[T](self, url: str, page: int | None = None, page_size: int | None = None, **kwargs) -> PaginatedListResponse[T]`: GET request with pagination support
- Expose reusable request builder that accepts filter/sort/pagination options

### 4. Integration Points

**File: `miso_client/__init__.py`**

- Export all new models from `models/pagination.py`, `models/filter.py`, `models/sort.py`
- Export enhanced `ErrorResponse` from `models/error_response.py`
- Export all utility functions from `utils/pagination.py`, `utils/filter.py`, `utils/sort.py`, `utils/error_utils.py`
- Export `FilterBuilder` class

**File: `miso_client/models/error_response.py`**

- Ensure backward compatibility with existing `ErrorResponse` (both camelCase and snake_case)
- Add `request_key` field if needed for snake_case support

### 5. Testing Requirements

**Test Files to Create:**

- `tests/unit/test_pagination.py` - Full coverage of pagination utilities
- `tests/unit/test_filter.py` - Full coverage of filter utilities (including FilterBuilder)
- `tests/unit/test_sort.py` - Full coverage of sort utilities
- `tests/unit/test_error_utils.py` - Test snake_case error transformation
- `tests/unit/test_http_client_filters.py` - Test HTTP client filter integration

**Test Coverage Requirements:**

- All utility functions must have 100% branch coverage
- All edge cases: None/empty inputs, empty arrays, invalid operators, malformed query strings
- FilterBuilder: all methods, dynamic filtering, query string building
- Pagination: boundary conditions (page 0, negative page, large page_size)
- Error transformation: both camelCase and snake_case inputs
- Type safety: all tests must pass with proper type hints

### 6. Linting and Type Checking

**Requirements:**

- All code must pass `ruff` with zero warnings or errors
- All code must pass `mypy` type checking with zero errors (with current mypy config)
- All types must be explicitly typed (use type hints, no implicit Any)
- Follow Python conventions:
  - Snake_case for function names and variables (matching API)
  - Pydantic models with `populate_by_name=True` for API compatibility
  - Docstrings for all public functions (Google or NumPy style)
  - Private methods prefixed with `_` for internal logic

**Lint Commands:**

- `ruff check .` - Must pass with zero warnings
- `ruff format .` - Auto-format code
- `mypy miso_client` - Must pass with zero errors (respecting current config)

### 7. Documentation Updates

**Files to Update:**

- `README.md`: Add section on pagination, filtering, sorting utilities
- Create/update `docs/api-reference.md`: Add complete API reference for:
  - `Meta` and `PaginatedListResponse` types
  - `FilterOption`, `FilterQuery`, `FilterBuilder` classes
  - `SortOption` type
  - `ErrorResponse` snake_case support
  - All utility functions with examples

**Documentation Requirements:**

- All public APIs must have docstrings
- All examples must be executable (copy-paste ready)
- All examples must include Python type hints
- Include both simple and advanced use cases

## Key Design Decisions

1. **Naming**: All new utilities use **snake_case** to match Miso/Dataplane API
2. **Filter Builder**: Supports dynamic filter construction with `field`, `op`, `value` pattern
3. **Query String Building**: Filter builder generates query parameters for path and query string
4. **Pydantic Models**: Use Pydantic BaseModel for all type definitions with `populate_by_name=True` for API compatibility
5. **Backward Compatibility**: Enhance existing error handling while maintaining compatibility
6. **Metadata Returns**: Meta class includes `current_page` (maps from `page` query param) and `page_size`
7. **Python Typing**: Use Python 3.8+ type hints with generic types (`list[T]`, `PaginatedListResponse[T]`)
8. **HTTP Client Integration**: Utilities integrate seamlessly with existing `HttpClient` class - query parameters are passed via `params` keyword argument to httpx (already supported via `**kwargs`)
9. **Metadata Filter Compatibility**: The implementation is designed to work with existing metadata endpoints that expect filter/pagination/sort query parameters in the standard format (`?filter=field:op:value&page=1&page_size=25&sort=-field`)

## Files to Create/Modify

**New Files:**

- `miso_client/models/pagination.py`
- `miso_client/models/filter.py`
- `miso_client/models/sort.py`
- `miso_client/utils/pagination.py`
- `miso_client/utils/filter.py`
- `miso_client/utils/sort.py`
- `miso_client/utils/error_utils.py`
- `tests/unit/test_pagination.py`
- `tests/unit/test_filter.py`
- `tests/unit/test_sort.py`
- `tests/unit/test_error_utils.py`
- `tests/unit/test_http_client_filters.py`

**Modified Files:**

- `miso_client/utils/http_client.py` (add filter builder support)
- `miso_client/models/error_response.py` (enhance with snake_case support)
- `miso_client/__init__.py` (export new utilities)
- `README.md` (documentation)

## Example Usage

```python
from miso_client import (
    FilterBuilder,
    parse_pagination_params,
    build_query_string,
    parse_filter_params,
    apply_filters,
    parse_sort_params,
    build_sort_string,
    create_paginated_list_response,
    PaginatedListResponse,
    Meta,
)

# Dynamic filter building (FilterBuilder)
filter_builder = FilterBuilder() \
    .add('status', 'eq', 'active') \
    .add('region', 'in', ['eu', 'us']) \
    .add('created_at', 'gte', '2024-01-01')

query_string = filter_builder.to_query_string()
# ?filter=status:eq:active&filter=region:in:eu,us&filter=created_at:gte:2024-01-01

# Pagination (page query param maps to current_page in Meta)
current_page, page_size = parse_pagination_params({'page': '1', 'page_size': '25'})

# Parse existing query params
filters = parse_filter_params({'filter': ['status:eq:active', 'region:in:eu,us']})
sort_options = parse_sort_params({'sort': '-updated_at'})
sort_string = build_sort_string(sort_options)  # '-updated_at'

# Combined query
combined_query = build_query_string(FilterQuery(
    filters=filter_builder.build(),
    sort=[SortOption(field='updated_at', order='desc')],
    page=1,
    page_size=25
))

# Response with Meta
response: PaginatedListResponse[dict] = PaginatedListResponse(
    meta=Meta(
        total_items=120,
        current_page=1,    # Maps from page query param
        page_size=25,      # From page_size query param
        type='item'
    ),
    data=[...]
)

# Create paginated response
paginated_response = create_paginated_list_response(
    items,
    total_items,
    current_page,
    page_size,
    'item'
)
```

### To-dos

- [ ] Create miso_client/models/pagination.py with Meta and PaginatedListResponse Pydantic models
- [ ] Create miso_client/models/filter.py with FilterOperator, FilterOption, FilterQuery, and FilterBuilder classes
- [ ] Create miso_client/models/sort.py with SortOption Pydantic model
- [ ] Enhance miso_client/models/error_response.py to support snake_case fields (request_key)
- [ ] Create miso_client/utils/pagination.py with parse_pagination_params, create_meta_object, apply_pagination_to_array, create_paginated_list_response functions
- [ ] Create miso_client/utils/filter.py with parse_filter_params, build_query_string, apply_filters, and FilterBuilder class implementation
- [ ] Create miso_client/utils/sort.py with parse_sort_params and build_sort_string functions
- [ ] Create miso_client/utils/error_utils.py with transform_error_to_snake_case and handle_api_error_snake_case functions
- [ ] Enhance miso_client/utils/http_client.py with get_with_filters and get_paginated helper methods
- [ ] Update miso_client/__init__.py to export all new models and utility functions
- [ ] Create tests/unit/test_pagination.py with comprehensive test coverage
- [ ] Create tests/unit/test_filter.py with comprehensive test coverage including FilterBuilder
- [ ] Create tests/unit/test_sort.py with comprehensive test coverage
- [ ] Create tests/unit/test_error_utils.py with tests for snake_case error transformation
- [ ] Create tests/unit/test_http_client_filters.py with tests for HTTP client filter integration
- [ ] Update README.md with documentation for pagination, filtering, and sorting utilities