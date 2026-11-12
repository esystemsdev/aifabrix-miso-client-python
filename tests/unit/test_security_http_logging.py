"""Security regressions for HTTP audit/debug logging and encryption failures."""

import json
import logging
import time
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio

from miso_client import MisoClient
from miso_client.errors import EncryptionError, MisoClientError
from miso_client.models.config import AuditConfig, LogEntry, MisoClientConfig
from miso_client.utils.data_masker import DataMasker
from miso_client.utils.http_client_logging import (
    _prepare_debug_context,
    log_http_request_audit,
)
from miso_client.utils.http_log_masker import is_security_endpoint
from miso_client.utils.log_request_transformer import transform_log_entry_to_request

PLAINTEXT_MARKER = "synthetic-plaintext-marker"
KEY_MARKER = "synthetic-encryption-key-marker"
REQUEST_MARKER = "synthetic-request-body-marker"
RESPONSE_MARKER = "synthetic-response-body-marker"
ERROR_MARKER = "synthetic-error-body-marker"
CORRELATION = "synthetic-security-correlation"


class Wire:
    """Capture requests while substituting only the HTTP transport."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.respond: Callable[[httpx.Request], httpx.Response] = self._success

    def _success(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/encrypt"):
            return httpx.Response(200, json={"value": "enc://synthetic", "storage": "local"})
        if request.url.path.endswith("/decrypt"):
            return httpx.Response(
                200,
                json={"plaintext": PLAINTEXT_MARKER, "diagnostic": RESPONSE_MARKER},
            )
        return httpx.Response(200, json={"deleted": True, "diagnostic": RESPONSE_MARKER})

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)


@pytest.fixture(autouse=True)
def reset_data_masker(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep global masker configuration isolated across security tests."""
    monkeypatch.delenv("MISO_SENSITIVE_FIELDS_CONFIG", raising=False)
    DataMasker._config_loaded = False
    DataMasker._sensitive_fields = None
    yield
    DataMasker._config_loaded = False
    DataMasker._sensitive_fields = None


@pytest_asyncio.fixture
async def security_sdk() -> AsyncIterator[tuple[MisoClient, Wire, list[LogEntry]]]:
    """Build the public SDK with real logging and an in-memory HTTP transport."""
    wire = Wire()
    config = MisoClientConfig(
        controller_url="https://controller.test",
        client_id="synthetic-client",
        client_secret="synthetic-client-secret",
        encryption_key=KEY_MARKER,
        cache={"encryptionCacheTTL": 0},
        log_level="debug",
        emit_events=True,
        audit=AuditConfig(enabled=True, level="detailed", batchSize=None, batchInterval=None),
    )
    client = MisoClient(config)
    internal = client.http_client.get_internal_client()
    internal.client = httpx.AsyncClient(
        base_url=config.controller_url,
        transport=httpx.MockTransport(wire.handle),
    )
    internal.token_manager.client_token = "synthetic-client-token"
    internal.token_manager.token_expires_at = datetime.now() + timedelta(hours=1)
    client.logger.application_context_service.get_application_context = AsyncMock(
        return_value=SimpleNamespace(
            to_dict=lambda: {
                "application": "security-test",
                "applicationId": "security-test",
                "environment": "unit",
            }
        )
    )
    entries: list[LogEntry] = []
    client.logger.on(entries.append)
    try:
        yield client, wire, entries
    finally:
        await client.disconnect()


def _serialized_entries(entries: list[LogEntry]) -> str:
    return "\n".join(entry.model_dump_json() for entry in entries)


def _serialized_delivery(entries: list[LogEntry]) -> str:
    return "\n".join(transform_log_entry_to_request(entry).model_dump_json() for entry in entries)


async def test_security_calls_omit_bodies_from_final_logs_and_delivery(
    security_sdk: tuple[MisoClient, Wire, list[LogEntry]],
) -> None:
    """Encrypt, decrypt, and delete retain wire behavior without logging bodies."""
    client, wire, entries = security_sdk

    encrypted = await client.encryption.encrypt(PLAINTEXT_MARKER, REQUEST_MARKER)
    decrypted = await client.encryption.decrypt(encrypted.value, REQUEST_MARKER)
    deleted = await client.http_client.post(
        "/api/security/parameters/delete",
        data={"parameterName": REQUEST_MARKER, "encryptionKey": KEY_MARKER},
    )
    await client.http_client._wait_for_logging_tasks(timeout=2.0)

    assert decrypted == PLAINTEXT_MARKER
    assert deleted == {"deleted": True, "diagnostic": RESPONSE_MARKER}
    assert len(wire.requests) == 3
    assert wire.requests[2].method == "POST"
    assert wire.requests[2].url.path == "/api/security/parameters/delete"
    assert json.loads(wire.requests[0].content) == {
        "plaintext": PLAINTEXT_MARKER,
        "parameterName": REQUEST_MARKER,
        "encryptionKey": KEY_MARKER,
    }
    assert {entry.level for entry in entries} >= {"audit", "debug"}
    visible = _serialized_entries(entries) + _serialized_delivery(entries)
    for marker in (PLAINTEXT_MARKER, KEY_MARKER, REQUEST_MARKER, RESPONSE_MARKER):
        assert marker not in visible


@pytest.mark.parametrize("audit_level", ["minimal", "standard"])
async def test_security_audit_uses_generic_failure_message(
    audit_level: Literal["minimal", "standard"],
) -> None:
    """Both audit branches retain metadata without raw security error text."""
    logger = AsyncMock()
    config = MisoClientConfig(
        controller_url="https://controller.test",
        client_id="synthetic-client",
        client_secret="synthetic-secret",
        audit=AuditConfig(level=audit_level),
    )
    await log_http_request_audit(
        logger=logger,
        method="POST",
        url="/api/security/parameters/decrypt",
        response=None,
        error=MisoClientError(ERROR_MARKER, status_code=500),
        start_time=time.perf_counter(),
        request_data={"diagnostic": ERROR_MARKER},
        user_id=None,
        log_level="debug",
        config=config,
        correlation_id=CORRELATION,
    )

    context = logger.audit.await_args.args[2]
    assert context["error"] == "Security request failed"
    assert context["statusCode"] == 500
    assert context["correlationId"] == CORRELATION
    assert ERROR_MARKER not in json.dumps(context, sort_keys=True)


async def test_encryption_failure_logs_are_generic_and_contract_is_preserved(
    security_sdk: tuple[MisoClient, Wire, list[LogEntry]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Service diagnostics omit exception output while caller errors stay structured."""
    client, wire, entries = security_sdk
    caplog.set_level(logging.ERROR, logger="miso_client.services.encryption")
    parameter_marker = "synthetic-parameter-marker"
    wire.respond = lambda _: httpx.Response(
        500,
        json={
            "detail": ERROR_MARKER,
            "code": "synthetic_failure",
            "correlationId": CORRELATION,
        },
        headers={"x-correlation-id": CORRELATION},
    )

    with pytest.raises(EncryptionError) as caught:
        await client.encryption.decrypt("enc://synthetic", parameter_marker)
    await client.http_client._wait_for_logging_tasks(timeout=2.0)

    assert caught.value.status_code == 500
    assert caught.value.parameter_name == parameter_marker
    assert caught.value.error_body is not None
    assert caught.value.error_body["detail"] == ERROR_MARKER
    assert caplog.records[-1].getMessage() == "Decryption request failed"
    assert getattr(caplog.records[-1], "statusCode") == 500
    assert getattr(caplog.records[-1], "correlationId") == CORRELATION
    formatted_output = caplog.text
    visible = formatted_output + _serialized_entries(entries)
    for marker in (ERROR_MARKER, parameter_marker, KEY_MARKER):
        assert marker not in visible


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("/api/security/parameters/encrypt", True),
        ("https://controller.test/api/security/parameters/decrypt?mode=full", True),
        ("/controller/base/api/security/parameters/delete", True),
        ("/api/security-other/parameters", False),
        ("/api/items?next=/api/security/parameters/decrypt", False),
    ],
)
def test_security_route_guard_uses_path_boundaries(url: str, expected: bool) -> None:
    assert is_security_endpoint(url) is expected


def test_nonsecurity_debug_still_contains_permitted_body_diagnostics() -> None:
    """The body guard does not disable ordinary HTTP debug diagnostics."""
    context = _prepare_debug_context(
        method="POST",
        url="/api/items",
        response={"result": "visible-response"},
        duration_ms=1,
        status_code=200,
        user_id=None,
        request_data={"note": "visible-request", "secret": "hidden"},
        request_headers=None,
        base_url="https://controller.test",
    )
    assert context["requestBody"] == {
        "note": "visible-request",
        "secret": DataMasker.MASKED_VALUE,
    }
    assert "visible-response" in context["responseBody"]


def test_permissive_custom_masking_cannot_bypass_security_body_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Route-level omission remains effective when field masking is permissive."""
    config_path = tmp_path / "permissive-mask.json"
    config_path.write_text(
        '{"mergeWithHardcodedDefaults": false, "fields": {"custom": ["other"]}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("MISO_SENSITIVE_FIELDS_CONFIG", str(config_path))
    DataMasker._config_loaded = False
    DataMasker._sensitive_fields = None

    context = _prepare_debug_context(
        method="POST",
        url="/api/security/parameters/decrypt",
        response={"diagnostic": RESPONSE_MARKER},
        duration_ms=1,
        status_code=200,
        user_id=None,
        request_data={"diagnostic": REQUEST_MARKER},
        request_headers=None,
        base_url="https://controller.test",
    )

    assert "requestBody" not in context
    assert "responseBody" not in context


def test_security_body_guard_runs_before_body_processing() -> None:
    """Unsafe body objects cannot prevent a metadata-only security event."""
    request_body = {"diagnostic": REQUEST_MARKER}
    response_body = {"diagnostic": RESPONSE_MARKER}
    original_mask = DataMasker.mask_sensitive_data

    def reject_body_processing(data: object) -> object:
        if data is request_body or data is response_body:
            raise AssertionError("security body was traversed")
        return original_mask(data)

    with patch.object(DataMasker, "mask_sensitive_data", side_effect=reject_body_processing):
        context = _prepare_debug_context(
            method="POST",
            url="/api/security/parameters/decrypt",
            response=response_body,
            duration_ms=1,
            status_code=200,
            user_id=None,
            request_data=request_body,
            request_headers={"authorization": "synthetic-token"},
            base_url="https://controller.test",
        )

    assert "requestBody" not in context
    assert "responseBody" not in context
    assert context["requestHeaders"]["authorization"] == DataMasker.MASKED_VALUE
