"""Logging context helpers for extracting indexed fields."""

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class HasId(Protocol):
    """Protocol for objects with id and displayName."""

    id: str
    displayName: Optional[str]


@runtime_checkable
class HasExternalSystem(Protocol):
    """Protocol for objects with id, displayName, and optional externalSystem."""

    id: str
    displayName: Optional[str]
    externalSystem: Optional[HasId]


def extract_logging_context(
    source: Optional[HasExternalSystem] = None,
    record: Optional[HasId] = None,
    external_system: Optional[HasId] = None,
) -> Dict[str, Any]:
    """Extract indexed fields for logging.

    Indexed fields:
    - sourceId, sourceDisplayName
    - externalSystemId, externalSystemDisplayName
    - recordId, recordDisplayName

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
        context["sourceId"] = source.id
        if source.displayName:
            context["sourceDisplayName"] = source.displayName
        if source.externalSystem:
            context["externalSystemId"] = source.externalSystem.id
            if source.externalSystem.displayName:
                context["externalSystemDisplayName"] = source.externalSystem.displayName

    if external_system:
        context["externalSystemId"] = external_system.id
        if external_system.displayName:
            context["externalSystemDisplayName"] = external_system.displayName

    if record:
        context["recordId"] = record.id
        if record.displayName:
            context["recordDisplayName"] = record.displayName

    return context
