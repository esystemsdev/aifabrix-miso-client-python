# Changelog

All notable changes to the MisoClient SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.7.0] - 2026-01-09

### Added

- **Enhanced Error Logging with Correlation IDs** - Automatic correlation ID extraction and propagation
  - New `extract_correlation_id_from_error()` utility function to extract correlation IDs from exceptions
  - Correlation IDs automatically extracted from HTTP response headers and included in error responses
  - Service methods now automatically extract and include correlation IDs in error logs
  - HTTP client audit logging includes correlation IDs from error responses
  - Improved traceability from API errors to log entries for easier debugging
  - Public logger methods return `LogEntry` objects with auto-extracted context for custom logger tables

- **Unified JSON Filter Model** - Consistent filtering API for both query strings and JSON bodies
  - New `JsonFilter` model for unified filter representation in JSON format
  - New `FilterGroup` model supporting complex AND/OR logic in filters
  - Support for null check operators (`isNull`, `isNotNull`) for checking null/not-null field values
  - Conversion utilities between query string format and JSON format
  - `FilterQuery` now supports JSON serialization/deserialization
  - New `post_with_filters()` method in HttpClient for JSON body filtering
  - Filter validation when deserializing from JSON
  - Support for nested filter groups with AND/OR operators

- **Redis-Backed Caching for Token Validation** - Improved performance for token validation
  - Token validation results are now cached in Redis with configurable TTL
  - Reduces redundant API calls to controller for token validation
  - Automatic cache invalidation on token expiration
  - Graceful fallback to controller when Redis is unavailable

- **HTTP Client Query Helpers** - Extracted helper utilities for better code organization
  - New `http_client_query_helpers.py` module with filter and pagination utilities
  - Improved code organization and maintainability
  - Better separation of concerns in HTTP client

- **Filter Conversion Utilities** - Enhanced filter manipulation capabilities
  - New utilities for converting between `FilterQuery`, `JsonFilter`, and query strings
  - `filter_query_to_json()` and `json_to_filter_query()` conversion functions
  - `json_filter_to_query_string()` and `query_string_to_json_filter()` utilities
  - Support for bidirectional conversion between formats

### Changed

- **HTTP Client Architecture** - Improved code organization and maintainability
  - Extracted logging helpers to `http_client_logging_helpers.py` module
  - Extracted query helpers to `http_client_query_helpers.py` module
  - Reduced `http_client.py` file size to comply with code size guidelines
  - Better separation of concerns and improved testability

- **Authorization Services** - Code quality improvements and reduced duplication
  - Extracted shared `validate_token_request()` utility to `auth_utils.py`
  - Eliminated code duplication between `RoleService` and `PermissionService`
  - Improved error handling with correlation ID extraction
  - Better code reuse and maintainability

- **Authentication Service** - Enhanced error handling and logging
  - Improved error logging with correlation ID extraction
  - Better integration with error utilities
  - Enhanced token validation error handling

- **Logger Service** - Enhanced logging capabilities
  - Improved error logging with correlation ID extraction
  - Public methods return `LogEntry` objects with auto-extracted context
  - Better support for projects using custom logger tables
  - Enhanced structured logging with correlation IDs

- **Filter Utilities** - Enhanced filter model and validation
  - `FilterQuery` now supports JSON serialization/deserialization
  - Added filter validation utilities
  - Improved filter group support with AND/OR operators
  - Better error messages for invalid filter structures

- **Internal HTTP Client** - Improved error handling
  - Enhanced error response parsing with correlation ID extraction
  - Better integration with error utilities
  - Improved error message generation

- **HTTP Client Logging** - Enhanced audit logging
  - Correlation IDs automatically extracted from error responses
  - Improved error context in audit logs
  - Better traceability for debugging

### Fixed

- **Code Quality** - Fixed linting issues
  - Removed unused imports across multiple files
  - Fixed code style violations
  - Improved code consistency

- **Filter Validation** - Enhanced validation and error handling
  - Better validation for filter structure when deserializing from JSON
  - Improved error messages for invalid filters
  - Better handling of edge cases in filter parsing

### Technical

- **New utility files**:
  - `miso_client/utils/http_client_query_helpers.py` - Filter and pagination query helpers
  - `miso_client/utils/http_client_logging_helpers.py` - HTTP client logging helpers
  - `miso_client/utils/filter_applier.py` - Filter application utilities
  - `miso_client/utils/filter_parser.py` - Filter parsing utilities

- **Enhanced models**:
  - `FilterQuery` - Added JSON serialization/deserialization support
  - `JsonFilter` - New unified JSON filter model
  - `FilterGroup` - New filter group model for complex AND/OR logic

- **Code organization improvements**:
  - Reduced file sizes to comply with code size guidelines
  - Better separation of concerns
  - Improved maintainability and testability

- **Test coverage improvements**:
  - Enhanced test coverage for filter utilities
  - Improved test coverage for logger service
  - Better test organization and structure

## [3.3.0] - 2025-12-23

### Added

- **Centralized API Layer with Typed Interfaces** - New architecture for controller API communication
  - New `ApiClient` class providing centralized access to all controller APIs
  - Domain-specific API classes: `AuthApi`, `RolesApi`, `PermissionsApi`, `LogsApi`
  - Typed request/response models in `miso_client/api/types/` for type safety
  - All API methods use camelCase naming convention for consistency
  - Services now use API layer internally for better separation of concerns
  - Improved maintainability and testability with clear API boundaries

- **User Token Refresh Manager** - Automatic user token refresh with proactive expiration handling
  - New `UserTokenRefreshManager` class for managing user Bearer token refresh
  - Supports multiple refresh mechanisms: callback functions, stored refresh tokens, JWT refresh tokens
  - Proactive token refresh before expiration to prevent 401 errors
  - Automatic retry on 401 errors with token refresh
  - Thread-safe concurrent refresh handling with per-user locks
  - Integrated with `AuthService` for seamless token refresh endpoint calls
  - Exported from main module for advanced use cases

- **Request Context Extraction Utilities** - Standardized request context extraction for HTTP frameworks
  - New `RequestContext` class for structured request metadata
  - New `extract_request_context()` function supporting multiple frameworks
  - Supports FastAPI/Starlette, Flask, and generic dict-like request objects
  - Extracts IP address, correlation ID, HTTP method, path, and user information
  - Handles various header formats and proxy configurations
  - Useful for audit logging and request tracing
  - Exported from main module for framework integration

- **Logging Helpers** - Enhanced logging utilities for structured logging
  - New `miso_client/utils/logging_helpers.py` with helper functions
  - Improved integration with request context for audit logging
  - Better support for correlation IDs and request tracing

- **Enhanced Logger Chain** - Improved fluent API for logging
  - Enhanced `LoggerChain` class with additional context methods
  - Better integration with request context extraction
  - Improved error handling and context propagation

### Changed

- **Service Layer Architecture** - Services now use centralized API layer
  - `AuthService`, `RoleService`, `PermissionService` now use `ApiClient` internally
  - Better separation between service logic and API communication
  - Improved type safety with typed API interfaces
  - Maintains backward compatibility with existing service methods

- **MisoClient Initialization** - Enhanced client initialization
  - `MisoClient` now creates `ApiClient` instance for API access
  - Services receive `ApiClient` instead of direct `HttpClient` access
  - Improved architecture with clear API boundaries

- **Logger Service** - Enhanced logging capabilities
  - Better integration with request context extraction
  - Improved structured logging with indexed fields
  - Enhanced error handling and context propagation

### Technical

- **New API layer files**:
  - `miso_client/api/__init__.py` - API client factory
  - `miso_client/api/auth_api.py` - Authentication API interface
  - `miso_client/api/roles_api.py` - Roles API interface
  - `miso_client/api/permissions_api.py` - Permissions API interface
  - `miso_client/api/logs_api.py` - Logs API interface
  - `miso_client/api/types/` - Typed request/response models

- **New utility files**:
  - `miso_client/utils/user_token_refresh.py` - User token refresh manager
  - `miso_client/utils/request_context.py` - Request context extraction
  - `miso_client/utils/logging_helpers.py` - Logging helper functions

- **New test files**:
  - `tests/unit/test_api_client.py` - API client tests
  - `tests/unit/test_auth_api.py` - Auth API tests
  - `tests/unit/test_roles_api.py` - Roles API tests
  - `tests/unit/test_permissions_api.py` - Permissions API tests
  - `tests/unit/test_logs_api.py` - Logs API tests
  - `tests/unit/test_request_context.py` - Request context tests
  - `tests/unit/test_user_token_refresh.py` - User token refresh tests
  - `tests/unit/test_logging_helpers.py` - Logging helpers tests

- **Exports updated**:
  - `miso_client/__init__.py` - Exports `ApiClient`, `UserTokenRefreshManager`, `RequestContext`, `extract_request_context`
  - Public API maintains snake_case naming convention for functions

- **Package structure**:
  - New `miso_client/api/` package for API layer
  - New `miso_client/api/types/` package for typed interfaces
  - Enhanced service layer with API integration

## [3.2.0] - 2025-12-22

### Added

- **Circuit breaker for HTTP logging** - Prevents infinite retry loops when logging service is unavailable
  - Added circuit breaker pattern to `LoggerService` and `AuditLogQueue`
  - Automatically disables HTTP logging after 3 consecutive failures
  - Circuit breaker opens for 60 seconds after failures, then resets
  - Prevents performance degradation when controller logging endpoint is unavailable
  - Gracefully handles network errors and server unavailability
  - Configurable via `AuditConfig.circuitBreaker` with `failureThreshold` and `resetTimeout`

- **Client token expiration checking** - Enhanced token validation with JWT expiration support
  - Improved `_fetch_client_token()` to check JWT expiration claims when expiration timestamp is missing
  - Decodes JWT tokens to extract `exp` claim for expiration validation
  - Better logging for debugging token expiration issues
  - Handles missing expiration timestamps gracefully
  - Automatically removes expired tokens from cache

- **Controller URL validation utility** - Exported URL validation function
  - `validate_url()` function now exported from `url_validator.py`
  - Validates HTTP/HTTPS URLs with comprehensive checks
  - Rejects dangerous protocols (`javascript:`, `data:`, `file:`, etc.)
  - Useful for validating URLs before use in application code
  - Exported from `miso_client` module for public use

- **Public and Private Controller URL Support** - Separate URLs for browser and server environments
  - New `controllerPublicUrl` configuration option for browser/public environments (accessible from internet)
  - New `controllerPrivateUrl` configuration option for server environments (internal network access)
  - New `resolve_controller_url()` utility function that automatically detects environment and selects appropriate URL
  - New `is_browser()` utility function for environment detection (always returns False for Python SDK)
  - Environment variable support: `MISO_WEB_SERVER_URL` (maps to `controllerPublicUrl` for browser)
  - Environment variable support: `MISO_CONTROLLER_URL` (maps to `controllerPrivateUrl` for server, maintains backward compatibility)
  - Automatic URL resolution based on environment:
    - Server environment: Uses `controllerPrivateUrl` → falls back to `controller_url`
  - URL validation ensures resolved URLs are valid HTTP/HTTPS URLs
  - Clear error messages when no URL is configured
  - `InternalHttpClient` and `AuthService` now use resolved URLs automatically

- **Flask/FastAPI Client Token Endpoint Utilities** - Server-side route handlers for client token endpoints
  - New `create_flask_client_token_endpoint()` function for Flask applications
  - New `create_fastapi_client_token_endpoint()` function for FastAPI applications
  - Automatically enriches response with DataClient configuration including `controllerPublicUrl`
  - Uses `get_environment_token()` with origin validation for security
  - Returns client token + DataClient config to frontend clients
  - Handles errors appropriately: 503 (not initialized), 403 (origin validation), 500 (other errors)
  - Supports optional configuration via `ClientTokenEndpointOptions`
  - Zero-config server-side setup for DataClient initialization
  - Flask and FastAPI are optional peer dependencies (graceful import handling)

### Changed

- **InternalHttpClient** - Now uses `resolve_controller_url()` for automatic URL resolution
  - Constructor uses resolved URL instead of hardcoded `config.controller_url`
  - Client token fetch uses resolved URL for temporary httpx instance
  - Maintains backward compatibility with existing `controller_url` configuration

- **Config Loader** - Enhanced environment variable parsing
  - `MISO_WEB_SERVER_URL` loads into `controllerPublicUrl` (browser/public)
  - `MISO_CONTROLLER_URL` loads into `controllerPrivateUrl` (server/private) and `controller_url` (backward compatibility)
  - Maintains existing behavior for applications using `MISO_CONTROLLER_URL`

- **LoggerService** - Integrated circuit breaker for HTTP logging
  - Checks circuit breaker state before attempting HTTP logging
  - Records success/failure in circuit breaker
  - Skips HTTP logging when circuit is OPEN to prevent infinite retry loops

- **AuditLogQueue** - Integrated circuit breaker for batch logging
  - Checks circuit breaker state before attempting HTTP batch logging
  - Records success/failure in circuit breaker
  - Skips HTTP logging when circuit is OPEN

### Technical

- **New utility files**:
  - `miso_client/utils/circuit_breaker.py` - Circuit breaker implementation
  - `miso_client/utils/url_validator.py` - URL validation utility
  - `miso_client/utils/controller_url_resolver.py` - URL resolution with environment detection
  - `miso_client/utils/flask_endpoints.py` - Flask route handler utilities
  - `miso_client/utils/fastapi_endpoints.py` - FastAPI route handler utilities

- **New test files**:
  - `tests/unit/test_circuit_breaker.py` - Circuit breaker tests
  - `tests/unit/test_url_validator.py` - URL validation tests
  - `tests/unit/test_controller_url_resolver.py` - URL resolution tests
  - `tests/unit/test_flask_endpoints.py` - Flask endpoint tests
  - `tests/unit/test_fastapi_endpoints.py` - FastAPI endpoint tests

- **Exports updated**:
  - `miso_client/__init__.py` - Exports `validate_url`, `resolve_controller_url`, `is_browser`, `create_flask_client_token_endpoint`, `create_fastapi_client_token_endpoint`
  - Public API maintains snake_case naming convention for functions

- **Configuration models updated**:
  - `AuditConfig` - Added `circuitBreaker` field (camelCase)
  - `MisoClientConfig` - Added `controllerPublicUrl` and `controllerPrivateUrl` fields (camelCase)
  - New models: `CircuitBreakerConfig`, `DataClientConfigResponse`, `ClientTokenEndpointResponse`, `ClientTokenEndpointOptions`

- **Package dependencies**:
  - Added optional dependencies: `flask>=2.0.0`, `fastapi>=0.100.0`
  - Flask and FastAPI are peer dependencies (not required unless using endpoint utilities)

## [3.0.1] - 2025-12-14

### Added

- **Server-Side Environment Token Utility**: New `get_environment_token()` function for secure server-side token fetching
  - Validates request origin against configured `allowedOrigins` before fetching token
  - Includes ISO 27001 compliant audit logging with automatic data masking
  - Raises `AuthenticationError` if origin validation fails
  - Supports various request header formats (dict, FastAPI, Flask, Starlette)
  - Exported from main module for easy integration

- **Origin Validation Utility**: New `validate_origin()` function for CORS security
  - Validates request origin against allowed origins list
  - Checks `origin` header first, falls back to `referer` header
  - Supports wildcard port matching (e.g., `http://localhost:*` matches any port)
  - Returns validation result with error message if invalid
  - Handles various request header object types (dict, FastAPI, Flask, Starlette)
  - Exported from main module for reuse in custom middleware

- **Client Token Info Extraction**: New `extract_client_token_info()` function for token introspection
  - Extracts application and environment information from client JWT tokens
  - Decodes JWT without verification (no secret available)
  - Supports multiple field name variations (`application`, `applicationId`, `environment`, `clientId`)
  - Returns dictionary with optional fields for flexible integration
  - Exported from main module for token analysis utilities

- **Configuration Enhancements**: Enhanced `MisoClientConfig` with origin validation support
  - Added `allowedOrigins` configuration field for CORS origin validation
  - Supports wildcard port matching in origin URLs
  - Backward compatible - validation is optional if `allowedOrigins` is not configured

### Changed

- **Internal HTTP Client**: Enhanced `InternalHttpClient` with environment token method
  - Added `get_environment_token()` method for fetching client tokens
  - Integrates with existing client token management infrastructure

- **HTTP Client**: Enhanced `HttpClient` with environment token access
  - Added `get_environment_token()` method delegating to internal client
  - Maintains consistent API surface for token operations

- **MisoClient**: Enhanced main client with environment token access
  - Added `get_environment_token()` method for convenient token access
  - Delegates to `AuthService` for consistent behavior

### Testing

- Added comprehensive unit tests for all new utilities
  - Tests for `get_environment_token()` with origin validation scenarios
  - Tests for `validate_origin()` with various header formats and wildcard matching
  - Tests for `extract_client_token_info()` with different token formats
  - All tests follow existing test patterns with proper mocking

### Technical

- **New Utility Modules**: Added three new utility modules for server-side security
  - `miso_client/utils/environment_token.py`: Server-side token wrapper with audit logging
  - `miso_client/utils/origin_validator.py`: CORS origin validation utility
  - `miso_client/utils/token_utils.py`: Client token introspection utilities

- **Module Exports**: All new utilities exported from main `miso_client` module
  - `get_environment_token`: Server-side token fetching with origin validation
  - `validate_origin`: CORS origin validation utility
  - `extract_client_token_info`: Client token information extraction

## [2.1.2] - 2025-12-11

### Added

- **Login Endpoint Support**: Implemented async `login()` method in `AuthService` and `MisoClient`
  - Makes GET request to `/api/v1/auth/login` with `redirect` (required) and optional `state` query parameters
  - Returns response dictionary with `success`, `data` (containing `loginUrl` and `state`), and `timestamp`
  - Supports CSRF protection via optional `state` parameter
  - Follows service method pattern: returns empty dict `{}` on errors
  - Client token is automatically handled via HTTP client interceptors

- **Logout Endpoint Support**: Enhanced `logout()` method in `AuthService` and `MisoClient`
  - Now accepts `token` parameter (required) for user token invalidation
  - Makes POST request to `/api/v1/auth/logout` with token in request body: `{"token": token}`
  - Uses `authenticated_request()` since it requires user token (Bearer authentication)
  - Returns response dictionary with `success`, `message`, and `timestamp`
  - Follows service method pattern: returns empty dict `{}` on errors

### Changed

- **Breaking Change: AuthService.login()**: Changed from synchronous URL builder to async HTTP request
  - Old: `def login(self, redirect_uri: str) -> str` (synchronous, returns URL string)
  - New: `async def login(self, redirect: str, state: Optional[str] = None) -> Dict[str, Any]` (async, returns response dict)
  - Now makes actual HTTP request to controller instead of just building URL
  - Parameter renamed from `redirect_uri` to `redirect` for consistency with API

- **Breaking Change: AuthService.logout()**: Now requires token parameter
  - Old: `async def logout(self) -> None` (no parameters, backend extracted from client token)
  - New: `async def logout(self, token: str) -> Dict[str, Any]` (requires token, returns response dict)
  - Now sends token in request body for explicit token invalidation
  - Returns response dictionary instead of None

- **Breaking Change: MisoClient.login()**: Updated to match new async signature
  - Old: `def login(self, redirect_uri: str) -> str`
  - New: `async def login(self, redirect: str, state: Optional[str] = None) -> Dict[str, Any]`

- **Breaking Change: MisoClient.logout()**: Updated to require token parameter
  - Old: `async def logout(self) -> None`
  - New: `async def logout(self, token: str) -> Dict[str, Any]`

### Testing

- Added comprehensive unit tests for login and logout methods
  - Test login with state parameter
  - Test login without state parameter (auto-generated by backend)
  - Test login error handling
  - Test logout success scenario
  - Test logout error handling
  - All tests follow existing test patterns with proper mocking

### Migration Guide

**For users upgrading from 2.0.0 or earlier:**

1. **Update login() calls**: Change from synchronous to async and update return value handling

   ```python
   # Old
   login_url = client.login("http://localhost:3000/auth/callback")
   window.location.href = login_url
   
   # New
   response = await client.login(redirect="http://localhost:3000/auth/callback", state="abc123")
   if response.get("success"):
       login_url = response["data"]["loginUrl"]
       state = response["data"]["state"]
       window.location.href = login_url
   ```

2. **Update logout() calls**: Add token parameter and handle response

   ```python
   # Old
   await client.logout()
   
   # New
   token = get_token_from_storage()  # Get user's access token
   response = await client.logout(token=token)
   if response.get("success"):
       print("Logout successful")
   ```

---

## [2.0.0] - 2025-11-24

### Changed

- **Major Version Release**: Version 2.0.0 marks a significant milestone in the MisoClient SDK
  - Improved stability and performance across all services
  - Enhanced error handling and logging capabilities
  - Better integration with Miso Controller API v1 endpoints

---

## [1.9.2] - 2025-11-24

### Changed

- **API Endpoint Versioning**: Updated all API endpoints from `/api/*` to `/api/v1/*` to match the latest Miso Controller API version
  - `/api/auth/login` → `/api/v1/auth/login`
  - `/api/auth/logout` → `/api/v1/auth/logout`
  - `/api/auth/validate` → `/api/v1/auth/validate`
  - `/api/auth/user` → `/api/v1/auth/user`
  - `/api/auth/token` → `/api/v1/auth/token`
  - `/api/auth/roles` → `/api/v1/auth/roles`
  - `/api/auth/roles/refresh` → `/api/v1/auth/roles/refresh`
  - `/api/auth/permissions` → `/api/v1/auth/permissions`
  - `/api/auth/permissions/refresh` → `/api/v1/auth/permissions/refresh`
  - `/api/logs` → `/api/v1/logs`
  - All endpoints now use the `/api/v1/` prefix for consistency with the OpenAPI specification

- **Code Refactoring**: Added `_validate_token_request()` helper method in `AuthService`, `RoleService`, and `PermissionService`
  - Reduces code duplication across services
  - Ensures consistent request body format for token validation
  - Properly sends `{"token": token}` in request body for `/api/v1/auth/validate` endpoint

- **Documentation Updates**: Enhanced `.cursorrules` documentation
  - Improved formatting and structure
  - Updated API endpoint documentation to reflect `/api/v1/*` paths
  - Better code examples and patterns

### Fixed

- **Token Validation Request Body**: Fixed `/api/v1/auth/validate` endpoint to properly send token in request body
  - Previously: Token was sent only in Authorization header
  - Now: Token is sent in both Authorization header and request body `{"token": token}` as required by the API specification

### Added

- **API Validation Tool**: Added `validate_api_calls.py` script and `VALIDATION_REPORT.md`
  - Validates all API calls in the codebase against OpenAPI specification
  - Reports any endpoints used in code but not found in the OpenAPI spec
  - Helps ensure API compatibility before releases
  - Can be run as part of CI/CD pipeline for continuous validation

---

## [1.9.1] - 2025-11-21

### Added

- **camelCase Utility Functions with Backward Compatibility**: New camelCase function names added alongside existing snake_case functions
  - `parsePaginationParams()`: Returns dictionary with `currentPage` and `pageSize` keys (alias: `parse_pagination_params()`)
  - `createMetaObject()`: Creates `Meta` objects with camelCase fields (alias: `create_meta_object()`)
  - `applyPaginationToArray()`: Applies pagination to arrays (alias: `apply_pagination_to_array()`)
  - `createPaginatedListResponse()`: Creates paginated list responses (alias: `create_paginated_list_response()`)
  - `transformError()`: Transforms error dictionaries to `ErrorResponse` objects (alias: `transform_error_to_snake_case()`)
  - `handleApiError()`: Creates `ApiErrorException` from API error responses (alias: `handle_api_error_snake_case()`)
  - `ApiErrorException`: New exception class for API errors (extends `MisoClientError`)
  - All camelCase functions maintain backward compatibility with snake_case aliases

- **Audit Logging Queue**: New `AuditLogQueue` class for batch logging of audit events
  - Queues audit logs and flushes them in batches to Redis or HTTP batch endpoint
  - Configurable batch size and flush interval via `AuditConfig`
  - Automatic batching reduces HTTP overhead for high-volume logging
  - Integrated with `LoggerService` for automatic audit log queuing

- **Audit Configuration**: New `AuditConfig` model for fine-grained audit logging control
  - `enabled`: Enable/disable audit logging (default: `true`)
  - `level`: Audit detail level - `minimal`, `standard`, `detailed`, `full` (default: `detailed`)
  - `maxResponseSize`: Truncate responses larger than this size in bytes (default: `10000`)
  - `maxMaskingSize`: Skip masking for objects larger than this size in bytes (default: `50000`)
  - `batchSize`: Batch size for queued logs (default: `10`)
  - `batchInterval`: Flush interval in milliseconds (default: `100`)
  - `skipEndpoints`: Array of endpoint patterns to exclude from audit logging

- **Audit Logging Performance Optimizations**:
  - Response body truncation based on `maxResponseSize` configuration
  - Size-based masking skip for large objects (prevents performance degradation)
  - Configurable audit levels (minimal, standard, detailed, full)
  - Minimal level: Only metadata, no masking
  - Standard level: Metadata + basic context
  - Detailed level: Full context with request/response sizes
  - Full level: Complete audit trail with all available data

### Changed

- **Pagination Default**: Changed default `pageSize` from `25` to `20` to match TypeScript implementation
  - `parsePaginationParams()` now returns `{"currentPage": 1, "pageSize": 20}` by default
  - `parse_pagination_params()` (legacy) still returns tuple `(1, 20)` for backward compatibility

- **Error Handling**: Enhanced error handling with new `ApiErrorException` class
  - `handleApiError()` now returns `ApiErrorException` instead of `MisoClientError`
  - `ApiErrorException` extends `MisoClientError` with structured error response support
  - Legacy `handle_api_error_snake_case()` still returns `MisoClientError` for backward compatibility

- **HTTP Client Logging**: Improved async logging task management
  - Added `_wait_for_logging_tasks()` helper method for proper async task synchronization
  - Better task tracking and error handling for background logging tasks
  - Improved reliability of audit logging in test environments

- **Audit Log Context**: Enhanced audit context preparation
  - Proper handling of `AuditConfig` objects vs dictionaries
  - Better integration with audit level configurations
  - Improved response body truncation in debug logs based on `maxResponseSize`

### Fixed

- **Audit Logging**: Fixed audit logging not being called in some scenarios
  - Fixed `should_skip_logging()` to properly handle `None` configs
  - Fixed audit config access in `log_http_request_audit()` (was accessing `.level` on dict instead of `AuditConfig` object)
  - Fixed async task completion in tests by adding proper task waiting mechanisms

- **Test Suite**: Fixed all failing tests (19 failures → 0 failures)
  - Updated pagination tests to use new default `pageSize` of 20
  - Fixed HTTP client tests to properly wait for async logging tasks
  - Updated response body truncation test to use `maxResponseSize` from audit config
  - Fixed size calculation tests to use audit level configuration instead of debug mode

### Technical Improvements

- **Type Safety**: Enhanced type hints for all new camelCase functions
- **Backward Compatibility**: All new camelCase functions have snake_case aliases
- **Test Coverage**: All 409 tests passing with 86% code coverage
- **Code Quality**: All linting checks passing

### Migration Guide

**For users upgrading from 1.8.1:**

1. **Optional: Use camelCase Functions**: You can now use camelCase function names if preferred
   - Old: `parse_pagination_params(params)` → New: `parsePaginationParams(params)`
   - Old: `create_meta_object(...)` → New: `createMetaObject(...)`
   - Old: `transform_error_to_snake_case(...)` → New: `transformError(...)`
   - Old: `handle_api_error_snake_case(...)` → New: `handleApiError(...)`
   - Note: All snake_case functions still work (backward compatible)

2. **Configure Audit Logging** (optional): You can now configure audit logging behavior

   ```python
   from miso_client.models.config import AuditConfig, MisoClientConfig
   
   config = MisoClientConfig(
       controller_url="https://controller.example.com",
       client_id="your-client-id",
       client_secret="your-secret",
       audit=AuditConfig(
           enabled=True,
           level="detailed",
           maxResponseSize=5000,
           batchSize=20,
           batchInterval=200
       )
   )
   ```

3. **Handle New Exception Type** (optional): `handleApiError()` now returns `ApiErrorException`
   - Old: `error = handle_api_error_snake_case(...)` → `MisoClientError`
   - New: `error = handleApiError(...)` → `ApiErrorException` (extends `MisoClientError`)
   - Both exception types are compatible, but `ApiErrorException` provides better structured error information

### Testing

- All 409 unit tests passing
- 86% code coverage
- Comprehensive test coverage for all new camelCase functions
- Test coverage for `AuditLogQueue` and audit configuration options
- All audit logging optimizations tested

---

## [1.8.1] - 2025-11-02

### Changed

- **Breaking Change: All Outgoing Data Now Uses camelCase Naming Convention**
  - All Pydantic model fields sent to API now use camelCase (e.g., `pageSize`, `totalItems`, `currentPage`, `userId`, `statusCode`, `correlationId`)
  - All JSON request bodies now use camelCase field names
  - All query parameters now use camelCase (e.g., `pageSize` instead of `page_size`)
  - All response data from API is expected in camelCase format
  - Python code conventions remain snake_case (functions, methods, variables, parameters)

- **Model Field Updates**:
  - `FilterQuery`: Changed `page_size` → `pageSize`
  - `Meta`: Changed `total_items` → `totalItems`, `current_page` → `currentPage`, `page_size` → `pageSize`
  - `ErrorResponse`: Changed `request_key` → `correlationId`, removed `status_code` alias (now only `statusCode`)
  - `LogEntry`: Removed all aliases (already camelCase): `applicationId`, `userId`, `correlationId`, `requestId`, `sessionId`, `stackTrace`, `ipAddress`, `userAgent`
  - `UserInfo`: Removed `first_name`/`last_name` aliases (now only `firstName`/`lastName`)
  - `RoleResult`: Removed `user_id` alias (now only `userId`)
  - `PermissionResult`: Removed `user_id` alias (now only `userId`)
  - `ClientTokenResponse`: Removed `expires_in`/`expires_at` aliases (now only `expiresIn`/`expiresAt`)
  - `PerformanceMetrics`: Removed `start_time`/`end_time`/`memory_usage` aliases (now only `startTime`/`endTime`/`memoryUsage`)
  - `ClientLoggingOptions`: Removed all aliases (already camelCase): `applicationId`, `userId`, `correlationId`, `requestId`, `sessionId`, `maskSensitiveData`, `performanceMetrics`

- **Query Parameter Updates**:
  - `build_query_string()`: Now generates `pageSize` instead of `page_size` in query strings
  - `_add_pagination_params()`: Now adds `pageSize` instead of `page_size` to request parameters
  - `parse_pagination_params()`: Still accepts both `pageSize` and `page_size` for backward compatibility (can parse either format)

- **Utility Function Updates**:
  - `create_meta_object()`: Now creates `Meta` objects with camelCase field names (`totalItems`, `currentPage`, `pageSize`)
  - `error_utils.py`: Updated to handle only camelCase error responses (removed snake_case handling)
  - `transform_error_to_snake_case()`: Function name retained for backward compatibility, but now expects camelCase data
  - `handle_api_error_snake_case()`: Function name retained for backward compatibility, but now expects camelCase data

- **Backward Compatibility Removed**:
  - Removed all `populate_by_name` configs from Pydantic models
  - Removed all snake_case property accessors (e.g., `status_code`, `totalItems`, `currentPage`, `pageSize` properties)
  - Removed all Field aliases that supported snake_case input

### Documentation

- Updated `.cursorrules` with "API Data Conventions (camelCase)" section documenting camelCase requirements
- Updated all test files to use camelCase field names when creating models and accessing fields
- Updated all docstrings and examples to reflect camelCase naming convention

### Migration Guide

**For users upgrading from previous versions:**

1. **Update model field references**: Change all snake_case field access to camelCase
   - Old: `response.meta.total_items` → New: `response.meta.totalItems`
   - Old: `response.meta.current_page` → New: `response.meta.currentPage`
   - Old: `response.meta.page_size` → New: `response.meta.pageSize`
   - Old: `error_response.status_code` → New: `error_response.statusCode`
   - Old: `error_response.request_key` → New: `error_response.correlationId`

2. **Update model instantiation**: Use camelCase field names when creating models
   - Old: `FilterQuery(page_size=25)` → New: `FilterQuery(pageSize=25)`
   - Old: `Meta(total_items=120, current_page=1, page_size=25)` → New: `Meta(totalItems=120, currentPage=1, pageSize=25)`

3. **Update query parameters**: Query strings now use camelCase
   - Old: `?page=1&page_size=25` → New: `?page=1&pageSize=25`

4. **Update JSON request bodies**: All outgoing JSON must use camelCase
   - Old: `{"user_id": "123", "application_id": "app-1"}` → New: `{"userId": "123", "applicationId": "app-1"}`

5. **API responses**: All API responses are expected in camelCase format

### Testing

- Updated all 409 unit tests to use camelCase field names
- All tests passing with 91% code coverage
- Comprehensive test coverage for all model field changes

---

## [0.5.0] - 2025-11-02

### Added

- **Pagination Utilities**: Complete pagination support for list responses
  - `Meta` and `PaginatedListResponse` Pydantic models for standardized paginated responses
  - `parse_pagination_params()` function to parse `page` and `page_size` query parameters
  - `create_meta_object()` function to construct pagination metadata objects
  - `apply_pagination_to_array()` function for local pagination in tests/mocks
  - `create_paginated_list_response()` function to wrap data with pagination metadata
  - Support for both snake_case (`total_items`, `current_page`, `page_size`) and camelCase (`totalItems`, `currentPage`, `pageSize`) attribute access
  - Full type safety with Pydantic models and generic type support

- **Filtering Utilities**: Comprehensive filtering support for API queries
  - `FilterOption`, `FilterQuery`, and `FilterBuilder` classes for building filter queries
  - `FilterOperator` type supporting: `eq`, `neq`, `in`, `nin`, `gt`, `lt`, `gte`, `lte`, `contains`, `like`
  - `parse_filter_params()` function to parse `filter=field:op:value` query parameters
  - `build_query_string()` function to convert `FilterQuery` objects to URL query strings
  - `apply_filters()` function for local filtering in tests/mocks
  - `FilterBuilder` class with fluent API for method chaining (e.g., `FilterBuilder().add('status', 'eq', 'active').add('region', 'in', ['eu', 'us'])`)
  - URL encoding support for field names and values (comma separators preserved for array values)
  - Integration with `/metadata/filter` endpoint through `FilterBuilder` compatibility with `AccessFieldFilter`

- **Sorting Utilities**: Sort parameter parsing and building
  - `SortOption` Pydantic model with `field` and `order` (asc/desc) properties
  - `parse_sort_params()` function to parse `sort=-field` query parameters
  - `build_sort_string()` function to convert `SortOption` lists to query string format
  - Support for multiple sort fields with ascending/descending order
  - URL encoding for field names with special characters

- **Error Handling Utilities**: Enhanced error response transformation and handling
  - `transform_error_to_snake_case()` function for converting error dictionaries to `ErrorResponse` objects
  - `handle_api_error_snake_case()` function for creating `MisoClientError` from API error responses
  - Support for both camelCase and snake_case field names in error responses
  - Automatic parameter overriding (instance and status_code parameters override response data)
  - Graceful handling of missing optional fields (title, instance, request_key)

- **HTTP Client Enhancements**: New helper methods for filtered and paginated requests
  - `get_with_filters()` method for making GET requests with `FilterBuilder` support
  - `get_paginated()` method for making GET requests with pagination parameters
  - Automatic query string building from filter/sort/pagination options
  - Flexible response parsing (returns `PaginatedListResponse` when format matches, raw response otherwise)

- **ErrorResponse Model Enhancements**:
  - Added `request_key` field for error tracking (supports both `request_key` and `correlationId` aliases)
  - Made `title` field optional (defaults to `None`) for graceful handling of missing titles
  - Added `status_code` property getter for snake_case access (complements `statusCode` camelCase field)
  - Full support for both snake_case and camelCase attribute access

- **Model Exports**: All new models and utilities exported from main module
  - Pagination: `Meta`, `PaginatedListResponse`, `parse_pagination_params`, `create_meta_object`, `apply_pagination_to_array`, `create_paginated_list_response`
  - Filtering: `FilterOperator`, `FilterOption`, `FilterQuery`, `FilterBuilder`, `parse_filter_params`, `build_query_string`, `apply_filters`
  - Sorting: `SortOption`, `parse_sort_params`, `build_sort_string`
  - Error: `transform_error_to_snake_case`, `handle_api_error_snake_case`
  - All utilities follow snake_case naming convention matching Miso/Dataplane API conventions

### Changed

- **ErrorResponse Model**: Made `title` field optional to support APIs that don't provide titles
  - Old: `title: str = Field(..., description="Human-readable error title")`
  - New: `title: Optional[str] = Field(default=None, description="Human-readable error title")`
  - Backward compatible - existing code with required titles still works

- **handle_api_error_snake_case Function**: Enhanced parameter override behavior
  - `instance` parameter now overrides instance in response_data (was only set if missing)
  - `status_code` parameter now always overrides status_code in response_data (was only set if missing)
  - Better error message generation when title is missing

### Technical Improvements

- **Type Safety**: Full type hints throughout all new utilities and models
- **Pydantic Models**: All new data structures use Pydantic for validation and serialization
- **Property Getters**: Added property getters to support both snake_case and camelCase attribute access in models
- **URL Encoding**: Smart encoding that preserves comma delimiters in array filter values
- **Comprehensive Tests**: 123 unit tests covering all utilities with 100% coverage for models and utilities
- **Documentation**: Complete README documentation with usage examples for all utilities
- **Snake_case Convention**: All utilities follow Python snake_case naming to match Miso/Dataplane API conventions

### Documentation

- Added comprehensive README section for pagination, filtering, and sorting utilities
- Usage examples for all utilities including combined usage patterns
- Integration examples with `/metadata/filter` endpoint
- Type hints and docstrings for all public APIs

---

## [0.4.0] - 2025-11-02

### Added

- **ISO 27001 Compliant HTTP Client with Automatic Audit and Debug Logging**: New public `HttpClient` class that wraps `InternalHttpClient` with automatic ISO 27001 compliant audit and debug logging
  - Automatic audit logging for all HTTP requests (`http.request.{METHOD}` format)
  - Debug logging when `log_level === 'debug'` with detailed request/response information
  - Automatic data masking using `DataMasker` before logging (ISO 27001 compliant)
  - All request headers are masked (Authorization, x-client-token, Cookie, etc.)
  - All request bodies are recursively masked for sensitive fields (password, token, secret, SSN, etc.)
  - All response bodies are masked (limited to first 1000 characters)
  - Query parameters are automatically masked
  - Error messages are masked if they contain sensitive data
  - Sensitive endpoints (`/api/logs`, `/api/auth/token`) are excluded from audit logging to prevent infinite loops
  - JWT user ID extraction from Authorization headers for audit context
  - Request duration tracking for performance monitoring
  - Request/response size tracking for observability

- **JSON Configuration Support for DataMasker**: Enhanced `DataMasker` with JSON configuration file support for sensitive fields
  - New `sensitive_fields_config.json` file with default ISO 27001 compliant sensitive fields
  - Categories: authentication, pii, security
  - Support for custom configuration path via `MISO_SENSITIVE_FIELDS_CONFIG` environment variable
  - `DataMasker.set_config_path()` method for programmatic configuration
  - Automatic merging of JSON fields with hardcoded defaults (fallback if JSON cannot be loaded)
  - Backward compatible - existing hardcoded fields still work as fallback

- **New InternalHttpClient Class**: Separated core HTTP functionality into `InternalHttpClient` class
  - Pure HTTP functionality with automatic client token management (no logging)
  - Used internally by public `HttpClient` for actual HTTP requests
  - Used by `LoggerService` for sending logs to prevent circular dependencies
  - Not exported in public API (internal use only)

- **New sensitive_fields_loader Module**: Utility module for loading and merging sensitive fields configuration
  - `load_sensitive_fields_config()` function for loading JSON configuration
  - `get_sensitive_fields_array()` function for flattened sensitive fields list
  - `get_field_patterns()` function for pattern matching rules
  - Support for custom configuration paths via environment variables

### Changed

- **Breaking Change: HttpClient Constructor**: Public `HttpClient` constructor now requires `logger` parameter
  - Old: `HttpClient(config)`
  - New: `HttpClient(config, logger)`
  - This is handled automatically when using `MisoClient` - no changes needed for typical usage
  - Only affects code that directly instantiates `HttpClient`

- **Breaking Change: LoggerService Constructor**: `LoggerService` constructor now uses `InternalHttpClient` instead of `HttpClient`
  - Old: `LoggerService(http_client: HttpClient, redis: RedisService)`
  - New: `LoggerService(internal_http_client: InternalHttpClient, redis: RedisService)`
  - This is handled automatically when using `MisoClient` - no changes needed for typical usage
  - Prevents circular dependency (LoggerService uses InternalHttpClient for log sending)

- **MisoClient Architecture**: Updated `MisoClient` constructor to use new HttpClient architecture
  - Creates `InternalHttpClient` first (pure HTTP functionality)
  - Creates `LoggerService` with `InternalHttpClient` (prevents circular dependency)
  - Creates public `HttpClient` wrapping `InternalHttpClient` with logger (adds audit/debug logging)
  - All services now use public `HttpClient` with automatic audit logging

- **DataMasker Enhancement**: Updated `DataMasker` to load sensitive fields from JSON configuration
  - Maintains backward compatibility with hardcoded fields as fallback
  - Automatic loading on first use with caching
  - Support for custom configuration paths

### ISO 27001 Compliance Features

- **Automatic Data Masking**: All sensitive data is automatically masked before logging
  - Request headers: Authorization, x-client-token, Cookie, Set-Cookie, and any header containing sensitive keywords
  - Request bodies: Recursively masks password, token, secret, SSN, creditcard, CVV, PIN, OTP, API keys, etc.
  - Response bodies: Especially important for error responses that might contain sensitive data
  - Query parameters: Automatically extracted and masked
  - Error messages: Masked if containing sensitive data

- **Audit Log Structure**: Standardized audit log format for all HTTP requests
  - Action: `http.request.{METHOD}` (e.g., `http.request.GET`, `http.request.POST`)
  - Resource: Request URL path
  - Context: method, url, statusCode, duration, userId, requestSize, responseSize, error (all sensitive data masked)

- **Debug Log Structure**: Detailed debug logging when `log_level === 'debug'`
  - All audit context fields plus: requestHeaders, responseHeaders, requestBody, responseBody (all masked)
  - Additional context: baseURL, timeout, queryParams (all sensitive data masked)

### Technical Improvements

- Improved error handling: Logging errors never break HTTP requests (all errors caught and swallowed)
- Performance: Async logging that doesn't block request/response flow
- Safety: Sensitive endpoints excluded from audit logging to prevent infinite loops
- Flexibility: Configurable sensitive fields via JSON configuration file

---

## [0.3.0] - 2025-11-01

### Added

- **Structured Error Response Interface**: Added generic `ErrorResponse` model following RFC 7807-style format for consistent error handling across applications
  - `ErrorResponse` Pydantic model with fields: `errors`, `type`, `title`, `statusCode`, `instance`
  - Automatic parsing of structured error responses from HTTP responses in `HttpClient`
  - Support for both camelCase (`statusCode`) and snake_case (`status_code`) field names
  - `MisoClientError` now includes optional `error_response` field with structured error information
  - Enhanced error messages automatically generated from structured error responses
  - Instance URI automatically extracted from request URL when not provided in response
  - Backward compatible - falls back to traditional `error_body` dict when structured format is not available
  - Export `ErrorResponse` from main module for reuse in other applications
  - Comprehensive test coverage for error response parsing and fallback behavior
  - Full type safety with Pydantic models

### Changed

- **Error Handling**: `MisoClientError` now prioritizes structured error information when available
  - Error messages are automatically enhanced from structured error responses
  - Status codes are extracted from structured responses when provided

---

## [0.2.0] - 2025-10-31

### Added

- **API_KEY Support for Testing**: Added optional `API_KEY` environment variable that allows bypassing OAuth2 authentication for testing purposes
  - When `API_KEY` is set in environment, bearer tokens matching the key will automatically validate without OAuth2
  - `validate_token()` returns `True` for matching API_KEY tokens without calling controller
  - `get_user()` and `get_user_info()` return `None` when using API_KEY (by design for testing scenarios)
  - Configuration supports `api_key` field in `MisoClientConfig`
  - Comprehensive test coverage for API_KEY authentication flows
  - Useful for testing without requiring Keycloak setup

- **PowerShell Makefile**: Added `Makefile.ps1` with all development commands for Windows PowerShell users
  - Replaces `dev.bat` and `dev.ps1` scripts with unified PowerShell Makefile
  - Supports all standard development commands (install, test, lint, format, build, etc.)
  - Consistent interface with Unix Makefile

- **Validate Command**: Added new `validate` target to both Makefile and Makefile.ps1
  - Runs lint + format + test in sequence
  - Useful for pre-commit validation and CI/CD pipelines
  - Usage: `make validate` or `.\Makefile.ps1 validate`

### Changed

- **Development Scripts**: Replaced `dev.bat` and `dev.ps1` with `Makefile.ps1` for better consistency
  - All development commands now available through Makefile interface
  - Improved cross-platform compatibility

### Testing

- Added comprehensive test suite for API_KEY functionality
  - Tests for `validate_token()` with API_KEY matching and non-matching scenarios
  - Tests for `get_user()` and `get_user_info()` with API_KEY
  - Tests for config loader API_KEY loading
  - All tests verify OAuth2 fallback behavior when API_KEY doesn't match

---

## [0.1.0] - 2025-10-30

### Added

- **Automatic Client Token Management in HttpClient**: Client tokens are now automatically fetched, cached, and refreshed by the HttpClient
  - Proactive token refresh when < 60 seconds until expiry (30 second buffer before actual expiration)
  - Automatic `x-client-token` header injection for all requests
  - Concurrent token fetch prevention using async locks
  - Automatic token clearing on 401 responses to force refresh
  
- **New Data Models**:
  - `ClientTokenResponse`: Response model for client token requests with expiration tracking
  - `PerformanceMetrics`: Performance metrics model for logging (start time, end time, duration, memory usage)
  - `ClientLoggingOptions`: Advanced logging options with JWT context extraction, correlation IDs, data masking, and performance metrics support
  
- **RedisConfig Enhancement**:
  - Added `db` field to specify Redis database number (default: 0)
  - Supports multi-database Redis deployments

### Changed

- **Module Structure**: Moved type definitions from `miso_client.types.config` to `miso_client.models.config` for better organization
  - All imports now use `from miso_client.models.config import ...`
  - Previous compatibility layer (`types_backup_test`) removed as no longer needed

- **HttpClient Improvements**:
  - Client token management is now fully automatic - no manual token handling required
  - Better error handling with automatic token refresh on authentication failures
  - All HTTP methods (GET, POST, PUT, DELETE) now automatically include client token header

### Technical Improvements

- Improved token expiration handling with proactive refresh mechanism
- Reduced API calls through intelligent token caching
- Better concurrency handling with async locks for token operations
- Enhanced error recovery with automatic token clearing on 401 responses

---

## [0.1.0] - 2025-10-01

### Added

- **Initial Release**: Complete MisoClient SDK implementation
- **Authentication**: JWT token validation and user management
- **Authorization**: Role-based access control (RBAC) with Redis caching
- **Permissions**: Fine-grained permission management with caching
- **Logging**: Structured logging with Redis queuing and HTTP fallback
- **Redis Integration**: Optional Redis caching for improved performance
- **Async Support**: Full async/await support for modern Python applications
- **Type Safety**: Complete type hints and Pydantic models
- **Graceful Degradation**: Works with or without Redis
- **Comprehensive Documentation**: Complete API reference and integration guides
- **Unit Tests**: Full test coverage mirroring TypeScript implementation
- **Package Distribution**: Ready for PyPI distribution with setup.py and pyproject.toml

### Features

#### Core Client

- `MisoClient` main class with initialization and lifecycle management
- Configuration management with `MisoClientConfig` and `RedisConfig`
- Connection state tracking and graceful fallback

#### Authentication Service

- Token validation with controller integration
- User information retrieval
- Login URL generation for web applications
- Logout functionality

#### Role Service

- Role retrieval with Redis caching (15-minute TTL)
- Role checking methods: `has_role`, `has_any_role`, `has_all_roles`
- Role refresh functionality to bypass cache
- Cache key management with user/environment/application scoping

#### Permission Service

- Permission retrieval with Redis caching (15-minute TTL)
- Permission checking methods: `has_permission`, `has_any_permission`, `has_all_permissions`
- Permission refresh functionality to bypass cache
- Cache clearing functionality
- Cache key management with user/environment/application scoping

#### Logger Service

- Structured logging with multiple levels: `info`, `error`, `audit`, `debug`
- Redis queue integration for log batching
- HTTP fallback when Redis is unavailable
- Context-aware logging with metadata support

#### HTTP Client

- Async HTTP client wrapper using httpx
- Automatic header injection (X-Environment, X-Application)
- Authenticated request support with Bearer token
- Error handling and status code management

#### Redis Service

- Async Redis integration using redis.asyncio
- Graceful degradation when Redis is unavailable
- Connection state tracking
- Key prefix support for multi-tenant environments

### Data Models

- `UserInfo`: User information from token validation
- `AuthResult`: Authentication result structure
- `LogEntry`: Structured log entry format
- `RoleResult`: Role query result
- `PermissionResult`: Permission query result
- `MisoClientConfig`: Main client configuration
- `RedisConfig`: Redis connection configuration

### Integration Examples

- **FastAPI**: Complete integration with dependencies and middleware
- **Django**: Middleware, decorators, and view integration
- **Flask**: Decorator-based authentication and authorization
- **Custom Applications**: Dependency injection and service patterns

### Documentation

- **README.md**: Comprehensive SDK documentation with quick start guide
- **API Reference**: Detailed method signatures and parameter descriptions
- **Integration Guide**: Framework-specific integration examples
- **Changelog**: Version history and feature tracking

### Testing

- **Unit Tests**: Comprehensive test coverage for all services
- **Mock Support**: Mock implementations for testing
- **Error Handling**: Test coverage for error scenarios and edge cases
- **Performance Tests**: Concurrent operation testing

### Package Management

- **setup.py**: Traditional Python package configuration
- **pyproject.toml**: Modern Python packaging (PEP 518)
- **Dependencies**: httpx, redis[hiredis], pydantic, pydantic-settings, structlog
- **Development Dependencies**: pytest, black, isort, mypy
- **Python Support**: Python 3.8+ compatibility

### Security

- **Token Handling**: Secure JWT token processing
- **Redis Security**: Password and key prefix support
- **Logging Security**: Careful handling of sensitive information
- **Error Handling**: Graceful error handling without information leakage

### Performance

- **Caching**: Redis-based caching for roles and permissions
- **Connection Pooling**: Efficient HTTP and Redis connection management
- **Async Operations**: Non-blocking async/await throughout
- **Batch Operations**: Support for concurrent operations

### Compatibility

- **Python Versions**: 3.8, 3.9, 3.10, 3.11, 3.12
- **Framework Support**: FastAPI, Django, Flask, and custom applications
- **Redis Versions**: Compatible with Redis 5.0+
- **HTTP Clients**: Uses httpx for modern async HTTP support

### Migration

- **From Keycloak**: Seamless migration from direct Keycloak integration
- **Backward Compatibility**: Maintains existing API patterns
- **Configuration**: Simple configuration migration
- **Testing**: Comprehensive migration testing support

---

## Future Releases

### Planned Features

- **WebSocket Support**: Real-time authentication updates
- **Metrics Integration**: Prometheus and OpenTelemetry support
- **Advanced Caching**: Cache invalidation strategies
- **Multi-Controller Support**: Load balancing across multiple controllers
- **SDK Extensions**: Framework-specific SDK extensions

### Roadmap

- **v1.1.0**: WebSocket support and real-time updates
- **v1.2.0**: Advanced metrics and monitoring
- **v2.0.0**: Multi-controller support and load balancing
- **v2.1.0**: Framework-specific SDK extensions

---

For more information about the MisoClient SDK, visit:

- [Documentation](https://docs.aifabrix.ai/miso-client-python)
- [GitHub Repository](https://github.com/aifabrix/miso-client-python)
- [Issue Tracker](https://github.com/aifabrix/miso-client-python/issues)
