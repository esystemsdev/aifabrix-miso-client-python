"""Data masker utility for client-side sensitive data protection.

Implements ISO 27001 data protection controls by masking sensitive fields
in log entries and context data. Policy is driven by ``sensitive_fields_config.json``
(plus optional per-call ``config_path``).
"""

from pathlib import Path
from typing import Any, Callable, Optional, Set

from .sensitive_fields_loader import get_sensitive_fields_array, load_sensitive_fields_config


class DataMasker:
    """Static class for masking sensitive data."""

    MASKED_VALUE = "***MASKED***"

    # Hardcoded set of sensitive field names (normalized) — used when JSON cannot be
    # loaded or mergeWithHardcodedDefaults is true. Avoid bare "key" and "cc" (false
    # positives on datasource ``key`` and ``success``); prefer compound names in JSON.
    _hardcoded_sensitive_fields: Set[str] = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "auth",
        "authorization",
        "cookie",
        "session",
        "ssn",
        "creditcard",
        "cvv",
        "pin",
        "otp",
        "apikey",
        "accesstoken",
        "refreshtoken",
        "privatekey",
        "secretkey",
    }

    _sensitive_fields: Optional[Set[str]] = None
    _config_loaded: bool = False
    _never_mask_fields: Set[str] = set()
    _substring_min_length: int = 4

    @classmethod
    def _normalize_field_name(cls, field: str) -> str:
        return field.lower().replace("_", "").replace("-", "")

    @classmethod
    def _never_mask_from_cfg(cls, cfg: dict) -> Set[str]:
        raw = cfg.get("neverMaskFields") or []
        out: Set[str] = set()
        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, str) and x.strip():
                    out.add(cls._normalize_field_name(x))
        return out

    @classmethod
    def _substr_min_from_cfg(cls, cfg: dict) -> int:
        sm = cfg.get("substringMinLength", 4)
        try:
            return max(1, min(int(sm), 64))
        except (TypeError, ValueError):
            return 4

    @classmethod
    def _key_is_sensitive(
        cls,
        key: str,
        sensitive_fields: Set[str],
        never_mask: Set[str],
        substr_min: int,
    ) -> bool:
        nk = cls._normalize_field_name(key)
        if nk in never_mask:
            return False
        if nk in sensitive_fields:
            return True
        for sf in sensitive_fields:
            if len(sf) >= substr_min and sf in nk:
                return True
        return False

    @classmethod
    def _load_config(cls, config_path: Optional[str] = None) -> None:
        """Load sensitive fields configuration from JSON and merge with hardcoded defaults."""
        if cls._config_loaded:
            return

        cfg = load_sensitive_fields_config(config_path)
        merge_defaults = bool(cfg.get("mergeWithHardcodedDefaults", True))

        merged_fields: Set[str] = set()
        if merge_defaults:
            merged_fields.update(cls._hardcoded_sensitive_fields)

        try:
            json_fields = get_sensitive_fields_array(config_path)
            if json_fields:
                for field in json_fields:
                    if isinstance(field, str):
                        merged_fields.add(cls._normalize_field_name(field))
        except Exception:
            pass

        if not merge_defaults and not merged_fields:
            merged_fields = set(cls._hardcoded_sensitive_fields)

        cls._never_mask_fields = cls._never_mask_from_cfg(cfg)
        cls._substring_min_length = cls._substr_min_from_cfg(cfg)
        cls._sensitive_fields = merged_fields
        cls._config_loaded = True

    @classmethod
    def _get_sensitive_fields(cls) -> Set[str]:
        if not cls._config_loaded:
            cls._load_config()
        assert cls._sensitive_fields is not None
        return cls._sensitive_fields

    @classmethod
    def set_config_path(cls, config_path: str) -> None:
        """Set custom path for sensitive fields configuration (global cache).

        Must be called before first use of DataMasker methods if a custom path is needed.
        """
        cls._config_loaded = False
        cls._sensitive_fields = None
        cls._never_mask_fields = set()
        cls._substring_min_length = 4
        cls._load_config(config_path)

    @classmethod
    def is_sensitive_field(cls, key: str) -> bool:
        """Check if a field name indicates sensitive data."""
        sensitive_fields = cls._get_sensitive_fields()
        return cls._key_is_sensitive(
            key,
            sensitive_fields,
            cls._never_mask_fields,
            cls._substring_min_length,
        )

    @classmethod
    def _mask_recursive(cls, data: Any, is_sensitive: Callable[[str], bool]) -> Any:
        if data is None:
            return data
        if not isinstance(data, (dict, list)):
            return data
        if isinstance(data, list):
            return [cls._mask_recursive(item, is_sensitive) for item in data]
        masked: dict[str, Any] = {}
        for key, value in data.items():
            if is_sensitive(key):
                masked[key] = cls.MASKED_VALUE
            elif isinstance(value, (dict, list)):
                masked[key] = cls._mask_recursive(value, is_sensitive)
            else:
                masked[key] = value
        return masked

    @classmethod
    def _sensitive_set_for_explicit_config(cls, config_path: str, cfg: dict) -> Set[str]:
        merge = bool(cfg.get("mergeWithHardcodedDefaults", True))
        sens: Set[str] = set()
        if merge:
            sens.update(cls._hardcoded_sensitive_fields)
        try:
            for field in get_sensitive_fields_array(config_path):
                if isinstance(field, str):
                    sens.add(cls._normalize_field_name(field))
        except Exception:
            pass
        if not merge and not sens:
            sens = set(cls._hardcoded_sensitive_fields)
        return sens

    @classmethod
    def mask_sensitive_data(cls, data: Any, *, config_path: Optional[str] = None) -> Any:
        """Mask sensitive data in objects, arrays, or primitives.

        Returns a masked copy without modifying the original.

        Args:
            data: Data to mask (dict, list, or primitive).
            config_path: Optional path to a sensitive-fields JSON file. When set, masking
                uses that file only for this call (does not change global cache). When
                omitted, uses the global config (env ``MISO_SENSITIVE_FIELDS_CONFIG`` or
                packaged default).

        """
        if config_path is None:
            return cls._mask_recursive(data, cls.is_sensitive_field)

        path = Path(config_path)
        if not path.is_file():
            return cls.mask_sensitive_data(data, config_path=None)

        cfg = load_sensitive_fields_config(config_path)
        sens = cls._sensitive_set_for_explicit_config(config_path, cfg)
        never = cls._never_mask_from_cfg(cfg)
        substr_min = cls._substr_min_from_cfg(cfg)

        def is_sens(k: str) -> bool:
            return cls._key_is_sensitive(k, sens, never, substr_min)

        return cls._mask_recursive(data, is_sens)

    @classmethod
    def mask_value(cls, value: str, show_first: int = 0, show_last: int = 0) -> str:
        """Mask specific value (useful for masking individual strings)."""
        if not value or len(value) <= show_first + show_last:
            return cls.MASKED_VALUE

        first = value[:show_first] if show_first > 0 else ""
        last = value[-show_last:] if show_last > 0 else ""
        masked_length = max(8, len(value) - show_first - show_last)
        masked = "*" * masked_length

        return f"{first}{masked}{last}"

    @classmethod
    def contains_sensitive_data(cls, data: Any) -> bool:
        """Check if data contains sensitive information."""
        if data is None or not isinstance(data, (dict, list)):
            return False

        if isinstance(data, list):
            return any(cls.contains_sensitive_data(item) for item in data)

        for key, value in data.items():
            if cls.is_sensitive_field(key):
                return True
            if isinstance(value, (dict, list)):
                if cls.contains_sensitive_data(value):
                    return True

        return False
