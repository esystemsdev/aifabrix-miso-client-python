"""
Unit tests for logging_helpers module.
"""

from typing import Optional

from miso_client.utils.logging_helpers import extract_logging_context


class MockHasKey:
    """Mock object with key and displayName."""

    def __init__(self, key: str, display_name: Optional[str] = None):
        self.key = key
        self.displayName = display_name


class MockHasExternalSystem:
    """Mock object with key, displayName, and optional externalSystem."""

    def __init__(
        self,
        key: str,
        display_name: Optional[str] = None,
        external_system: Optional[MockHasKey] = None,
    ):
        self.key = key
        self.displayName = display_name
        self.externalSystem = external_system


class TestExtractLoggingContext:
    """Test cases for extract_logging_context function."""

    def test_extract_with_source_only(self):
        """Test extracting context with source only."""
        source = MockHasExternalSystem("source-key", "Source Display Name")
        result = extract_logging_context(source=source)

        assert result["sourceKey"] == "source-key"
        assert result["sourceDisplayName"] == "Source Display Name"
        assert "externalSystemKey" not in result
        assert "recordKey" not in result

    def test_extract_with_source_and_external_system(self):
        """Test extracting context with source and external system."""
        external_system = MockHasKey("system-key", "System Display Name")
        source = MockHasExternalSystem(
            "source-key", "Source Display Name", external_system=external_system
        )
        result = extract_logging_context(source=source)

        assert result["sourceKey"] == "source-key"
        assert result["sourceDisplayName"] == "Source Display Name"
        assert result["externalSystemKey"] == "system-key"
        assert result["externalSystemDisplayName"] == "System Display Name"
        assert "recordKey" not in result

    def test_extract_with_record_only(self):
        """Test extracting context with record only."""
        record = MockHasKey("record-key", "Record Display Name")
        result = extract_logging_context(record=record)

        assert result["recordKey"] == "record-key"
        assert result["recordDisplayName"] == "Record Display Name"
        assert "sourceKey" not in result
        assert "externalSystemKey" not in result

    def test_extract_with_external_system_only(self):
        """Test extracting context with external system only."""
        external_system = MockHasKey("system-key", "System Display Name")
        result = extract_logging_context(external_system=external_system)

        assert result["externalSystemKey"] == "system-key"
        assert result["externalSystemDisplayName"] == "System Display Name"
        assert "sourceKey" not in result
        assert "recordKey" not in result

    def test_extract_with_all_parameters(self):
        """Test extracting context with all parameters."""
        external_system = MockHasKey("system-key", "System Display Name")
        source = MockHasExternalSystem(
            "source-key", "Source Display Name", external_system=external_system
        )
        record = MockHasKey("record-key", "Record Display Name")
        result = extract_logging_context(
            source=source, record=record, external_system=external_system
        )

        assert result["sourceKey"] == "source-key"
        assert result["sourceDisplayName"] == "Source Display Name"
        assert result["externalSystemKey"] == "system-key"
        assert result["externalSystemDisplayName"] == "System Display Name"
        assert result["recordKey"] == "record-key"
        assert result["recordDisplayName"] == "Record Display Name"

    def test_extract_without_display_names(self):
        """Test extracting context without display names."""
        source = MockHasExternalSystem("source-key")
        record = MockHasKey("record-key")
        result = extract_logging_context(source=source, record=record)

        assert result["sourceKey"] == "source-key"
        assert "sourceDisplayName" not in result
        assert result["recordKey"] == "record-key"
        assert "recordDisplayName" not in result

    def test_extract_with_none_values(self):
        """Test extracting context with None values."""
        result = extract_logging_context()

        assert result == {}

    def test_extract_external_system_overrides_source_external_system(self):
        """Test that explicit external_system parameter overrides source.externalSystem."""
        source_external_system = MockHasKey("source-system-key", "Source System")
        source = MockHasExternalSystem(
            "source-key", "Source", external_system=source_external_system
        )
        explicit_external_system = MockHasKey("explicit-system-key", "Explicit System")
        result = extract_logging_context(source=source, external_system=explicit_external_system)

        # Explicit external_system should override source.externalSystem
        assert result["externalSystemKey"] == "explicit-system-key"
        assert result["externalSystemDisplayName"] == "Explicit System"
        assert result["sourceKey"] == "source-key"

    def test_extract_with_empty_strings(self):
        """Test extracting context handles empty strings correctly."""
        source = MockHasExternalSystem("source-key", "")
        record = MockHasKey("record-key", "")
        result = extract_logging_context(source=source, record=record)

        # Empty strings should be treated as falsy and not included
        assert result["sourceKey"] == "source-key"
        assert "sourceDisplayName" not in result
        assert result["recordKey"] == "record-key"
        assert "recordDisplayName" not in result
