"""Owned secret runtime shared by local and client-credential initialization."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING, Awaitable, Callable, Dict, List, Optional

from ..models.bootstrap import (
    ApplicationTokenProvider,
    BootstrapContext,
    BootstrapError,
    ChangeHandler,
    InvalidationHandler,
    InvalidationReason,
)
from .bootstrap_snapshot import Snapshot, SnapshotClock, parse_snapshot, timestamp
from .bootstrap_transport import BrokerTransport

if TYPE_CHECKING:
    from ..client import MisoClient
    from ..models.config import MisoClientConfig

logger = logging.getLogger(__name__)


class SecretAccessor:
    """Read-only access to a runtime's currently valid secret snapshot."""

    def __init__(self, runtime: "SecretsRuntime"):
        self._runtime = runtime

    def get(self, name: str) -> Optional[str]:
        """Return an optional value; reject a closed or expired runtime."""
        self._runtime.ensure_active()
        return self._runtime.read_secret(name)

    def require(self, name: str) -> str:
        """Return a nonempty value or raise a fixed, value-free error."""
        value = self.get(name)
        if not value:
            raise BootstrapError("required-secret-unavailable")
        return value


class SecretsRuntime(ApplicationTokenProvider):
    """Owns client, private secret state, refresh and cleanup for one init call."""

    def __init__(self, values: Optional[Dict[str, str]] = None):
        self._client: Optional["MisoClient"] = None
        self._context: Optional[BootstrapContext] = None
        self._values = dict(values or {})
        self.secrets = SecretAccessor(self)
        self._reason: Optional[InvalidationReason] = None
        self._snapshot: Optional[Snapshot] = None
        self._clock: Optional[SnapshotClock] = None
        self._transport: Optional[BrokerTransport] = None
        self._changes: List[ChangeHandler] = []
        self._invalidations: List[InvalidationHandler] = []
        self._refresh_task: Optional[asyncio.Task[None]] = None
        self._scheduler: Optional[asyncio.Task[None]] = None
        self._close_task: Optional[asyncio.Task[None]] = None
        self._refresh_at = 0.0
        self._next_attempt = 0.0
        self._rejected_token: Optional[str] = None
        self._generation = 0

    def read_secret(self, name: str) -> Optional[str]:
        """Read private state after enforcing its lifetime."""
        self.ensure_active()
        return self._values.get(name)

    def attach_transport(
        self,
        transport: BrokerTransport,
    ) -> None:
        """Attach internal owned cleanup resources before initialization."""
        self._transport = transport

    async def initialize_client(
        self, config: "MisoClientConfig", values: Optional[Dict[str, str]] = None
    ) -> None:
        """Construct the ordinary SDK only after the provider is ready."""
        from ..client import MisoClient

        if values is not None:
            self._values = dict(values)
        self._client = MisoClient(config)
        await self._client.initialize()

    @property
    def client_identifier(self) -> str:
        """Read the validated compatibility identifier without exposing tokens."""
        if self._snapshot is None:
            raise BootstrapError("not-initialized")
        return self._snapshot.clientId

    @property
    def client(self) -> "MisoClient":
        """Return the initialized SDK client."""
        self.ensure_active()
        if self._client is None:
            raise BootstrapError("not-initialized")
        return self._client

    @property
    def context(self) -> Optional[BootstrapContext]:
        """Return verified immutable context, or None for unresolved local context."""
        return self._context

    def ensure_active(self) -> None:
        """Reject invalidated state and enforce the independent snapshot deadline."""
        if self._reason is None and self._clock is not None:
            if self._clock.now(time.time(), time.monotonic()) >= self._clock.secrets:
                self.invalidate("snapshot-expired")
        if self._reason is not None:
            raise BootstrapError(self._reason)

    def invalidate(self, reason: InvalidationReason) -> None:
        """Atomically revoke access before synchronously notifying consumers."""
        if self._reason is not None and reason != "closed":
            return
        if self._reason == "closed":
            return
        self._reason = reason
        self._generation += 1
        if self._transport is not None:
            self._transport.invalidate()
        self._values.clear()
        self._snapshot = None
        self._rejected_token = None
        if self._client is not None:
            internal = self._client.http_client.get_internal_client()
            internal.token_manager.clear_token()
            if internal.client is not None:
                internal.client.headers.pop("x-client-token", None)
        for listener in tuple(self._invalidations):
            try:
                listener(reason)
            except Exception:
                logger.warning("Secret runtime invalidation listener failed")

    def on_secrets_changed(self, handler: ChangeHandler) -> Callable[[], None]:
        """Subscribe to changed key names; return an idempotent unsubscribe."""
        self.ensure_active()
        self._changes.append(handler)
        return lambda: self._remove(self._changes, handler)

    def on_invalidated(self, handler: InvalidationHandler) -> Callable[[], None]:
        """Subscribe to value-free invalidation reasons."""
        self.ensure_active()
        self._invalidations.append(handler)
        return lambda: self._remove(self._invalidations, handler)

    @staticmethod
    def _remove(listeners: List[Callable[..., None]], handler: Callable[..., None]) -> None:
        if handler in listeners:
            listeners.remove(handler)

    def install(self, snapshot: Snapshot) -> None:
        """Install a validated snapshot atomically and notify key changes."""
        if self._reason is not None:
            raise BootstrapError(self._reason)
        if (self._context is not None and self._context != snapshot.context) or (
            self._snapshot is not None and self._snapshot.clientId != snapshot.clientId
        ):
            self.invalidate("protocol-error")
            raise BootstrapError("protocol-error")
        values = {key: value.get_secret_value() for key, value in snapshot.configuration.items()}
        changed = self._changed_keys(values)
        clock = SnapshotClock(snapshot, time.time(), time.monotonic())
        if self._transport is not None:
            self._transport.install_token(snapshot.clientToken, clock)
        self._snapshot, self._context, self._values = snapshot, snapshot.context, values
        self._clock = clock
        self._refresh_at = timestamp(snapshot.issuedAt) + random.uniform(110, 120)
        self._notify_changes(changed)

    def _changed_keys(self, values: Dict[str, str]) -> tuple[str, ...]:
        return tuple(
            sorted(
                key
                for key in self._values.keys() | values.keys()
                if self._values.get(key) != values.get(key)
            )
        )

    def _notify_changes(self, changed: tuple[str, ...]) -> None:
        for listener in tuple(self._changes) if changed else ():
            try:
                listener(changed)
            except Exception:
                logger.warning("Secret runtime change listener failed")

    async def handle_auth_error(self, code: str, token: Optional[str]) -> None:
        """Revoke typed denials or refresh expiry once, without replaying a request."""
        if code != "bootstrap_token_expired":
            self.invalidate("authorization-denied")
            return
        self.ensure_active()
        if self._snapshot is None:
            return
        current = self._snapshot.clientToken.get_secret_value()
        if token is not None and token != current:
            return  # Another response already refreshed this request's old token.
        self._rejected_token = current
        try:
            await self.refresh()
        except BootstrapError:
            pass  # The caller still receives its original failed operation response.

    async def get_token(self) -> str:
        """Return a valid token, refreshing only within the shared retry budget."""
        self.ensure_active()
        if self._snapshot is None or self._clock is None:
            raise BootstrapError("token-unavailable")
        if (
            self._clock.now(time.time(), time.monotonic()) >= self._clock.token
            or self._snapshot.clientToken.get_secret_value() == self._rejected_token
        ):
            await self.refresh()
        self.ensure_active()
        if (
            self._clock.now(time.time(), time.monotonic()) >= self._clock.token
            or self._snapshot.clientToken.get_secret_value() == self._rejected_token
        ):
            raise BootstrapError("token-expired")
        return self._snapshot.clientToken.get_secret_value()

    async def refresh(self) -> None:
        """Coalesce refreshes; cancelling a waiter does not cancel shared work."""
        self.ensure_active()
        if self._refresh_task is None or self._refresh_task.done():
            if time.monotonic() < self._next_attempt:
                raise BootstrapError("temporarily-unavailable")
            self._refresh_task = asyncio.create_task(self._refresh())
        await asyncio.shield(self._refresh_task)

    async def _refresh(self) -> None:
        if self._transport is None:
            raise BootstrapError("not-initialized")
        generation = self._generation
        try:
            body = await self._transport.fetch()
            snapshot = parse_snapshot(body, time.time())
            if generation == self._generation:
                self.ensure_active()
                self.install(snapshot)
        except BootstrapError as error:
            self._next_attempt = time.monotonic() + 30
            if error.code == "snapshot-expired":
                self.invalidate("snapshot-expired")
            elif error.code in ("authorization-denied", "protocol-error"):
                self.invalidate(
                    "authorization-denied"
                    if error.code == "authorization-denied"
                    else "protocol-error"
                )
            raise

    def start_refresh(self) -> None:
        """Start the owned background refresh loop after successful initialization."""
        self._scheduler = asyncio.create_task(self._run_refresh())

    def _refresh_delay(self) -> float:
        if self._clock is None:
            return 0
        now = self._clock.now(time.time(), time.monotonic())
        refresh_delay = max(self._refresh_at - now, self._next_attempt - time.monotonic())
        return max(0, min(refresh_delay, self._clock.secrets - now))

    async def _run_refresh(self) -> None:
        while self._reason is None and self._snapshot is not None:
            await asyncio.sleep(self._refresh_delay())
            try:
                self.ensure_active()
                if self._refresh_delay() <= 0:
                    await self.refresh()
            except BootstrapError:
                pass  # Failure cooldown and expiry are included in the next delay.

    async def close(self) -> None:
        """Invalidate immediately and close owned resources within five seconds."""
        if self._close_task is None:
            self.invalidate("closed")
            self._close_task = asyncio.create_task(self._bounded_cleanup())
        await asyncio.shield(self._close_task)

    async def _bounded_cleanup(self) -> None:
        task = asyncio.create_task(self._cleanup())
        done, _ = await asyncio.wait({task}, timeout=5)
        if not done:
            task.cancel()
            task.add_done_callback(self._consume_cleanup_result)
            raise BootstrapError("cleanup-failed")
        if task.cancelled() or task.exception() is not None:
            raise BootstrapError("cleanup-failed")

    @staticmethod
    def _consume_cleanup_result(task: asyncio.Task[None]) -> None:
        if not task.cancelled():
            task.exception()

    async def _cleanup(self) -> None:
        tasks = [t for t in (self._scheduler, self._refresh_task) if t is not None]
        for task in tasks:
            task.cancel()
        self._changes.clear()
        self._invalidations.clear()
        cleanup: List[Awaitable[None]] = [self._settle_tasks(tasks)]
        if self._client is not None:
            cleanup.append(self._client.disconnect())
        if self._transport is not None:
            cleanup.append(self._transport.close())
        if cleanup:
            results = await asyncio.gather(*cleanup, return_exceptions=True)
            if any(isinstance(result, BaseException) for result in results):
                raise BootstrapError("cleanup-failed")

    @staticmethod
    async def _settle_tasks(tasks: List[asyncio.Task[None]]) -> None:
        """Consume prior refresh failures; they are not resource-cleanup failures."""
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
