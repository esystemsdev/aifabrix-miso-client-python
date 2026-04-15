"""Logger chain for fluent logging API.

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
        """Initialize logger chain.

        Args:
            logger: Logger service instance
            context: Initial context
            options: Initial logging options

        """
        self.logger = logger
        self.context = context or {}
        self.options = options or ClientLoggingOptions()

    def _ensure_options(self) -> ClientLoggingOptions:
        """Ensure logging options instance exists and return it."""
        if self.options is None:
            self.options = ClientLoggingOptions()
        return self.options

    def _merge_request_auto_fields(self, ctx: Any) -> None:
        """Merge auto-computable request fields into chain context."""
        field_pairs = (
            ("userId", ctx.user_id),
            ("sessionId", ctx.session_id),
            ("correlationId", ctx.correlation_id),
            ("requestId", ctx.request_id),
            ("ipAddress", ctx.ip_address),
            ("userAgent", ctx.user_agent),
        )
        for key, value in field_pairs:
            if value:
                self.context[key] = value

    def _merge_request_detail_fields(self, ctx: Any) -> None:
        """Merge additional request details into chain context."""
        detail_pairs = (
            ("method", ctx.method),
            ("path", ctx.path),
            ("referer", ctx.referer),
            ("requestSize", ctx.request_size),
        )
        for key, value in detail_pairs:
            if value:
                self.context[key] = value

    def _set_option_if_present(self, option_field: str, value: Any) -> None:
        """Set option field when value is not None/empty."""
        if value is None or value == "":
            return
        setattr(self._ensure_options(), option_field, value)

    def add_context(self, key: str, value: Any) -> "LoggerChain":
        """Add context key-value pair."""
        self.context[key] = value
        return self

    def with_application(self, application: str) -> "LoggerChain":
        """Override application name for this log entry."""
        self._ensure_options().application = application
        return self

    def with_environment(self, environment: str) -> "LoggerChain":
        """Override environment name for this log entry."""
        self._ensure_options().environment = environment
        return self

    def without_masking(self) -> "LoggerChain":
        """Disable data masking."""
        self._ensure_options().maskSensitiveData = False
        return self

    def with_request(self, request: Any) -> "LoggerChain":
        """Auto-extract logging context from HTTP Request object."""
        ctx = extract_request_context(request)
        self._ensure_options()
        self._merge_request_auto_fields(ctx)
        self._merge_request_detail_fields(ctx)
        return self

    def with_indexed_context(
        self,
        source_id: Optional[str] = None,
        source_display_name: Optional[str] = None,
        external_system_id: Optional[str] = None,
        external_system_display_name: Optional[str] = None,
        record_id: Optional[str] = None,
        record_display_name: Optional[str] = None,
    ) -> "LoggerChain":
        """Add indexed context fields for fast querying."""
        self._set_option_if_present("sourceId", source_id)
        self._set_option_if_present("sourceDisplayName", source_display_name)
        self._set_option_if_present("externalSystemId", external_system_id)
        self._set_option_if_present("externalSystemDisplayName", external_system_display_name)
        self._set_option_if_present("recordId", record_id)
        self._set_option_if_present("recordDisplayName", record_display_name)
        return self

    def with_credential_context(
        self,
        credential_id: Optional[str] = None,
        credential_type: Optional[str] = None,
    ) -> "LoggerChain":
        """Add credential context for performance analysis.

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
        response_size: Optional[int] = None,
        duration_ms: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        timeout: Optional[float] = None,
        retry_count: Optional[int] = None,
    ) -> "LoggerChain":
        """Add request/response metrics."""
        self._set_option_if_present("responseSize", response_size)
        self._set_option_if_present("durationMs", duration_ms)
        self._set_option_if_present("durationSeconds", duration_seconds)
        self._set_option_if_present("timeout", timeout)
        self._set_option_if_present("retryCount", retry_count)
        return self

    def with_error_context(
        self,
        error_category: Optional[str] = None,
        http_status_category: Optional[str] = None,
    ) -> "LoggerChain":
        """Add error classification context.

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

    async def error(self, message: str, stack_trace: Optional[str] = None) -> None:
        """Log error."""
        await self.logger.error(message, self.context, stack_trace, self.options)

    async def info(self, message: str) -> None:
        """Log info."""
        await self.logger.info(message, self.context, self.options)

    async def warn(self, message: str) -> None:
        """Log warning."""
        await self.logger.warn(message, self.context, self.options)

    async def audit(self, action: str, resource: str) -> None:
        """Log audit."""
        await self.logger.audit(action, resource, self.context, self.options)

    async def debug(self, message: str) -> None:
        """Log debug message.

        Only logs if log level is set to 'debug' in config.

        Args:
            message: Debug message

        """
        await self.logger.debug(message, self.context, self.options)
