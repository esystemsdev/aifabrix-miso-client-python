"""Live bootstrap smoke; requires an explicitly configured HTTPS controller."""

from __future__ import annotations

import os
from typing import Optional

import pytest
from dotenv import load_dotenv

from miso_client import BootstrapError, init_secrets
from miso_client.utils.bootstrap_credentials import validate_settings


def _configure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Load deployment credentials without printing any values."""
    load_dotenv(override=False)
    for name in ("MISO_CONTROLLER_URL", "MISO_CLIENTID", "MISO_CLIENTSECRET"):
        if not os.environ.get(name):
            pytest.fail(f"Missing required setting: {name}", pytrace=False)
    valid = True
    try:
        validate_settings(os.environ["MISO_CONTROLLER_URL"])
    except BootstrapError:
        valid = False
    if not valid:
        pytest.fail(
            "Live bootstrap requires a configured, trusted HTTPS controller URL.", pytrace=False
        )
    monkeypatch.setenv("MISO_AUTH_MODE", "client-credentials")


@pytest.mark.asyncio
async def test_live_initialize_refresh_configuration_and_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove startup, token-chain refresh and access to a known permitted key."""
    _configure(monkeypatch)
    key = os.environ.get("BOOTSTRAP_SMOKE_KEY")
    if not key:
        pytest.fail(
            "Set BOOTSTRAP_SMOKE_KEY to a known permitted configuration key.", pytrace=False
        )
    failure: Optional[str] = None
    try:
        runtime = await init_secrets()
        try:
            assert runtime.context is not None
            runtime.secrets.require(key)
            await runtime.refresh()
            runtime.secrets.require(key)
        finally:
            await runtime.close()
    except BootstrapError as error:
        failure = error.code
    if failure is not None:
        pytest.fail("Live bootstrap failed: " + failure, pytrace=False)


@pytest.mark.asyncio
async def test_live_invalid_credentials_are_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """A synthetic invalid secret must never initialize or fall back to local mode."""
    _configure(monkeypatch)
    monkeypatch.setenv("MISO_CLIENTSECRET", "deliberately-invalid-smoke-credential")
    failure: Optional[str] = None
    try:
        runtime = await init_secrets()
    except BootstrapError as error:
        failure = error.code
    else:
        await runtime.close()
    if failure != "authorization-denied":
        pytest.fail("Expected terminal authorization-denied; got " + str(failure), pytrace=False)
