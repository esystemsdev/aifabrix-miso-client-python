# Changelog

All notable changes to the MisoClient SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

## [1.2.0] - 2025-10-31

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

## [1.1.0] - 2025-10-30

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

## [1.0.0] - 2025-10-01

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
