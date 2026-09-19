"""Tests for current public application URL resolution."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from miso_client.utils.application_url_resolver import (
    parse_public_application_url_reference,
    resolve_public_application_url,
    resolve_public_origins,
)


def test_parse_self_and_target_public_references():
    assert parse_public_application_url_reference("url://public").target_key is None
    parsed = parse_public_application_url_reference("url://keycloak-host-public")
    assert parsed.target_key == "keycloak"
    assert parsed.surface == "host"


@pytest.mark.asyncio
async def test_reads_current_status_without_client_local_url_cache():
    reader = SimpleNamespace(
        get_application_status=AsyncMock(
            side_effect=[
                SimpleNamespace(url="https://direct.example/app"),
                SimpleNamespace(url="https://custom.example/app"),
            ]
        )
    )
    assert (
        await resolve_public_application_url(reader, "dev", "portal", "url://public")
        == "https://direct.example/app"
    )
    assert (
        await resolve_public_application_url(reader, "dev", "portal", "url://public")
        == "https://custom.example/app"
    )
    assert reader.get_application_status.await_count == 2


@pytest.mark.asyncio
async def test_resolves_mixed_cors_and_deduplicates_origins():
    async def status(_env_key, app_key, _auth_strategy=None):
        return SimpleNamespace(url=f"https://{app_key}.frontdoor.example/base")

    reader = SimpleNamespace(get_application_status=AsyncMock(side_effect=status))
    result = await resolve_public_origins(
        reader,
        "dev",
        "portal",
        [
            "http://localhost:*, url://public",
            "url://keycloak-public",
            "https://portal.frontdoor.example",
        ],
    )
    assert result == [
        "http://localhost:*",
        "https://portal.frontdoor.example",
        "https://keycloak.frontdoor.example",
    ]


@pytest.mark.asyncio
async def test_rejects_internal_runtime_reference():
    reader = SimpleNamespace(get_application_status=AsyncMock())
    with pytest.raises(ValueError, match="only public URL references"):
        await resolve_public_origins(reader, "dev", "portal", ["url://keycloak-internal"])
