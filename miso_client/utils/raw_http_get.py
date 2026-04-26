"""Ephemeral HTTP GET for arbitrary absolute URLs (CIP / external APIs).

Uses a short-lived ``httpx.AsyncClient`` without the controller ``base_url`` or
``x-client-token`` headers, so callers pass the full URL and outbound headers
(e.g. OAuth Bearer) only. Intended for binary GETs where JSON/text adapters would
fail (``UnicodeDecodeError`` on ``/content``-style bodies).
"""

from typing import Any, Dict, Optional

import httpx


async def raw_http_get(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
    follow_redirects: bool = False,
) -> httpx.Response:
    """Perform GET and return the raw ``httpx`` response (no ``.json()`` / body decode)."""
    async with httpx.AsyncClient(
        follow_redirects=follow_redirects,
        timeout=timeout,
    ) as client:
        return await client.get(url, headers=headers or None, params=params)
