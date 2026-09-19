"""Strict response validation and lifecycle deadlines with synthetic values only."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from miso_client import BootstrapError
from miso_client.utils.bootstrap_runtime import SecretsRuntime
from miso_client.utils.bootstrap_snapshot import MAX_BODY, SnapshotClock, parse_snapshot
from tests.unit.test_bootstrap import response_data

T0 = 1893456000.0


def snapshot():
    return parse_snapshot(json.dumps(response_data(T0)).encode(), T0)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(protocolVersion=True),
        lambda d: d.update(protocolVersion=2),
        lambda d: d.update(clientSecret="secret-sentinel"),
        lambda d: d.update(issuedAt="bad"),
        lambda d: d.update(clientToken=""),
        lambda d: d.update(clientToken="x" * 65537),
        lambda d: d.update(configuration={"DATABASE_URL": 123}),
        lambda d: d.update(configuration={"DATABASE_URL": None}),
        lambda d: d.update(configuration={"MISO_AUTH_MODE": "local"}),
        lambda d: d.update(configuration={"bad-name": "value"}),
        lambda d: d.update(configuration={"DATABASE_URL": "x" * 65537}),
        lambda d: d.update(configuration={f"KEY{i}": "x" for i in range(257)}),
        lambda d: d.update(context={"installationId": "i", "applicationId": "a"}),
    ],
)
def test_reject_invalid_without_sensitive_exception(mutate):
    data = response_data(T0)
    mutate(data["data"])
    with pytest.raises(BootstrapError) as caught:
        parse_snapshot(json.dumps(data).encode(), T0)
    assert "secret-sentinel" not in str(caught.value)
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "body",
    [
        b"null",
        b"{}",
        b"{",
        b"[]",
        b"x" * (MAX_BODY + 1),
        b'{"success":true,"success":true,"data":{}}',
    ],
)
def test_reject_envelope_duplicate_and_size(body):
    with pytest.raises(BootstrapError):
        parse_snapshot(body, T0)


@pytest.mark.parametrize("skew", [-30, 30])
def test_clock_skew_boundary_accepted(skew):
    parse_snapshot(json.dumps(response_data(T0)).encode(), T0 + skew)


@pytest.mark.parametrize("skew", [-31, 31])
def test_clock_skew_outside_rejected(skew):
    with pytest.raises(BootstrapError):
        parse_snapshot(json.dumps(response_data(T0)).encode(), T0 + skew)


def test_clock_rollback_never_extends_deadline():
    clock = SnapshotClock(snapshot(), T0, 100)
    assert clock.now(T0 - 100, 370) == T0 + 270
    assert clock.token == T0 + 270
    assert clock.secrets == T0 + 870


@pytest.mark.asyncio
async def test_token_and_secret_deadlines_are_independent():
    runtime = SecretsRuntime()
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=T0), patch(
        "miso_client.utils.bootstrap_runtime.time.monotonic", return_value=0
    ):
        runtime.install(snapshot())
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=T0 + 269), patch(
        "miso_client.utils.bootstrap_runtime.time.monotonic", return_value=269
    ):
        assert await runtime.get_token() == "application-sentinel"
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=T0 + 270), patch(
        "miso_client.utils.bootstrap_runtime.time.monotonic", return_value=270
    ), patch.object(
        runtime, "refresh", new=AsyncMock(side_effect=BootstrapError("temporarily-unavailable"))
    ):
        with pytest.raises(BootstrapError):
            await runtime.get_token()
        assert runtime.secrets.require("DATABASE_URL") == "secret-sentinel"
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=T0 + 869), patch(
        "miso_client.utils.bootstrap_runtime.time.monotonic", return_value=869
    ):
        assert runtime.secrets.get("DATABASE_URL") == "secret-sentinel"
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=T0 + 870), patch(
        "miso_client.utils.bootstrap_runtime.time.monotonic", return_value=870
    ):
        with pytest.raises(BootstrapError, match="snapshot-expired"):
            runtime.secrets.get("DATABASE_URL")
    await runtime.close()


@pytest.mark.asyncio
async def test_change_notifications_atomic_order_unsubscribe(caplog):
    runtime = SecretsRuntime()
    values = []
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=T0):
        runtime.install(snapshot())

        def broken(keys):
            raise ValueError("secret-sentinel")

        runtime.on_secrets_changed(broken)
        unsubscribe = runtime.on_secrets_changed(
            lambda keys: values.append((keys, runtime.secrets.get("DATABASE_URL")))
        )
        data = response_data(T0)
        data["data"]["configuration"]["DATABASE_URL"] = "rotated"
        runtime.install(parse_snapshot(json.dumps(data).encode(), T0))
        assert values == [(("DATABASE_URL",), "rotated")]
        unsubscribe()
        unsubscribe()
        runtime.install(snapshot())
        assert len(values) == 1
    assert "secret-sentinel" not in caplog.text
    await runtime.close()


@pytest.mark.asyncio
async def test_changed_context_invalidates_and_close_is_idempotent():
    runtime = SecretsRuntime()
    reasons = []
    with patch("miso_client.utils.bootstrap_runtime.time.time", return_value=T0):
        runtime.install(snapshot())
        runtime.on_invalidated(reasons.append)
        data = response_data(T0)
        data["data"]["context"]["applicationId"] = "other"
        with pytest.raises(BootstrapError):
            runtime.install(parse_snapshot(json.dumps(data).encode(), T0))
        with pytest.raises(BootstrapError):
            runtime.secrets.get("DATABASE_URL")
        await runtime.close()
        await runtime.close()
    assert reasons == ["protocol-error", "closed"]
