"""Regression checks for the unit suite's offline boundary."""

import socket

import pytest
from pytest_socket import SocketBlockedError


@pytest.mark.parametrize("family", [socket.AF_INET, socket.AF_INET6])
@pytest.mark.filterwarnings("ignore:A test tried to use socket.socket:UserWarning")
def test_unit_tests_cannot_create_network_sockets(family: socket.AddressFamily) -> None:
    """Fail before a real HTTP or Redis connection can be attempted."""
    with pytest.raises(SocketBlockedError):
        socket.socket(family, socket.SOCK_STREAM)


@pytest.mark.asyncio
async def test_asyncio_remains_available_without_network() -> None:
    """The event loop must still be able to schedule asynchronous unit tests."""
    import asyncio

    await asyncio.sleep(0)
