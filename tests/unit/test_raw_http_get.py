"""Tests for ephemeral raw GET (CIP / external binary URLs)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from miso_client.models.config import MisoClientConfig
from miso_client.services.logger import LoggerService
from miso_client.services.redis import RedisService
from miso_client.utils.http_client import HttpClient
from miso_client.utils.internal_http_client import InternalHttpClient
from miso_client.utils.raw_http_get import raw_http_get


@pytest.mark.asyncio
async def test_raw_http_get_invokes_httpx_get_with_kwargs():
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.aclose = AsyncMock()

    captured: dict = {}

    class CM:
        async def __aenter__(self_inner):
            return mock_client_instance

        async def __aexit__(self_inner, *args):
            return None

    def client_factory(**kwargs):
        captured.update(kwargs)
        return CM()

    with patch("miso_client.utils.raw_http_get.httpx.AsyncClient", side_effect=client_factory):
        out = await raw_http_get(
            "https://example.com/file",
            headers={"Authorization": "Bearer x"},
            params={"a": "1"},
            timeout=42.0,
            follow_redirects=True,
        )

    assert out is mock_response
    assert captured["follow_redirects"] is True
    assert captured["timeout"] == 42.0
    mock_client_instance.get.assert_awaited_once()
    call_kw = mock_client_instance.get.await_args
    assert call_kw[0][0] == "https://example.com/file"
    assert call_kw[1]["headers"] == {"Authorization": "Bearer x"}
    assert call_kw[1]["params"] == {"a": "1"}


@pytest.mark.asyncio
async def test_http_client_get_raw_delegates_to_raw_http_get():
    from miso_client.models.config import AuditConfig

    config = MisoClientConfig(
        controller_url="https://controller.aifabrix.ai",
        client_id="c",
        client_secret="s",
        log_level="info",
        audit=AuditConfig(enabled=False, level="minimal"),
    )
    redis = RedisService(config.redis)
    internal = InternalHttpClient(config)
    logger = LoggerService(internal, redis)
    client = HttpClient(config, logger)
    client.logger.audit = AsyncMock()
    client.logger.debug = AsyncMock()

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200

    with patch(
        "miso_client.utils.http_client.raw_http_get",
        new=AsyncMock(return_value=mock_resp),
    ) as mock_raw:
        result = await client.get_raw(
            "https://graph.example/v1.0/me/photo/$value",
            headers={"Authorization": "Bearer t"},
            params=None,
            timeout=7.5,
            follow_redirects=True,
        )
        await client._wait_for_logging_tasks(timeout=1.0)

    assert result is mock_resp
    mock_raw.assert_awaited_once()
    aa = mock_raw.await_args
    assert aa.args[0] == "https://graph.example/v1.0/me/photo/$value"
    rw_kw = aa.kwargs
    assert rw_kw["headers"]["Authorization"] == "Bearer t"
    assert "x-correlation-id" in {k.lower() for k in rw_kw["headers"]}
    assert rw_kw["timeout"] == 7.5
    assert rw_kw["follow_redirects"] is True

    await client.close()
