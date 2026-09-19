"""Keep managed application credentials on their configured HTTPS origin."""

from __future__ import annotations

from typing import Any, Dict

import httpx

from ..models.bootstrap import BootstrapError


class ManagedRequestPolicy:
    """Pin the controller origin once, independently of mutable client config."""

    def __init__(self, controller_url: str):
        self.origin = httpx.URL(controller_url)
        if self.origin.scheme != "https" or not self.origin.host or self.origin.userinfo:
            raise BootstrapError("invalid-azure-settings")

    def prepare(self, base: httpx.URL, url: str, kwargs: Dict[str, Any]) -> None:
        """Reject credential forwarding and disable redirects before token lookup."""
        allowed = False
        try:
            target = httpx.URL(url)
            target = target if target.is_absolute_url else base.join(target)
            allowed = (
                not url.startswith("//")
                and not target.userinfo
                and all(
                    (candidate.scheme, candidate.host, candidate.port)
                    == (self.origin.scheme, self.origin.host, self.origin.port)
                    for candidate in (base, target)
                )
            )
        except (ValueError, httpx.InvalidURL):
            allowed = False  # Never expose malformed URLs through parser diagnostics.
        if not allowed or kwargs.get("auth") is not None:
            raise BootstrapError("untrusted-request-target")
        kwargs["follow_redirects"] = False
