"""MisoClient SDK - Python client for AI Fabrix authentication, authorization, and logging.

This package provides a reusable client SDK for integrating with the Miso Controller
for authentication, role-based access control, permission management, and logging.
"""

# Core client
from .client import MisoClient

# Errors
from .errors import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError,
    ConnectionError,
    EncryptionError,
    MisoClientError,
)

# Config models
from .models.config import (
    AuthMethod,
    AuthResult,
    AuthStrategy,
    CircuitBreakerConfig,
    ClientLoggingOptions,
    ClientTokenEndpointOptions,
    ClientTokenEndpointResponse,
    ClientTokenResponse,
    DataClientConfigResponse,
    LogEntry,
    MisoClientConfig,
    PermissionResult,
    RedisConfig,
    RoleResult,
    UserInfo,
)

# Encryption models
from .models.encryption import EncryptResult, StorageType

# Error response models
from .models.error_response import ErrorResponse

# Filter models
from .models.filter import (
    FilterBuilder,
    FilterGroup,
    FilterOperator,
    FilterOption,
    FilterQuery,
    JsonFilter,
)

# Filter schema models
from .models.filter_schema import (
    CompiledFilter,
    FilterError,
    FilterFieldDefinition,
    FilterSchema,
)

# Pagination models
from .models.pagination import Meta, PaginatedListResponse

# Sort models
from .models.sort import SortOption

# Services
from .services.auth import AuthService
from .services.cache import CacheService
from .services.encryption import EncryptionService
from .services.logger import LoggerService
from .services.logger_chain import LoggerChain
from .services.permission import PermissionService
from .services.redis import RedisService
from .services.role import RoleService
from .services.unified_logger import UnifiedLogger

# Utilities
from .utils.audit_log_queue import AuditLogQueue
from .utils.config_loader import load_config
from .utils.controller_url_resolver import is_browser, resolve_controller_url
from .utils.environment_token import get_environment_token
from .utils.error_utils import ApiErrorException, handleApiError, transformError
from .utils.http_error_handler import detect_auth_method_from_headers
from .utils.fastapi_endpoints import create_fastapi_client_token_endpoint
from .utils.fastapi_logger_middleware import (
    logger_context_middleware as fastapi_logger_context_middleware,
)
from .utils.filter import (
    apply_filters,
    build_query_string,
    coerce_filter_value,
    filter_query_to_json,
    json_filter_to_query_string,
    json_to_filter_query,
    parse_filter_params,
    query_string_to_json_filter,
    validate_filter_option,
    validate_filter_with_schema,
    validate_json_filter,
)
from .utils.filter_schema import (
    DEFAULT_OPERATORS_BY_TYPE,
    coerce_value,
    compile_filter,
    compile_filters,
    create_filter_schema,
    parse_json_filter,
    validate_filter,
    validate_filters,
)
from .utils.flask_endpoints import create_flask_client_token_endpoint
from .utils.flask_logger_middleware import (
    logger_context_middleware as flask_logger_context_middleware,
)
from .utils.flask_logger_middleware import (
    register_logger_context_middleware,
)
from .utils.http_client import HttpClient
from .utils.jwt_tools import extract_user_id
from .utils.logging_helpers import extract_logging_context
from .utils.origin_validator import validate_origin
from .utils.pagination import (
    applyPaginationToArray,
    createMetaObject,
    createPaginatedListResponse,
    parse_pagination_params,
    parsePaginationParams,
)
from .utils.request_context import RequestContext, extract_request_context
from .utils.sort import build_sort_string, parse_sort_params
from .utils.token_utils import extract_client_token_info
from .utils.unified_logger_factory import clear_logger_context, get_logger, set_logger_context
from .utils.url_validator import validate_url

__version__ = "4.2.0"
__author__ = "AI Fabrix Team"
__license__ = "MIT"


# Export types
# Export types
__all__ = [
    # Core
    "MisoClient",
    # Config models
    "RedisConfig",
    "MisoClientConfig",
    "UserInfo",
    "AuthResult",
    "AuthStrategy",
    "AuthMethod",
    "LogEntry",
    "RoleResult",
    "PermissionResult",
    "ClientTokenResponse",
    "ClientTokenEndpointResponse",
    "ClientTokenEndpointOptions",
    "DataClientConfigResponse",
    "CircuitBreakerConfig",
    "ClientLoggingOptions",
    # Error models
    "ErrorResponse",
    # Encryption models
    "EncryptResult",
    "StorageType",
    # Pagination models
    "Meta",
    "PaginatedListResponse",
    # Filter models
    "FilterOperator",
    "FilterOption",
    "FilterQuery",
    "FilterBuilder",
    "JsonFilter",
    "FilterGroup",
    # Filter schema models
    "FilterSchema",
    "FilterFieldDefinition",
    "FilterError",
    "CompiledFilter",
    # Sort models
    "SortOption",
    # Pagination utilities
    "parsePaginationParams",
    "parse_pagination_params",
    "createMetaObject",
    "applyPaginationToArray",
    "createPaginatedListResponse",
    # Filter utilities
    "parse_filter_params",
    "build_query_string",
    "apply_filters",
    "filter_query_to_json",
    "json_to_filter_query",
    "json_filter_to_query_string",
    "query_string_to_json_filter",
    "validate_filter_option",
    "validate_json_filter",
    "validate_filter_with_schema",
    "coerce_filter_value",
    # Filter schema utilities
    "validate_filter",
    "validate_filters",
    "coerce_value",
    "compile_filter",
    "compile_filters",
    "parse_json_filter",
    "create_filter_schema",
    "DEFAULT_OPERATORS_BY_TYPE",
    # Sort utilities
    "parse_sort_params",
    "build_sort_string",
    # Error utilities
    "transformError",
    "handleApiError",
    "ApiErrorException",
    "detect_auth_method_from_headers",
    # Services
    "AuthService",
    "RoleService",
    "PermissionService",
    "LoggerService",
    "LoggerChain",
    "UnifiedLogger",
    "RedisService",
    "EncryptionService",
    "CacheService",
    "HttpClient",
    "AuditLogQueue",
    # Errors
    "load_config",
    "MisoClientError",
    "AuthenticationError",
    "AuthorizationError",
    "ConnectionError",
    "ConfigurationError",
    "EncryptionError",
    # Server-side utilities
    "get_environment_token",
    "validate_origin",
    "extract_client_token_info",
    "validate_url",
    "resolve_controller_url",
    "is_browser",
    "create_flask_client_token_endpoint",
    "create_fastapi_client_token_endpoint",
    # Request context utilities
    "extract_request_context",
    "RequestContext",
    # JWT utilities
    "extract_user_id",
    # Logging utilities
    "extract_logging_context",
    "get_logger",
    "set_logger_context",
    "clear_logger_context",
    "fastapi_logger_context_middleware",
    "flask_logger_context_middleware",
    "register_logger_context_middleware",
]
