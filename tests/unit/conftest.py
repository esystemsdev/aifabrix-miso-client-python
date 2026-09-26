"""Keep unit tests independent of live controller and Redis services."""

from collections.abc import Iterator

import pytest
import pytest_socket


@pytest.fixture(autouse=True)
def block_unit_test_network() -> Iterator[None]:
    """Block network sockets while allowing asyncio's local Unix socket pair."""
    pytest_socket.disable_socket(allow_unix_socket=True)
    try:
        yield
    finally:
        pytest_socket.enable_socket()
