"""Tests for await_shared (shield semantics without 3.14 abandoned-failure logging)."""

import asyncio
import gc
from typing import Any

import pytest

from miso_client.utils.shared_task import await_shared


@pytest.mark.asyncio
async def test_returns_result_and_propagates_error() -> None:
    async def ok() -> str:
        return "token"

    async def fail() -> str:
        raise ValueError("boom")

    assert await await_shared(asyncio.create_task(ok())) == "token"
    with pytest.raises(ValueError, match="boom"):
        await await_shared(asyncio.create_task(fail()))


@pytest.mark.asyncio
async def test_cancelled_waiter_leaves_shared_task_running() -> None:
    release = asyncio.Event()

    async def work() -> str:
        await release.wait()
        return "done"

    shared = asyncio.create_task(work())
    waiter = asyncio.create_task(await_shared(shared))
    await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    release.set()
    assert await shared == "done"


@pytest.mark.asyncio
async def test_abandoned_failure_is_not_reported() -> None:
    """[EDGE] All waiters cancelled, then the work fails: no loop error report."""
    loop = asyncio.get_running_loop()
    errors: list[dict[str, Any]] = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: errors.append(context))
    release = asyncio.Event()

    async def work() -> str:
        await release.wait()
        raise RuntimeError("mint failed")

    try:
        waiter = asyncio.create_task(await_shared(asyncio.create_task(work())))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        release.set()
        for _ in range(3):
            await asyncio.sleep(0)
        gc.collect()
        assert not errors
    finally:
        loop.set_exception_handler(previous)


@pytest.mark.asyncio
async def test_cancelled_shared_task_cancels_waiter() -> None:
    shared = asyncio.create_task(asyncio.sleep(10))
    waiter = asyncio.create_task(await_shared(shared))
    await asyncio.sleep(0)
    shared.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
