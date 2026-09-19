"""Strict v1 parsing and independent wall/monotonic snapshot deadlines."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, cast

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictInt, ValidationError

from ..models.bootstrap import BootstrapContext, BootstrapError

MAX_BODY = 1024 * 1024
RESERVED_KEYS = {
    "MISO_AUTH_MODE",
    "MISO_AUTH_STRATEGY",
    "MISO_CONTROLLER_URL",
    "MISO_WEB_SERVER_URL",
    "MISO_BOOTSTRAP_AUDIENCE",
    "AZURE_CLIENT_ID",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_SECRET",
    "MISO_CLIENTID",
    "MISO_CLIENT_ID",
    "MISO_CLIENTSECRET",
    "MISO_CLIENT_SECRET",
    "MISO_CLIENT_TOKEN_URI",
}


class Snapshot(BaseModel):
    """Confidential validated response; values never appear in repr/dumps."""

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    protocolVersion: StrictInt
    issuedAt: str
    context: BootstrapContext
    clientId: str = Field(min_length=1, max_length=256)
    clientToken: SecretStr = Field(repr=False, exclude=True)
    clientTokenExpiresAt: str
    configuration: Dict[str, SecretStr] = Field(repr=False, exclude=True)
    refreshAfter: str
    expiresAt: str


def _unique_object(pairs: List[Tuple[str, object]]) -> Dict[str, object]:
    """Reject duplicate members before model construction."""
    result: Dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate member")
        result[key] = value
    return result


def timestamp(value: str) -> float:
    """Parse an explicit UTC RFC3339 timestamp."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value):
        raise ValueError("invalid timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _validate_values(snapshot: Snapshot, now: float) -> None:
    """Enforce fixed v1 types, bounds and timing policy."""
    issued = timestamp(snapshot.issuedAt)
    if snapshot.protocolVersion != 1 or abs(now - issued) > 30:
        raise ValueError("protocol or clock")
    for value, delta in (
        (snapshot.refreshAfter, 120),
        (snapshot.clientTokenExpiresAt, 300),
        (snapshot.expiresAt, 900),
    ):
        if timestamp(value) != issued + delta:
            raise ValueError("invalid deadline")
    if timestamp(snapshot.refreshAfter) <= now:
        raise ValueError("past refresh")
    token = snapshot.clientToken.get_secret_value()
    if not token or len(token) > 65536 or len(snapshot.configuration) > 256:
        raise ValueError("invalid bounds")
    for name, secret in snapshot.configuration.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", name) or name in RESERVED_KEYS:
            raise ValueError("invalid key")
        if len(secret.get_secret_value().encode("utf-8")) > 65536:
            raise ValueError("oversize value")


def parse_snapshot(body: bytes, now: float) -> Snapshot:
    """Parse broker bytes without retaining sensitive validation exceptions.

    Args:
        body: Decoded, size-bounded HTTP response bytes.
        now: Wall-clock receipt time in seconds.

    Returns:
        Validated confidential snapshot.
    """
    result: Optional[Snapshot] = None
    try:
        if len(body) > MAX_BODY:
            raise ValueError("oversize")
        raw = cast(object, json.loads(body, object_pairs_hook=_unique_object))
        if not isinstance(raw, dict):
            raise ValueError("envelope")
        envelope = cast(Dict[str, object], raw)
        if envelope.get("success") is not True:
            raise ValueError("envelope")
        candidate = Snapshot.model_validate(envelope.get("data"))
        _validate_values(candidate, now)
        result = candidate
    except (ValueError, TypeError, ValidationError, RecursionError):
        pass
    if result is None:
        raise BootstrapError("protocol-error")
    return result


class SnapshotClock:
    """Conservative deadlines that cannot be extended by a wall-clock rollback."""

    def __init__(self, snapshot: Snapshot, wall: float, monotonic: float):
        self.token = timestamp(snapshot.clientTokenExpiresAt) - 30
        self.secrets = timestamp(snapshot.expiresAt) - 30
        self.wall = wall
        self.monotonic = monotonic

    def now(self, wall: float, monotonic: float) -> float:
        """Return the later of wall time and monotonic elapsed time."""
        return max(wall, self.wall + max(0, monotonic - self.monotonic))
