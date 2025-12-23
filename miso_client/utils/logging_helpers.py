"""Logging context helpers for extracting indexed fields."""

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class HasKey(Protocol):
    """Protocol for objects with key and displayName."""

    key: str
    displayName: Optional[str]


@runtime_checkable
class HasExternalSystem(Protocol):
    """Protocol for objects with key, displayName, and optional externalSystem."""

    key: str
    displayName: Optional[str]
    externalSystem: Optional[HasKey]


def extract_logging_context(
    source: Optional[HasExternalSystem] = None,
    record: Optional[HasKey] = None,
    external_system: Optional[HasKey] = None,
) -> Dict[str, Any]:
    """
    Extract indexed fields for logging.

    Indexed fields:
    - sourceKey, sourceDisplayName
    - externalSystemKey, externalSystemDisplayName
    - recordKey, recordDisplayName

    Args:
        source: ExternalDataSource object (optional)
        record: ExternalRecord object (optional)
        external_system: ExternalSystem object (optional)

    Returns:
        Dictionary with indexed context fields (only non-None values)

    Design principles:
    - No DB access
    - Explicit context passing
    - Safe to use in hot paths
    """
    context: Dict[str, Any] = {}

    if source:
        context["sourceKey"] = source.key
        if source.displayName:
            context["sourceDisplayName"] = source.displayName
        if source.externalSystem:
            context["externalSystemKey"] = source.externalSystem.key
            if source.externalSystem.displayName:
                context["externalSystemDisplayName"] = source.externalSystem.displayName

    if external_system:
        context["externalSystemKey"] = external_system.key
        if external_system.displayName:
            context["externalSystemDisplayName"] = external_system.displayName

    if record:
        context["recordKey"] = record.key
        if record.displayName:
            context["recordDisplayName"] = record.displayName

    return context
