"""
Factory functions for unified logger with automatic context detection.

This module provides factory functions to create UnifiedLogger instances
that automatically detect context from contextvars.
"""

from typing import Optional

from ..services.logger import LoggerService
from ..services.unified_logger import UnifiedLogger
from .logger_context_storage import (
    LoggerContextStorage,
    clear_logger_context,
    set_logger_context,
)

# Module-level variable to store the default logger service
# This should be set by MisoClient during initialization
_default_logger_service: Optional[LoggerService] = None


def set_default_logger_service(logger_service: LoggerService) -> None:
    """
    Set the default logger service for get_logger() factory function.

    This should be called once during MisoClient initialization.

    Args:
        logger_service: LoggerService instance to use as default

    Example:
        >>> from miso_client import MisoClient, set_default_logger_service
        >>> client = MisoClient(config)
        >>> set_default_logger_service(client.logger)
    """
    global _default_logger_service
    _default_logger_service = logger_service


def get_logger(logger_service: Optional[LoggerService] = None) -> UnifiedLogger:
    """
    Get logger instance with automatic context detection from contextvars.

    Returns a UnifiedLogger instance that automatically extracts context
    from contextvars, eliminating the need to manually pass Request objects.

    Args:
        logger_service: Optional LoggerService instance. If not provided,
            uses the default logger service set via set_default_logger_service().
            If no default is set, raises RuntimeError.

    Returns:
        UnifiedLogger instance

    Raises:
        RuntimeError: If no logger_service provided and no default is set

    Example:
        >>> from miso_client import get_logger
        >>> logger = get_logger()
        >>> await logger.info("Message")  # Auto-extracts context
    """
    if logger_service is None:
        if _default_logger_service is None:
            raise RuntimeError(
                "No logger service available. Either provide logger_service parameter "
                "or call set_default_logger_service() during MisoClient initialization."
            )
        logger_service = _default_logger_service

    context_storage = LoggerContextStorage()
    return UnifiedLogger(logger_service, context_storage)


# Re-export context management functions for convenience
__all__ = [
    "get_logger",
    "set_default_logger_service",
    "set_logger_context",
    "clear_logger_context",
]
