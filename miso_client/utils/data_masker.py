"""
Data masker utility for client-side sensitive data protection.

Implements ISO 27001 data protection controls by masking sensitive fields
in log entries and context data.
"""

from typing import Any, Set


class DataMasker:
    """Static class for masking sensitive data."""
    
    MASKED_VALUE = "***MASKED***"
    
    # Set of sensitive field names (normalized)
    _sensitive_fields: Set[str] = {
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
        
        # Check exact match
        if normalized_key in cls._sensitive_fields:
            return True
        
        # Check if field contains sensitive keywords
        for sensitive_field in cls._sensitive_fields:
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

