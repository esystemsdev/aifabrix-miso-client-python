"""HTTP client logging utilities for ISO 27001 compliant audit and debug logging.

This module provides logging functionality extracted from HttpClient to keep
the main HTTP client class focused and within size limits. All sensitive data
is automatically masked using DataMasker before logging.
"""

import time
from typing import Any, Dict, Optional

from .http_log_formatter import build_audit_context, build_debug_context
from .http_log_masker import (
    extract_and_mask_query_params,
    mask_error_message,
    mask_request_data,
    mask_response_data,
)


def should_skip_logging(url: str, config: Optional[Any] = None) -> bool:
    """Check whether request logging should be skipped."""
    if config and config.audit and config.audit.enabled is False:
        return True

    if config and config.audit and config.audit.skipEndpoints:
        for endpoint in config.audit.skipEndpoints:
            if endpoint in url:
                return True

    if url == "/api/v1/logs" or url.startswith("/api/v1/logs"):
        return True

    client_token_uri = "/api/v1/auth/token"
    if config and config.clientTokenUri:
        client_token_uri = config.clientTokenUri

    if url == client_token_uri or url.startswith(client_token_uri):
        return True
    return False


def calculate_request_metrics(
    start_time: float, response: Optional[Any] = None, error: Optional[Exception] = None
) -> tuple[int, Optional[int]]:
    """Calculate duration and response status for request logging."""
    duration_ms = int((time.perf_counter() - start_time) * 1000)

    status_code: Optional[int] = None
    if response is not None:
        response_status = getattr(response, "status_code", None)
        if isinstance(response_status, int):
            status_code = response_status
        else:
            status_code = 200
    elif error is not None:
        response_obj = getattr(error, "response", None)
        response_status = getattr(response_obj, "status_code", None)
        if isinstance(response_status, int):
            status_code = response_status
        elif hasattr(error, "status_code"):
            status_code = error.status_code
        else:
            status_code = 500

    return duration_ms, status_code


def calculate_request_sizes(
    request_data: Optional[Dict[str, Any]], response: Optional[Any]
) -> tuple[Optional[int], Optional[int]]:
    """Calculate request and response sizes in bytes.

    Args:
        request_data: Request body data
        response: Response data

    Returns:
        Tuple of (request_size, response_size) in bytes, None if unavailable

    """
    request_size: Optional[int] = None
    if request_data is not None:
        try:
            request_str = str(request_data)
            request_size = len(request_str.encode("utf-8"))
        except Exception:
            pass

    response_size: Optional[int] = None
    if response is not None:
        try:
            response_str = str(response)
            response_size = len(response_str.encode("utf-8"))
        except Exception:
            pass

    return request_size, response_size


def _prepare_audit_context(
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    log_level: str,
    audit_config: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Prepare audit context for logging."""
    duration_ms, status_code = calculate_request_metrics(start_time, response, error)
    audit_level = (audit_config or {}).get("level", "detailed")
    request_size, response_size = _resolve_request_response_sizes(
        audit_level, request_data, response
    )
    error_message = mask_error_message(error) if error is not None else None
    return build_audit_context(
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        request_size=request_size,
        response_size=response_size,
        error_message=error_message,
        correlation_id=correlation_id,
    )


def _resolve_request_response_sizes(
    audit_level: str, request_data: Optional[Dict[str, Any]], response: Optional[Any]
) -> tuple[Optional[int], Optional[int]]:
    """Resolve request/response sizes for configured audit level."""
    if audit_level in ("detailed", "full"):
        return calculate_request_sizes(request_data, response)
    return None, None


def _extract_correlation_id(
    error: Optional[Exception], correlation_id: Optional[str]
) -> Optional[str]:
    """Resolve correlation ID from explicit argument or exception metadata."""
    if correlation_id is not None or error is None:
        return correlation_id
    from ..utils.error_utils import extract_correlation_id_from_error

    return extract_correlation_id_from_error(error)


def _extract_audit_config(config: Optional[Any]) -> tuple[Optional[Any], str]:
    """Extract audit config object and effective audit level."""
    if config and config.audit:
        audit_config = config.audit
        return audit_config, audit_config.level or "detailed"
    return None, "detailed"


def _to_dict_audit_config(audit_config: Optional[Any]) -> Dict[str, Any]:
    """Normalize audit config object into dictionary."""
    if audit_config is None:
        return {}
    if hasattr(audit_config, "model_dump"):
        result = audit_config.model_dump()
        return result if isinstance(result, dict) else {}
    if hasattr(audit_config, "dict"):
        result = audit_config.dict()  # type: ignore[attr-defined]
        return result if isinstance(result, dict) else {}
    return {}


def _build_minimal_audit_context(
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    user_id: Optional[str],
    correlation_id: Optional[str],
) -> Dict[str, Any]:
    """Build minimal-level audit context."""
    duration_ms, status_code = calculate_request_metrics(start_time, response, error)
    context: Dict[str, Any] = {
        "method": method,
        "url": url,
        "statusCode": status_code,
        "duration": duration_ms,
    }
    if user_id:
        context["userId"] = user_id
    if error:
        context["error"] = str(error)
    if correlation_id:
        context["correlationId"] = correlation_id
    return context


async def _log_minimal_audit(
    logger: Any,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    user_id: Optional[str],
    correlation_id: Optional[str],
) -> None:
    """Log minimal-level audit event."""
    context = _build_minimal_audit_context(
        method, url, response, error, start_time, user_id, correlation_id
    )
    await logger.audit(f"http.request.{method.upper()}", url, context)


async def _log_standard_audit(
    logger: Any,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    log_level: str,
    audit_config: Optional[Any],
    correlation_id: Optional[str],
) -> None:
    """Log non-minimal audit event."""
    context = _prepare_audit_context(
        method,
        url,
        response,
        error,
        start_time,
        request_data,
        user_id,
        log_level,
        _to_dict_audit_config(audit_config),
        correlation_id=correlation_id,
    )
    if context is not None:
        await logger.audit(f"http.request.{method.upper()}", url, context)


async def log_http_request_audit(
    logger: Any,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    log_level: str,
    config: Optional[Any] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Log HTTP request audit event with ISO 27001 masking."""
    try:
        await _log_http_request_audit_impl(
            logger,
            method,
            url,
            response,
            error,
            start_time,
            request_data,
            user_id,
            log_level,
            config,
            correlation_id,
        )
    except Exception:
        pass


async def _log_http_request_audit_impl(
    logger: Any,
    method: str,
    url: str,
    response: Optional[Any],
    error: Optional[Exception],
    start_time: float,
    request_data: Optional[Dict[str, Any]],
    user_id: Optional[str],
    log_level: str,
    config: Optional[Any],
    correlation_id: Optional[str],
) -> None:
    if should_skip_logging(url, config):
        return
    resolved_correlation_id = _extract_correlation_id(error, correlation_id)
    audit_config, audit_level = _extract_audit_config(config)
    context: Dict[str, Any] = {
        "method": method,
        "url": url,
        "response": response,
        "error": error,
        "start_time": start_time,
        "request_data": request_data,
        "user_id": user_id,
        "log_level": log_level,
        "audit_config": audit_config,
        "correlation_id": resolved_correlation_id,
    }
    await _log_by_audit_level(logger, audit_level, context)


async def _log_by_audit_level(logger: Any, audit_level: str, context: Dict[str, Any]) -> None:
    """Dispatch to minimal or standard audit logging by configured level."""
    method = str(context["method"])
    url = str(context["url"])
    response = context["response"]
    error = context["error"]
    start_time = float(context["start_time"])
    request_data = context["request_data"]
    user_id = context["user_id"]
    log_level = str(context["log_level"])
    audit_config = context["audit_config"]
    correlation_id = context["correlation_id"]
    if audit_level == "minimal":
        await _log_minimal_audit(
            logger, method, url, response, error, start_time, user_id, correlation_id
        )
        return
    await _log_standard_audit(
        logger,
        method,
        url,
        response,
        error,
        start_time,
        request_data,
        user_id,
        log_level,
        audit_config,
        correlation_id,
    )


def _prepare_debug_context(
    method: str,
    url: str,
    response: Optional[Any],
    duration_ms: int,
    status_code: Optional[int],
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
    base_url: str,
    max_response_size: Optional[int] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepare debug context for logging."""
    return build_debug_context(
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms,
        base_url=base_url,
        user_id=user_id,
        masked_headers=mask_request_data(request_headers, request_data)[0],
        masked_body=mask_request_data(request_headers, request_data)[1],
        masked_response=mask_response_data(response, max_size=max_response_size),
        query_params=extract_and_mask_query_params(url),
        correlation_id=correlation_id,
    )


def _resolve_max_response_size(config: Optional[Any]) -> Optional[int]:
    """Extract max response size from audit configuration."""
    if config and config.audit and hasattr(config.audit, "maxResponseSize"):
        max_size = config.audit.maxResponseSize
        if isinstance(max_size, int):
            return max_size
    return None


async def log_http_request_debug(
    logger: Any,
    method: str,
    url: str,
    response: Optional[Any],
    duration_ms: int,
    status_code: Optional[int],
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
    base_url: str,
    config: Optional[Any] = None,
    correlation_id: Optional[str] = None,
) -> None:
    """Log detailed debug information for HTTP request."""
    try:
        await _log_http_request_debug_impl(
            logger,
            method,
            url,
            response,
            duration_ms,
            status_code,
            user_id,
            request_data,
            request_headers,
            base_url,
            config,
            correlation_id,
        )
    except Exception:
        pass


async def _log_http_request_debug_impl(
    logger: Any,
    method: str,
    url: str,
    response: Optional[Any],
    duration_ms: int,
    status_code: Optional[int],
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    request_headers: Optional[Dict[str, Any]],
    base_url: str,
    config: Optional[Any],
    correlation_id: Optional[str],
) -> None:
    """Internal debug logging implementation."""
    debug_context = _prepare_debug_context(
        method,
        url,
        response,
        duration_ms,
        status_code,
        user_id,
        request_data,
        request_headers,
        base_url,
        max_response_size=_resolve_max_response_size(config),
        correlation_id=correlation_id,
    )
    await logger.debug(
        f"HTTP {method} {url} - Status: {status_code}, Duration: {duration_ms}ms",
        debug_context,
    )
