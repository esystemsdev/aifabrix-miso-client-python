"""Audit log queue for batching multiple logs into single requests.

Reduces network overhead by batching audit logs.
"""

import asyncio
import signal
from types import FrameType
from typing import TYPE_CHECKING, List, Optional

from ..models.config import AuditConfig, LogEntry, MisoClientConfig
from ..services.redis import RedisService
from ..utils.circuit_breaker import CircuitBreaker

if TYPE_CHECKING:
    from ..utils.http_client import HttpClient


class QueuedLogEntry:
    """Internal class for queued log entries."""

    def __init__(self, entry: LogEntry, timestamp: int):
        """Initialize queued log entry.

        Args:
            entry: LogEntry object
            timestamp: Timestamp in milliseconds

        """
        self.entry = entry
        self.timestamp = timestamp


class AuditLogQueue:
    """Audit log queue for batching multiple logs into single requests.

    Automatically batches audit logs based on size and time thresholds.
    Supports Redis LIST for efficient queuing with HTTP fallback.
    """

    def __init__(
        self,
        http_client: "HttpClient",
        redis: RedisService,
        config: MisoClientConfig,
    ):
        """Initialize audit log queue."""
        self.http_client = http_client
        self.redis = redis
        self.config = config
        self.queue: List[QueuedLogEntry] = []
        self.flush_timer: Optional[asyncio.Task] = None
        self.is_flushing = False

        audit_config: Optional[AuditConfig] = config.audit
        self.batch_size, self.batch_interval = self._resolve_batch_config(audit_config)
        circuit_breaker_config = audit_config.circuitBreaker if audit_config else None
        self.circuit_breaker = CircuitBreaker(circuit_breaker_config)
        self._setup_signal_handlers()

    def _resolve_batch_config(self, audit_config: Optional[AuditConfig]) -> tuple[int, int]:
        """Resolve batch size and interval from audit configuration."""
        batch_size = (
            audit_config.batchSize if audit_config and audit_config.batchSize is not None else 10
        )
        batch_interval = (
            audit_config.batchInterval
            if audit_config and audit_config.batchInterval is not None
            else 100
        )
        return batch_size, batch_interval

    def _setup_signal_handlers(self) -> None:
        """Register graceful shutdown signal handlers when supported."""
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except (ValueError, OSError):
            pass

    def _signal_handler(self, signum: int, frame: Optional[FrameType]) -> None:
        """Handle shutdown signals."""
        # Schedule flush on next event loop iteration
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(self.flush(True))

    async def add(self, entry: LogEntry) -> None:
        """Add log entry to queue.

        Automatically flushes if batch size is reached.

        Args:
            entry: LogEntry to add to queue

        """
        self.queue.append(QueuedLogEntry(entry, self._current_timestamp()))

        # Flush if batch size reached
        if len(self.queue) >= self.batch_size:
            await self.flush(False)
            return

        # Setup flush timer if not already set
        if self.flush_timer is None and len(self.queue) > 0:
            self.flush_timer = asyncio.create_task(self._schedule_flush())

    async def _schedule_flush(self) -> None:
        """Schedule automatic flush after batch interval."""
        try:
            await asyncio.sleep(self.batch_interval / 1000.0)  # Convert ms to seconds
            await self.flush(False)
        except asyncio.CancelledError:
            # Timer was cancelled, ignore
            pass
        finally:
            self.flush_timer = None

    def _current_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        import time

        return int(time.time() * 1000)

    async def flush(self, sync: bool = False) -> None:
        """Flush queued logs.

        Args:
            sync: If True, wait for flush to complete (for shutdown)

        """
        _ = sync
        if self.is_flushing:
            return
        await self._cancel_flush_timer()
        if len(self.queue) == 0:
            return
        self.is_flushing = True
        try:
            entries = self._drain_queue()
            if not entries:
                return
            if await self._try_redis_enqueue(entries):
                return
            if self.circuit_breaker.is_open():
                return
            await self._send_http_batch(entries)
        except Exception:
            pass
        finally:
            self.is_flushing = False

    async def _cancel_flush_timer(self) -> None:
        """Cancel scheduled flush timer if it exists."""
        if not self.flush_timer:
            return
        self.flush_timer.cancel()
        try:
            await self.flush_timer
        except asyncio.CancelledError:
            pass
        self.flush_timer = None

    def _drain_queue(self) -> List[LogEntry]:
        """Drain in-memory queue and return copied entries."""
        entries = self.queue[:]
        self.queue.clear()
        return [queued.entry for queued in entries]

    async def _try_redis_enqueue(self, entries: List[LogEntry]) -> bool:
        """Try to enqueue batch to Redis, return success flag."""
        if not self.redis.is_connected():
            return False
        import json

        queue_name = f"audit-logs:{self.config.client_id}"
        entries_json = json.dumps([entry.model_dump() for entry in entries])
        success = await self.redis.rpush(queue_name, entries_json)
        return bool(success)

    async def _send_http_batch(self, entries: List[LogEntry]) -> None:
        """Send log batch via HTTP fallback and update circuit breaker."""
        try:
            await self.http_client.request(
                "POST",
                "/api/v1/logs/batch",
                {"logs": [entry.model_dump(exclude_none=True) for entry in entries]},
            )
            self.circuit_breaker.record_success()
        except Exception:
            self.circuit_breaker.record_failure()

    def get_queue_size(self) -> int:
        """Get current queue size.

        Returns:
            Number of entries in queue

        """
        return len(self.queue)

    def clear(self) -> None:
        """Clear queue (for testing/cleanup)."""
        if self.flush_timer:
            self.flush_timer.cancel()
            self.flush_timer = None
        self.queue.clear()
