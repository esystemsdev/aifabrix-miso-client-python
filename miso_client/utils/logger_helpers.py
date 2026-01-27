"""Logger helper functions for building log entries.

Extracted from logger.py to reduce file size and improve maintainability.
"""

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Union

from ..models.config import ClientLoggingOptions, ForeignKeyReference, LogEntry
from ..utils.data_masker import DataMasker
from ..utils.jwt_tools import decode_token


def extract_jwt_context(token: Optional[str]) -> Dict[str, Any]:
    """Extract JWT token information.

    Args:
        token: JWT token string

    Returns:
        Dictionary with userId, applicationId, sessionId, roles, permissions

    """
    if not token:
        return {}

    try:
        decoded = decode_token(token)
        if not decoded:
            return {}

        # Extract roles - handle different formats
        roles = []
        if "roles" in decoded:
            roles = decoded["roles"] if isinstance(decoded["roles"], list) else []
        elif "realm_access" in decoded and isinstance(decoded["realm_access"], dict):
            roles = decoded["realm_access"].get("roles", [])

        # Extract permissions - handle different formats
        permissions = []
        if "permissions" in decoded:
            permissions = decoded["permissions"] if isinstance(decoded["permissions"], list) else []
        elif "scope" in decoded and isinstance(decoded["scope"], str):
            permissions = decoded["scope"].split()

        return {
            "userId": decoded.get("sub") or decoded.get("userId") or decoded.get("user_id"),
            "applicationId": decoded.get("applicationId") or decoded.get("app_id"),
            "sessionId": decoded.get("sessionId") or decoded.get("sid"),
            "roles": roles,
            "permissions": permissions,
        }
    except Exception:
        # JWT parsing failed, return empty context
        return {}


def extract_metadata() -> Dict[str, Any]:
    """Extract metadata from environment (browser or Node.js).

    Returns:
        Dictionary with hostname, userAgent, etc.

    """
    metadata: Dict[str, Any] = {}

    # Try to extract Node.js/Python metadata
    if hasattr(os, "environ"):
        metadata["hostname"] = os.environ.get("HOSTNAME", "unknown")

    # In Python, we don't have browser metadata like in TypeScript
    # But we can capture some environment info
    metadata["platform"] = sys.platform
    metadata["python_version"] = sys.version

    return metadata


def _convert_to_foreign_key_reference(
    value: Optional[Union[str, ForeignKeyReference]], entity_type: str
) -> Optional[ForeignKeyReference]:
    """Convert string ID or ForeignKeyReference to ForeignKeyReference object.

    Args:
        value: String ID or ForeignKeyReference object
        entity_type: Entity type (e.g., 'User', 'Application')

    Returns:
        ForeignKeyReference object or None

    """
    if value is None:
        return None

    # If already a ForeignKeyReference, return as-is
    if isinstance(value, ForeignKeyReference):
        return value

    # If string, create minimal ForeignKeyReference
    # Note: This is a minimal conversion - full ForeignKeyReference should come from API responses
    if isinstance(value, str):
        return ForeignKeyReference(
            id=value,
            key=value,  # Use id as key when key is not available
            name=value,  # Use id as name when name is not available
            type=entity_type,
        )

    return None


def build_log_entry(
    level: Literal["error", "audit", "info", "debug"],
    message: str,
    context: Optional[Dict[str, Any]],
    config_client_id: str,
    correlation_id: Optional[str] = None,
    jwt_token: Optional[str] = None,
    stack_trace: Optional[str] = None,
    options: Optional[ClientLoggingOptions] = None,
    metadata: Optional[Dict[str, Any]] = None,
    mask_sensitive: bool = True,
    application_context: Optional[Dict[str, Optional[str]]] = None,
) -> LogEntry:
    """Build LogEntry object from parameters.

    Args:
        level: Log level
        message: Log message
        context: Additional context data
        config_client_id: Client ID from config
        correlation_id: Optional correlation ID
        jwt_token: Optional JWT token for context extraction
        stack_trace: Stack trace for errors
        options: Logging options
        metadata: Environment metadata
        mask_sensitive: Whether to mask sensitive data
        application_context: Optional context dict (application, applicationId, environment)

    Returns:
        LogEntry object

    """
    # Extract JWT context if token provided
    jwt_context = extract_jwt_context(jwt_token or (options.token if options else None))

    # Extract environment metadata
    env_metadata = metadata or extract_metadata()

    # Generate correlation ID if not provided
    final_correlation_id = correlation_id or (options.correlationId if options else None)

    # Mask sensitive data in context if enabled
    should_mask = (options.maskSensitiveData if options else None) is not False and mask_sensitive
    masked_context = DataMasker.mask_sensitive_data(context) if should_mask and context else context

    # Get application context (from parameter, options overwrites, or defaults)
    app_context = application_context or {}

    # Determine application name (priority: options > application_context > config_client_id)
    application_name = (
        (options.application if options else None)
        or app_context.get("application")
        or config_client_id
    )

    # Determine environment (priority: options > application_context > "unknown")
    environment_name = (
        (options.environment if options else None) or app_context.get("environment") or "unknown"
    )

    # Determine applicationId (priority: options > application_context > jwt_context)
    application_id_value = (
        (options.applicationId if options else None)
        or app_context.get("applicationId")
        or jwt_context.get("applicationId")
    )

    user_id_value = (options.userId if options else None) or jwt_context.get("userId")

    application_id_ref = _convert_to_foreign_key_reference(application_id_value, "Application")
    user_id_ref = _convert_to_foreign_key_reference(user_id_value, "User")

    log_entry_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "environment": environment_name,
        "application": application_name,
        "applicationId": application_id_ref,
        "message": message,
        "context": masked_context,
        "stackTrace": stack_trace,
        "correlationId": final_correlation_id,
        "userId": user_id_ref,
        "sessionId": (options.sessionId if options else None) or jwt_context.get("sessionId"),
        "requestId": options.requestId if options else None,
        "ipAddress": options.ipAddress if options else None,
        "userAgent": options.userAgent if options else None,
        **env_metadata,
        # Indexed context fields from options
        "sourceKey": options.sourceKey if options else None,
        "sourceDisplayName": options.sourceDisplayName if options else None,
        "externalSystemKey": options.externalSystemKey if options else None,
        "externalSystemDisplayName": options.externalSystemDisplayName if options else None,
        "recordKey": options.recordKey if options else None,
        "recordDisplayName": options.recordDisplayName if options else None,
        # Credential context
        "credentialId": options.credentialId if options else None,
        "credentialType": options.credentialType if options else None,
        # Request metrics
        "requestSize": options.requestSize if options else None,
        "responseSize": options.responseSize if options else None,
        "durationMs": options.durationMs if options else None,
        "durationSeconds": options.durationSeconds if options else None,
        "timeout": options.timeout if options else None,
        "retryCount": options.retryCount if options else None,
        # Error classification
        "errorCategory": options.errorCategory if options else None,
        "httpStatusCategory": options.httpStatusCategory if options else None,
    }

    # Remove None values
    log_entry_data = {k: v for k, v in log_entry_data.items() if v is not None}

    return LogEntry(**log_entry_data)


def transform_log_entry_to_request(log_entry: LogEntry) -> Any:
    """Transform LogEntry to LogRequest format for API layer.

    Args:
        log_entry: LogEntry to transform

    Returns:
        LogRequest object for API layer

    """
    # Import here to avoid circular dependency
    from ..api.types.logs_types import AuditLogData, GeneralLogData, LogRequest

    ctx = log_entry.context or {}
    if log_entry.level == "audit":
        return LogRequest(
            type="audit",
            data=AuditLogData(
                entityType=ctx.get("entityType", ctx.get("resource", "unknown")),
                entityId=ctx.get("entityId", ctx.get("resourceId", "unknown")),
                action=ctx.get("action", "unknown"),
                oldValues=ctx.get("oldValues"),
                newValues=ctx.get("newValues"),
                correlationId=log_entry.correlationId,
            ),
        )

    log_type: Literal["error", "general"] = "error" if log_entry.level == "error" else "general"
    return LogRequest(
        type=log_type,
        data=GeneralLogData(
            level=log_entry.level if log_entry.level != "error" else "error",  # type: ignore
            message=log_entry.message,
            context=ctx,
            correlationId=log_entry.correlationId,
        ),
    )
