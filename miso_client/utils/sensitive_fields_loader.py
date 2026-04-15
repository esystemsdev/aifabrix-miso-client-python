"""Sensitive fields configuration loader for ISO 27001 compliance.

This module provides utilities to load and merge sensitive fields configuration
from JSON files, supporting custom configuration paths and environment variables.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Default path to sensitive fields config relative to this file
_DEFAULT_CONFIG_PATH = Path(__file__).parent / "sensitive_fields_config.json"


def _resolve_config_file_path(config_path: Optional[str]) -> Path:
    """Resolve sensitive fields config path by priority rules."""
    if config_path:
        return Path(config_path)
    env_path = os.environ.get("MISO_SENSITIVE_FIELDS_CONFIG")
    if env_path:
        return Path(env_path)
    return _DEFAULT_CONFIG_PATH


def _load_json_config(file_path: Path) -> Dict[str, Any]:
    """Load JSON config file and return dict payload when valid."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config if isinstance(config, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, IOError, OSError):
        return {}


def load_sensitive_fields_config(
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Load sensitive fields configuration from JSON file.

    Supports custom path via:
    1. config_path parameter
    2. MISO_SENSITIVE_FIELDS_CONFIG environment variable
    3. Default path: miso_client/utils/sensitive_fields_config.json

    Args:
        config_path: Optional custom path to JSON config file

    Returns:
        Dictionary with optional keys: ``fields``, ``fieldPatterns``,
        ``neverMaskFields`` (list of field names to never redact),
        ``substringMinLength`` (int, min length for substring keyword matching; default 4),
        ``mergeWithHardcodedDefaults`` (bool; default true).
        Returns empty dict if file cannot be loaded

    Example:
        >>> config = load_sensitive_fields_config()
        >>> fields = config.get('fields', {})

    """
    return _load_json_config(_resolve_config_file_path(config_path))


def get_sensitive_fields_array(
    config_path: Optional[str] = None,
) -> List[str]:
    """Get flattened array of all sensitive field names from configuration.

    Args:
        config_path: Optional custom path to JSON config file

    Returns:
        Flattened list of all sensitive field names from all categories
        Returns empty list if config cannot be loaded

    Example:
        >>> fields = get_sensitive_fields_array()
        >>> assert 'password' in fields
        >>> assert 'token' in fields

    """
    config = load_sensitive_fields_config(config_path)
    fields_dict = config.get("fields", {})

    all_fields: List[str] = []
    if isinstance(fields_dict, dict):
        for category_fields in fields_dict.values():
            if isinstance(category_fields, list):
                all_fields.extend(category_fields)
    return _unique_fields_preserving_order(all_fields)


def _unique_fields_preserving_order(fields: List[str]) -> List[str]:
    """Remove case-insensitive duplicates while preserving original order."""
    seen = set()
    unique_fields: List[str] = []
    for field in fields:
        key = field.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_fields.append(field)
    return unique_fields


def get_field_patterns(config_path: Optional[str] = None) -> List[str]:
    """Get field pattern matching rules from configuration.

    Args:
        config_path: Optional custom path to JSON config file

    Returns:
        List of field pattern matching rules
        Returns empty list if config cannot be loaded or no patterns defined

    Example:
        >>> patterns = get_field_patterns()
        >>> # Patterns can be regex patterns or simple matching rules

    """
    config = load_sensitive_fields_config(config_path)
    patterns = config.get("fieldPatterns", [])
    return patterns if isinstance(patterns, list) else []
