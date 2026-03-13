"""Data masker utility for client-side sensitive data protection.

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

    @staticmethod
    def _normalize_sensitive_field_name(field: str) -> str:
        """Normalize sensitive field names for comparison."""
        return field.lower().replace("_", "").replace("-", "")

    @classmethod
    def _load_config(cls, config_path: Optional[str] = None) -> None:
        """Load JSON sensitive fields config and merge with defaults."""
        if cls._config_loaded:
            return
        merged_fields = set(cls._hardcoded_sensitive_fields)
        try:
            json_fields = get_sensitive_fields_array(config_path)
            if json_fields:
                for field in json_fields:
                    if isinstance(field, str):
                        merged_fields.add(cls._normalize_sensitive_field_name(field))
        except Exception:
            pass
        cls._sensitive_fields = merged_fields
        cls._config_loaded = True

    @classmethod
    def _get_sensitive_fields(cls) -> Set[str]:
        """Get the set of sensitive fields (loads config on first call).

        Returns:
            Set of normalized sensitive field names

        """
        if not cls._config_loaded:
            cls._load_config()
        assert cls._sensitive_fields is not None
        return cls._sensitive_fields

    @classmethod
    def set_config_path(cls, config_path: str) -> None:
        """Set custom path for sensitive fields configuration.

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
        """Check if a field name indicates sensitive data.

        Args:
            key: Field name to check

        Returns:
            True if field is sensitive, False otherwise

        """
        normalized_key = cls._normalize_sensitive_field_name(key)
        sensitive_fields = cls._get_sensitive_fields()
        if normalized_key in sensitive_fields:
            return True
        for sensitive_field in sensitive_fields:
            if sensitive_field in normalized_key:
                return True
        return False

    @classmethod
    def mask_sensitive_data(cls, data: Any) -> Any:
        """Mask sensitive data in objects, arrays, or primitives.

        Returns a masked copy without modifying the original.
        Recursively processes nested objects and arrays.

        Args:
            data: Data to mask (dict, list, or primitive)

        Returns:
            Masked copy of the data

        """
        if data is None:
            return data
        if not isinstance(data, (dict, list)):
            return data
        if isinstance(data, list):
            return [cls.mask_sensitive_data(item) for item in data]
        return cls._mask_dict_values(data)

    @classmethod
    def _mask_dict_values(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Mask sensitive fields in dictionary values recursively."""
        masked: dict[str, Any] = {}
        for key, value in data.items():
            if cls.is_sensitive_field(key):
                masked[key] = cls.MASKED_VALUE
            elif isinstance(value, (dict, list)):
                masked[key] = cls.mask_sensitive_data(value)
            else:
                masked[key] = value
        return masked

    @classmethod
    def mask_value(cls, value: str, show_first: int = 0, show_last: int = 0) -> str:
        """Mask specific value (useful for masking individual strings).

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
        """Check if data contains sensitive information.

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
