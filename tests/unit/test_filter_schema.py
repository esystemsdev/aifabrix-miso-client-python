"""
Unit tests for filter schema validation and utilities.

This module contains comprehensive tests for filter schema validation,
type coercion, SQL compilation, and error handling.
"""

import uuid
from datetime import datetime

from miso_client.models.filter import FilterOption
from miso_client.models.filter_schema import (
    FilterError,
    FilterFieldDefinition,
    FilterSchema,
)
from miso_client.utils.filter_schema import (
    coerce_value,
    compile_filter,
    parse_json_filter,
    validate_filter,
)


class TestFilterSchemaModels:
    """Test cases for filter schema models."""

    def test_filter_field_definition_creation(self):
        """Test creating FilterFieldDefinition."""
        field_def = FilterFieldDefinition(
            column="name", type="string", operators=["eq", "ilike"]
        )

        assert field_def.column == "name"
        assert field_def.type == "string"
        assert field_def.operators == ["eq", "ilike"]
        assert field_def.enum is None

    def test_filter_field_definition_with_enum(self):
        """Test creating FilterFieldDefinition with enum."""
        field_def = FilterFieldDefinition(
            column="status",
            type="enum",
            operators=["eq", "in"],
            enum=["active", "disabled"],
        )

        assert field_def.type == "enum"
        assert field_def.enum == ["active", "disabled"]

    def test_filter_schema_creation(self):
        """Test creating FilterSchema."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq", "ilike"]
                )
            },
        )

        assert schema.resource == "applications"
        assert "name" in schema.fields
        assert schema.fields["name"].type == "string"


class TestValidateFilter:
    """Test cases for validate_filter function."""

    def test_validate_filter_success(self):
        """Test successful filter validation."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq", "ilike"]
                )
            },
        )
        filter_opt = FilterOption(field="name", op="eq", value="test")

        is_valid, error = validate_filter(filter_opt, schema)

        assert is_valid is True
        assert error is None

    def test_validate_filter_unknown_field(self):
        """Test validation with unknown field."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                )
            },
        )
        filter_opt = FilterOption(field="unknown", op="eq", value="test")

        is_valid, error = validate_filter(filter_opt, schema)

        assert is_valid is False
        assert error is not None
        assert error.type == "/Errors/FilterValidation/UnknownField"
        assert error.statusCode == 400
        assert "unknown" in error.errors[0].lower()

    def test_validate_filter_invalid_operator(self):
        """Test validation with invalid operator."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                )
            },
        )
        filter_opt = FilterOption(field="name", op="ilike", value="test")

        is_valid, error = validate_filter(filter_opt, schema)

        assert is_valid is False
        assert error is not None
        assert error.type == "/Errors/FilterValidation/InvalidOperator"
        assert error.statusCode == 400

    def test_validate_filter_isnull_operator(self):
        """Test validation with isNull operator (no value needed)."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "deleted_at": FilterFieldDefinition(
                    column="deleted_at", type="timestamp", operators=["isNull"]
                )
            },
        )
        filter_opt = FilterOption(field="deleted_at", op="isNull", value=None)

        is_valid, error = validate_filter(filter_opt, schema)

        assert is_valid is True
        assert error is None


class TestCoerceValue:
    """Test cases for coerce_value function."""

    def test_coerce_string(self):
        """Test coercing string value."""
        field_def = FilterFieldDefinition(
            column="name", type="string", operators=["eq"]
        )

        coerced, error = coerce_value("test", field_def)

        assert coerced == "test"
        assert error is None

    def test_coerce_number_int(self):
        """Test coercing integer value."""
        field_def = FilterFieldDefinition(
            column="age", type="number", operators=["eq"]
        )

        coerced, error = coerce_value("25", field_def)

        assert coerced == 25
        assert isinstance(coerced, int)
        assert error is None

    def test_coerce_number_float(self):
        """Test coercing float value."""
        field_def = FilterFieldDefinition(
            column="price", type="number", operators=["eq"]
        )

        coerced, error = coerce_value("99.99", field_def)

        assert coerced == 99.99
        assert isinstance(coerced, float)
        assert error is None

    def test_coerce_number_invalid(self):
        """Test coercing invalid number."""
        field_def = FilterFieldDefinition(
            column="age", type="number", operators=["eq"]
        )

        coerced, error = coerce_value("not_a_number", field_def)

        assert coerced is None
        assert error is not None
        assert error.type == "/Errors/FilterValidation/InvalidType"
        assert error.statusCode == 400

    def test_coerce_boolean_true(self):
        """Test coercing boolean true."""
        field_def = FilterFieldDefinition(
            column="active", type="boolean", operators=["eq"]
        )

        coerced, error = coerce_value("true", field_def)

        assert coerced is True
        assert error is None

    def test_coerce_boolean_false(self):
        """Test coercing boolean false."""
        field_def = FilterFieldDefinition(
            column="active", type="boolean", operators=["eq"]
        )

        coerced, error = coerce_value("false", field_def)

        assert coerced is False
        assert error is None

    def test_coerce_boolean_invalid(self):
        """Test coercing invalid boolean."""
        field_def = FilterFieldDefinition(
            column="active", type="boolean", operators=["eq"]
        )

        coerced, error = coerce_value("maybe", field_def)

        assert coerced is None
        assert error is not None
        assert error.type == "/Errors/FilterValidation/InvalidType"

    def test_coerce_uuid_valid(self):
        """Test coercing valid UUID."""
        field_def = FilterFieldDefinition(
            column="id", type="uuid", operators=["eq"]
        )
        test_uuid = str(uuid.uuid4())

        coerced, error = coerce_value(test_uuid, field_def)

        assert coerced == test_uuid
        assert error is None

    def test_coerce_uuid_invalid(self):
        """Test coercing invalid UUID."""
        field_def = FilterFieldDefinition(
            column="id", type="uuid", operators=["eq"]
        )

        coerced, error = coerce_value("not-a-uuid", field_def)

        assert coerced is None
        assert error is not None
        assert error.type == "/Errors/FilterValidation/InvalidUuid"
        assert error.statusCode == 400

    def test_coerce_timestamp_valid(self):
        """Test coercing valid timestamp."""
        field_def = FilterFieldDefinition(
            column="created_at", type="timestamp", operators=["eq"]
        )
        timestamp_str = "2024-01-01T12:00:00"

        coerced, error = coerce_value(timestamp_str, field_def)

        assert coerced == timestamp_str
        assert error is None

    def test_coerce_timestamp_datetime_object(self):
        """Test coercing datetime object."""
        field_def = FilterFieldDefinition(
            column="created_at", type="timestamp", operators=["eq"]
        )
        dt = datetime(2024, 1, 1, 12, 0, 0)

        coerced, error = coerce_value(dt, field_def)

        assert isinstance(coerced, str)
        assert "2024-01-01" in coerced
        assert error is None

    def test_coerce_timestamp_invalid(self):
        """Test coercing invalid timestamp."""
        field_def = FilterFieldDefinition(
            column="created_at", type="timestamp", operators=["eq"]
        )

        coerced, error = coerce_value("not-a-date", field_def)

        assert coerced is None
        assert error is not None
        assert error.type == "/Errors/FilterValidation/InvalidDate"
        assert error.statusCode == 400

    def test_coerce_enum_valid(self):
        """Test coercing valid enum value."""
        field_def = FilterFieldDefinition(
            column="status",
            type="enum",
            operators=["eq"],
            enum=["active", "disabled"],
        )

        coerced, error = coerce_value("active", field_def)

        assert coerced == "active"
        assert error is None

    def test_coerce_enum_invalid(self):
        """Test coercing invalid enum value."""
        field_def = FilterFieldDefinition(
            column="status",
            type="enum",
            operators=["eq"],
            enum=["active", "disabled"],
        )

        coerced, error = coerce_value("pending", field_def)

        assert coerced is None
        assert error is not None
        assert error.type == "/Errors/FilterValidation/InvalidEnum"
        assert error.statusCode == 400

    def test_coerce_enum_missing_definition(self):
        """Test coercing enum without enum values defined."""
        field_def = FilterFieldDefinition(
            column="status", type="enum", operators=["eq"], enum=None
        )

        coerced, error = coerce_value("active", field_def)

        assert coerced is None
        assert error is not None
        assert error.type == "/Errors/FilterValidation/InvalidEnum"

    def test_coerce_list_values(self):
        """Test coercing list values (for 'in' operator)."""
        field_def = FilterFieldDefinition(
            column="status",
            type="enum",
            operators=["in"],
            enum=["active", "disabled"],
        )

        coerced, error = coerce_value(["active", "disabled"], field_def)

        assert coerced == ["active", "disabled"]
        assert error is None

    def test_coerce_list_with_invalid_value(self):
        """Test coercing list with invalid value."""
        field_def = FilterFieldDefinition(
            column="status",
            type="enum",
            operators=["in"],
            enum=["active", "disabled"],
        )

        coerced, error = coerce_value(["active", "invalid"], field_def)

        assert coerced is None
        assert error is not None
        assert error.type == "/Errors/FilterValidation/InvalidEnum"


class TestCompileFilter:
    """Test cases for compile_filter function."""

    def test_compile_eq_operator(self):
        """Test compiling eq operator."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                )
            },
        )
        filter_opt = FilterOption(field="name", op="eq", value="test")

        compiled = compile_filter(filter_opt, schema)

        assert compiled.sql == "name = $1"
        assert compiled.params == ["test"]
        assert compiled.param_index == 2

    def test_compile_ilike_operator(self):
        """Test compiling ilike operator."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["ilike"]
                )
            },
        )
        filter_opt = FilterOption(field="name", op="ilike", value="test")

        compiled = compile_filter(filter_opt, schema)

        assert compiled.sql == "name ILIKE $1"
        assert compiled.params == ["test"]

    def test_compile_in_operator(self):
        """Test compiling in operator."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "status": FilterFieldDefinition(
                    column="status", type="string", operators=["in"]
                )
            },
        )
        filter_opt = FilterOption(field="status", op="in", value=["active", "disabled"])

        compiled = compile_filter(filter_opt, schema)

        assert compiled.sql == "status = ANY($1)"
        assert compiled.params == [["active", "disabled"]]

    def test_compile_isnull_operator(self):
        """Test compiling isNull operator."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "deleted_at": FilterFieldDefinition(
                    column="deleted_at", type="timestamp", operators=["isNull"]
                )
            },
        )
        filter_opt = FilterOption(field="deleted_at", op="isNull", value=None)

        compiled = compile_filter(filter_opt, schema)

        assert compiled.sql == "deleted_at IS NULL"
        assert compiled.params == []

    def test_compile_contains_operator(self):
        """Test compiling contains operator (adds %%)."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["contains"]
                )
            },
        )
        filter_opt = FilterOption(field="name", op="contains", value="test")

        compiled = compile_filter(filter_opt, schema)

        assert compiled.sql == "name ILIKE $1"
        assert compiled.params == ["%test%"]

    def test_compile_with_custom_param_index(self):
        """Test compiling with custom parameter index."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                )
            },
        )
        filter_opt = FilterOption(field="name", op="eq", value="test")

        compiled = compile_filter(filter_opt, schema, param_index=5)

        assert compiled.sql == "name = $5"
        assert compiled.params == ["test"]
        assert compiled.param_index == 6


class TestParseJsonFilter:
    """Test cases for parse_json_filter function."""

    def test_parse_nested_json_format(self):
        """Test parsing nested JSON format."""
        json_data = {"status": {"eq": "active"}, "name": {"ilike": "test"}}

        filters = parse_json_filter(json_data)

        assert len(filters) == 2
        assert filters[0].field == "status"
        assert filters[0].op == "eq"
        assert filters[0].value == "active"
        assert filters[1].field == "name"
        assert filters[1].op == "ilike"
        assert filters[1].value == "test"

    def test_parse_flat_json_format(self):
        """Test parsing flat JSON format (defaults to eq)."""
        json_data = {"status": "active", "name": "test"}

        filters = parse_json_filter(json_data)

        assert len(filters) == 2
        assert filters[0].field == "status"
        assert filters[0].op == "eq"
        assert filters[0].value == "active"
        assert filters[1].field == "name"
        assert filters[1].op == "eq"
        assert filters[1].value == "test"

    def test_parse_mixed_format(self):
        """Test parsing mixed nested and flat format."""
        json_data = {"status": {"eq": "active"}, "name": "test"}

        filters = parse_json_filter(json_data)

        assert len(filters) == 2
        assert filters[0].op == "eq"
        assert filters[1].op == "eq"


class TestFilterErrorRFC7807:
    """Test cases for RFC 7807 compliant FilterError."""

    def test_filter_error_structure(self):
        """Test FilterError follows RFC 7807 structure."""
        error = FilterError(
            type="/Errors/FilterValidation/UnknownField",
            title="Unknown Field",
            statusCode=400,
            errors=["Field 'unknown' is not filterable"],
            instance="/api/applications",
            correlationId="req-123",
        )

        assert error.type == "/Errors/FilterValidation/UnknownField"
        assert error.title == "Unknown Field"
        assert error.statusCode == 400
        assert len(error.errors) == 1
        assert error.instance == "/api/applications"
        assert error.correlationId == "req-123"

    def test_filter_error_camelcase_fields(self):
        """Test FilterError uses camelCase fields."""
        error = FilterError(
            type="/Errors/Test",
            statusCode=400,
            errors=["Test error"],
        )

        # Verify camelCase fields exist
        assert hasattr(error, "statusCode")
        assert hasattr(error, "correlationId")
        assert error.statusCode == 400


class TestMetadataFields:
    """Test cases for new metadata fields (TypeScript parity)."""

    def test_filter_field_definition_with_nullable(self):
        """Test FilterFieldDefinition with nullable field."""
        field_def = FilterFieldDefinition(
            column="deleted_at",
            type="timestamp",
            operators=["isNull", "isNotNull"],
            nullable=True,
        )

        assert field_def.nullable is True

    def test_filter_field_definition_with_description(self):
        """Test FilterFieldDefinition with description field."""
        field_def = FilterFieldDefinition(
            column="name",
            type="string",
            operators=["eq", "ilike"],
            description="Application name for filtering",
        )

        assert field_def.description == "Application name for filtering"

    def test_filter_field_definition_with_all_metadata(self):
        """Test FilterFieldDefinition with all metadata fields."""
        field_def = FilterFieldDefinition(
            column="status",
            type="enum",
            operators=["eq", "in"],
            enum=["active", "disabled"],
            nullable=False,
            description="Application status",
        )

        assert field_def.nullable is False
        assert field_def.description == "Application status"
        assert field_def.enum == ["active", "disabled"]

    def test_filter_schema_with_version(self):
        """Test FilterSchema with version field."""
        schema = FilterSchema(
            resource="applications",
            version="1.0",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                )
            },
        )

        assert schema.version == "1.0"
        assert schema.resource == "applications"

    def test_filter_schema_without_version(self):
        """Test FilterSchema without version (defaults to None)."""
        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                )
            },
        )

        assert schema.version is None


class TestValidateFilters:
    """Test cases for validate_filters batch function."""

    def test_validate_filters_all_valid(self):
        """Test validating multiple valid filters."""
        from miso_client.utils.filter_schema import validate_filters

        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq", "ilike"]
                ),
                "status": FilterFieldDefinition(
                    column="status",
                    type="enum",
                    operators=["eq", "in"],
                    enum=["active", "disabled"],
                ),
            },
        )
        filters = [
            FilterOption(field="name", op="eq", value="test"),
            FilterOption(field="status", op="eq", value="active"),
        ]

        is_valid, errors = validate_filters(filters, schema)

        assert is_valid is True
        assert errors == []

    def test_validate_filters_with_errors(self):
        """Test validating filters with multiple errors."""
        from miso_client.utils.filter_schema import validate_filters

        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                ),
            },
        )
        filters = [
            FilterOption(field="name", op="eq", value="test"),  # valid
            FilterOption(field="unknown", op="eq", value="bad"),  # invalid field
            FilterOption(field="name", op="ilike", value="test"),  # invalid operator
        ]

        is_valid, errors = validate_filters(filters, schema)

        assert is_valid is False
        assert len(errors) == 2

    def test_validate_filters_empty_list(self):
        """Test validating empty filter list."""
        from miso_client.utils.filter_schema import validate_filters

        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                ),
            },
        )

        is_valid, errors = validate_filters([], schema)

        assert is_valid is True
        assert errors == []


class TestCompileFilters:
    """Test cases for compile_filters batch function."""

    def test_compile_filters_with_and(self):
        """Test compiling multiple filters with AND logic."""
        from miso_client.utils.filter_schema import compile_filters

        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                ),
                "status": FilterFieldDefinition(
                    column="status", type="string", operators=["eq"]
                ),
            },
        )
        filters = [
            FilterOption(field="name", op="eq", value="test"),
            FilterOption(field="status", op="eq", value="active"),
        ]

        compiled = compile_filters(filters, schema)

        assert compiled.sql == "name = $1 AND status = $2"
        assert compiled.params == ["test", "active"]
        assert compiled.param_index == 3

    def test_compile_filters_with_or(self):
        """Test compiling multiple filters with OR logic."""
        from miso_client.utils.filter_schema import compile_filters

        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                ),
                "status": FilterFieldDefinition(
                    column="status", type="string", operators=["eq"]
                ),
            },
        )
        filters = [
            FilterOption(field="name", op="eq", value="test"),
            FilterOption(field="status", op="eq", value="active"),
        ]

        compiled = compile_filters(filters, schema, logic="or")

        assert compiled.sql == "name = $1 OR status = $2"
        assert compiled.params == ["test", "active"]

    def test_compile_filters_empty_list(self):
        """Test compiling empty filter list."""
        from miso_client.utils.filter_schema import compile_filters

        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                ),
            },
        )

        compiled = compile_filters([], schema)

        assert compiled.sql == ""
        assert compiled.params == []
        assert compiled.param_index == 1

    def test_compile_filters_single_filter(self):
        """Test compiling single filter."""
        from miso_client.utils.filter_schema import compile_filters

        schema = FilterSchema(
            resource="applications",
            fields={
                "name": FilterFieldDefinition(
                    column="name", type="string", operators=["eq"]
                ),
            },
        )
        filters = [FilterOption(field="name", op="eq", value="test")]

        compiled = compile_filters(filters, schema)

        assert compiled.sql == "name = $1"
        assert compiled.params == ["test"]


class TestCreateFilterSchema:
    """Test cases for create_filter_schema helper function."""

    def test_create_filter_schema_with_defaults(self):
        """Test creating schema with default operators."""
        from miso_client.utils.filter_schema import create_filter_schema

        schema = create_filter_schema(
            resource="applications",
            fields={
                "name": {"column": "name", "type": "string"},
                "age": {"column": "age", "type": "number"},
            },
        )

        assert schema.resource == "applications"
        assert "eq" in schema.fields["name"].operators
        assert "ilike" in schema.fields["name"].operators
        assert "gt" in schema.fields["age"].operators
        assert "lte" in schema.fields["age"].operators

    def test_create_filter_schema_with_custom_operators(self):
        """Test creating schema with custom operators."""
        from miso_client.utils.filter_schema import create_filter_schema

        schema = create_filter_schema(
            resource="applications",
            fields={
                "name": {"column": "name", "type": "string", "operators": ["eq"]},
            },
        )

        assert schema.fields["name"].operators == ["eq"]

    def test_create_filter_schema_with_version(self):
        """Test creating schema with version."""
        from miso_client.utils.filter_schema import create_filter_schema

        schema = create_filter_schema(
            resource="applications",
            fields={
                "name": {"column": "name", "type": "string"},
            },
            version="2.0",
        )

        assert schema.version == "2.0"

    def test_create_filter_schema_with_enum(self):
        """Test creating schema with enum field."""
        from miso_client.utils.filter_schema import create_filter_schema

        schema = create_filter_schema(
            resource="applications",
            fields={
                "status": {
                    "column": "status",
                    "type": "enum",
                    "enum": ["active", "disabled"],
                },
            },
        )

        assert schema.fields["status"].type == "enum"
        assert schema.fields["status"].enum == ["active", "disabled"]
        assert "eq" in schema.fields["status"].operators
        assert "in" in schema.fields["status"].operators

    def test_create_filter_schema_with_metadata(self):
        """Test creating schema with metadata fields."""
        from miso_client.utils.filter_schema import create_filter_schema

        schema = create_filter_schema(
            resource="applications",
            fields={
                "deleted_at": {
                    "column": "deleted_at",
                    "type": "timestamp",
                    "nullable": True,
                    "description": "Soft delete timestamp",
                },
            },
        )

        assert schema.fields["deleted_at"].nullable is True
        assert schema.fields["deleted_at"].description == "Soft delete timestamp"


class TestDefaultOperatorsByType:
    """Test cases for DEFAULT_OPERATORS_BY_TYPE constant."""

    def test_default_operators_exist(self):
        """Test that DEFAULT_OPERATORS_BY_TYPE constant exists."""
        from miso_client.utils.filter_schema import DEFAULT_OPERATORS_BY_TYPE

        assert "string" in DEFAULT_OPERATORS_BY_TYPE
        assert "number" in DEFAULT_OPERATORS_BY_TYPE
        assert "boolean" in DEFAULT_OPERATORS_BY_TYPE
        assert "uuid" in DEFAULT_OPERATORS_BY_TYPE
        assert "timestamp" in DEFAULT_OPERATORS_BY_TYPE
        assert "enum" in DEFAULT_OPERATORS_BY_TYPE

    def test_string_operators(self):
        """Test default operators for string type."""
        from miso_client.utils.filter_schema import DEFAULT_OPERATORS_BY_TYPE

        string_ops = DEFAULT_OPERATORS_BY_TYPE["string"]
        assert "eq" in string_ops
        assert "neq" in string_ops
        assert "ilike" in string_ops
        assert "contains" in string_ops

    def test_number_operators(self):
        """Test default operators for number type."""
        from miso_client.utils.filter_schema import DEFAULT_OPERATORS_BY_TYPE

        number_ops = DEFAULT_OPERATORS_BY_TYPE["number"]
        assert "eq" in number_ops
        assert "gt" in number_ops
        assert "gte" in number_ops
        assert "lt" in number_ops
        assert "lte" in number_ops

    def test_boolean_operators(self):
        """Test default operators for boolean type."""
        from miso_client.utils.filter_schema import DEFAULT_OPERATORS_BY_TYPE

        boolean_ops = DEFAULT_OPERATORS_BY_TYPE["boolean"]
        assert boolean_ops == ["eq"]

    def test_uuid_operators(self):
        """Test default operators for uuid type."""
        from miso_client.utils.filter_schema import DEFAULT_OPERATORS_BY_TYPE

        uuid_ops = DEFAULT_OPERATORS_BY_TYPE["uuid"]
        assert "eq" in uuid_ops
        assert "in" in uuid_ops

    def test_timestamp_operators(self):
        """Test default operators for timestamp type."""
        from miso_client.utils.filter_schema import DEFAULT_OPERATORS_BY_TYPE

        timestamp_ops = DEFAULT_OPERATORS_BY_TYPE["timestamp"]
        assert "eq" in timestamp_ops
        assert "gt" in timestamp_ops
        assert "lte" in timestamp_ops

    def test_enum_operators(self):
        """Test default operators for enum type."""
        from miso_client.utils.filter_schema import DEFAULT_OPERATORS_BY_TYPE

        enum_ops = DEFAULT_OPERATORS_BY_TYPE["enum"]
        assert "eq" in enum_ops
        assert "in" in enum_ops
