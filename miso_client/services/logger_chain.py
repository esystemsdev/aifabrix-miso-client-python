"""
Logger chain for fluent logging API.

This module provides the LoggerChain class for method chaining in logging operations.
"""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .logger import LoggerService

from ..models.config import ClientLoggingOptions
from ..utils.request_context import extract_request_context


class LoggerChain:
    """Method chaining class for fluent logging API."""

    def __init__(
        self,
        logger: "LoggerService",
        context: Optional[dict[str, Any]] = None,
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

    def without_masking(self) -> "LoggerChain":
        """Disable data masking."""
        if self.options is None:
            self.options = ClientLoggingOptions()
        self.options.maskSensitiveData = False
        return self

    def with_request(self, request: Any) -> "LoggerChain":
        """
        Auto-extract logging context from HTTP Request object.

        Extracts: IP, method, path, user-agent, correlation ID, user from JWT.

        Supports:
        - FastAPI/Starlette Request
        - Flask Request
        - Generic dict-like request objects

        Args:
            request: HTTP request object

        Returns:
            Self for method chaining

        Example:
            >>> await logger.with_request(request).info("Processing request")
        """
        ctx = extract_request_context(request)

        if self.options is None:
            self.options = ClientLoggingOptions()

        # Merge into options (these become top-level LogEntry fields)
        if ctx.user_id:
            self.options.userId = ctx.user_id
        if ctx.session_id:
            self.options.sessionId = ctx.session_id
        if ctx.correlation_id:
            self.options.correlationId = ctx.correlation_id
        if ctx.request_id:
            self.options.requestId = ctx.request_id
        if ctx.ip_address:
            self.options.ipAddress = ctx.ip_address
        if ctx.user_agent:
            self.options.userAgent = ctx.user_agent

        # Merge into context (additional request info, not top-level LogEntry fields)
        if ctx.method:
            self.context["method"] = ctx.method
        if ctx.path:
            self.context["path"] = ctx.path
        if ctx.referer:
            self.context["referer"] = ctx.referer
        if ctx.request_size:
            self.context["requestSize"] = ctx.request_size

        return self

    def with_indexed_context(
        self,
        source_key: Optional[str] = None,
        source_display_name: Optional[str] = None,
        external_system_key: Optional[str] = None,
        external_system_display_name: Optional[str] = None,
        record_key: Optional[str] = None,
        record_display_name: Optional[str] = None,
    ) -> "LoggerChain":
        """
        Add indexed context fields for fast querying.

        Args:
            source_key: ExternalDataSource.key
            source_display_name: Human-readable source name
            external_system_key: ExternalSystem.key
            external_system_display_name: Human-readable system name
            record_key: ExternalRecord.key
            record_display_name: Human-readable record identifier

        Returns:
            Self for method chaining
        """
        if self.options is None:
            self.options = ClientLoggingOptions()
        if source_key:
            self.options.sourceKey = source_key
        if source_display_name:
            self.options.sourceDisplayName = source_display_name
        if external_system_key:
            self.options.externalSystemKey = external_system_key
        if external_system_display_name:
            self.options.externalSystemDisplayName = external_system_display_name
        if record_key:
            self.options.recordKey = record_key
        if record_display_name:
            self.options.recordDisplayName = record_display_name
        return self

    def with_credential_context(
        self,
        credential_id: Optional[str] = None,
        credential_type: Optional[str] = None,
    ) -> "LoggerChain":
        """
        Add credential context for performance analysis.

        Args:
            credential_id: Credential identifier
            credential_type: Credential type (apiKey, oauth2, etc.)

        Returns:
            Self for method chaining
        """
        if self.options is None:
            self.options = ClientLoggingOptions()
        if credential_id:
            self.options.credentialId = credential_id
        if credential_type:
            self.options.credentialType = credential_type
        return self

    def with_request_metrics(
        self,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
        duration_ms: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        timeout: Optional[float] = None,
        retry_count: Optional[int] = None,
    ) -> "LoggerChain":
        """
        Add request/response metrics.

        Args:
            request_size: Request body size in bytes
            response_size: Response body size in bytes
            duration_ms: Duration in milliseconds
            duration_seconds: Duration in seconds
            timeout: Request timeout in seconds
            retry_count: Number of retry attempts

        Returns:
            Self for method chaining
        """
        if self.options is None:
            self.options = ClientLoggingOptions()
        if request_size is not None:
            self.options.requestSize = request_size
        if response_size is not None:
            self.options.responseSize = response_size
        if duration_ms is not None:
            self.options.durationMs = duration_ms
        if duration_seconds is not None:
            self.options.durationSeconds = duration_seconds
        if timeout is not None:
            self.options.timeout = timeout
        if retry_count is not None:
            self.options.retryCount = retry_count
        return self

    def with_error_context(
        self,
        error_category: Optional[str] = None,
        http_status_category: Optional[str] = None,
    ) -> "LoggerChain":
        """
        Add error classification context.

        Args:
            error_category: Error category (network, timeout, auth, validation, server)
            http_status_category: HTTP status category (2xx, 4xx, 5xx)

        Returns:
            Self for method chaining
        """
        if self.options is None:
            self.options = ClientLoggingOptions()
        if error_category:
            self.options.errorCategory = error_category
        if http_status_category:
            self.options.httpStatusCategory = http_status_category
        return self

    def add_session(self, session_id: str) -> "LoggerChain":
        """
        Add session ID to logging context.

        Args:
            session_id: Session identifier

        Returns:
            Self for method chaining
        """
        if self.options is None:
            self.options = ClientLoggingOptions()
        self.options.sessionId = session_id
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

    async def debug(self, message: str) -> None:
        """
        Log debug message.

        Only logs if log level is set to 'debug' in config.

        Args:
            message: Debug message
        """
        await self.logger.debug(message, self.context, self.options)
