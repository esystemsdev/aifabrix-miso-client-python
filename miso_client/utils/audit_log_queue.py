"""
Audit log queue for batching multiple logs into single requests.

Reduces network overhead by batching audit logs.
"""

import asyncio
import signal
from typing import TYPE_CHECKING, List, Optional

from ..models.config import AuditConfig, LogEntry, MisoClientConfig
from ..services.redis import RedisService
from ..utils.circuit_breaker import CircuitBreaker

if TYPE_CHECKING:
    from ..utils.http_client import HttpClient


class QueuedLogEntry:
    """Internal class for queued log entries."""

    def __init__(self, entry: LogEntry, timestamp: int):
        """
        Initialize queued log entry.

        Args:
            entry: LogEntry object
            timestamp: Timestamp in milliseconds
        """
        self.entry = entry
        self.timestamp = timestamp


class AuditLogQueue:
    """
    Audit log queue for batching multiple logs into single requests.

    Automatically batches audit logs based on size and time thresholds.
    Supports Redis LIST for efficient queuing with HTTP fallback.
    """

    def __init__(
        self,
        http_client: "HttpClient",
        redis: RedisService,
        config: MisoClientConfig,
    ):
        """
        Initialize audit log queue.

        Args:
            http_client: HttpClient instance for sending logs
            redis: RedisService instance for queuing
            config: MisoClientConfig with audit configuration
        """
        self.http_client = http_client
        self.redis = redis
        self.config = config
        self.queue: List[QueuedLogEntry] = []
        self.flush_timer: Optional[asyncio.Task] = None
        self.is_flushing = False

        audit_config: Optional[AuditConfig] = config.audit
        self.batch_size: int = (
            audit_config.batchSize if audit_config and audit_config.batchSize is not None else 10
        )
        self.batch_interval: int = (
            audit_config.batchInterval
            if audit_config and audit_config.batchInterval is not None
            else 100
        )

        # Initialize circuit breaker for HTTP logging
        circuit_breaker_config = audit_config.circuitBreaker if audit_config else None
        self.circuit_breaker = CircuitBreaker(circuit_breaker_config)

        # Setup graceful shutdown handlers (if available)
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except (ValueError, OSError):
            # Signal handlers may not be available in all environments
            pass

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        # Schedule flush on next event loop iteration
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(self.flush(True))

    async def add(self, entry: LogEntry) -> None:
        """
        Add log entry to queue.

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
        """
        Flush queued logs.

        Args:
            sync: If True, wait for flush to complete (for shutdown)
        """
        if self.is_flushing:
            return

        # Cancel flush timer
        if self.flush_timer:
            self.flush_timer.cancel()
            try:
                await self.flush_timer
            except asyncio.CancelledError:
                pass
            self.flush_timer = None

        if len(self.queue) == 0:
            return

        self.is_flushing = True

        try:
            entries = self.queue[:]  # Copy queue
            self.queue.clear()  # Clear queue

            if len(entries) == 0:
                self.is_flushing = False
                return

            log_entries = [e.entry for e in entries]

            # Try Redis first (if available)
            if self.redis.is_connected():
                queue_name = f"audit-logs:{self.config.client_id}"
                # Serialize all entries as JSON array
                import json

                entries_json = json.dumps([entry.model_dump() for entry in log_entries])
                success = await self.redis.rpush(queue_name, entries_json)

                if success:
                    self.is_flushing = False
                    return  # Successfully queued in Redis

            # Check circuit breaker before attempting HTTP logging
            if self.circuit_breaker.is_open():
                # Circuit is open, skip HTTP logging to prevent infinite retry loops
                self.is_flushing = False
                return

            # Fallback to HTTP batch endpoint
            try:
                await self.http_client.request(
                    "POST",
                    "/api/v1/logs/batch",
                    {
                        "logs": [
                            entry.model_dump(
                                exclude={"environment", "application"}, exclude_none=True
                            )
                            for entry in log_entries
                        ]
                    },
                )
                # Record success in circuit breaker
                self.circuit_breaker.record_success()
            except Exception:
                # Failed to send logs - record failure in circuit breaker
                self.circuit_breaker.record_failure()
                # Silently fail to avoid infinite loops
                pass
        except Exception:
            # Silently swallow errors - never break logging
            pass
        finally:
            self.is_flushing = False

    def get_queue_size(self) -> int:
        """
        Get current queue size.

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
