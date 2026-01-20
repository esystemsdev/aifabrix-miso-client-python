"""
Logger service for application logging and audit events.

This module provides structured logging with Redis queuing and HTTP fallback.
Includes JWT context extraction, data masking, and correlation IDs.
"""

import asyncio
import inspect
import random
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional, cast

if TYPE_CHECKING:
    # Avoid import at runtime for frameworks not installed
    pass

from ..models.config import ClientLoggingOptions, ForeignKeyReference, LogEntry
from ..services.application_context import ApplicationContextService
from ..services.redis import RedisService
from ..utils.audit_log_queue import AuditLogQueue
from ..utils.circuit_breaker import CircuitBreaker
from ..utils.internal_http_client import InternalHttpClient
from ..utils.logger_helpers import build_log_entry, extract_metadata
from ..utils.logger_request_helpers import (
    get_for_request,
    get_log_with_request,
    get_with_context,
    get_with_token,
)

if TYPE_CHECKING:
    from ..api import ApiClient
    from ..api.types.logs_types import LogRequest

# Import LoggerChain at runtime to avoid circular dependency
from .logger_chain import LoggerChain


class LoggerService:
    """Logger service for application logging and audit events."""

    def __init__(
        self,
        internal_http_client: InternalHttpClient,
        redis: RedisService,
        http_client: Optional[Any] = None,
        api_client: Optional["ApiClient"] = None,
    ):
        """
        Initialize logger service.

        Args:
            internal_http_client: Internal HTTP client instance (used for log sending)
            redis: Redis service instance
            http_client: Optional HttpClient instance for audit log queue (if available)
            api_client: Optional API client instance (for typed API calls, use with caution to avoid circular dependency)
        """
        self.config = internal_http_client.config
        self.internal_http_client = internal_http_client
        self.redis = redis
        self.api_client = api_client
        self.mask_sensitive_data = True  # Default: mask sensitive data
        self.correlation_counter = 0
        self.audit_log_queue: Optional[AuditLogQueue] = None

        # Initialize application context service
        self.application_context_service = ApplicationContextService(internal_http_client)

        # Initialize circuit breaker for HTTP logging
        circuit_breaker_config = self.config.audit.circuitBreaker if self.config.audit else None
        self.circuit_breaker = CircuitBreaker(circuit_breaker_config)

        # Event emission mode: list of callbacks for log events
        # Callbacks receive (log_entry: LogEntry) as argument
        self._event_listeners: List[Callable[[LogEntry], None]] = []

        # Audit log queue will be initialized later by MisoClient after http_client is created
        # This avoids circular dependency issues

    def set_masking(self, enabled: bool) -> None:
        """
        Enable or disable sensitive data masking.

        Args:
            enabled: Whether to enable data masking
        """
        self.mask_sensitive_data = enabled

    def on(self, callback: Callable[[LogEntry], None]) -> None:
        """
        Register an event listener for log events.

        When `emit_events=True` in config, logs are emitted as events instead of
        being sent via HTTP/Redis. Registered callbacks receive LogEntry objects.

        Args:
            callback: Async or sync function that receives LogEntry as argument

        Example:
            >>> async def log_handler(log_entry: LogEntry):
            ...     print(f"Log: {log_entry.level} - {log_entry.message}")
            >>> logger.on(log_handler)
        """
        if callback not in self._event_listeners:
            self._event_listeners.append(callback)

    def off(self, callback: Callable[[LogEntry], None]) -> None:
        """
        Unregister an event listener.

        Args:
            callback: Callback function to remove from listeners
        """
        if callback in self._event_listeners:
            self._event_listeners.remove(callback)

    def _generate_correlation_id(self) -> str:
        """
        Generate unique correlation ID for request tracking.

        Format: {clientId[0:10]}-{timestamp}-{counter}-{random}

        Returns:
            Correlation ID string
        """
        self.correlation_counter = (self.correlation_counter + 1) % 10000
        timestamp = int(datetime.now().timestamp() * 1000)
        random_part = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
        client_prefix = (
            self.config.client_id[:10] if len(self.config.client_id) > 10 else self.config.client_id
        )
        return f"{client_prefix}-{timestamp}-{self.correlation_counter}-{random_part}"

    async def error(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        options: Optional[ClientLoggingOptions] = None,
    ) -> None:
        """
        Log error message with optional stack trace and enhanced options.

        Args:
            message: Error message
            context: Additional context data
            stack_trace: Stack trace string
            options: Logging options
        """
        await self._log("error", message, context, stack_trace, options)

    async def audit(
        self,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
        options: Optional[ClientLoggingOptions] = None,
    ) -> None:
        """
        Log audit event with enhanced options.

        Args:
            action: Action performed
            resource: Resource affected
            context: Additional context data
            options: Logging options
        """
        audit_context = {"action": action, "resource": resource, **(context or {})}
        await self._log("audit", f"Audit: {action} on {resource}", audit_context, None, options)

    async def info(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        options: Optional[ClientLoggingOptions] = None,
    ) -> None:
        """
        Log info message with enhanced options.

        Args:
            message: Info message
            context: Additional context data
            options: Logging options
        """
        await self._log("info", message, context, None, options)

    async def debug(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        options: Optional[ClientLoggingOptions] = None,
    ) -> None:
        """
        Log debug message with enhanced options.

        Args:
            message: Debug message
            context: Additional context data
            options: Logging options
        """
        if self.config.log_level == "debug":
            await self._log("debug", message, context, None, options)

    async def _emit_log_event(self, log_entry: LogEntry) -> bool:
        """
        Emit log entry as event if event emission is enabled.

        Args:
            log_entry: LogEntry to emit

        Returns:
            True if event was emitted, False otherwise
        """
        if not (self.config.emit_events and self._event_listeners):
            return False

        for callback in self._event_listeners:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(log_entry)
                else:
                    callback(log_entry)
            except Exception:
                # Silently fail to avoid breaking application flow
                pass
        return True

    async def _queue_audit_log(self, log_entry: LogEntry) -> bool:
        """
        Queue audit log entry if audit queue is available.

        Args:
            log_entry: LogEntry to queue

        Returns:
            True if queued, False otherwise
        """
        if log_entry.level == "audit" and self.audit_log_queue:
            await self.audit_log_queue.add(log_entry)
            return True
        return False

    async def _queue_redis_log(self, log_entry: LogEntry) -> bool:
        """
        Queue log entry in Redis if available.

        Args:
            log_entry: LogEntry to queue

        Returns:
            True if queued, False otherwise
        """
        if not self.redis.is_connected():
            return False

        queue_name = f"logs:{self.config.client_id}"
        success = await self.redis.rpush(queue_name, log_entry.model_dump_json())
        return success

    async def _send_http_log(self, log_entry: LogEntry) -> None:
        """
        Send log entry via HTTP to controller.

        Args:
            log_entry: LogEntry to send
        """
        # Check circuit breaker before attempting HTTP logging
        if self.circuit_breaker.is_open():
            return

        try:
            if self.api_client:
                log_request = self._transform_log_entry_to_request(log_entry)
                await self.api_client.logs.send_log(log_request)
            else:
                log_payload = log_entry.model_dump(
                    exclude={"environment", "application"}, exclude_none=True
                )
                await self.internal_http_client.request("POST", "/api/v1/logs", log_payload)
            self.circuit_breaker.record_success()
        except Exception:
            # Failed to send log to controller
            self.circuit_breaker.record_failure()
            # Silently fail to avoid infinite logging loops
            pass

    async def _get_app_context(self, options: Optional[ClientLoggingOptions]) -> Dict[str, Any]:
        """Get application context with option overwrites."""
        try:
            app_id = None
            if options and options.applicationId:
                app_id = (
                    options.applicationId.id
                    if isinstance(options.applicationId, ForeignKeyReference)
                    else options.applicationId
                )
            ctx = await self.application_context_service.get_application_context(
                overwrite_application=options.application if options else None,
                overwrite_application_id=app_id,
                overwrite_environment=options.environment if options else None,
            )
            return ctx.to_dict()
        except (RuntimeError, asyncio.CancelledError, ConnectionError):
            # Event loop closed or connection error - return default context
            return {
                "application": (
                    options.application if options and options.application else "unknown"
                ),
                "applicationId": app_id if app_id else None,
                "environment": (
                    options.environment if options and options.environment else "unknown"
                ),
            }

    async def _build_log_entry(
        self,
        level: Literal["error", "audit", "info", "debug"],
        message: str,
        context: Optional[Dict[str, Any]],
        stack_trace: Optional[str],
        options: Optional[ClientLoggingOptions],
    ) -> LogEntry:
        """Build log entry with all context."""
        correlation_id = (
            options.correlationId if options else None
        ) or self._generate_correlation_id()
        return build_log_entry(
            level=level,
            message=message,
            context=context,
            config_client_id=self.config.client_id,
            correlation_id=correlation_id,
            jwt_token=options.token if options else None,
            stack_trace=stack_trace,
            options=options,
            metadata=extract_metadata(),
            mask_sensitive=self.mask_sensitive_data,
            application_context=await self._get_app_context(options),
        )

    async def _log(
        self,
        level: Literal["error", "audit", "info", "debug"],
        message: str,
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        options: Optional[ClientLoggingOptions] = None,
    ) -> None:
        """Core logging method with Redis queuing and HTTP fallback."""
        log_entry = await self._build_log_entry(level, message, context, stack_trace, options)

        # Try backends in order: events -> audit queue -> redis -> http
        if await self._emit_log_event(log_entry):
            return
        if await self._queue_audit_log(log_entry):
            return
        if await self._queue_redis_log(log_entry):
            return
        await self._send_http_log(log_entry)

    def _transform_log_entry_to_request(self, log_entry: LogEntry) -> "LogRequest":
        """Transform LogEntry to LogRequest format for API layer."""
        from ..api.types.logs_types import AuditLogData, GeneralLogData, LogRequest

        ctx = log_entry.context or {}
        if log_entry.level == "audit":
            return LogRequest(
                type="audit",
                data=AuditLogData(
                    entityType=ctx.get("entityType", ctx.get("resource", "unknown")),
                    entityId=ctx.get("entityId", ctx.get("resourceId", "unknown")),
                    action=ctx.get("action", "unknown"),
                    oldValues=ctx.get("oldValues"),
                    newValues=ctx.get("newValues"),
                    correlationId=log_entry.correlationId,
                ),
            )

        log_type = cast(
            Literal["error", "general"], "error" if log_entry.level == "error" else "general"
        )
        return LogRequest(
            type=log_type,
            data=GeneralLogData(
                level=log_entry.level if log_entry.level != "error" else "error",  # type: ignore
                message=log_entry.message,
                context=ctx,
                correlationId=log_entry.correlationId,
            ),
        )

    def with_context(self, context: Dict[str, Any]) -> "LoggerChain":
        """Create logger chain with context."""
        return LoggerChain(self, context, ClientLoggingOptions())

    def with_token(self, token: str) -> "LoggerChain":
        """Create logger chain with token."""
        return LoggerChain(self, {}, ClientLoggingOptions(token=token))

    def without_masking(self) -> "LoggerChain":
        """Create logger chain without data masking."""
        opts = ClientLoggingOptions()
        opts.maskSensitiveData = False
        return LoggerChain(self, {}, opts)

    def for_request(self, request: Any) -> "LoggerChain":
        """
        Create logger chain with request context pre-populated.

        Shortcut for: logger.with_context({}).with_request(request)

        Args:
            request: HTTP request object (FastAPI, Flask, Starlette)

        Returns:
            LoggerChain with request context

        Example:
            >>> await logger.for_request(request).info("Processing")
        """
        return LoggerChain(self, {}, ClientLoggingOptions()).with_request(request)

    async def get_log_with_request(
        self,
        request: Any,
        message: str,
        level: Literal["error", "audit", "info", "debug"] = "info",
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
    ) -> LogEntry:
        """
        Get LogEntry object with auto-extracted request context.

        Extracts IP, method, path, userAgent, correlationId, userId from request.
        Returns LogEntry object ready for use in other projects' logger tables.

        Args:
            request: HTTP request object (FastAPI, Flask, Starlette)
            message: Log message
            level: Log level (default: "info")
            context: Additional context data (optional)
            stack_trace: Stack trace for errors (optional)

        Returns:
            LogEntry object with request context extracted

        Example:
            >>> log_entry = logger.get_log_with_request(request, "Processing request")
            >>> # Use log_entry in your own logger table
        """
        return await get_log_with_request(self, request, message, level, context, stack_trace)

    async def get_with_context(
        self,
        context: Dict[str, Any],
        message: str,
        level: Literal["error", "audit", "info", "debug"] = "info",
        stack_trace: Optional[str] = None,
        options: Optional[ClientLoggingOptions] = None,
    ) -> LogEntry:
        """
        Get LogEntry with custom context for use in custom logging tables.

        Args:
            context: Custom context data
            message: Log message
            level: Log level (default: "info")
            stack_trace: Stack trace for errors
            options: Optional logging options
        """
        return await get_with_context(self, context, message, level, stack_trace, options)

    async def get_with_token(
        self,
        token: str,
        message: str,
        level: Literal["error", "audit", "info", "debug"] = "info",
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
    ) -> LogEntry:
        """
        Get LogEntry with JWT token context (userId, sessionId) extracted.

        Args:
            token: JWT token string
            message: Log message
            level: Log level (default: "info")
            context: Additional context data
            stack_trace: Stack trace for errors
        """
        return await get_with_token(self, token, message, level, context, stack_trace)

    async def get_for_request(
        self,
        request: Any,
        message: str,
        level: Literal["error", "audit", "info", "debug"] = "info",
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
    ) -> LogEntry:
        """
        Get LogEntry object with request context (alias for get_log_with_request).

        Same functionality as get_log_with_request() for convenience.

        Args:
            request: HTTP request object (FastAPI, Flask, Starlette)
            message: Log message
            level: Log level (default: "info")
            context: Additional context data (optional)
            stack_trace: Stack trace for errors (optional)

        Returns:
            LogEntry object with request context extracted

        Example:
            >>> log_entry = await logger.get_for_request(request, "Request processed")
        """
        return await get_for_request(self, request, message, level, context, stack_trace)
