# validate-code

This command analyzes all core code (`miso_client/services`, `miso_client/utils`, `miso_client/models`) against development rules and creates or updates a single detailed improvement plan with the full list of required fixes.

## Purpose

The command:
1. Reads all development rules from the repository-specific cursor rules (`.cursorrules`)
2. Analyzes all core code in:
   - `miso_client/services/` (primary focus - AuthService, RolesService, PermissionsService, LoggerService, RedisService, CacheService, EncryptionService)
   - `miso_client/utils/` (HTTP client, config loader, data masker, internal HTTP client, JWT tools, pagination, filter, sort)
   - `miso_client/models/` (Pydantic models - config, error_response, filter, pagination, sort)
   - `miso_client/__init__.py` (Main MisoClient class exports)
3. Aggregates all findings across modules into a single unified list of required fixes
4. Checks if a plan file already exists with pattern `*-fix-and-improve-code.plan.md`
5. If a plan exists, updates the existing plan file
6. If no plan exists, creates a new plan file with format: `<next-number>-fix-and-improve-code.plan.md`
7. Documents all violations and required improvements based on cursor rules in one plan file

## Usage

Run this command in chat with `/validate-code`

## What It Does

For the single unified plan, the command:

1. **Analyzes Code Reuse**:
   - Checks for code duplication across modules
   - Verifies use of reusable utilities from `miso_client/utils/`
   - Validates proper abstraction of common patterns
   - Checks for forbidden manual implementations (error handling, HTTP operations, token management)
   - Identifies opportunities for shared utility functions
   - Verifies use of existing utility modules where applicable

2. **Analyzes Error Handling**:
   - Verifies proper exception usage with descriptive messages
   - Checks for proper exception propagation
   - Validates error messages are descriptive and user-friendly
   - Checks for proper error context in exceptions
   - Verifies try-except blocks wrap all async operations
   - Validates error handling follows project patterns (services return empty arrays `[]` on error, `None` for single objects)
   - Checks that service methods never raise uncaught errors (catch and return defaults)
   - Verifies use of `exc_info=error` in logger.error() for proper stack traces

3. **Analyzes Logging**:
   - Verifies proper use of logging module (logger.info, logger.error, logger.warning)
   - Checks for proper logging context (user IDs, operation names)
   - Validates logging includes appropriate context
   - Checks that secrets are never logged (use DataMasker)
   - Verifies appropriate log levels (info, error, warning)
   - Validates audit logging for critical operations (ISO 27001 compliance)
   - Checks that logging errors never break HTTP requests (catch and swallow)

4. **Analyzes Type Safety**:
   - Verifies all functions have proper Python type hints (Python 3.8+)
   - Checks for proper return type annotations
   - Validates async function signatures (`async def`)
   - Checks for proper use of Python types (Optional, List, Dict, Union)
   - Verifies Google-style docstrings include Args, Returns, Raises sections
   - Validates proper use of Pydantic models for public APIs
   - Checks for proper type hints throughout (no untyped functions)

5. **Analyzes Async Patterns**:
   - Verifies all async operations use async/await
   - Checks for proper use of async/await (not raw coroutines)
   - Validates proper async context management
   - Verifies API calls use async patterns
   - Validates proper error handling in async functions
   - Checks for proper use of `asyncio.gather()` for concurrent operations

6. **Analyzes HTTP Client Patterns**:
   - Verifies use of `HttpClient` or `InternalHttpClient` for HTTP operations
   - Checks for proper use of `authenticated_request()` for user-authenticated requests
   - Validates use of `request()` for unauthenticated requests (client token automatic)
   - Checks for proper client token management (automatic via interceptors)
   - Verifies proper header usage (`x-client-token` lowercase, `Authorization: Bearer`)
   - Validates proper API endpoint format (`/api/v1/` prefix)
   - Checks for proper use of `get_with_filters()` and `get_paginated()` methods

7. **Analyzes Token Management**:
   - Verifies proper JWT token decoding (not verification - no secret available)
   - Checks for proper userId extraction from tokens (`sub`, `userId`, `user_id`, `id`)
   - Validates client token is fetched automatically via interceptors
   - Checks that client token uses `x-client-token` header (lowercase)
   - Verifies user tokens use `Authorization: Bearer <token>` header
   - Validates token refresh logic
   - Checks for proper use of temporary httpx client for client token fetch (avoid recursion)

8. **Analyzes Redis Caching**:
   - Verifies proper Redis connection checks (`redis.is_connected()`)
   - Checks for proper cache key format (`roles:{userId}`, `permissions:{userId}`)
   - Validates cache format (json.dumps with timestamp)
   - Checks for proper TTL usage (default 900 seconds)
   - Verifies fallback to controller when Redis fails
   - Validates proper error handling for Redis operations
   - Checks that Redis failures don't break requests (graceful fallback)

9. **Analyzes Service Layer Patterns**:
   - Verifies services receive `HttpClient` and `RedisService` as dependencies
   - Checks for proper use of `http_client.config` (public readonly property)
   - Validates services follow constructor pattern
   - Checks for proper separation of concerns
   - Verifies services don't contain HTTP client logic (should use HttpClient)
   - Validates single responsibility principle
   - Checks that services use `self.config = http_client.config` pattern

10. **Analyzes Testing**:
    - Checks for test coverage of core modules
    - Validates test structure mirrors code structure (`tests/unit/`)
    - Verifies all error cases are tested
    - Checks for proper use of pytest mocks (httpx, redis, PyJWT)
    - Validates async test patterns (`@pytest.mark.asyncio`)
    - Verifies tests follow pytest patterns from project rules
    - Checks for proper mocking of HttpClient and RedisService
    - Validates use of `AsyncMock` for async method mocks
    - Verifies tests use `mocker.patch()` for patching dependencies
    - Checks that all tests are properly mocked (no real network calls)

11. **Analyzes Code Quality**:
    - Checks for proper function documentation (Google-style docstrings)
    - Validates code follows Python best practices (PEP 8)
    - Checks for proper variable naming conventions (snake_case)
    - Verifies no hardcoded values (use configuration)
    - Validates proper use of constants (UPPER_SNAKE_CASE)
    - Checks file size limits (≤500 lines per file, ≤20-30 lines per method)
    - Verifies proper code organization and structure
    - Checks for proper import organization (standard library, third-party, internal)

12. **Analyzes Security & Compliance**:
    - Verifies no hardcoded secrets, passwords, or tokens
    - Checks that `clientId` and `clientSecret` are never exposed to client code
    - Validates proper secret management
    - Checks that secrets are never logged or exposed
    - Verifies proper input sanitization
    - Validates audit logging for critical operations (ISO 27001 compliance)
    - Checks for proper data masking using DataMasker
    - Verifies sensitive endpoints are excluded from audit logging

13. **Analyzes API Data Conventions**:
    - Verifies all outgoing data uses camelCase naming convention
    - Checks that Pydantic model fields sent to API use camelCase
    - Validates JSON request bodies use camelCase field names
    - Checks that query parameters use camelCase
    - Verifies Python code uses snake_case (functions, methods, variables)
    - Validates proper transformation between snake_case (Python) and camelCase (API)

14. **Analyzes Model Patterns**:
    - Verifies proper use of Pydantic models for data validation
    - Checks for proper model field definitions
    - Validates proper use of Field() for field configuration
    - Checks for proper model serialization/deserialization
    - Verifies models follow project conventions

15. **Analyzes Utility Patterns**:
    - Verifies utilities are properly organized
    - Checks for proper utility function signatures
    - Validates utilities follow single responsibility principle
    - Checks for proper error handling in utilities
    - Verifies utilities are properly tested

## Output

Creates or updates a single plan file in `.cursor/plans/` with:
- Overview of the overall codebase scope analyzed
- List of all files/modules analyzed
- Detailed violation analysis grouped by category and file
- Specific improvement tasks with file references
- Code examples for fixes
- Testing requirements
- Priority recommendations

**Important**: If a plan file with pattern `*-fix-and-improve-code.plan.md` already exists (e.g., `70-fix-and-improve-code.plan.md`), the command will **update** the existing plan instead of creating a new one. This ensures that progress on the single unified plan is preserved and updated with the latest analysis.

**Execution Behavior**: When generating a new plan, it should be clearly identified as a "code improvement plan and execution". The command should execute improvements automatically without asking for user input or showing progress details, unless there are breaking changes or other critical reasons that require user confirmation. The focus is on silent, automated execution of code improvements based on the analysis.

## Example Plan Structure

```markdown
# Fix and Improve Code - Services - Authentication

## Overview
[Description of the module category and its purpose]

## Modules Analyzed
[List of all files in this category]

## Key Issues Identified
[Summary of main violations]

## Implementation Tasks

### Task 1: Fix Code Duplication
[Detailed task description with code examples showing duplication and how to refactor using miso_client/utils/]

### Task 2: Add Proper Error Handling
[Detailed task description with code examples showing proper exception usage and try-except patterns]

### Task 3: Improve Logging
[Detailed task description with code examples showing proper logging patterns]

### Task 4: Add Type Hints
[Detailed task description with code examples showing proper Python type hints]

### Task 5: Fix Async Patterns
[Detailed task description with code examples showing proper async/await usage]

### Task 6: Add Input Validation
[Detailed task description with code examples showing proper parameter validation]

### Task 7: Improve Security
[Detailed task description with code examples showing secret management and security best practices]

...
```

## Module Categories (Grouping Only)

The unified plan groups findings under these categories for readability, but all fixes live in a single plan file:

### Services - Authentication
- **Services - Authentication**: `miso_client/services/auth.py`, authentication-related services

### Services - Authorization
- **Services - Authorization**: `miso_client/services/role.py`, `miso_client/services/permission.py`

### Services - Logging
- **Services - Logging**: `miso_client/services/logger.py`

### Services - Infrastructure
- **Services - Infrastructure**: `miso_client/services/redis.py`, `miso_client/services/cache.py`, `miso_client/services/encryption.py`

### Utils - HTTP Client
- **Utils - HTTP Client**: `miso_client/utils/http_client.py`, `miso_client/utils/internal_http_client.py`, `miso_client/utils/http_client_logging.py`

### Utils - Configuration
- **Utils - Configuration**: `miso_client/utils/config_loader.py`

### Utils - Data Processing
- **Utils - Data Processing**: `miso_client/utils/data_masker.py`, `miso_client/utils/sensitive_fields_loader.py`

### Utils - Authentication
- **Utils - Authentication**: `miso_client/utils/jwt_tools.py`, `miso_client/utils/token_utils.py`, `miso_client/utils/environment_token.py`, `miso_client/utils/auth_strategy.py`

### Utils - Validation
- **Utils - Validation**: `miso_client/utils/origin_validator.py`

### Utils - Pagination & Filtering
- **Utils - Pagination & Filtering**: `miso_client/utils/pagination.py`, `miso_client/utils/filter.py`, `miso_client/utils/sort.py`

### Utils - Error Handling
- **Utils - Error Handling**: `miso_client/utils/error_utils.py`

### Utils - Audit & Logging
- **Utils - Audit & Logging**: `miso_client/utils/audit_log_queue.py`

### Models - Configuration
- **Models - Configuration**: `miso_client/models/config.py`

### Models - Error Response
- **Models - Error Response**: `miso_client/models/error_response.py`

### Models - Filtering
- **Models - Filtering**: `miso_client/models/filter.py`

### Models - Pagination
- **Models - Pagination**: `miso_client/models/pagination.py`

### Models - Sorting
- **Models - Sorting**: `miso_client/models/sort.py`

### Core
- **Core**: `miso_client/__init__.py`, main MisoClient class

## Notes

- **Existing Plans**: If a plan file matching pattern `*-fix-and-improve-code.plan.md` already exists, it will be updated rather than creating a new one
- **New Plans**: If no existing plan is found, a new plan is created with sequential numbering (starting from biggest number in plan folder plus 1). New plans are **code improvement plans and execution** - they should be executed automatically without user input or progress updates, unless breaking changes or other critical reasons require user confirmation
- **Execution**: Do NOT ask the user for input or show what's being done unless necessary for breaking changes or other critical reasons. The command should execute improvements silently and automatically
- Only one plan file is created or updated
- Plans include actionable tasks with specific file locations and line numbers where applicable
- Plans reference specific cursor rules that are violated
- Focus is on `miso_client/services/` and `miso_client/utils/` as the primary targets, but all core code is analyzed
- The command prioritizes code reuse violations as they are critical for maintainability
- When updating the existing plan, the command preserves the plan number and updates the content with the latest analysis
- All analysis should follow the patterns defined in the repository-specific cursor rules (`.cursorrules`)
- Security and ISO 27001 compliance are critical - all plans must address security concerns
- File size limits (≤500 lines per file, ≤20-30 lines per method) must be checked and enforced
- All public API outputs (Pydantic models, return values) must use camelCase for API data, but Python code uses snake_case
- Python-specific: All functions, methods, and variables use snake_case (not camelCase)
- Python-specific: Classes use PascalCase
- Python-specific: Constants use UPPER_SNAKE_CASE
