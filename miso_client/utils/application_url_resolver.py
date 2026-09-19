"""Resolve public ``url://`` references through the existing application-status API."""

from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

from ..models.config import AuthStrategy


@dataclass(frozen=True)
class PublicUrlReference:
    """Parsed public URL reference."""

    target_key: Optional[str]
    surface: str


def parse_public_application_url_reference(reference: str) -> PublicUrlReference:
    """Parse the Builder-compatible public subset of the ``url://`` grammar."""
    if not reference.startswith("url://"):
        raise ValueError("URL reference must start with url://")
    token = reference[len("url://") :].strip()
    exact = {"public": "full", "host-public": "host", "vdir-public": "vdir"}
    if token in exact:
        return PublicUrlReference(None, exact[token])
    if token in {"internal", "private"} or token.endswith(("-internal", "-private")):
        raise ValueError("Runtime clients can resolve only public URL references")
    for suffix, surface in (
        ("-host-public", "host"),
        ("-vdir-public", "vdir"),
        ("-public", "full"),
    ):
        if token.endswith(suffix):
            target = token[: -len(suffix)]
            if not target:
                raise ValueError("URL reference target is required")
            return PublicUrlReference(target, surface)
    return PublicUrlReference(None, "full")


def _project_public_url(value: str, surface: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Canonical application URL must use HTTP or HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("Canonical application URL must not contain credentials")
    if surface == "host":
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    if surface == "vdir":
        return parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


async def resolve_public_application_url(
    reader: Any,
    env_key: str,
    own_app_key: str,
    reference: str,
    auth_strategy: Optional[AuthStrategy] = None,
) -> str:
    """Read and project one current public application URL."""
    parsed = parse_public_application_url_reference(reference)
    status = await reader.get_application_status(
        env_key, parsed.target_key or own_app_key, auth_strategy
    )
    value = status.url
    if not value:
        raise ValueError("Referenced application public URL is unavailable")
    return _project_public_url(value, parsed.surface)


async def resolve_public_origins(
    reader: Any,
    env_key: str,
    own_app_key: str,
    origins: Optional[list[str]],
    auth_strategy: Optional[AuthStrategy] = None,
) -> Optional[list[str]]:
    """Resolve and deduplicate a mixed CORS list without retaining a client-local cache."""
    if origins is None:
        return None
    resolved: list[str] = []
    for entry in (item.strip() for value in origins for item in value.split(",")):
        if not entry:
            continue
        if entry.startswith("url://"):
            public_url = await resolve_public_application_url(
                reader, env_key, own_app_key, entry, auth_strategy
            )
            parsed = urlsplit(public_url)
            entry = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
        if entry not in resolved:
            resolved.append(entry)
    return resolved
