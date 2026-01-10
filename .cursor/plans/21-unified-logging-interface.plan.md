# Unified Logging Interface - SDK Enhancement (Python)

## Overview

Enhance the miso-client SDK with a unified logging interface that provides a minimal API (1-3 parameters maximum) with automatic context extraction. This enables simple, consistent logging across all applications using the SDK without requiring manual context passing.

## Rules and Standards

This plan must comply with the following rules from [Project Rules](.cursor/rules/project-rules.mdc):

- **[Architecture Patterns - Service Layer](.cursor/rules/project-rules.mdc#service-layer)** - Service structure, dependency injection, configuration access. UnifiedLogger service follows service layer patterns.
- **[Architecture Patterns - Logger Chain Pattern](.cursor/rules/project-rules.mdc#logger-chain-pattern)** - Fluent API patterns, context chaining, error handling in logger.
- **[Code Style - Python Conventions](.cursor/rules/project-rules.mdc#python-conventions)** - Use type hints throughout, snake_case for functions/methods/variables, PascalCase for classes, Pydantic models for public APIs.
- **[Code Style - Error Handling](.cursor/rules/project-rules.mdc#error-handling)** - Services return empty lists `[]` on errors (get methods), return `None` on errors (single object methods), use try-except for all async operations, log errors with `exc_info=error`.
- **[Code Style - Async/Await](.cursor/rules/project-rules.mdc#asyncawait)** - Always use async/await, try-except for async operations, proper error handling.
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - pytest patterns, test structure, 80%+ coverage, mock all external dependencies (httpx, redis, PyJWT).
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - ISO 27001 compliance, PII masking, never expose secrets, proper token handling.
- **[Code Quality Standards](.cursor/rules/project-rules.mdc#code-size-guidelines)** - File size limits (≤500 lines), method size limits (≤20-30 lines), Google-style docstrings.
- **[File Organization](.cursor/rules/project-rules.mdc#file-organization)** - Source structure, import order, export strategy.
- **[Documentation](.cursor/rules/project-rules.mdc#documentation)** - Google-style docstrings for public methods, parameter types, return types, error conditions.

**Key Requirements**:

- Services receive `HttpClient` and `RedisService` as dependencies
- Services use `http_client.config` (public readonly property) for configuration access
- Use Pydantic models for public API definitions (LoggerContext model)
- All public API outputs use camelCase (no snake_case) - **Exception**: Python code uses snake_case
- Add Google-style docstrings for all public functions with parameter types and return types
- Keep files ≤500 lines and methods ≤20-30 lines
- Error handling in logger should be silent (catch and swallow)
- Always log errors with comprehensive context (IP, endpoint, user, status code, stack trace)
- Use try-except for all async operations
- Write tests with pytest, mock all external dependencies (contextvars, LoggerService)
- Aim for 80%+ branch coverage
- Never expose `clientId` or `clientSecret` in client code
- Mask sensitive data in logs (use DataMasker)
- Export only what's needed in `miso_client/__init__.py`
- Update documentation in `docs/` directory (if exists)

## Before Development

- [ ] Read Architecture Patterns - Service Layer section from project-rules.mdc
- [ ] Review existing LoggerService implementation for patterns
- [ ] Review existing context extraction utilities (`extract_request_context`, `extract_jwt_context`)
- [ ] Review existing DataMasker for PII masking patterns
- [ ] Understand contextvars API (Python 3.7+)
- [ ] Review FastAPI/Flask middleware patterns (if applicable)
- [ ] Review error handling patterns and RFC 7807 compliance
- [ ] Understand testing requirements and mock patterns (contextvars mocking)
- [ ] Review Google-style docstring documentation patterns in existing services
- [ ] Review file organization and export patterns
- [ ] Review documentation structure (if exists)

## Definition of Done

Before marking this plan as complete, ensure:

1. **Lint**: Run `make lint` or `ruff check` (must pass with zero errors/warnings)
2. **Test**: Run `make test` or `pytest` (all tests must pass, ≥80% coverage for new code)
3. **Type Check**: Run `mypy` (if configured, must pass)
4. **Validation Order**: LINT → TEST → TYPE CHECK (mandatory sequence, never skip steps)
5. **File Size Limits**: Files ≤500 lines, methods ≤20-30 lines
6. **Docstring Documentation**: All public functions have Google-style docstrings with parameter types and return types
7. **Code Quality**: All rule requirements met
8. **Security**: No hardcoded secrets, ISO 27001 compliance, proper token handling, PII masking
9. **Error Handling**: Use try-except for all async operations, error handling in logger should be silent
10. **Python Conventions**: Use type hints throughout, snake_case for functions/methods/variables, PascalCase for classes
11. **Naming Conventions**: All public API outputs use camelCase (no snake_case) - **Exception**: Python code uses snake_case
12. **Testing**: Unit tests with 80%+ coverage, integration tests for FastAPI/Flask middleware (if applicable), mock all dependencies
13. **Documentation**: Update documentation as needed (README, API docs, guides, usage examples)
14. **Exports**: Export only what's needed in `miso_client/__init__.py`
15. **Context Extraction**: Automatic context extraction from contextvars works correctly
16. **Framework Middleware**: Middleware sets context correctly and works seamlessly with FastAPI/Flask/Starlette
17. **Context Propagation**: Context propagation works across async boundaries
18. **All Tasks Completed**: All implementation tasks marked as complete

## Design Goals

1. **Minimal Interface**: Maximum 1-3 parameters per logging call
2. **Automatic Context Extraction**: Context extracted automatically via contextvars
3. **Simple API**: `logger.info(message)`, `logger.error(message, error?)`, `logger.audit(action, entity_type, entity_id?, old_values?, new_values?)`
4. **Framework Agnostic**: Works in FastAPI routes, Flask routes, service layers, background jobs
5. **Zero Configuration**: Context automatically available when middleware is used
6. **Leverage Existing Code**: Reuse existing context extraction, JWT handling, PII masking

## Current State

### What Already Exists in SDK ✅

- **Context Extraction**: `extract_request_context()`, `extract_jwt_context()` (via `logger_helpers.py`)
- **PII Masking**: `DataMasker` for automatic sensitive data masking
- **JWT Handling**: Token extraction and decoding utilities (`jwt_tools.py`)
- **LoggerService**: Core logging service with Redis/HTTP/Event emission support
- **LoggerChain**: Fluent API for method chaining

### What's Missing ❌

- **contextvars Context Storage**: No mechanism to store context without Request objects
- **UnifiedLogger Class**: No simplified interface with minimal parameters
- **get_logger() Factory**: No factory function that auto-detects available context
- **Context Propagation**: No way to propagate context across async boundaries without Request objects
- **Framework Middleware**: No middleware helpers for FastAPI/Flask/Starlette

## Service Interface

### Core Interface

```python
class UnifiedLogger:
    """
    Unified logger with minimal API and automatic context extraction.
    
    Provides a simplified interface for logging with automatic context
    extraction from contextvars. Works seamlessly in web frameworks,
    service layers, and background jobs.
    """
    
    async def info(self, message: str) -> None:
        """
        Log info message.
        
        Args:
            message: Info message
        """
        ...
    
    async def warn(self, message: str) -> None:
        """
        Log warning message.
        
        Args:
            message: Warning message
        """
        ...
    
    async def debug(self, message: str) -> None:
        """
        Log debug message.
        
        Args:
            message: Debug message
        """
        ...
    
    async def error(self, message: str, error: Optional[Exception] = None) -> None:
        """
        Log error message.
        
        Args:
            message: Error message
            error: Optional error object (auto-extracts stack trace)
        """
        ...
    
    async def audit(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log audit event.
        
        Args:
            action: Action performed (e.g., 'create', 'update', 'delete', 'access')
                Must be lowercase to match backend schema requirements.
            entity_type: Entity type (e.g., 'User', 'Tenant', 'Order')
                Maps to entityType in backend schema.
            entity_id: Optional entity ID (defaults to 'unknown')
                Maps to entityId in backend schema.
            old_values: Optional old values for UPDATE operations (ISO 27001 requirement)
                Maps to oldValues in backend schema (camelCase).
            new_values: Optional new values for CREATE/UPDATE operations (ISO 27001 requirement)
                Maps to newValues in backend schema (camelCase).
        """
        ...
```

### Usage Examples

#### FastAPI Route Handler

```python
from miso_client import get_logger

@app.get("/api/users")
async def get_users(request: Request):
    logger = get_logger()  # Auto-detects context from contextvars
    
    await logger.info("Users list accessed")  # Auto-extracts request context
    
    users = await fetch_users()
    return users
```

#### Service Layer

```python
from miso_client import get_logger

class UserService:
    async def get_user(self, user_id: str):
        logger = get_logger()  # Uses contextvars context if available
        
        await logger.info("Fetching user")  # Auto-extracts context if available
        
        try:
            user = await db.user.find_unique({"id": user_id})
            await logger.audit("access", "User", user_id)  # Read access audit
            return user
        except Exception as error:
            await logger.error("Failed to fetch user", error)  # Auto-extracts error details
            raise
```

#### Background Job

```python
from miso_client import get_logger, set_logger_context

async def background_job():
    # Set context for this async execution context
    set_logger_context({
        "userId": "system",
        "correlationId": "job-123",
        "ipAddress": "127.0.0.1",
    })
    
    logger = get_logger()
    await logger.info("Background job started")
    
    # All logs in this async context will use the set context
    await process_data()
```

## Implementation Architecture

### Context Management Strategy

1. **contextvars**: Use contextvars to store request context per async execution context

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Context set by FastAPI/Flask middleware or manually via `set_logger_context()`
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Automatically available to all code in the same async context
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No need to pass Request objects around

2. **Manual Context**: Allow manual context setting for cases without request context

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `set_logger_context()` function for manual context setting
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Useful for background jobs, scheduled tasks, etc.

### Context Extraction Priority

1. **contextvars**: When context is set via middleware or `set_logger_context()`
2. **Default Context**: Minimal context with application name only (when no context available)

### Context Fields Automatically Extracted

- `ipAddress` - Client IP address (from request.client.host or request.remote_addr)
- `userAgent` - User agent string (from User-Agent header)
- `correlationId` - Request correlation ID (from x-correlation-id header or auto-generated)
- `userId` - Authenticated user ID (from JWT token or x-user-id header)
- `sessionId` - Session ID (from JWT token or x-session-id header)
- `method` - HTTP method (GET, POST, etc.)
- `path` - Request path
- `hostname` - Request hostname (from Host header)
- `applicationId` - Application identifier (from JWT token or x-application-id header)

### Leveraging Existing SDK Features

**Reuse Existing Functionality**:

1. **JWT Token Handling** ✅ Already exists:

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Use `extract_jwt_context()` from `logger_helpers.py` - Extracts userId, sessionId, applicationId from JWT
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Use existing token extraction from Request headers
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No need to reimplement JWT parsing

2. **Context Extraction** ✅ Already exists:

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Use `extract_request_context()` from `request_context.py` - Extracts IP, method, path, userAgent, correlationId
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Use `extract_metadata()` from `logger_helpers.py` - Extracts hostname, userAgent from environment
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No need to reimplement request parsing

3. **PII Masking** ✅ Already exists:

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Use `DataMasker.mask_sensitive_data()` - Automatic PII masking
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No need to reimplement data masking

4. **LoggerService** ✅ Already exists:

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Use existing `LoggerService` for actual log emission
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - UnifiedLogger wraps LoggerService with simplified interface
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No need to reimplement logging logic

## Implementation Plan

### Phase 1: Create contextvars Context Storage

**File**: `miso_client/utils/logger_context_storage.py`

Create contextvars-based context storage:

- Store request context per async execution context
- Provide methods to get/set/clear context
- Support context merging with additional fields
- Thread-safe context access

**Key Functions**:

- `get_logger_context() -> Optional[LoggerContext]` - Get current context
- `set_logger_context(context: Dict[str, Any]) -> None` - Set context for current async context
- `clear_logger_context() -> None` - Clear context
- `merge_logger_context(additional: Dict[str, Any]) -> None` - Merge additional fields

**Type Definition**:

```python
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variable for storing logger context
_logger_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "logger_context", default=None
)

class LoggerContextStorage:
    """
    Context storage for logger context using contextvars.
    
    Provides thread-safe context storage per async execution context.
    """
    
    @staticmethod
    def get_context() -> Optional[Dict[str, Any]]:
        """Get current logger context."""
        ...
    
    @staticmethod
    def set_context(context: Dict[str, Any]) -> None:
        """Set logger context for current async context."""
        ...
    
    @staticmethod
    def clear_context() -> None:
        """Clear logger context."""
        ...
    
    @staticmethod
    def merge_context(additional: Dict[str, Any]) -> None:
        """Merge additional fields into current context."""
        ...
```

### Phase 2: Create UnifiedLogger Service

**File**: `miso_client/services/unified_logger.py`

Create `UnifiedLogger` service that:

- Implements the minimal interface (1-3 parameters max)
- Automatically extracts context from contextvars
- Uses existing `LoggerService` for actual log emission
- Auto-extracts error details (stack trace, error name, error message)

**Implementation Pattern**:

```python
from typing import Any, Dict, Optional
import traceback

from ..services.logger import LoggerService
from ..utils.logger_context_storage import LoggerContextStorage
from ..models.config import ClientLoggingOptions

class UnifiedLogger:
    """
    Unified logger with minimal API and automatic context extraction.
    """
    
    def __init__(self, logger_service: LoggerService):
        """
        Initialize unified logger.
        
        Args:
            logger_service: LoggerService instance for log emission
        """
        self.logger_service = logger_service
        self.context_storage = LoggerContextStorage()
    
    async def info(self, message: str) -> None:
        """Log info message."""
        context = self._get_context()
        options = self._build_options(context)
        await self.logger_service.info(message, context=None, options=options)
    
    async def error(self, message: str, error: Optional[Exception] = None) -> None:
        """Log error message."""
        context = self._get_context()
        error_context = self._extract_error_context(error) if error else {}
        options = self._build_options(context)
        
        stack_trace = None
        if error:
            stack_trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        
        await self.logger_service.error(
            message,
            context={**context, **error_context},
            stack_trace=stack_trace,
            options=options,
        )
    
    async def audit(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log audit event.
        
        Maps parameters to backend schema:
        - entity_type → entityType (required)
        - entity_id → entityId (required, defaults to 'unknown')
        - action → action (required, must be lowercase: 'create', 'update', 'delete', 'access')
        - old_values → oldValues (optional, camelCase)
        - new_values → newValues (optional, camelCase)
        """
        context = self._get_context()
        # Normalize action to lowercase (backend requirement)
        normalized_action = action.lower() if action else "unknown"
        
        # Build audit context matching backend schema
        audit_context = {
            "action": normalized_action,
            "entityType": entity_type,  # Maps to backend entityType field
            "entityId": entity_id or "unknown",  # Maps to backend entityId field
            "oldValues": old_values,  # Maps to backend oldValues field (camelCase)
            "newValues": new_values,  # Maps to backend newValues field (camelCase)
        }
        options = self._build_options(context)
        await self.logger_service.audit(normalized_action, entity_type, audit_context, options)
    
    def _get_context(self) -> Dict[str, Any]:
        """Get context from contextvars or return default."""
        return self.context_storage.get_context() or {}
    
    def _build_options(self, context: Dict[str, Any]) -> ClientLoggingOptions:
        """Build ClientLoggingOptions from context."""
        options = ClientLoggingOptions()
        if "userId" in context:
            options.userId = context["userId"]
        if "sessionId" in context:
            options.sessionId = context["sessionId"]
        if "correlationId" in context:
            options.correlationId = context["correlationId"]
        if "ipAddress" in context:
            options.ipAddress = context["ipAddress"]
        if "userAgent" in context:
            options.userAgent = context["userAgent"]
        if "applicationId" in context:
            options.applicationId = context["applicationId"]
        if "token" in context:
            options.token = context["token"]
        return options
    
    def _extract_error_context(self, error: Exception) -> Dict[str, Any]:
        """Extract error context from exception."""
        return {
            "errorType": type(error).__name__,
            "errorMessage": str(error),
        }
```

### Phase 3: Create Factory Function

**File**: `miso_client/services/unified_logger.py` (add factory functions)

Create `get_logger()` factory function that:

- Returns `UnifiedLogger` instance
- Automatically detects available context from contextvars
- Works in both FastAPI routes and service layers

**Factory Functions**:

```python
from typing import Optional
from ..services.logger import LoggerService
from ..utils.logger_context_storage import LoggerContextStorage

# Global logger service instance (set by MisoClient)
_logger_service_instance: Optional[LoggerService] = None

def set_logger_service(logger_service: LoggerService) -> None:
    """
    Set global logger service instance.
    
    Called by MisoClient during initialization.
    
    Args:
        logger_service: LoggerService instance
    """
    global _logger_service_instance
    _logger_service_instance = logger_service

def get_logger() -> UnifiedLogger:
    """
    Get logger instance with automatic context detection from contextvars.
    
    Returns:
        UnifiedLogger instance
        
    Raises:
        RuntimeError: If logger service not initialized (call MisoClient first)
    """
    if _logger_service_instance is None:
        raise RuntimeError(
            "Logger service not initialized. "
            "Create MisoClient instance first to initialize logger service."
        )
    return UnifiedLogger(_logger_service_instance)

def set_logger_context(context: Dict[str, Any]) -> None:
    """
    Set logger context for current async execution context.
    
    Args:
        context: Context dictionary with fields like userId, correlationId, etc.
    """
    LoggerContextStorage.set_context(context)

def clear_logger_context() -> None:
    """Clear logger context for current async execution context."""
    LoggerContextStorage.clear_context()
```

### Phase 4: Create FastAPI/Flask Middleware Helpers (Optional)

**File**: `miso_client/middleware/logger_context.py`

Create middleware helpers that:

- Extract context from Request object
- Set context in contextvars
- Use existing `extract_request_context()` and `extract_jwt_context()`
- Work seamlessly with FastAPI/Flask middleware chain

**FastAPI Middleware Pattern**:

```python
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils.logger_context_storage import LoggerContextStorage
from ..utils.request_context import extract_request_context
from ..utils.logger_helpers import extract_jwt_context

class LoggerContextMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to set logger context from request.
    
    Call this early in middleware chain (after auth middleware).
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Extract context and set in contextvars."""
        # Extract request context
        request_ctx = extract_request_context(request)
        
        # Extract JWT context if available
        auth_header = request.headers.get("authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
        jwt_ctx = extract_jwt_context(token) if token else {}
        
        # Build context dictionary
        context = {
            "ipAddress": request_ctx.ip_address,
            "userAgent": request_ctx.user_agent,
            "correlationId": request_ctx.correlation_id,
            "userId": request_ctx.user_id or jwt_ctx.get("userId"),
            "sessionId": request_ctx.session_id or jwt_ctx.get("sessionId"),
            "method": request_ctx.method,
            "path": request_ctx.path,
            "applicationId": jwt_ctx.get("applicationId"),
            "token": token,
        }
        
        # Set context in contextvars
        LoggerContextStorage.set_context(context)
        
        try:
            response = await call_next(request)
            return response
        finally:
            # Clear context after request
            LoggerContextStorage.clear_context()
```

**Flask Middleware Pattern**:

```python
from typing import Callable
from flask import Flask, request as flask_request

from ..utils.logger_context_storage import LoggerContextStorage
from ..utils.request_context import extract_request_context
from ..utils.logger_helpers import extract_jwt_context

def logger_context_middleware(app: Flask) -> None:
    """
    Flask middleware to set logger context from request.
    
    Register this early in middleware chain (after auth middleware).
    
    Args:
        app: Flask application instance
    """
    @app.before_request
    def set_context():
        """Extract context and set in contextvars."""
        # Extract request context
        request_ctx = extract_request_context(flask_request)
        
        # Extract JWT context if available
        auth_header = flask_request.headers.get("authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
        jwt_ctx = extract_jwt_context(token) if token else {}
        
        # Build context dictionary
        context = {
            "ipAddress": request_ctx.ip_address,
            "userAgent": request_ctx.user_agent,
            "correlationId": request_ctx.correlation_id,
            "userId": request_ctx.user_id or jwt_ctx.get("userId"),
            "sessionId": request_ctx.session_id or jwt_ctx.get("sessionId"),
            "method": request_ctx.method,
            "path": request_ctx.path,
            "applicationId": jwt_ctx.get("applicationId"),
            "token": token,
        }
        
        # Set context in contextvars
        LoggerContextStorage.set_context(context)
    
    @app.teardown_request
    def clear_context(_):
        """Clear context after request."""
        LoggerContextStorage.clear_context()
```

### Phase 5: Update MisoClient to Initialize Unified Logger

**File**: `miso_client/__init__.py` (update)

Update `MisoClient` to:

- Initialize unified logger service
- Set global logger service instance for factory function
- Export unified logging API

**Update Pattern**:

```python
from .services.unified_logger import set_logger_service

class MisoClient:
    def __init__(self, config: MisoClientConfig):
        # ... existing initialization ...
        
        # Initialize unified logger service
        from .services.unified_logger import set_logger_service
        set_logger_service(self.logger)
```

### Phase 6: Export Public API

**File**: `miso_client/__init__.py` (update)

Export unified logging API:

- `get_logger()` - Factory function to get logger instance
- `set_logger_context()` - Set context manually
- `clear_logger_context()` - Clear context
- `UnifiedLogger` - Class type
- `LoggerContextMiddleware` - FastAPI middleware (if FastAPI available)
- `logger_context_middleware` - Flask middleware helper (if Flask available)

**Export Pattern**:

```python
# Unified logging API
from .services.unified_logger import (
    UnifiedLogger,
    get_logger,
    set_logger_context,
    clear_logger_context,
)

# Middleware (optional, framework-specific)
try:
    from .middleware.logger_context import LoggerContextMiddleware, logger_context_middleware
except ImportError:
    # FastAPI/Flask not available
    LoggerContextMiddleware = None
    logger_context_middleware = None

__all__ = [
    # ... existing exports ...
    "get_logger",
    "set_logger_context",
    "clear_logger_context",
    "UnifiedLogger",
    "LoggerContextMiddleware",
    "logger_context_middleware",
]
```

### Phase 7: Update Documentation

**Files to Update**:

#### 7.1: `README.md` - Add Unified Logging Feature

**Location**: Add to "Features" or "Usage" section

**Content to Add**:

1. **Add to Feature List**:

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - "Unified Logging Interface - Minimal API with automatic context extraction"

2. **Add Quick Example**:
   ```python
   # Simple unified logging
   from miso_client import get_logger
   
   logger = get_logger()
   await logger.info("Message")  # Auto-extracts context
   ```

3. **Update Logging Section**:

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Mention unified logging as recommended approach
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Link to examples

#### 7.2: `CHANGELOG.md` - Document New Features

**Location**: Add new entry at top of file

**Content to Add**:

```markdown
## [Unreleased] - Unified Logging Interface

### Added
- **Unified Logging Interface**: New minimal API with automatic context extraction
 - `get_logger()` factory function for automatic context detection
 - `set_logger_context()` and `clear_logger_context()` for manual context management
 - `LoggerContextMiddleware` FastAPI middleware helper
 - `logger_context_middleware` Flask middleware helper
 - contextvars-based context propagation across async boundaries
 - Simplified API: `logger.info(message)`, `logger.error(message, error?)`, `logger.audit(action, entity_type, entity_id?, old_values?, new_values?)`
 - Automatic context extraction from contextvars

### Documentation
- Added unified logging examples and guides
- Updated FastAPI/Flask middleware examples with unified logging pattern
- Added background job logging examples with unified interface
- Comprehensive API reference for UnifiedLogger class
```

## Key Design Decisions

1. **Minimal Parameters**: Maximum 1-3 parameters per call to keep interface simple
2. **Backend Schema Compliance**: Audit logs map correctly to backend Prisma schema:

            - `entity_type` parameter → `entityType` field (required)
            - `entity_id` parameter → `entityId` field (required, defaults to 'unknown')
            - `action` parameter → `action` field (required, lowercase: 'create', 'update', 'delete', 'access')
            - `old_values` parameter → `oldValues` field (optional, camelCase)
            - `new_values` parameter → `newValues` field (optional, camelCase)

3. **Automatic Context**: Context extracted automatically via contextvars, no manual passing required
4. **Leverage Existing Code**: Reuse existing context extraction, JWT handling, PII masking
5. **contextvars**: Use Python contextvars for context propagation (Python 3.7+)
6. **Public API**: Single `get_logger()` factory function for all use cases
7. **Framework Agnostic**: Works in FastAPI routes, Flask routes, service layers, background jobs
8. **Zero Configuration**: Works out of the box when middleware is used
9. **No Duplicate Code**: Reuse existing SDK functionality instead of reimplementing

## Files to Create

- `miso_client/utils/logger_context_storage.py` - contextvars context management
- `miso_client/services/unified_logger.py` - UnifiedLogger implementation
- `miso_client/middleware/logger_context.py` - FastAPI/Flask middleware helpers (optional)

## Files to Modify

- `miso_client/__init__.py` - Export unified logging API, initialize unified logger
- `README.md` - Add unified logging examples
- `CHANGELOG.md` - Document new features

## Testing Strategy

### Unit Tests

- Test contextvars context storage (get/set/clear/merge)
- Test UnifiedLogger with contextvars context
- Test UnifiedLogger with no context (default behavior)
- Test error extraction (stack trace, error name, error message)
- Test audit logging with old_values/new_values
- Mock LoggerService for all tests

### Integration Tests

- Test FastAPI middleware sets context correctly
- Test Flask middleware sets context correctly
- Test context propagation across async boundaries
- Test multiple concurrent requests (context isolation)

### Test File Structure

- `tests/unit/test_logger_context_storage.py` - Context storage tests
- `tests/unit/test_unified_logger.py` - UnifiedLogger tests
- `tests/integration/test_unified_logger_middleware.py` - Middleware integration tests

## Success Criteria

**Functional Requirements**:

- ✅ UnifiedLogger provides minimal interface (1-3 parameters max)
- ✅ Request context automatically extracted via contextvars
- ✅ User identification from JWT tokens works automatically
- ✅ PII masking handled automatically (existing DataMasker)
- ✅ Public API (`get_logger()`) works in FastAPI routes and service layers
- ✅ FastAPI middleware automatically sets context from request
- ✅ Flask middleware automatically sets context from request
- ✅ Works seamlessly in FastAPI routes, Flask routes, service layers, background jobs
- ✅ Context propagation works across async boundaries

**Code Quality**:

- ✅ All code passes lint → test → type check validation sequence
- ✅ Input validation on all public methods
- ✅ Type safety with type hints throughout
- ✅ Unit tests with 80%+ coverage
- ✅ Integration tests for FastAPI/Flask middleware
- ✅ Documentation updated

## Dependencies

- **Python**: Requires Python 3.7+ for contextvars support
- **No New Dependencies**: Uses existing SDK dependencies only
- **FastAPI**: Optional peer dependency (for middleware helper)
- **Flask**: Optional peer dependency (for middleware helper)

## Notes

- contextvars is available in Python 3.7+ (current SDK supports Python 3.8+)
- Context is automatically isolated per async execution context
- No performance impact - contextvars is very fast
- Thread-safe - each async context has its own storage
- Works with async/await, asyncio tasks, and concurrent.futures

---

## Plan Validation Report

**Date**: 2026-01-10

**Plan**: `.cursor/plans/21-unified-logging-interface.plan.md`

**Status**: ✅ VALIDATED

### Backend Schema Validation

**Validated Against**: `/workspace/aifabrix-miso-backend/prisma/schema.prisma`

**Audit Log Schema Requirements** (from Prisma schema):

- `entityType` (String) - Required field
- `entityId` (String) - Required field
- `action` (String) - Required field, values: 'create', 'update', 'delete', 'access' (lowercase)
- `oldValues` (Json?) - Optional field
- `newValues` (Json?) - Optional field

**Plan Compliance**:

- ✅ `entity_type` parameter maps to `entityType` field (camelCase)
- ✅ `entity_id` parameter maps to `entityId` field (camelCase)
- ✅ `action` parameter normalized to lowercase to match backend requirements
- ✅ `old_values` parameter maps to `oldValues` field (camelCase)
- ✅ `new_values` parameter maps to `newValues` field (camelCase)
- ✅ Implementation uses existing `_transform_log_entry_to_request()` which correctly maps context fields

### Plan Purpose

This plan enhances the miso-client SDK with a unified logging interface that provides a minimal API (1-3 parameters maximum) with automatic context extraction using contextvars. The implementation includes:

- **New Services**: UnifiedLogger service, LoggerContextStorage utility
- **Framework Utilities**: FastAPI/Flask middleware helpers
- **Infrastructure**: contextvars-based context management
- **Type Definitions**: LoggerContext dictionary type
- **Documentation**: Comprehensive examples and API reference updates

**Plan Type**: Service Development (Logger Service Enhancement) + Infrastructure (contextvars Context Management) + Framework Utilities (Middleware Helpers)

**Affected Areas**:

- Services (`miso_client/services/`)
- Utilities (`miso_client/utils/`)
- Middleware (`miso_client/middleware/`)
- Public API exports (`miso_client/__init__.py`)
- Documentation (`README.md`, `CHANGELOG.md`)

### Applicable Rules

- ✅ **[Architecture Patterns - Service Layer](.cursor/rules/project-rules.mdc#service-layer)** - UnifiedLogger service follows service layer patterns with dependency injection
- ✅ **[Architecture Patterns - Logger Chain Pattern](.cursor/rules/project-rules.mdc#logger-chain-pattern)** - Logging patterns, fluent API, error handling
- ✅ **[Code Style - Python Conventions](.cursor/rules/project-rules.mdc#python-conventions)** - Type hints, snake_case, PascalCase, Pydantic models
- ✅ **[Code Style - Error Handling](.cursor/rules/project-rules.mdc#error-handling)** - Comprehensive error logging with context, RFC 7807 compliance
- ✅ **[Code Style - Async/Await](.cursor/rules/project-rules.mdc#asyncawait)** - Async/await patterns, try-except for async operations
- ✅ **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - pytest patterns, 80%+ coverage, mock all dependencies
- ✅ **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - ISO 27001 compliance, PII masking, token handling
- ✅ **[Code Quality Standards](.cursor/rules/project-rules.mdc#code-size-guidelines)** - File size limits (≤500 lines), method size limits (≤20-30 lines), Google-style docstrings
- ✅ **[File Organization](.cursor/rules/project-rules.mdc#file-organization)** - Source structure, import order, export strategy
- ✅ **[Documentation](.cursor/rules/project-rules.mdc#documentation)** - Google-style docstrings, parameter types, return types, error conditions

### Rule Compliance

- ✅ **DoD Requirements**: Fully documented with LINT → TEST → TYPE CHECK sequence
- ✅ **Service Layer**: Plan follows service layer patterns with dependency injection
- ✅ **Python Conventions**: Plan specifies type hints, snake_case, PascalCase conventions
- ✅ **Error Handling**: Plan addresses comprehensive error logging with context
- ✅ **Testing Conventions**: Plan includes unit tests (80%+ coverage) and integration tests
- ✅ **Security Guidelines**: Plan addresses ISO 27001 compliance, PII masking, token handling
- ✅ **Code Quality Standards**: Plan addresses file size limits, method size limits, Google-style docstrings
- ✅ **File Organization**: Plan follows source structure and export patterns
- ✅ **Documentation**: Plan includes comprehensive documentation updates

### Plan Updates Made

- ✅ Added **Rules and Standards** section with all applicable rule references
- ✅ Added **Before Development** checklist with prerequisites and preparation steps
- ✅ Added **Definition of Done** section with complete validation requirements
- ✅ Added rule references: Architecture Patterns (Service Layer, Logger Chain Pattern), Code Style (Python Conventions, Error Handling, Async/Await), Testing Conventions, Security Guidelines, Code Quality Standards, File Organization, Documentation
- ✅ Updated DoD with mandatory LINT → TEST → TYPE CHECK validation sequence
- ✅ Added file size limits (≤500 lines) and method size limits (≤20-30 lines) to DoD
- ✅ Added Google-style docstring documentation requirement to DoD
- ✅ Added security requirements (ISO 27001 compliance, PII masking) to DoD
- ✅ Added testing requirements (80%+ coverage, unit tests, integration tests) to DoD
- ✅ Added documentation update requirements to DoD
- ✅ Adapted TypeScript AsyncLocalStorage to Python contextvars
- ✅ Adapted Express middleware to FastAPI/Flask middleware
- ✅ Adapted TypeScript conventions to Python conventions (snake_case, type hints, Google-style docstrings)

### Recommendations

1. **contextvars Mocking**: Ensure test mocks properly simulate contextvars behavior for context isolation testing
2. **Error Handling**: Verify that UnifiedLogger error handling is silent (catch and swallow) as per Logger Chain Pattern
3. **Context Extraction**: Ensure context extraction priority (contextvars → Default) is properly tested
4. **Framework Middleware**: Verify middleware works seamlessly with existing FastAPI/Flask middleware chain
5. **Documentation**: Ensure all documentation updates are completed before release
6. **Type Safety**: Verify all public API types use type hints and proper return types
7. **Export Strategy**: Ensure only necessary exports are added to `miso_client/__init__.py`

### Validation Summary

The plan is **VALIDATED** and ready for production implementation. All required sections have been added:

- ✅ Rules and Standards section with applicable rule references
- ✅ Before Development checklist
- ✅ Definition of Done with complete validation requirements
- ✅ All mandatory DoD requirements documented (LINT → TEST → TYPE CHECK sequence)
- ✅ File size limits and method size limits documented
- ✅ Google-style docstring documentation requirements documented
- ✅ Security requirements documented
- ✅ Testing requirements documented (80%+ coverage)
- ✅ Documentation update requirements documented

The plan comprehensively addresses:

- Service layer architecture patterns
- Python conventions and type safety
- Error handling and logging patterns
- Security and ISO 27001 compliance
- Testing requirements and coverage
- Code quality standards
- File organization and exports
- Documentation updates

**Next Steps**: Proceed with implementation following the plan tasks and ensuring all DoD requirements are met before marking as complete.