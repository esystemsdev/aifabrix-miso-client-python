"""
Logger context storage using contextvars for async context propagation.

This module provides context storage for logger context that automatically
propagates across async boundaries using Python's contextvars.
"""

from contextvars import ContextVar
from typing import Any, Dict, Optional

# Context variable for storing logger context per async execution context
logger_context_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "logger_context", default=None
)


class LoggerContextStorage:
    """
    Storage for logger context using contextvars.

    Provides thread-safe context storage that automatically propagates
    across async boundaries within the same execution context.
    """

    @staticmethod
    def get_context() -> Optional[Dict[str, Any]]:
        """
        Get current logger context from contextvars.

        Returns:
            Current context dictionary, or None if no context is set
        """
        return logger_context_var.get()

    @staticmethod
    def set_context(context: Dict[str, Any]) -> None:
        """
        Set logger context for current async execution context.

        Args:
            context: Context dictionary to set
        """
        logger_context_var.set(context)

    @staticmethod
    def clear_context() -> None:
        """
        Clear logger context for current async execution context.
        """
        logger_context_var.set(None)

    @staticmethod
    def merge_context(additional: Dict[str, Any]) -> None:
        """
        Merge additional fields into existing context.

        Args:
            additional: Additional context fields to merge
        """
        current = logger_context_var.get()
        if current is None:
            logger_context_var.set(additional)
        else:
            merged = {**current, **additional}
            logger_context_var.set(merged)


def get_logger_context() -> Optional[Dict[str, Any]]:
    """
    Get current logger context from contextvars.

    Returns:
        Current context dictionary, or None if no context is set
    """
    return LoggerContextStorage.get_context()


def set_logger_context(context: Dict[str, Any]) -> None:
    """
    Set logger context for current async execution context.

    Args:
        context: Context dictionary to set

    Example:
        >>> set_logger_context({
        ...     "userId": "user-123",
        ...     "correlationId": "req-456",
        ...     "ipAddress": "127.0.0.1"
        ... })
    """
    LoggerContextStorage.set_context(context)


def clear_logger_context() -> None:
    """
    Clear logger context for current async execution context.

    Example:
        >>> clear_logger_context()
    """
    LoggerContextStorage.clear_context()


def merge_logger_context(additional: Dict[str, Any]) -> None:
    """
    Merge additional fields into existing context.

    Args:
        additional: Additional context fields to merge

    Example:
        >>> merge_logger_context({"customField": "value"})
    """
    LoggerContextStorage.merge_context(additional)
