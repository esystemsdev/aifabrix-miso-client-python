"""Wait on shared asyncio work without letting one waiter cancel it.

``asyncio.shield`` reports an abandoned failure to the loop's exception handler
on Python 3.14+, even when the owner already retrieves it. Waiting with
``asyncio.wait`` keeps the shield semantics without that report.
"""

import asyncio
from typing import TypeVar

T = TypeVar("T")


def _retrieve(task: "asyncio.Future[T]") -> None:
    if not task.cancelled():
        task.exception()


async def await_shared(task: "asyncio.Future[T]") -> T:
    """Return the task result; cancelling this waiter leaves the task running."""
    task.add_done_callback(_retrieve)
    await asyncio.wait((task,))
    return task.result()
