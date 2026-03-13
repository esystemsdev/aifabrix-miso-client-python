"""Logger helper functions for building log entries."""

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union

from ..models.config import ClientLoggingOptions, ForeignKeyReference, LogEntry, LogLevel
from ..utils.data_masker import DataMasker
from ..utils.jwt_tools import decode_token
from ..utils.log_request_transformer import (
    transform_log_entry_to_request as _transform_log_entry_to_request,
)


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
    except Exception:
        return {}
    if not decoded:
        return {}
    return {
        "userId": decoded.get("sub") or decoded.get("userId") or decoded.get("user_id"),
        "applicationId": decoded.get("applicationId") or decoded.get("app_id"),
        "sessionId": decoded.get("sessionId") or decoded.get("sid"),
        "roles": _extract_jwt_roles(decoded),
        "permissions": _extract_jwt_permissions(decoded),
    }


def _extract_jwt_roles(decoded: Dict[str, Any]) -> list[Any]:
    """Extract roles from decoded JWT claims."""
    if "roles" in decoded:
        return decoded["roles"] if isinstance(decoded["roles"], list) else []
    if "realm_access" in decoded and isinstance(decoded["realm_access"], dict):
        roles = decoded["realm_access"].get("roles", [])
        return roles if isinstance(roles, list) else []
    return []


def _extract_jwt_permissions(decoded: Dict[str, Any]) -> list[Any]:
    """Extract permissions from decoded JWT claims."""
    if "permissions" in decoded:
        return decoded["permissions"] if isinstance(decoded["permissions"], list) else []
    if "scope" in decoded and isinstance(decoded["scope"], str):
        return decoded["scope"].split()
    return []


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


AUTO_CONTEXT_KEYS = {
    "applicationId",
    "clientId",
    "correlationId",
    "ipAddress",
    "requestId",
    "requestSize",
    "sessionId",
    "token",
    "userAgent",
    "userId",
}

TRACEABILITY_KEYS = {
    "applicationId",
    "clientId",
    "correlationId",
    "requestId",
    "userId",
    "application",
    "environment",
}


def _is_empty_trace_value(value: Any) -> bool:
    """Return True for empty traceability values.

    Empty values include None, empty string, and whitespace-only string.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _pick_first_non_empty(*values: Any) -> Optional[str]:
    """Pick first non-empty value from candidates and stringify it."""
    for value in values:
        if not _is_empty_trace_value(value):
            return str(value).strip() if isinstance(value, str) else str(value)
    return None


def merge_traceability_context(
    stored_context: Dict[str, Any], explicit_context: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge context dicts without empty-value clobbering on traceability keys."""
    merged: Dict[str, Any] = dict(stored_context)
    for key, value in explicit_context.items():
        if key in TRACEABILITY_KEYS:
            if _is_empty_trace_value(value):
                # Keep existing non-empty value, or drop empty explicit value.
                continue
            merged[key] = value
            continue
        merged[key] = value
    return merged


def split_log_context(context: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split context into additional context and auto-computable fields.

    Args:
        context: Context dictionary (optional)

    Returns:
        Tuple of (context_without_auto_fields, auto_fields)

    """
    if not context:
        return {}, {}

    auto_fields = {key: value for key, value in context.items() if key in AUTO_CONTEXT_KEYS}
    remaining_context = {
        key: value for key, value in context.items() if key not in AUTO_CONTEXT_KEYS
    }
    return remaining_context, auto_fields


def _convert_to_foreign_key_reference(
    value: Optional[Union[str, ForeignKeyReference]], entity_type: str
) -> Optional[ForeignKeyReference]:
    """Convert string id or object into `ForeignKeyReference`."""
    if value is None:
        return None
    if isinstance(value, ForeignKeyReference):
        return value
    if isinstance(value, str):
        return ForeignKeyReference(
            id=value,
            key=value,
            name=value,
            type=entity_type,
        )
    return None


def _resolve_application_and_environment(
    context: Optional[Dict[str, Any]],
    options: Optional[ClientLoggingOptions],
    app_context: Dict[str, Optional[str]],
    config_client_id: str,
) -> Tuple[str, str]:
    """Resolve application and environment names using deterministic precedence."""
    context_application = context.get("application") if isinstance(context, dict) else None
    context_environment = context.get("environment") if isinstance(context, dict) else None

    application_name = (
        _pick_first_non_empty(
            options.application if options else None,
            context_application if isinstance(context_application, str) else None,
            app_context.get("application"),
            config_client_id,
        )
        or config_client_id
    )
    environment_name = (
        _pick_first_non_empty(
            options.environment if options else None,
            context_environment if isinstance(context_environment, str) else None,
            app_context.get("environment"),
            "unknown",
        )
        or "unknown"
    )
    return application_name, environment_name


def _resolve_traceability_identifiers(
    auto_fields: Dict[str, Any],
    jwt_context: Dict[str, Any],
    app_context: Dict[str, Optional[str]],
    correlation_id: Optional[str],
) -> Dict[str, Optional[str]]:
    """Resolve traceability identifiers using non-empty precedence rules."""
    return {
        "final_correlation_id": _pick_first_non_empty(
            correlation_id, auto_fields.get("correlationId")
        ),
        "client_id_value": _pick_first_non_empty(auto_fields.get("clientId")),
        "application_id_value": _pick_first_non_empty(
            auto_fields.get("applicationId"),
            app_context.get("applicationId"),
            jwt_context.get("applicationId"),
        ),
        "user_id_value": _pick_first_non_empty(
            auto_fields.get("userId"), jwt_context.get("userId")
        ),
        "session_id_value": _pick_first_non_empty(
            auto_fields.get("sessionId"), jwt_context.get("sessionId")
        ),
        "request_id_value": _pick_first_non_empty(auto_fields.get("requestId")),
        "ip_address_value": _pick_first_non_empty(auto_fields.get("ipAddress")),
        "user_agent_value": _pick_first_non_empty(auto_fields.get("userAgent")),
    }


def _ensure_nested_application_id(
    masked_context: Optional[Dict[str, Any]], application_id_value: Optional[str]
) -> None:
    """Keep non-empty nested applicationId in context for transport compatibility."""
    if not isinstance(masked_context, dict):
        return
    context_application_id = _pick_first_non_empty(masked_context.get("applicationId"))
    resolved_context_application_id = _pick_first_non_empty(
        context_application_id, application_id_value
    )
    if resolved_context_application_id:
        masked_context["applicationId"] = resolved_context_application_id


def _build_optional_option_fields(
    options: Optional[ClientLoggingOptions], request_size: Any
) -> Dict[str, Any]:
    """Build optional option-derived fields for LogEntry payload."""
    return {
        "sourceId": options.sourceId if options else None,
        "sourceDisplayName": options.sourceDisplayName if options else None,
        "externalSystemId": options.externalSystemId if options else None,
        "externalSystemDisplayName": options.externalSystemDisplayName if options else None,
        "recordId": options.recordId if options else None,
        "recordDisplayName": options.recordDisplayName if options else None,
        "credentialId": options.credentialId if options else None,
        "credentialType": options.credentialType if options else None,
        "requestSize": request_size,
        "responseSize": options.responseSize if options else None,
        "durationMs": options.durationMs if options else None,
        "durationSeconds": options.durationSeconds if options else None,
        "timeout": options.timeout if options else None,
        "retryCount": options.retryCount if options else None,
        "errorCategory": options.errorCategory if options else None,
        "httpStatusCategory": options.httpStatusCategory if options else None,
    }


def _build_log_entry_data(level: LogLevel, message: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """Build raw LogEntry payload before model validation."""
    options = values["options"]
    base_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "environment": values["environment_name"],
        "application": values["application_name"],
        "clientId": values["client_id_value"],
        "applicationId": values["application_id_ref"],
        "message": message,
        "context": values["masked_context"],
        "stackTrace": values["stack_trace"],
        "correlationId": values["final_correlation_id"],
        "userId": values["user_id_ref"],
        "sessionId": values["session_id_value"],
        "requestId": values["request_id_value"],
        "ipAddress": values["ip_address_value"],
        "userAgent": values["user_agent_value"],
        **values["env_metadata"],
    }
    base_payload.update(_build_optional_option_fields(options, values["request_size"]))
    return base_payload


def _resolve_auto_fields_and_context(
    context: Optional[Dict[str, Any]], auto_fields: Optional[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Resolve auto fields and normalized context."""
    resolved_auto_fields = auto_fields or {}
    if auto_fields is None:
        context, resolved_auto_fields = split_log_context(context)
    return context, resolved_auto_fields


def _resolve_masked_context(
    context: Optional[Dict[str, Any]],
    options: Optional[ClientLoggingOptions],
    mask_sensitive: bool,
) -> Optional[Dict[str, Any]]:
    """Resolve masking decision and return context payload."""
    should_mask = (options.maskSensitiveData if options else None) is not False and mask_sensitive
    return DataMasker.mask_sensitive_data(context) if should_mask and context else context


def _resolve_log_entry_inputs(params: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve normalized inputs used by log entry construction."""
    context, auto_fields = params["context"], params["auto_fields"]
    options, config_client_id = params["options"], params["config_client_id"]
    correlation_id, jwt_token = params["correlation_id"], params["jwt_token"]
    metadata, mask_sensitive = params["metadata"], params["mask_sensitive"]
    application_context = params["application_context"]
    context, resolved_auto_fields = _resolve_auto_fields_and_context(context, auto_fields)
    token_value = jwt_token or resolved_auto_fields.get("token")
    jwt_context = extract_jwt_context(token_value)
    env_metadata = metadata or extract_metadata()
    masked_context = _resolve_masked_context(context, options, mask_sensitive)
    app_context = application_context or {}
    application_name, environment_name = _resolve_application_and_environment(
        context, options, app_context, config_client_id
    )
    traceability = _resolve_traceability_identifiers(
        resolved_auto_fields, jwt_context, app_context, correlation_id
    )
    _ensure_nested_application_id(masked_context, traceability["application_id_value"])
    return {
        "resolved_auto_fields": resolved_auto_fields,
        "env_metadata": env_metadata,
        "masked_context": masked_context,
        "application_name": application_name,
        "environment_name": environment_name,
        **traceability,
    }


def _drop_none_values(log_entry_data: Dict[str, Any]) -> Dict[str, Any]:
    """Drop None values from payload before LogEntry validation."""
    return {k: v for k, v in log_entry_data.items() if v is not None}


def _build_log_entry_values(
    resolved_inputs: Dict[str, Any],
    options: Optional[ClientLoggingOptions],
    stack_trace: Optional[str],
    config_client_id: str,
) -> Dict[str, Any]:
    """Build values map used by final LogEntry payload assembly."""
    application_id_ref = _convert_to_foreign_key_reference(
        resolved_inputs["application_id_value"], "Application"
    )
    user_id_ref = _convert_to_foreign_key_reference(resolved_inputs["user_id_value"], "User")
    return {
        **resolved_inputs,
        "client_id_value": resolved_inputs["client_id_value"] or config_client_id,
        "application_id_ref": application_id_ref,
        "user_id_ref": user_id_ref,
        "stack_trace": stack_trace,
        "options": options,
        "request_size": resolved_inputs["resolved_auto_fields"].get("requestSize"),
    }


def _build_resolve_params(
    context: Optional[Dict[str, Any]],
    auto_fields: Optional[Dict[str, Any]],
    options: Optional[ClientLoggingOptions],
    config_client_id: str,
    correlation_id: Optional[str],
    jwt_token: Optional[str],
    metadata: Optional[Dict[str, Any]],
    mask_sensitive: bool,
    application_context: Optional[Dict[str, Optional[str]]],
) -> Dict[str, Any]:
    """Build resolver input dictionary for log entry normalization."""
    return {
        "context": context,
        "auto_fields": auto_fields,
        "options": options,
        "config_client_id": config_client_id,
        "correlation_id": correlation_id,
        "jwt_token": jwt_token,
        "metadata": metadata,
        "mask_sensitive": mask_sensitive,
        "application_context": application_context,
    }


def build_log_entry(
    level: LogLevel,
    message: str,
    context: Optional[Dict[str, Any]],
    config_client_id: str,
    correlation_id: Optional[str] = None,
    jwt_token: Optional[str] = None,
    stack_trace: Optional[str] = None,
    options: Optional[ClientLoggingOptions] = None,
    auto_fields: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    mask_sensitive: bool = True,
    application_context: Optional[Dict[str, Optional[str]]] = None,
) -> LogEntry:
    """Build and validate a `LogEntry` using normalized traceability fields."""
    return _build_log_entry_internal(
        level=level,
        message=message,
        context=context,
        config_client_id=config_client_id,
        correlation_id=correlation_id,
        jwt_token=jwt_token,
        stack_trace=stack_trace,
        options=options,
        auto_fields=auto_fields,
        metadata=metadata,
        mask_sensitive=mask_sensitive,
        application_context=application_context,
    )


def _build_log_entry_internal(
    level: LogLevel,
    message: str,
    context: Optional[Dict[str, Any]],
    config_client_id: str,
    correlation_id: Optional[str] = None,
    jwt_token: Optional[str] = None,
    stack_trace: Optional[str] = None,
    options: Optional[ClientLoggingOptions] = None,
    auto_fields: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    mask_sensitive: bool = True,
    application_context: Optional[Dict[str, Optional[str]]] = None,
) -> LogEntry:
    resolved_inputs = _resolve_log_entry_inputs(
        _build_resolve_params(
            context,
            auto_fields,
            options,
            config_client_id,
            correlation_id,
            jwt_token,
            metadata,
            mask_sensitive,
            application_context,
        )
    )
    values = _build_log_entry_values(resolved_inputs, options, stack_trace, config_client_id)
    log_entry_data = _build_log_entry_data(level=level, message=message, values=values)
    return LogEntry(**_drop_none_values(log_entry_data))


def transform_log_entry_to_request(log_entry: LogEntry) -> Any:
    """Transform LogEntry to API ``LogRequest``."""
    return _transform_log_entry_to_request(log_entry)
