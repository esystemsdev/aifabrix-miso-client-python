"""
Logger service for application logging and audit events.

This module provides structured logging with Redis queuing and HTTP fallback.
Includes JWT context extraction, data masking, correlation IDs, and performance metrics.
"""

import os
import random
import sys
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from ..models.config import ClientLoggingOptions, LogEntry
from ..services.redis import RedisService
from ..utils.audit_log_queue import AuditLogQueue
from ..utils.data_masker import DataMasker
from ..utils.internal_http_client import InternalHttpClient
from ..utils.jwt_tools import decode_token


class LoggerService:
    """Logger service for application logging and audit events."""

    def __init__(
        self,
        internal_http_client: InternalHttpClient,
        redis: RedisService,
        http_client: Optional[Any] = None,
    ):
        """
        Initialize logger service.

        Args:
            internal_http_client: Internal HTTP client instance (used for log sending)
            redis: Redis service instance
            http_client: Optional HttpClient instance for audit log queue (if available)
        """
        self.config = internal_http_client.config
        self.internal_http_client = internal_http_client
        self.redis = redis
        self.mask_sensitive_data = True  # Default: mask sensitive data
        self.correlation_counter = 0
        self.performance_metrics: Dict[str, Dict[str, Any]] = {}
        self.audit_log_queue: Optional[AuditLogQueue] = None

        # Audit log queue will be initialized later by MisoClient after http_client is created
        # This avoids circular dependency issues

    def set_masking(self, enabled: bool) -> None:
        """
        Enable or disable sensitive data masking.

        Args:
            enabled: Whether to enable data masking
        """
        self.mask_sensitive_data = enabled

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

    def start_performance_tracking(self, operation_id: str) -> None:
        """
        Start performance tracking.

        Args:
            operation_id: Unique identifier for this operation
        """
        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()
            memory_usage = {
                "rss": memory_info.rss,
                "heapTotal": memory_info.rss,  # Approximation
                "heapUsed": (
                    memory_info.rss - memory_info.available
                    if hasattr(memory_info, "available")
                    else memory_info.rss
                ),
                "external": 0,
                "arrayBuffers": 0,
            }
        except ImportError:
            # psutil not available
            memory_usage = None

        self.performance_metrics[operation_id] = {
            "startTime": int(datetime.now().timestamp() * 1000),
            "memoryUsage": memory_usage,
        }

    def end_performance_tracking(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        End performance tracking and get metrics.

        Args:
            operation_id: Unique identifier for this operation

        Returns:
            Performance metrics dictionary or None if not found
        """
        if operation_id not in self.performance_metrics:
            return None

        metrics = self.performance_metrics[operation_id]
        metrics["endTime"] = int(datetime.now().timestamp() * 1000)
        metrics["duration"] = metrics["endTime"] - metrics["startTime"]

        try:
            import psutil

            process = psutil.Process()
            memory_info = process.memory_info()
            metrics["memoryUsage"] = {
                "rss": memory_info.rss,
                "heapTotal": memory_info.rss,
                "heapUsed": (
                    memory_info.rss - memory_info.available
                    if hasattr(memory_info, "available")
                    else memory_info.rss
                ),
                "external": 0,
                "arrayBuffers": 0,
            }
        except (ImportError, Exception):
            pass  # psutil not available or error getting memory info

        del self.performance_metrics[operation_id]
        return metrics

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

        # Add performance metrics if requested
        enhanced_context = masked_context
        if options and options.performanceMetrics:
            try:
                import psutil

                process = psutil.Process()
                memory_info = process.memory_info()
                enhanced_context = {
                    **(enhanced_context or {}),
                    "performance": {
                        "memoryUsage": {
                            "rss": memory_info.rss,
                            "heapTotal": memory_info.rss,
                            "heapUsed": (
                                memory_info.rss - memory_info.available
                                if hasattr(memory_info, "available")
                                else memory_info.rss
                            ),
                        },
                        "uptime": psutil.boot_time() if hasattr(psutil, "boot_time") else 0,
                    },
                }
            except (ImportError, Exception):
                pass  # psutil not available or error getting memory info

        log_entry_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "environment": "unknown",  # Backend extracts from client credentials
            "application": self.config.client_id,  # Use clientId as application identifier
            "applicationId": options.applicationId if options else None,
            "message": message,
            "context": enhanced_context,
            "stackTrace": stack_trace,
            "correlationId": correlation_id,
            "userId": (options.userId if options else None) or jwt_context.get("userId"),
            "sessionId": (options.sessionId if options else None) or jwt_context.get("sessionId"),
            "requestId": options.requestId if options else None,
            **metadata,
        }

        # Remove None values
        log_entry_data = {k: v for k, v in log_entry_data.items() if v is not None}

        log_entry = LogEntry(**log_entry_data)

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

        # Fallback to unified logging endpoint with client credentials
        # Use InternalHttpClient to avoid circular dependency with HttpClient
        try:
            # Backend extracts environment and application from client credentials
            log_payload = log_entry.model_dump(
                exclude={"environment", "application"}, exclude_none=True
            )
            await self.internal_http_client.request("POST", "/api/v1/logs", log_payload)
        except Exception:
            # Failed to send log to controller
            # Silently fail to avoid infinite logging loops
            # Application should implement retry or buffer strategy if needed
            pass

    def with_context(self, context: Dict[str, Any]) -> "LoggerChain":
        """Create logger chain with context."""
        return LoggerChain(self, context, ClientLoggingOptions())

    def with_token(self, token: str) -> "LoggerChain":
        """Create logger chain with token."""
        return LoggerChain(self, {}, ClientLoggingOptions(token=token))

    def with_performance(self) -> "LoggerChain":
        """Create logger chain with performance metrics."""
        opts = ClientLoggingOptions()
        opts.performanceMetrics = True
        return LoggerChain(self, {}, opts)

    def without_masking(self) -> "LoggerChain":
        """Create logger chain without data masking."""
        opts = ClientLoggingOptions()
        opts.maskSensitiveData = False
        return LoggerChain(self, {}, opts)


class LoggerChain:
    """Method chaining class for fluent logging API."""

    def __init__(
        self,
        logger: LoggerService,
        context: Optional[Dict[str, Any]] = None,
        options: Optional[ClientLoggingOptions] = None,
    ):
        """
        Initialize logger chain.

        Args:
            logger: Logger service instance
            context: Initial context
            options: Initial logging options
        """
        self.logger = logger
        self.context = context or {}
        self.options = options or ClientLoggingOptions()

    def add_context(self, key: str, value: Any) -> "LoggerChain":
        """Add context key-value pair."""
        self.context[key] = value
        return self

    def add_user(self, user_id: str) -> "LoggerChain":
        """Add user ID."""
        if self.options is None:
            self.options = ClientLoggingOptions()
        self.options.userId = user_id
        return self

    def add_application(self, application_id: str) -> "LoggerChain":
        """Add application ID."""
        if self.options is None:
            self.options = ClientLoggingOptions()
        self.options.applicationId = application_id
        return self

    def add_correlation(self, correlation_id: str) -> "LoggerChain":
        """Add correlation ID."""
        if self.options is None:
            self.options = ClientLoggingOptions()
        self.options.correlationId = correlation_id
        return self

    def with_token(self, token: str) -> "LoggerChain":
        """Add token for context extraction."""
        if self.options is None:
            self.options = ClientLoggingOptions()
        self.options.token = token
        return self

    def with_performance(self) -> "LoggerChain":
        """Enable performance metrics."""
        if self.options is None:
            self.options = ClientLoggingOptions()
        self.options.performanceMetrics = True
        return self

    def without_masking(self) -> "LoggerChain":
        """Disable data masking."""
        if self.options is None:
            self.options = ClientLoggingOptions()
        self.options.maskSensitiveData = False
        return self

    async def error(self, message: str, stack_trace: Optional[str] = None) -> None:
        """Log error."""
        await self.logger.error(message, self.context, stack_trace, self.options)

    async def info(self, message: str) -> None:
        """Log info."""
        await self.logger.info(message, self.context, self.options)

    async def audit(self, action: str, resource: str) -> None:
        """Log audit."""
        await self.logger.audit(action, resource, self.context, self.options)
