"""Helpers for transforming LogEntry into API log requests."""

from typing import Any, Literal, cast

from ..models.config import LogEntry


def _load_log_types() -> Any:
    """Load API log type models lazily to avoid circular imports."""
    from ..api.types.logs_types import AuditLogData, GeneralLogData, LogRequest

    return AuditLogData, GeneralLogData, LogRequest


def _serialize_foreign_refs(log_entry: LogEntry) -> tuple[Any, Any]:
    """Serialize optional foreign-key references from LogEntry."""
    application_id = log_entry.applicationId.model_dump() if log_entry.applicationId else None
    user_id = log_entry.userId.model_dump() if log_entry.userId else None
    return application_id, user_id


def _build_shared_payload(
    log_entry: LogEntry, ctx: dict[str, Any], application_id: Any, user_id: Any
) -> dict[str, Any]:
    """Build payload fields shared between audit and general logs."""
    return {
        "context": ctx,
        "application": log_entry.application,
        "environment": log_entry.environment,
        "applicationId": application_id,
        "clientId": log_entry.clientId,
        "userId": user_id,
        "sourceId": log_entry.sourceId,
        "sourceDisplayName": log_entry.sourceDisplayName,
        "externalSystemId": log_entry.externalSystemId,
        "externalSystemDisplayName": log_entry.externalSystemDisplayName,
        "recordId": log_entry.recordId,
        "recordDisplayName": log_entry.recordDisplayName,
        "requestId": log_entry.requestId,
        "sessionId": log_entry.sessionId,
        "ipAddress": log_entry.ipAddress,
        "userAgent": log_entry.userAgent,
        "correlationId": log_entry.correlationId,
    }


def _build_audit_request(
    log_entry: LogEntry, ctx: dict[str, Any], application_id: Any, user_id: Any
) -> Any:
    """Build audit LogRequest payload."""
    AuditLogData, _, LogRequest = _load_log_types()
    shared = _build_shared_payload(log_entry, ctx, application_id, user_id)
    return LogRequest(
        type="audit",
        data=AuditLogData(
            entityType=ctx.get("entityType", ctx.get("resource", "unknown")),
            entityId=ctx.get("entityId", ctx.get("resourceId", "unknown")),
            action=ctx.get("action", "unknown"),
            oldValues=ctx.get("oldValues"),
            newValues=ctx.get("newValues"),
            **shared,
        ),
    )


def _resolve_general_level(level: str) -> Literal["error", "warn", "info", "debug"]:
    """Resolve general log level literal for API model."""
    if level == "error":
        return "error"
    return cast(Literal["warn", "info", "debug"], level)


def _build_general_request(
    log_entry: LogEntry, ctx: dict[str, Any], application_id: Any, user_id: Any
) -> Any:
    """Build non-audit LogRequest payload."""
    _, GeneralLogData, LogRequest = _load_log_types()
    shared = _build_shared_payload(log_entry, ctx, application_id, user_id)
    return LogRequest(
        type="error" if log_entry.level == "error" else "general",
        data=GeneralLogData(
            level=_resolve_general_level(log_entry.level),
            message=log_entry.message,
            **shared,
        ),
    )


def transform_log_entry_to_request(log_entry: LogEntry) -> Any:
    """Transform ``LogEntry`` to ``LogRequest`` format for API layer."""
    ctx = log_entry.context or {}
    application_id, user_id = _serialize_foreign_refs(log_entry)
    if log_entry.level == "audit":
        return _build_audit_request(log_entry, ctx, application_id, user_id)
    return _build_general_request(log_entry, ctx, application_id, user_id)
