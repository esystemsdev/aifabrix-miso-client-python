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


def _apply_entity_context(context: Dict[str, Any], prefix: str, entity: HasId) -> None:
    """Apply id/displayName fields for a contextual entity."""
    context[f"{prefix}Id"] = entity.id
    if entity.displayName:
        context[f"{prefix}DisplayName"] = entity.displayName


def extract_logging_context(
    source: Optional[HasExternalSystem] = None,
    record: Optional[HasId] = None,
    external_system: Optional[HasId] = None,
) -> Dict[str, Any]:
    """Extract indexed fields for logging."""
    context: Dict[str, Any] = {}

    if source:
        _apply_entity_context(context, "source", source)
        if source.externalSystem:
            _apply_entity_context(context, "externalSystem", source.externalSystem)

    if external_system:
        _apply_entity_context(context, "externalSystem", external_system)

    if record:
        _apply_entity_context(context, "record", record)

    return context
