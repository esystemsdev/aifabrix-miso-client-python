"""
Unified logger service with minimal API and automatic context extraction.

This module provides a simplified logging interface that automatically extracts
context from contextvars, eliminating the need to manually pass Request objects.
"""

import traceback
from typing import Any, Dict, Optional

from ..models.config import ClientLoggingOptions
from ..utils.logger_context_storage import LoggerContextStorage
from .logger import LoggerService


class UnifiedLogger:
    """
    Unified logger interface with minimal API and automatic context extraction.

    Provides simple logging methods that automatically extract context from
    contextvars, eliminating the need to manually pass Request objects or context.
    """

    def __init__(
        self,
        logger_service: LoggerService,
        context_storage: Optional[LoggerContextStorage] = None,
    ):
        """
        Initialize unified logger.

        Args:
            logger_service: LoggerService instance for actual log emission
            context_storage: Optional LoggerContextStorage instance (creates new if not provided)
        """
        self.logger_service = logger_service
        self.context_storage = context_storage or LoggerContextStorage()

    async def info(self, message: str) -> None:
        """
        Log info message.

        Args:
            message: Info message
        """
        try:
            context, options = self._build_context_and_options()
            await self.logger_service.info(message, context=context, options=options)
        except Exception:
            # Error handling in logger should be silent (catch and swallow)
            pass

    async def warn(self, message: str) -> None:
        """
        Log warning message.

        Args:
            message: Warning message
        """
        try:
            context, options = self._build_context_and_options()
            # Use info level for warnings (LoggerService doesn't have warn level)
            await self.logger_service.info(f"WARNING: {message}", context=context, options=options)
        except Exception:
            # Error handling in logger should be silent (catch and swallow)
            pass

    async def debug(self, message: str) -> None:
        """
        Log debug message.

        Args:
            message: Debug message
        """
        try:
            context, options = self._build_context_and_options()
            await self.logger_service.debug(message, context=context, options=options)
        except Exception:
            # Error handling in logger should be silent (catch and swallow)
            pass

    async def error(self, message: str, error: Optional[Exception] = None) -> None:
        """
        Log error message.

        Args:
            message: Error message
            error: Optional error object (auto-extracts stack trace)
        """
        try:
            context, options = self._build_context_and_options()
            error_context = self._extract_error_context(error)
            merged_context = {**context, **error_context}
            stack_trace = self._extract_stack_trace(error)
            await self.logger_service.error(
                message, context=merged_context, stack_trace=stack_trace, options=options
            )
        except Exception:
            # Error handling in logger should be silent (catch and swallow)
            pass

    async def audit(
        self,
        action: str,
        resource: str,
        entity_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log audit event.

        Args:
            action: Action performed (e.g., 'CREATE', 'UPDATE', 'DELETE')
            resource: Resource type (e.g., 'User', 'Tenant')
            entity_id: Optional entity ID (defaults to 'unknown')
            old_values: Optional old values for UPDATE operations (ISO 27001 requirement)
            new_values: Optional new values for CREATE/UPDATE operations (ISO 27001 requirement)
        """
        try:
            context, options = self._build_context_and_options()
            audit_context = {
                **context,
                "entityId": entity_id or "unknown",
                "oldValues": old_values,
                "newValues": new_values,
            }
            await self.logger_service.audit(
                action, resource, context=audit_context, options=options
            )
        except Exception:
            # Error handling in logger should be silent (catch and swallow)
            pass

    def _get_context(self) -> Dict[str, Any]:
        """
        Get current context from contextvars.

        Returns:
            Context dictionary (empty dict if no context available)
        """
        context = self.context_storage.get_context()
        return context if context is not None else {}

    def _build_context_and_options(self) -> tuple[Dict[str, Any], ClientLoggingOptions]:
        """
        Build context and options from contextvars.

        Returns:
            Tuple of (context dict, ClientLoggingOptions)
        """
        ctx = self._get_context()

        # Extract fields that go into ClientLoggingOptions
        options_dict: Dict[str, Any] = {}
        context_dict: Dict[str, Any] = {}

        # Map context fields to ClientLoggingOptions
        option_fields = {
            "userId": "userId",
            "applicationId": "applicationId",
            "correlationId": "correlationId",
            "requestId": "requestId",
            "sessionId": "sessionId",
            "token": "token",
            "ipAddress": "ipAddress",
            "userAgent": "userAgent",
        }

        for ctx_key, option_key in option_fields.items():
            if ctx_key in ctx:
                options_dict[option_key] = ctx[ctx_key]

        # Remaining fields go into context
        context_fields = {"method", "path", "hostname"}
        for key, value in ctx.items():
            if key not in option_fields and key not in context_fields:
                context_dict[key] = value

        # Add method, path, hostname to context
        if "method" in ctx:
            context_dict["method"] = ctx["method"]
        if "path" in ctx:
            context_dict["path"] = ctx["path"]
        if "hostname" in ctx:
            context_dict["hostname"] = ctx["hostname"]

        options = ClientLoggingOptions(**options_dict) if options_dict else ClientLoggingOptions()

        return context_dict, options

    def _extract_error_context(self, error: Optional[Exception]) -> Dict[str, Any]:
        """
        Extract error context from exception.

        Args:
            error: Exception object

        Returns:
            Dictionary with error context
        """
        if error is None:
            return {}

        error_context: Dict[str, Any] = {
            "errorName": type(error).__name__,
            "errorMessage": str(error),
        }

        return error_context

    def _extract_stack_trace(self, error: Optional[Exception]) -> Optional[str]:
        """
        Extract stack trace from exception.

        Args:
            error: Exception object

        Returns:
            Stack trace string, or None if no error
        """
        if error is None:
            return None

        try:
            return "".join(traceback.format_exception(type(error), error, error.__traceback__))
        except Exception:
            return str(error)
