"""
Logger service for application logging and audit events.

This module provides structured logging with Redis queuing and HTTP fallback.
Includes JWT context extraction, data masking, and correlation IDs.
"""

import inspect
import os
import random
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional, cast

if TYPE_CHECKING:
    # Avoid import at runtime for frameworks not installed
    pass

from ..models.config import ClientLoggingOptions, LogEntry
from ..services.redis import RedisService
from ..utils.audit_log_queue import AuditLogQueue
from ..utils.circuit_breaker import CircuitBreaker
from ..utils.data_masker import DataMasker
from ..utils.internal_http_client import InternalHttpClient
from ..utils.jwt_tools import decode_token

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

    def _extract_jwt_context(self, token: Optional[str]) -> Dict[str, Any]:
        """
        Extract JWT token information.

        Args:
            token: JWT token string

        Returns:
            Dictionary with userId, applicationId, sessionId, roles, permissions
        """
        if not token:
            return {}

        try:
            decoded = decode_token(token)
            if not decoded:
                return {}

            # Extract roles - handle different formats
            roles = []
            if "roles" in decoded:
                roles = decoded["roles"] if isinstance(decoded["roles"], list) else []
            elif "realm_access" in decoded and isinstance(decoded["realm_access"], dict):
                roles = decoded["realm_access"].get("roles", [])

            # Extract permissions - handle different formats
            permissions = []
            if "permissions" in decoded:
                permissions = (
                    decoded["permissions"] if isinstance(decoded["permissions"], list) else []
                )
            elif "scope" in decoded and isinstance(decoded["scope"], str):
                permissions = decoded["scope"].split()

            return {
                "userId": decoded.get("sub") or decoded.get("userId") or decoded.get("user_id"),
                "applicationId": decoded.get("applicationId") or decoded.get("app_id"),
                "sessionId": decoded.get("sessionId") or decoded.get("sid"),
                "roles": roles,
                "permissions": permissions,
            }
        except Exception:
            # JWT parsing failed, return empty context
            return {}

    def _extract_metadata(self) -> Dict[str, Any]:
        """
        Extract metadata from environment (browser or Node.js).

        Returns:
            Dictionary with hostname, userAgent, etc.
        """
        metadata: Dict[str, Any] = {}

        # Try to extract Node.js/Python metadata
        if hasattr(os, "environ"):
            metadata["hostname"] = os.environ.get("HOSTNAME", "unknown")

        # In Python, we don't have browser metadata like in TypeScript
        # But we can capture some environment info
        metadata["platform"] = sys.platform
        metadata["python_version"] = sys.version

        return metadata

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

    async def _log(
        self,
        level: Literal["error", "audit", "info", "debug"],
        message: str,
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        options: Optional[ClientLoggingOptions] = None,
    ) -> None:
        """
        Internal log method with enhanced features.

        Args:
            level: Log level
            message: Log message
            context: Additional context data
            stack_trace: Stack trace for errors
            options: Logging options
        """
        # Extract JWT context if token provided
        jwt_context = (
            self._extract_jwt_context(options.token if options else None) if options else {}
        )

        # Extract environment metadata
        metadata = self._extract_metadata()

        # Generate correlation ID if not provided
        correlation_id = (
            options.correlationId if options else None
        ) or self._generate_correlation_id()

        # Mask sensitive data in context if enabled
        mask_sensitive = (
            options.maskSensitiveData if options else None
        ) is not False and self.mask_sensitive_data
        masked_context = (
            DataMasker.mask_sensitive_data(context) if mask_sensitive and context else context
        )

        log_entry_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "environment": "unknown",  # Backend extracts from client credentials
            "application": self.config.client_id,  # Use clientId as application identifier
            "applicationId": options.applicationId if options else None,
            "message": message,
            "context": masked_context,
            "stackTrace": stack_trace,
            "correlationId": correlation_id,
            "userId": (options.userId if options else None) or jwt_context.get("userId"),
            "sessionId": (options.sessionId if options else None) or jwt_context.get("sessionId"),
            "requestId": options.requestId if options else None,
            "ipAddress": options.ipAddress if options else None,
            "userAgent": options.userAgent if options else None,
            **metadata,
            # Indexed context fields from options
            "sourceKey": options.sourceKey if options else None,
            "sourceDisplayName": options.sourceDisplayName if options else None,
            "externalSystemKey": options.externalSystemKey if options else None,
            "externalSystemDisplayName": options.externalSystemDisplayName if options else None,
            "recordKey": options.recordKey if options else None,
            "recordDisplayName": options.recordDisplayName if options else None,
            # Credential context
            "credentialId": options.credentialId if options else None,
            "credentialType": options.credentialType if options else None,
            # Request metrics
            "requestSize": options.requestSize if options else None,
            "responseSize": options.responseSize if options else None,
            "durationMs": options.durationMs if options else None,
            "durationSeconds": options.durationSeconds if options else None,
            "timeout": options.timeout if options else None,
            "retryCount": options.retryCount if options else None,
            # Error classification
            "errorCategory": options.errorCategory if options else None,
            "httpStatusCategory": options.httpStatusCategory if options else None,
        }

        # Remove None values
        log_entry_data = {k: v for k, v in log_entry_data.items() if v is not None}

        log_entry = LogEntry(**log_entry_data)

        # Event emission mode: emit events instead of sending via HTTP/Redis
        if self.config.emit_events and self._event_listeners:
            for callback in self._event_listeners:
                try:
                    # Check if callback is async
                    if inspect.iscoroutinefunction(callback):
                        await callback(log_entry)
                    else:
                        callback(log_entry)
                except Exception:
                    # Silently fail to avoid breaking application flow
                    # Event listeners should handle their own errors
                    pass
            # In event emission mode, don't send via HTTP/Redis
            return

        # Use batch queue for audit logs if available
        if level == "audit" and self.audit_log_queue:
            await self.audit_log_queue.add(log_entry)
            return

        # Try Redis first (if available)
        if self.redis.is_connected():
            queue_name = f"logs:{self.config.client_id}"
            success = await self.redis.rpush(queue_name, log_entry.model_dump_json())

            if success:
                return  # Successfully queued in Redis

        # Check circuit breaker before attempting HTTP logging
        if self.circuit_breaker.is_open():
            # Circuit is open, skip HTTP logging to prevent infinite retry loops
            return

        # Fallback to unified logging endpoint with client credentials
        # Use InternalHttpClient to avoid circular dependency with HttpClient
        # Note: ApiClient wraps HttpClient which uses LoggerService for audit logging,
        # so using ApiClient here would create a circular dependency. We keep InternalHttpClient
        # as the primary method, but ApiClient can be used as optional fallback if needed.
        try:
            if self.api_client:
                # Use ApiClient for typed API calls (if available, but beware of circular dependency)
                # Transform LogEntry to LogRequest format
                log_request = self._transform_log_entry_to_request(log_entry)
                await self.api_client.logs.send_log(log_request)
            else:
                # Use InternalHttpClient to avoid circular dependency
                # Backend extracts environment and application from client credentials
                log_payload = log_entry.model_dump(
                    exclude={"environment", "application"}, exclude_none=True
                )
                await self.internal_http_client.request("POST", "/api/v1/logs", log_payload)
            # Record success in circuit breaker
            self.circuit_breaker.record_success()
        except Exception:
            # Failed to send log to controller
            # Record failure in circuit breaker
            self.circuit_breaker.record_failure()
            # Silently fail to avoid infinite logging loops
            # Application should implement retry or buffer strategy if needed
            pass

    def _transform_log_entry_to_request(self, log_entry: LogEntry) -> "LogRequest":
        """
        Transform LogEntry to LogRequest format for API layer.

        Args:
            log_entry: LogEntry to transform

        Returns:
            LogRequest with appropriate type and data
        """
        from ..api.types.logs_types import AuditLogData, GeneralLogData, LogRequest

        context = log_entry.context or {}

        if log_entry.level == "audit":
            # Transform to AuditLogData
            audit_data = AuditLogData(
                entityType=context.get("entityType", context.get("resource", "unknown")),
                entityId=context.get("entityId", context.get("resourceId", "unknown")),
                action=context.get("action", "unknown"),
                oldValues=context.get("oldValues"),
                newValues=context.get("newValues"),
                correlationId=log_entry.correlationId,
            )
            return LogRequest(type="audit", data=audit_data)
        else:
            # Transform to GeneralLogData
            # Map level: "error" -> "error", others -> "general"
            log_type = cast(
                Literal["error", "general"], "error" if log_entry.level == "error" else "general"
            )
            general_data = GeneralLogData(
                level=log_entry.level if log_entry.level != "error" else "error",  # type: ignore
                message=log_entry.message,
                context=context,
                correlationId=log_entry.correlationId,
            )
            return LogRequest(type=log_type, data=general_data)

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
