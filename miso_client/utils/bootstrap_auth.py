"""Interpret only controller-defined application bootstrap errors on normal APIs."""

from __future__ import annotations

from typing import Dict, cast

import httpx

from ..models.bootstrap import ApplicationTokenProvider

BOOTSTRAP_AUTH_ERRORS = {
    "bootstrap_identity_disabled": 403,
    "bootstrap_binding_mismatch": 403,
    "bootstrap_token_invalid": 401,
    "bootstrap_token_expired": 401,
}


def bootstrap_error_code(response: httpx.Response) -> str:
    """Extract an allowlisted code, without retaining raw diagnostic payloads."""
    if response.status_code not in (401, 403) or len(response.content) > 65536:
        return ""
    code: object = None
    try:
        data: object = response.json()
        if isinstance(data, dict):
            code = cast(Dict[str, object], data).get("code")
    except (ValueError, TypeError, RecursionError):
        code = None  # Ordinary malformed error bodies carry no trusted runtime code.
    if isinstance(code, str) and BOOTSTRAP_AUTH_ERRORS.get(code) == response.status_code:
        return code
    return ""


async def handle_bootstrap_auth_response(
    response: httpx.Response, provider: ApplicationTokenProvider
) -> None:
    """Notify the runtime without treating user/RBAC failures as identity revocation."""
    code = bootstrap_error_code(response)
    if not code:
        return
    token = response.request.headers.get("x-client-token")
    await provider.handle_auth_error(code, token)
