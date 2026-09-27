"""Decide which transport a request may use.

The SDK owns one application credential: the client token. It belongs to the
Miso controller and to nothing else. Every request is therefore classified by
its target origin before any credential is looked up:

* **controller target** — a relative path, or an absolute URL whose scheme,
  host and port equal one of the configured controller URLs. These requests
  carry ``x-client-token`` and, under a managed runtime, the origin pin.
* **external target** — every other absolute URL (LLM providers, CRMs,
  SharePoint, webhooks). These requests travel on a plain transport that adds
  nothing of the SDK's; SDK credential headers a caller may have copied in are
  removed. Protocol-relative URLs (``//host/...``) are external: their scheme
  would be borrowed from the controller, so they can never be trusted.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple, Union, cast

import httpx

from ..models.config import MisoClientConfig

Origin = Tuple[str, str, int]

SDK_CREDENTIAL_HEADERS = ("x-client-token", "x-client-id", "x-client-secret")
_DEFAULT_PORTS = {"http": 80, "https": 443}


def origin_of(url: Any) -> Optional[Origin]:
    """``(scheme, host, effective port)`` of an absolute URL; ``None`` otherwise."""
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        parsed = httpx.URL(url.strip())
    except (ValueError, httpx.InvalidURL):
        return None
    if not parsed.is_absolute_url or not parsed.host:
        return None
    scheme = parsed.scheme.lower()
    port = parsed.port or _DEFAULT_PORTS.get(scheme, 0)
    return (scheme, parsed.host.lower(), port)


class RequestTarget:
    """Classify request URLs against the configured controller origins."""

    def __init__(self, config: MisoClientConfig) -> None:
        self._origins: Set[Origin] = set()
        for candidate in (
            config.controller_url,
            getattr(config, "controllerPrivateUrl", None),
            getattr(config, "controllerPublicUrl", None),
        ):
            origin = origin_of(candidate)
            if origin is not None:
                self._origins.add(origin)

    @property
    def controller_origins(self) -> Set[Origin]:
        return set(self._origins)

    def is_controller(self, url: str) -> bool:
        """Relative paths and controller-origin URLs; protocol-relative never."""
        text = str(url).strip()
        if text.startswith("//"):
            return False
        origin = origin_of(text)
        if origin is None:
            return True
        return origin in self._origins

    @staticmethod
    def strip_sdk_credentials(kwargs: Dict[str, Any]) -> None:
        """Drop SDK credential headers a caller copied into an external request."""
        headers = kwargs.get("headers")
        if not isinstance(headers, dict):
            return
        typed: Dict[str, Any] = cast(Dict[str, Any], headers)
        for name in [str(key) for key in typed]:
            if name.lower() in SDK_CREDENTIAL_HEADERS:
                del typed[name]


def build_external_client(timeout: Union[float, httpx.Timeout]) -> httpx.AsyncClient:
    """Plain transport for external targets: no base URL, no default headers."""
    return httpx.AsyncClient(timeout=timeout, trust_env=True, follow_redirects=False)
