"""Sanitize controller diagnostics before they become public exception data."""

import json
from typing import Any, Iterable, cast

import httpx

from .data_masker import DataMasker

_AUTH_METHODS = {"bearer", "client-token", "client-credentials", "api-key"}

_DIAGNOSTICS = {
    "type",
    "title",
    "status",
    "statusCode",
    "code",
    "detail",
    "authMethod",
    "clientIdentity",
    "instance",
    "correlationId",
    "errors",
}


def _secret_values(value: Any) -> set[str]:
    """Collect values under sensitive keys, including nested request payloads."""
    values: set[str] = set()
    if isinstance(value, dict):
        for key, item in cast(dict[str, Any], value).items():
            if key == "authMethod" and isinstance(item, str) and item in _AUTH_METHODS:
                continue
            if DataMasker.is_sensitive_field(str(key)) and isinstance(item, str) and item:
                values.add(item)
            values.update(_secret_values(item))
    elif isinstance(value, list):
        for item in cast(list[Any], value):
            values.update(_secret_values(item))
    return values


def _redact(value: Any, secrets: set[str]) -> Any:
    if isinstance(value, str):
        for secret in sorted(secrets, key=len, reverse=True):
            value = value.replace(secret, DataMasker.MASKED_VALUE)
        return value
    if isinstance(value, dict):
        return {
            _redact(key, secrets): _redact(item, secrets)
            for key, item in cast(dict[str, Any], value).items()
        }
    if isinstance(value, list):
        return [_redact(item, secrets) for item in cast(list[Any], value)]
    return value


def safe_error_body(
    response: httpx.Response, known_secrets: Iterable[str], managed: bool
) -> dict[str, Any]:
    """Return bounded JSON diagnostics with sensitive fields and known values masked.

    Args:
        response: Failed HTTP response, including its request when available.
        known_secrets: Configured credentials not necessarily present in the response.
        managed: Restrict runtime errors to controller diagnostic fields.
    """
    try:
        if len(response.content) > 65536:
            return {}
        body = response.json()
        if not isinstance(body, dict):
            return {}
        body = cast(dict[str, Any], body)
        secrets = {value for value in known_secrets if value} | _secret_values(body)
        secrets.update(_request_secrets(response))
        selected = {key: value for key, value in body.items() if not managed or key in _DIAGNOSTICS}
        _add_correlation(selected, response)
        masked = DataMasker.mask_sensitive_data(selected)
        auth_method = selected.get("authMethod")
        if isinstance(auth_method, str) and auth_method in _AUTH_METHODS:
            masked["authMethod"] = auth_method
        return dict(_redact(masked, secrets))
    except (ValueError, TypeError, RecursionError):
        return {}


def _add_correlation(selected: dict[str, Any], response: httpx.Response) -> None:
    """Copy a correlation header before redacting all diagnostic strings."""
    if not selected.get("correlationId"):
        for header in (
            "x-correlation-id",
            "x-request-id",
            "correlation-id",
            "correlationId",
            "x-correlationid",
            "request-id",
        ):
            correlation = response.headers.get(header)
            if isinstance(correlation, str) and correlation:
                selected["correlationId"] = correlation
                break


def _request_secrets(response: httpx.Response) -> set[str]:
    try:
        request = response.request
    except RuntimeError:
        return set()
    values = _secret_values(dict(request.headers))
    authorization = request.headers.get("authorization", "")
    if " " in authorization:
        values.add(authorization.split(" ", 1)[1])
    try:
        body = json.loads(request.content)
        values.update(_secret_values(body))
        if isinstance(body, dict):
            body = cast(dict[str, Any], body)
            for field in ("plaintext", "value"):
                if isinstance(body.get(field), str) and body[field]:
                    values.add(body[field])
    except (ValueError, TypeError, UnicodeDecodeError, httpx.RequestNotRead):
        pass
    return values


def safe_error_text(response: httpx.Response, known_secrets: Iterable[str]) -> str:
    """Preserve bounded non-JSON provider explanations without echoed credentials."""
    if "json" in response.headers.get("content-type", ""):
        return ""
    text = response.text
    return str(
        _redact(
            text[:65536], {value for value in known_secrets if value} | _request_secrets(response)
        )
    )
