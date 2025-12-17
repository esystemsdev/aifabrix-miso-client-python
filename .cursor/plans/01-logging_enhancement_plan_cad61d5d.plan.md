# Logging Enhancement Plan

## Indexed Fields and Structured Context for Observability

## Overview

This plan introduces standardized, indexed logging fields for general, audit, and performance logs in the MisoClient SDK. The changes improve:

- Query performance (index-based filtering vs JSON extraction)
- Root-cause analysis
- Cross-system traceability
- Human-readable diagnostics

It aligns general logging with existing ABAC/RBAC audit logging principles while keeping implementation incremental and low-risk.

## Current State

The SDK currently provides:

- [`LoggerService`](miso_client/services/logger.py) with `info()`, `error()`, `audit()`, `debug()` methods
- [`LoggerChain`](miso_client/services/logger.py) for fluent API logging
- [`LogEntry`](miso_client/models/config.py) Pydantic model for log structure
- [`ClientLoggingOptions`](miso_client/models/config.py) for logging configuration
- Data masking via [`DataMasker`](miso_client/utils/data_masker.py)

**Key Problem**: Logs lack indexed context fields (`sourceKey`, `sourceDisplayName`, `externalSystemKey`, etc.), making:

- Filtering rely on IDs or free-text search
- Queries slow and inconsistent
- Logs hard to correlate across systems

---

## Standard Indexed Log Fields

### Required Fields (when applicable)

| Field | Description | Indexed |

|-------|-------------|---------|

| `sourceKey` | ExternalDataSource.key | Yes |

| `sourceDisplayName` | ExternalDataSource.displayName | Yes |

| `externalSystemKey` | ExternalSystem.key | Yes |

| `externalSystemDisplayName` | ExternalSystem.displayName | Yes |

| `recordKey` | ExternalRecord.key | Optional |

| `recordDisplayName` | ExternalRecord.displayName | Optional |

| `userId` | Authenticated user ID | Yes |

| `correlationId` | Request/workflow correlation ID | Yes |

| `environment` | Environment (dev/test/prod) | Yes |

These fields should be **top-level metadata**, not nested blobs.

---

## Phase 1: Logging Context Helper

Create a new utility to extract indexed fields for logging.

### New File: `miso_client/utils/logging_helpers.py`

```python
"""Logging context helpers for extracting indexed fields."""

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class HasKey(Protocol):
    """Protocol for objects with key and displayName."""
    key: str
    displayName: Optional[str]


@runtime_checkable
class HasExternalSystem(Protocol):
    """Protocol for objects with key, displayName, and optional externalSystem."""
    key: str
    displayName: Optional[str]
    externalSystem: Optional[HasKey]


def extract_logging_context(
    source: Optional[HasExternalSystem] = None,
    record: Optional[HasKey] = None,
    external_system: Optional[HasKey] = None,
) -> Dict[str, Any]:
    """
    Extract indexed fields for logging.

    Indexed fields:
    - sourceKey, sourceDisplayName
    - externalSystemKey, externalSystemDisplayName
    - recordKey, recordDisplayName

    Args:
        source: ExternalDataSource object (optional)
        record: ExternalRecord object (optional)
        external_system: ExternalSystem object (optional)

    Returns:
        Dictionary with indexed context fields (only non-None values)

    Design principles:
    - No DB access
    - Explicit context passing
    - Safe to use in hot paths
    """
    context: Dict[str, Any] = {}

    if source:
        context["sourceKey"] = source.key
        if source.displayName:
            context["sourceDisplayName"] = source.displayName
        if source.externalSystem:
            context["externalSystemKey"] = source.externalSystem.key
            if source.externalSystem.displayName:
                context["externalSystemDisplayName"] = source.externalSystem.displayName

    if external_system:
        context["externalSystemKey"] = external_system.key
        if external_system.displayName:
            context["externalSystemDisplayName"] = external_system.displayName

    if record:
        context["recordKey"] = record.key
        if record.displayName:
            context["recordDisplayName"] = record.displayName

    return context
```

---

## Phase 2: Enhanced Log Entry Model

Update [`miso_client/models/config.py`](miso_client/models/config.py) to add indexed fields.

### 2.1 Update `LogEntry`

```python
class LogEntry(BaseModel):
    """Log entry structure."""

    # Existing fields...
    timestamp: str = Field(..., description="ISO timestamp")
    level: Literal["error", "audit", "info", "debug"] = Field(..., description="Log level")
    environment: str = Field(..., description="Environment name")
    application: str = Field(..., description="Application identifier (clientId)")
    message: str = Field(..., description="Log message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")
    userId: Optional[str] = Field(default=None, description="User ID")
    # ... other existing fields ...

    # NEW: Indexed context fields (top-level for fast queries)
    sourceKey: Optional[str] = Field(default=None, description="ExternalDataSource.key")
    sourceDisplayName: Optional[str] = Field(default=None, description="Human-readable source name")
    externalSystemKey: Optional[str] = Field(default=None, description="ExternalSystem.key")
    externalSystemDisplayName: Optional[str] = Field(default=None, description="Human-readable system name")
    recordKey: Optional[str] = Field(default=None, description="ExternalRecord.key")
    recordDisplayName: Optional[str] = Field(default=None, description="Human-readable record identifier")

    # NEW: Credential context (for performance analysis)
    credentialId: Optional[str] = Field(default=None, description="Credential ID")
    credentialType: Optional[str] = Field(default=None, description="Credential type (apiKey, oauth2, etc.)")

    # NEW: Request/Response metrics
    requestSize: Optional[int] = Field(default=None, description="Request body size in bytes")
    responseSize: Optional[int] = Field(default=None, description="Response body size in bytes")
    durationMs: Optional[int] = Field(default=None, description="Duration in milliseconds")
    durationSeconds: Optional[float] = Field(default=None, description="Duration in seconds")
    timeout: Optional[float] = Field(default=None, description="Request timeout in seconds")
    retryCount: Optional[int] = Field(default=None, description="Number of retry attempts")

    # NEW: Error classification
    errorCategory: Optional[str] = Field(
        default=None,
        description="Error category: network, timeout, auth, validation, server"
    )
    httpStatusCategory: Optional[str] = Field(
        default=None,
        description="HTTP status category: 2xx, 4xx, 5xx"
    )
```

### 2.2 Update `ClientLoggingOptions`

```python
class ClientLoggingOptions(BaseModel):
    """Options for client logging."""

    # Existing fields...
    applicationId: Optional[str] = Field(default=None, description="Application ID")
    userId: Optional[str] = Field(default=None, description="User ID")
    correlationId: Optional[str] = Field(default=None, description="Correlation ID")
    # ... other existing fields ...

    # NEW: Indexed context
    sourceKey: Optional[str] = Field(default=None, description="ExternalDataSource.key")
    sourceDisplayName: Optional[str] = Field(default=None, description="Human-readable source name")
    externalSystemKey: Optional[str] = Field(default=None, description="ExternalSystem.key")
    externalSystemDisplayName: Optional[str] = Field(default=None, description="Human-readable system name")
    recordKey: Optional[str] = Field(default=None, description="ExternalRecord.key")
    recordDisplayName: Optional[str] = Field(default=None, description="Human-readable record identifier")

    # NEW: Credential context
    credentialId: Optional[str] = Field(default=None, description="Credential ID")
    credentialType: Optional[str] = Field(default=None, description="Credential type")

    # NEW: Request metrics
    requestSize: Optional[int] = Field(default=None, description="Request body size in bytes")
    responseSize: Optional[int] = Field(default=None, description="Response body size in bytes")
    durationMs: Optional[int] = Field(default=None, description="Duration in milliseconds")
    durationSeconds: Optional[float] = Field(default=None, description="Duration in seconds")
    timeout: Optional[float] = Field(default=None, description="Request timeout in seconds")
    retryCount: Optional[int] = Field(default=None, description="Retry count")

    # NEW: Error classification
    errorCategory: Optional[str] = Field(default=None, description="Error category")
    httpStatusCategory: Optional[str] = Field(default=None, description="HTTP status category")
```

---

## Phase 3: LoggerService Enhancement

Update [`miso_client/services/logger.py`](miso_client/services/logger.py):

### 3.1 Add `with_indexed_context()` to LoggerChain

```python
def with_indexed_context(
    self,
    source_key: Optional[str] = None,
    source_display_name: Optional[str] = None,
    external_system_key: Optional[str] = None,
    external_system_display_name: Optional[str] = None,
    record_key: Optional[str] = None,
    record_display_name: Optional[str] = None,
) -> "LoggerChain":
    """
    Add indexed context fields for fast querying.

    Args:
        source_key: ExternalDataSource.key
        source_display_name: Human-readable source name
        external_system_key: ExternalSystem.key
        external_system_display_name: Human-readable system name
        record_key: ExternalRecord.key
        record_display_name: Human-readable record identifier

    Returns:
        Self for method chaining
    """
    if self.options is None:
        self.options = ClientLoggingOptions()
    if source_key:
        self.options.sourceKey = source_key
    if source_display_name:
        self.options.sourceDisplayName = source_display_name
    if external_system_key:
        self.options.externalSystemKey = external_system_key
    if external_system_display_name:
        self.options.externalSystemDisplayName = external_system_display_name
    if record_key:
        self.options.recordKey = record_key
    if record_display_name:
        self.options.recordDisplayName = record_display_name
    return self
```

### 3.2 Add `with_credential_context()` to LoggerChain

```python
def with_credential_context(
    self,
    credential_id: Optional[str] = None,
    credential_type: Optional[str] = None,
) -> "LoggerChain":
    """
    Add credential context for performance analysis.

    Args:
        credential_id: Credential identifier
        credential_type: Credential type (apiKey, oauth2, etc.)

    Returns:
        Self for method chaining
    """
    if self.options is None:
        self.options = ClientLoggingOptions()
    if credential_id:
        self.options.credentialId = credential_id
    if credential_type:
        self.options.credentialType = credential_type
    return self
```

### 3.3 Add `with_request_metrics()` to LoggerChain

```python
def with_request_metrics(
    self,
    request_size: Optional[int] = None,
    response_size: Optional[int] = None,
    duration_ms: Optional[int] = None,
    duration_seconds: Optional[float] = None,
    timeout: Optional[float] = None,
    retry_count: Optional[int] = None,
) -> "LoggerChain":
    """
    Add request/response metrics.

    Args:
        request_size: Request body size in bytes
        response_size: Response body size in bytes
        duration_ms: Duration in milliseconds
        duration_seconds: Duration in seconds
        timeout: Request timeout in seconds
        retry_count: Number of retry attempts

    Returns:
        Self for method chaining
    """
    if self.options is None:
        self.options = ClientLoggingOptions()
    if request_size is not None:
        self.options.requestSize = request_size
    if response_size is not None:
        self.options.responseSize = response_size
    if duration_ms is not None:
        self.options.durationMs = duration_ms
    if duration_seconds is not None:
        self.options.durationSeconds = duration_seconds
    if timeout is not None:
        self.options.timeout = timeout
    if retry_count is not None:
        self.options.retryCount = retry_count
    return self
```

### 3.4 Add `with_error_context()` to LoggerChain

```python
def with_error_context(
    self,
    error_category: Optional[str] = None,
    http_status_category: Optional[str] = None,
) -> "LoggerChain":
    """
    Add error classification context.

    Args:
        error_category: Error category (network, timeout, auth, validation, server)
        http_status_category: HTTP status category (2xx, 4xx, 5xx)

    Returns:
        Self for method chaining
    """
    if self.options is None:
        self.options = ClientLoggingOptions()
    if error_category:
        self.options.errorCategory = error_category
    if http_status_category:
        self.options.httpStatusCategory = http_status_category
    return self
```

### 3.5 Update `_log()` Method

Update the `_log()` method in `LoggerService` to include indexed fields in log entries:

```python
async def _log(
    self,
    level: Literal["error", "audit", "info", "debug"],
    message: str,
    context: Optional[Dict[str, Any]] = None,
    stack_trace: Optional[str] = None,
    options: Optional[ClientLoggingOptions] = None,
) -> None:
    # ... existing code ...

    log_entry_data = {
        # Existing fields...
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "environment": "unknown",
        "application": self.config.client_id,
        "message": message,
        "context": enhanced_context,
        "correlationId": correlation_id,
        "userId": (options.userId if options else None) or jwt_context.get("userId"),
        # ... other existing fields ...

        # NEW: Indexed context fields from options
        "sourceKey": options.sourceKey if options else None,
        "sourceDisplayName": options.sourceDisplayName if options else None,
        "externalSystemKey": options.externalSystemKey if options else None,
        "externalSystemDisplayName": options.externalSystemDisplayName if options else None,
        "recordKey": options.recordKey if options else None,
        "recordDisplayName": options.recordDisplayName if options else None,

        # NEW: Credential context
        "credentialId": options.credentialId if options else None,
        "credentialType": options.credentialType if options else None,

        # NEW: Request metrics
        "requestSize": options.requestSize if options else None,
        "responseSize": options.responseSize if options else None,
        "durationMs": options.durationMs if options else None,
        "durationSeconds": options.durationSeconds if options else None,
        "timeout": options.timeout if options else None,
        "retryCount": options.retryCount if options else None,

        # NEW: Error classification
        "errorCategory": options.errorCategory if options else None,
        "httpStatusCategory": options.httpStatusCategory if options else None,
    }

    # Remove None values
    log_entry_data = {k: v for k, v in log_entry_data.items() if v is not None}
```

---

## Phase 4: MisoLogger Enhancement for Error Forwarding

Ensure forwarded error logs always include indexed fields when available.

**Key Rules**:

1. Always log locally via the logger
2. Forward enriched metadata to MisoClient (controller)
3. Attach `userId`, `environment`, and any provided indexed fields
4. `miso_logger` does **not** infer domain context implicitly - callers pass `sourceKey`, `recordKey`, etc. or use `extract_logging_context()`

---

## Usage Patterns

### Before (Current)

```python
logger.info("Sync operation started", sourceId=source.id)
logger.error("Failed to process record", recordId=record.id, error=str(e))
```

### After (Enhanced)

```python
from miso_client.utils.logging_helpers import extract_logging_context

log_context = extract_logging_context(source=source, record=record)

await logger \
    .with_indexed_context(**log_context) \
    .with_correlation(correlation_id) \
    .add_user(user_id) \
    .info("Sync operation started")

await logger \
    .with_indexed_context(**log_context) \
    .with_error_context(error_category="validation") \
    .error("Failed to process record", error=str(e))
```

**Rule**: If a `source`, `record`, or `externalSystem` exists, **always** include extracted context.

### Audit Logging with Indexed Fields

```python
await logger.audit(
    action="abac.authorization.grant",
    resource="external_record",
    context={
        # Indexed fields (top-level for fast queries)
        "sourceKey": resource_ctx.datasource_key,
        "sourceDisplayName": source.displayName if source else None,
        "externalSystemKey": resource_ctx.external_system_key,
        "recordDisplayName": record.displayName if record else None,

        # Required audit fields
        "userId": miso_ctx.user_id,
        "correlationId": correlation_id,

        # Contextual fields
        "operation": action_ctx.operation,
        "toolName": action_ctx.tool_name,
        "recordId": resource_ctx.record_id,

        # Policy context
        "policyKeys": policy_keys,
        "policyCount": len(policies),
    }
)
```

### Performance Logging with Full Metrics

```python
import time
import json

start_time = time.time()
# ... execute request ...
duration_seconds = time.time() - start_time

await logger \
    .with_indexed_context(
        source_key=external_data_source.key,
        source_display_name=external_data_source.displayName,
        external_system_key=external_system.key,
        external_system_display_name=external_system.displayName,
    ) \
    .with_credential_context(
        credential_id=credential.id if credential else None,
        credential_type=credential.type if credential else None,
    ) \
    .with_request_metrics(
        request_size=len(json.dumps(request_body)) if request_body else 0,
        response_size=len(json.dumps(response_json)) if response_json else 0,
        duration_ms=int(duration_seconds * 1000),
        duration_seconds=duration_seconds,
        timeout=30.0,
        retry_count=0,
    ) \
    .with_error_context(
        http_status_category=f"{status_code // 100}xx" if status_code else None,
    ) \
    .add_user(user_id) \
    .add_correlation(correlation_id) \
    .info("Upstream API call completed")
```

---

## Query Benefits

### Fast Index-Based Queries

```sql
-- Errors by source
WHERE sourceKey = 'hubspot-deals'

-- Errors by external system
WHERE level = 'error' AND externalSystemKey = 'hubspot-main'

-- User activity across systems
WHERE userId = 'user123' AND sourceKey IN ('hubspot-deals', 'salesforce-opportunities')

-- ABAC decisions per source
WHERE action LIKE 'abac.authorization.%' AND sourceKey = 'salesforce-opportunities'

-- Authorization events for a user on a system
WHERE userId = 'user123' AND externalSystemKey = 'hubspot-main'

-- Denied access attempts for a source
WHERE action = 'abac.authorization.deny' AND sourceKey = 'hubspot-deals'
```

### Human-Readable Analysis

- Filter by `sourceDisplayName` (e.g., "HubSpot Deals")
- Group by `externalSystemDisplayName`
- Display `recordDisplayName` in error reports (e.g., "Opportunity: ACME Renewal")

---

## Files to Create/Modify

| File | Action | Description |

|------|--------|-------------|

| `miso_client/utils/logging_helpers.py` | Create | New context extraction utility with `extract_logging_context()` |

| `miso_client/models/config.py` | Modify | Add indexed fields to `LogEntry` and `ClientLoggingOptions` |

| `miso_client/services/logger.py` | Modify | Add `with_indexed_context()`, `with_credential_context()`, `with_request_metrics()`, `with_error_context()` to `LoggerChain`; update `_log()` |

| `miso_client/__init__.py` | Modify | Export `extract_logging_context` |

| `tests/unit/test_logging_helpers.py` | Create | Unit tests for `extract_logging_context()` |

| `tests/unit/test_logger_chain.py` | Modify | Add tests for new `LoggerChain` methods |

---

## Summary of Indexed Fields

| Category | Field | Purpose | Indexed |

|----------|-------|---------|---------|

| Context | sourceKey | Filter by data source | Yes |

| Context | sourceDisplayName | Human-readable queries | Yes |

| Context | externalSystemKey | Filter by system | Yes |

| Context | externalSystemDisplayName | Human-readable system | Yes |

| Context | recordKey | Filter by record | Optional |

| Context | recordDisplayName | Human-readable record | Optional |

| User | userId | Link to audit and activity | Yes |

| Correlation | correlationId | Request tracing | Yes |

| Environment | environment | Environment-level filtering | Yes |

| Credential | credentialId | Credential performance | Optional |

| Credential | credentialType | Auth analysis | Optional |

| Metrics | durationMs | Performance analysis | Yes |

| Metrics | durationSeconds | Performance analysis | Yes |

| Metrics | requestSize | Payload analysis | No |

| Metrics | responseSize | Payload analysis | No |

| Metrics | timeout | Timeout configuration | No |

| Metrics | retryCount | Retry strategy analysis | No |

| Error | errorCategory | Error classification | Optional |

| Error | httpStatusCategory | Status grouping | Optional |

---

## Implementation Strategy

| Phase | Description | Risk |

|-------|-------------|------|

| Phase 1 | Add `extract_logging_context()` helper | Low |

| Phase 2 | Update `LogEntry` and `ClientLoggingOptions` models | Low |

| Phase 3 | Add new `LoggerChain` methods and update `_log()` | Low |

| Phase 4 | Enhance `miso_logger` forwarding behavior | Low |

All changes are:

- **Additive** (no breaking changes to existing API)
- **Optional** (new fields default to `None`)
- **Backward compatible** (existing code continues to work)