"""
Data masker utility for client-side sensitive data protection.

Implements ISO 27001 data protection controls by masking sensitive fields
in log entries and context data.
"""

from typing import Any, Optional, Set

from .sensitive_fields_loader import get_sensitive_fields_array


class DataMasker:
    """Static class for masking sensitive data."""

    MASKED_VALUE = "***MASKED***"

    # Hardcoded set of sensitive field names (normalized) - fallback if JSON cannot be loaded
    _hardcoded_sensitive_fields: Set[str] = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "key",
        "auth",
        "authorization",
        "cookie",
        "session",
        "ssn",
        "creditcard",
        "cc",
        "cvv",
        "pin",
        "otp",
        "apikey",
        "accesstoken",
        "refreshtoken",
        "privatekey",
        "secretkey",
    }

    # Cached merged sensitive fields (loaded on first use)
    _sensitive_fields: Optional[Set[str]] = None
    _config_loaded: bool = False

    @classmethod
    def _load_config(cls, config_path: Optional[str] = None) -> None:
        """
        Load sensitive fields configuration from JSON and merge with hardcoded defaults.

        This method is called automatically on first use. It loads JSON configuration
        and merges it with hardcoded defaults, ensuring backward compatibility.

        Args:
            config_path: Optional custom path to JSON config file
        """
        if cls._config_loaded:
            return

        # Start with hardcoded fields as base
        merged_fields = set(cls._hardcoded_sensitive_fields)

        try:
            # Try to load fields from JSON configuration
            json_fields = get_sensitive_fields_array(config_path)
            if json_fields:
                # Normalize and add JSON fields (same normalization as hardcoded fields)
                for field in json_fields:
                    if isinstance(field, str):
                        # Normalize: lowercase and remove underscores/hyphens
                        normalized = field.lower().replace("_", "").replace("-", "")
                        merged_fields.add(normalized)
        except Exception:
            # If JSON loading fails, fall back to hardcoded fields only
            pass

        cls._sensitive_fields = merged_fields
        cls._config_loaded = True

    @classmethod
    def _get_sensitive_fields(cls) -> Set[str]:
        """
        Get the set of sensitive fields (loads config on first call).

        Returns:
            Set of normalized sensitive field names
        """
        if not cls._config_loaded:
            cls._load_config()
        assert cls._sensitive_fields is not None
        return cls._sensitive_fields

    @classmethod
    def set_config_path(cls, config_path: str) -> None:
        """
        Set custom path for sensitive fields configuration.

        Must be called before first use of DataMasker methods if custom path is needed.
        Otherwise, default path or environment variable will be used.

        Args:
            config_path: Path to JSON configuration file
        """
        # Reset cache to force reload with new path
        cls._config_loaded = False
        cls._sensitive_fields = None
        cls._load_config(config_path)

    @classmethod
    def is_sensitive_field(cls, key: str) -> bool:
        """
        Check if a field name indicates sensitive data.

        Args:
            key: Field name to check

        Returns:
            True if field is sensitive, False otherwise
        """
        # Normalize key: lowercase and remove underscores/hyphens
        normalized_key = key.lower().replace("_", "").replace("-", "")

        # Get sensitive fields (loads config on first use)
        sensitive_fields = cls._get_sensitive_fields()

        # Check exact match
        if normalized_key in sensitive_fields:
            return True

        # Check if field contains sensitive keywords
        for sensitive_field in sensitive_fields:
            if sensitive_field in normalized_key:
                return True

        return False

    @classmethod
    def mask_sensitive_data(cls, data: Any) -> Any:
        """
        Mask sensitive data in objects, arrays, or primitives.

        Returns a masked copy without modifying the original.
        Recursively processes nested objects and arrays.

        Args:
            data: Data to mask (dict, list, or primitive)

        Returns:
            Masked copy of the data
        """
        # Handle null and undefined
        if data is None:
            return data

        # Handle primitives (string, number, boolean)
        if not isinstance(data, (dict, list)):
            return data

        # Handle arrays
        if isinstance(data, list):
            return [cls.mask_sensitive_data(item) for item in data]

        # Handle objects/dicts
        masked: dict[str, Any] = {}
        for key, value in data.items():
            if cls.is_sensitive_field(key):
                # Mask sensitive field
                masked[key] = cls.MASKED_VALUE
            elif isinstance(value, (dict, list)):
                # Recursively mask nested objects
                masked[key] = cls.mask_sensitive_data(value)
            else:
                # Keep non-sensitive value as-is
                masked[key] = value

        return masked

    @classmethod
    def mask_value(cls, value: str, show_first: int = 0, show_last: int = 0) -> str:
        """
        Mask specific value (useful for masking individual strings).

        Args:
            value: String value to mask
            show_first: Number of characters to show at the start
            show_last: Number of characters to show at the end

        Returns:
            Masked string value
        """
        if not value or len(value) <= show_first + show_last:
            return cls.MASKED_VALUE

        first = value[:show_first] if show_first > 0 else ""
        last = value[-show_last:] if show_last > 0 else ""
        masked_length = max(8, len(value) - show_first - show_last)
        masked = "*" * masked_length

        return f"{first}{masked}{last}"

    @classmethod
    def contains_sensitive_data(cls, data: Any) -> bool:
        """
        Check if data contains sensitive information.

        Args:
            data: Data to check

        Returns:
            True if data contains sensitive fields, False otherwise
        """
        if data is None or not isinstance(data, (dict, list)):
            return False

        if isinstance(data, list):
            return any(cls.contains_sensitive_data(item) for item in data)

        # Check object keys
        for key, value in data.items():
            if cls.is_sensitive_field(key):
                return True
            if isinstance(value, (dict, list)):
                if cls.contains_sensitive_data(value):
                    return True

        return False
