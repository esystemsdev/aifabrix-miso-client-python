# AI Fabrix Miso Client SDK (Python)

[![PyPI version](https://badge.fury.io/py/miso-client.svg)](https://badge.fury.io/py/miso-client)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

The **AI Fabrix Miso Client SDK** provides authentication, authorization, and logging for Python applications integrated with the AI Fabrix platform.

## ✨ Benefits

### 🔐 Enterprise Security

### **SSO and Federated Identity**

- Single Sign-On (SSO) with Keycloak
- OAuth 2.0 and OpenID Connect (OIDC) support
- Multi-factor authentication (MFA) ready
- Social login integration (Google, Microsoft, etc.)

### **Centralized Access Control**

- Role-based access control (RBAC)
- Fine-grained permissions
- Dynamic policy enforcement
- Attribute-based access control (ABAC)

### **API Security**

- JWT token validation
- API key authentication
- Token revocation support
- Secure token storage
- Data encryption/decryption (AES-256-GCM)

### 📊 Compliance & Audit

### **ISO 27001 Compliance**

- Comprehensive audit trails for all user actions and HTTP requests
- Automatic data masking for all sensitive information in logs
- HTTP request/response audit logging with masked sensitive data
- Data access logging and monitoring
- Security event tracking
- Accountability and non-repudiation
- Configurable sensitive fields via JSON configuration

### **Regulatory Compliance**

- GDPR-ready data protection
- HIPAA-compliant audit logging
- SOC 2 audit trail requirements
- Industry-standard security controls

### **Audit Capabilities**

- Real-time audit event logging
- Immutable audit records
- Forensic analysis support
- Compliance reporting automation

### ⚡ Performance & Scalability

### **Intelligent Caching**

- Redis-based role and permission caching
- Generic cache service with Redis and in-memory fallback
- Configurable cache TTL (default: 15 minutes)
- Automatic cache invalidation
- Fallback to controller when Redis unavailable

### **High Availability**

- Automatic failover to controller
- Redundant infrastructure support
- Load balancing compatible
- Zero-downtime deployments

### **Optimized Network**

- Efficient API calls with caching
- Batch operations support
- Connection pooling
- Minimal latency

### 🛠️ Developer Experience

### **Easy Integration**

- Progressive activation (6-step setup)
- Works with any framework (FastAPI, Django, Flask, Starlette)
- Python 3.8+ support with full type hints
- Async/await support throughout

### **Flexible Configuration**

- Environment-based configuration
- Support for dev, test, and production environments
- Docker and Kubernetes ready
- CI/CD friendly

### **Observability**

- Centralized logging with correlation IDs
- Automatic HTTP request/response audit logging (ISO 27001 compliant)
- Debug logging with detailed request/response information (when `log_level='debug'`)
- Performance tracking and metrics
- Error tracking and debugging
- Health monitoring
- Automatic data masking for sensitive information in logs
- Configurable sensitive fields via JSON configuration

---

## 🚀 Quick Start

Get your application secured in 30 seconds.

### Step 1: Install

```bash
pip install miso-client
```

### Step 2: Create `.env`

```bash
MISO_CLIENTID=ctrl-dev-my-app
MISO_CLIENTSECRET=your-secret
MISO_CONTROLLER_URL=http://localhost:3000
REDIS_HOST=localhost
```

### Step 3: Use It

```python
from miso_client import MisoClient, load_config

client = MisoClient(load_config())
await client.initialize()

is_valid = await client.validate_token(token)
```

**That's it!** You now have authentication, roles, and logging.

→ [Full Getting Started Guide](docs/getting-started.md)

---

### Infrastructure Setup

**First time?** You'll need Keycloak and Miso Controller running.

Use the [AI Fabrix Builder](https://github.com/esystemsdev/aifabrix-builder/blob/main/docs/QUICK-START.md):

```bash
# Start infrastructure (Postgres, Redis)
aifabrix up

# Install Keycloak for authentication
aifabrix create keycloak --port 8082 --database --template platform
aifabrix build keycloak
aifabrix run keycloak

# Install Miso Controller
aifabrix create miso-controller --port 3000 --database --redis --template platform
aifabrix build miso-controller
aifabrix run miso-controller
```

→ [Infrastructure Guide](https://github.com/esystemsdev/aifabrix-builder/blob/main/docs/INFRASTRUCTURE.md)

**Already have Keycloak and Controller?** Use the Quick Start above.

---

## 📚 Documentation

**What happens:** Your app validates user tokens from Keycloak.

```python
from miso_client import MisoClient, load_config

# Create client (loads from .env automatically)
client = MisoClient(load_config())
await client.initialize()

# Get token from request (helper method)
token = client.get_token(req)

if token:
    is_valid = await client.validate_token(token)
    if is_valid:
        user = await client.get_user(token)
        print('User:', user)
```

**Where to get tokens?** Users authenticate via Keycloak, then your app receives JWTs in the `Authorization` header.

→ [Complete authentication example](examples/step-3-authentication.py)

---

### Step 4: Activate RBAC (Roles)

**What happens:** Check user roles to control access. Roles are cached in Redis for performance.

```python
from miso_client import MisoClient, load_config

# Build on Step 3 - add Redis in .env file
client = MisoClient(load_config())
await client.initialize()

token = client.get_token(req)

# Check if user has role
is_admin = await client.has_role(token, 'admin')
roles = await client.get_roles(token)

# Gate features by role
if is_admin:
    # Show admin panel
    pass
```

**Pro tip:** Without Redis, checks go to the controller. Add Redis to cache role lookups (15-minute default TTL).

→ [Complete RBAC example](examples/step-4-rbac.py)  
→ [AI Fabrix Builder Quick Start](https://github.com/esystemsdev/aifabrix-builder/blob/main/docs/QUICK-START.md)

---

### Step 5: Activate Logging

**What happens:** Application logs are sent to the Miso Controller with client token authentication. All HTTP requests are automatically audited with ISO 27001 compliant data masking.

```python
from miso_client import MisoClient, load_config

# Client token is automatically managed - no API key needed
client = MisoClient(load_config())
await client.initialize()

token = client.get_token(req)
user = await client.get_user(token)

# Log messages
await client.log.info('User accessed dashboard', {'userId': user.id if user else None})
await client.log.error('Operation failed', {'error': str(err)})
await client.log.warn('Unusual activity', {'details': '...'})

# HTTP requests are automatically audited
# All sensitive data is automatically masked before logging
result = await client.http_client.get('/api/users')
# This automatically creates an audit log: http.request.GET with masked sensitive data
```

**What happens to logs?** They're sent to the Miso Controller for centralized monitoring and analysis. Client token is automatically included. Audit logs are automatically batched using `AuditLogQueue` for improved performance (configurable via `AuditConfig`).

**ISO 27001 Compliance:** All HTTP requests are automatically audited with sensitive data masked. Configure audit logging behavior using `AuditConfig`:

- **Audit Levels**: Choose from `minimal`, `standard`, `detailed`, or `full` (default: `detailed`)
  - `minimal`: Only metadata, no masking
  - `standard`: Metadata + basic context
  - `detailed`: Full context with request/response sizes (default)
  - `full`: Complete audit trail with all available data
- **Performance Optimizations**:
  - Response body truncation based on `maxResponseSize` configuration (default: 10000 bytes)
  - Size-based masking skip for large objects (prevents performance degradation)
  - Automatic batching via `AuditLogQueue` reduces HTTP overhead for high-volume logging
- Set `log_level='debug'` to enable detailed request/response logging (all sensitive data is still masked).

→ [Complete logging example](examples/step-5-logging.py)  
→ [Logging Reference](docs/api-reference.md#logger-service)

---

### Step 6: Activate Audit

**What happens:** Create audit trails for compliance and security monitoring.

```python
from miso_client import MisoClient, load_config

# Complete configuration (all in .env)
client = MisoClient(load_config())
await client.initialize()

token = client.get_token(req)
is_valid = await client.validate_token(token)
can_edit = await client.has_permission(token, 'edit:content')
user = await client.get_user(token)

# Audit: User actions
await client.log.audit('user.login', 'authentication', {
    'userId': user.id if user else None,
    'ip': req.get('ip', ''),
    'userAgent': req.get('headers', {}).get('user-agent', ''),
})

# Audit: Content changes
await client.log.audit('post.created', 'content', {
    'userId': user.id if user else None,
    'postId': 'post-123',
    'postTitle': req.get('body', {}).get('title', ''),
})

# Audit: Permission checks
await client.log.audit('access.denied', 'authorization', {
    'userId': user.id if user else None,
    'requiredPermission': 'edit:content',
    'resource': 'posts',
})
```

**What to audit:** Login/logout, permission checks, content creation/deletion, role changes, sensitive operations.

→ [Complete audit example](examples/step-6-audit.py)  
→ [Best Practices](docs/getting-started.md#common-patterns)

---

### Encryption and Caching

**What happens:** Use encryption for sensitive data and generic caching for improved performance.

```python
from miso_client import MisoClient, load_config

client = MisoClient(load_config())
await client.initialize()

# Encryption (requires ENCRYPTION_KEY in .env)
encrypted = client.encrypt('sensitive-data')
decrypted = client.decrypt(encrypted)
print('Decrypted:', decrypted)

# Generic caching (automatically uses Redis if available, falls back to memory)
await client.cache_set('user:123', {'name': 'John', 'age': 30}, 600)  # 10 minutes TTL
user = await client.cache_get('user:123')
if user:
    print('Cached user:', user)
```

**Configuration:**

```bash
# Add to .env
ENCRYPTION_KEY=your-32-byte-encryption-key
```

→ [API Reference](docs/api-reference.md#encryption-methods)  
→ [Cache Methods](docs/api-reference.md#cache-methods)

---

### Testing with API Key

**What happens:** When `API_KEY` is set in your `.env` file, you can authenticate requests using the API key as a bearer token, bypassing OAuth2 authentication. This is useful for testing without setting up Keycloak.

```python
from miso_client import MisoClient, load_config

client = MisoClient(load_config())
await client.initialize()

# Use API_KEY as bearer token (for testing only)
api_key_token = "your-api-key-from-env"
is_valid = await client.validate_token(api_key_token)
# Returns True if token matches API_KEY from .env

user = await client.get_user(api_key_token)
# Returns None (API key auth doesn't provide user info)
```

**Configuration:**

```bash
# Add to .env for testing
API_KEY=your-test-api-key-here
```

**Important:**

- API_KEY authentication bypasses OAuth2 validation completely
- User information methods (`get_user()`, `get_user_info()`) return `None` when using API_KEY
- Token validation returns `True` if the bearer token matches the configured `API_KEY`
- This feature is intended for testing and development only

---

## 🔧 Configuration

```python
from miso_client import MisoClientConfig, RedisConfig, AuditConfig

config = MisoClientConfig(
    controller_url="http://localhost:3000",  # Required: Controller URL
    client_id="ctrl-dev-my-app",              # Required: Client ID
    client_secret="your-secret",              # Required: Client secret
    redis=RedisConfig(                        # Optional: For caching
        host="localhost",
        port=6379,
    ),
    log_level="info",                         # Optional: 'debug' | 'info' | 'warn' | 'error'
                                              # Set to 'debug' for detailed HTTP request/response logging
    api_key="your-test-api-key",              # Optional: API key for testing (bypasses OAuth2)
    cache={                                   # Optional: Cache TTL settings
        "role_ttl": 900,       # Role cache TTL (default: 900s)
        "permission_ttl": 900, # Permission cache TTL (default: 900s)
    },
    audit=AuditConfig(                        # Optional: Audit logging configuration
        enabled=True,                         # Enable/disable audit logging (default: true)
        level="detailed",                     # Audit detail level: 'minimal' | 'standard' | 'detailed' | 'full' (default: 'detailed')
        maxResponseSize=10000,                # Truncate responses larger than this in bytes (default: 10000)
        maxMaskingSize=50000,                 # Skip masking for objects larger than this in bytes (default: 50000)
        batchSize=10,                         # Batch size for queued logs (default: 10)
        batchInterval=100,                    # Flush interval in milliseconds (default: 100)
        skipEndpoints=None                    # Array of endpoint patterns to exclude from audit logging
    )
)
```

**Recommended:** Use `load_config()` to load from `.env` file automatically.

**ISO 27001 Data Masking Configuration:**

Sensitive fields are configured via `miso_client/utils/sensitive_fields_config.json`. You can customize this by:

1. Setting `MISO_SENSITIVE_FIELDS_CONFIG` environment variable to point to a custom JSON file
2. Using `DataMasker.set_config_path()` to set a custom path programmatically

The default configuration includes ISO 27001 compliant sensitive fields:

- Authentication: password, token, secret, key, auth, authorization
- PII: ssn, creditcard, cc, cvv, pin, otp
- Security: apikey, accesstoken, refreshtoken, privatekey, secretkey, cookie, session

**Audit Logging Configuration:**

Configure audit logging behavior using `AuditConfig` (see Configuration section above):

- **Audit Levels**: Control detail level (`minimal`, `standard`, `detailed`, `full`)
- **Response Truncation**: Configure `maxResponseSize` to truncate large responses (default: 10000 bytes)
- **Performance**: Set `maxMaskingSize` to skip masking for very large objects (default: 50000 bytes)
- **Batching**: Configure `batchSize` and `batchInterval` for audit log queuing (reduces HTTP overhead)

→ [Complete Configuration Reference](docs/configuration.md)

---

## 📚 Read more

- **[Getting Started](docs/getting-started.md)** - Detailed setup guide
- **[API Reference](docs/api-reference.md)** - Complete API documentation
- **[Configuration](docs/configuration.md)** - Configuration options
- **[Examples](docs/examples.md)** - Framework-specific examples
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues and solutions

---

## 🏗️ Architecture

The SDK consists of five core services:

- **AuthService** - Token validation and user authentication
- **RoleService** - Role management with Redis caching
- **PermissionService** - Fine-grained permissions
- **LoggerService** - Centralized logging with API key authentication
- **RedisService** - Caching and queue management (optional)

### HTTP Client Architecture

The SDK uses a two-layer HTTP client architecture for ISO 27001 compliance:

- **InternalHttpClient** - Core HTTP functionality with automatic client token management (internal)
- **HttpClient** - Public wrapper that adds automatic ISO 27001 compliant audit and debug logging

**Features:**

- Automatic audit logging for all HTTP requests (`http.request.{METHOD}`)
- Configurable audit levels (`minimal`, `standard`, `detailed`, `full`) via `AuditConfig`
- Debug logging when `log_level === 'debug'` with detailed request/response information
- Automatic data masking using `DataMasker` before logging (ISO 27001 compliant)
- Sensitive endpoints (`/api/logs`, `/api/auth/token`) are excluded from audit logging to prevent infinite loops
- All sensitive data (headers, bodies, query params) is automatically masked before logging
- `AuditLogQueue` integration for automatic batching of audit logs (reduces HTTP overhead)
- Performance optimizations: response body truncation and size-based masking skip for large objects

**ISO 27001 Compliance:**

- All request headers are masked (Authorization, x-client-token, Cookie, etc.)
- All request bodies are recursively masked for sensitive fields (password, token, secret, SSN, etc.)
- All response bodies are masked and truncated based on `maxResponseSize` configuration (default: 10000 bytes)
- Query parameters are automatically masked
- Error messages are masked if they contain sensitive data
- Sensitive fields configuration can be customized via `sensitive_fields_config.json`
- Configurable audit levels control the detail level of audit logs (minimal, standard, detailed, full)

→ [Architecture Details](docs/api-reference.md#architecture)

---

## 🌐 Setup Your Application

**First time setup?** Use the AI Fabrix Builder:

1. **Create your app:**

   ```bash
   aifabrix create myapp --port 3000 --database --language python
   ```

2. **Login to controller:**

   ```bash
   aifabrix login
   ```

3. **Register your application:**

   ```bash
   aifabrix app register myapp --environment dev
   ```

4. **Start development** and then deploy to Docker or Azure.

→ [Full Quick Start Guide](https://github.com/esystemsdev/aifabrix-builder/blob/main/docs/QUICK-START.md)

---

## 💡 Next Steps

### Learn More

- [FastAPI Integration](docs/examples.md#fastapi-integration) - Protect API routes
- [Django Middleware](docs/examples.md#django-middleware) - Django integration
- [Flask Decorators](docs/examples.md#flask-decorators) - Decorator-based auth
- [Error Handling](docs/examples.md#error-handling) - Best practices

---

### Structured Error Responses

**What happens:** The SDK automatically parses structured error responses from the API (RFC 7807-style format) and makes them available through the `MisoClientError` and `ApiErrorException` exceptions.

```python
from miso_client import MisoClient, MisoClientError, ApiErrorException, ErrorResponse, load_config, handleApiError

client = MisoClient(load_config())
await client.initialize()

try:
    result = await client.http_client.get("/api/some-endpoint")
except MisoClientError as e:
    # Check if structured error response is available
    if e.error_response:
        print(f"Error Type: {e.error_response.type}")
        print(f"Error Title: {e.error_response.title}")
        print(f"Status Code: {e.error_response.statusCode}")
        print(f"Errors: {e.error_response.errors}")
        print(f"Instance: {e.error_response.instance}")
    else:
        # Fallback to traditional error handling
        print(f"Error: {e.message}")
        print(f"Status Code: {e.status_code}")
        print(f"Error Body: {e.error_body}")

# Using handleApiError() for structured error handling
try:
    response_data = {"errors": ["Validation failed"], "type": "/Errors/Validation", "title": "Validation Error", "statusCode": 422}
    error = handleApiError(response_data, 422, "/api/endpoint")
    # handleApiError() returns ApiErrorException (extends MisoClientError)
    if isinstance(error, ApiErrorException):
        print(f"Structured Error: {error.error_response.title}")
except ApiErrorException as e:
    # ApiErrorException provides better structured error information
    print(f"API Error: {e.error_response.title}")
    print(f"Errors: {e.error_response.errors}")
```

**Error Response Structure:**

The `ErrorResponse` model follows RFC 7807-style format:

```json
{
   "errors": [
      "The user has provided input that the browser is unable to convert.",
      "There are multiple rows in the database for the same value"
   ],
   "type": "/Errors/Bad Input",
   "title": "Bad Request",
   "statusCode": 400,
   "instance": "/OpenApi/rest/Xzy"
}
```

**Features:**

- **Automatic Parsing**: Structured error responses are automatically parsed from HTTP responses
- **ApiErrorException**: New exception class (extends `MisoClientError`) for better structured error handling
  - `handleApiError()` returns `ApiErrorException` with structured error response support
  - Legacy `handle_api_error_snake_case()` still returns `MisoClientError` for backward compatibility
- **Backward Compatible**: Falls back to traditional error handling when structured format is not available
- **Type Safety**: Full type hints with Pydantic models for reliable error handling
- **Generic Interface**: `ErrorResponse` model can be reused across different applications
- **Instance URI**: Automatically extracted from request URL if not provided in response

**Using ErrorResponse directly:**

```python
from miso_client import ErrorResponse

# Create ErrorResponse from dict
error_data = {
    "errors": ["Validation failed"],
    "type": "/Errors/Validation",
    "title": "Validation Error",
    "statusCode": 422,
    "instance": "/api/endpoint"
}
error_response = ErrorResponse(**error_data)

# Access fields
print(error_response.errors)  # ["Validation failed"]
print(error_response.type)    # "/Errors/Validation"
print(error_response.title)   # "Validation Error"
print(error_response.statusCode)  # 422
print(error_response.instance)   # "/api/endpoint"
```

---

### Pagination, Filtering, and Sorting Utilities

**What happens:** The SDK provides reusable utilities for pagination, filtering, sorting, and error handling that work with any API endpoint.

#### Pagination

**Pagination Parameters:**

- `page`: Page number (1-based, defaults to 1)
- `page_size`: Number of items per page (defaults to 20)

```python
from miso_client import (
    parse_pagination_params,
    parsePaginationParams,  # camelCase alternative
    create_paginated_list_response,
    createPaginatedListResponse,  # camelCase alternative
    PaginatedListResponse,
)

# Parse pagination from query parameters (snake_case - returns tuple)
params = {"page": "1", "page_size": "20"}
current_page, page_size = parse_pagination_params(params)

# Or use camelCase function (returns dict with currentPage/pageSize keys)
pagination = parsePaginationParams(params)
# Returns: {"currentPage": 1, "pageSize": 20}

# Create paginated response
items = [{"id": 1}, {"id": 2}]
response = create_paginated_list_response(
    items,
    total_items=120,
    current_page=1,
    page_size=20,
    type="item"
)

# Response structure:
# {
#   "meta": {
#     "total_items": 120,
#     "current_page": 1,
#     "page_size": 20,
#     "type": "item"
#   },
#   "data": [{"id": 1}, {"id": 2}]
# }
```

#### Filtering

**Filter Operators:** `eq`, `neq`, `in`, `nin`, `gt`, `lt`, `gte`, `lte`, `contains`, `like`

**Filter Format:** `field:op:value` (e.g., `status:eq:active`)

```python
from miso_client import FilterBuilder, parse_filter_params, build_query_string

# Dynamic filter building with FilterBuilder
filter_builder = FilterBuilder() \
    .add('status', 'eq', 'active') \
    .add('region', 'in', ['eu', 'us']) \
    .add('created_at', 'gte', '2024-01-01')

# Get query string
query_string = filter_builder.to_query_string()
# Returns: "filter=status:eq:active&filter=region:in:eu,us&filter=created_at:gte:2024-01-01"

# Parse existing filter parameters
params = {'filter': ['status:eq:active', 'region:in:eu,us']}
filters = parse_filter_params(params)
# Returns: [FilterOption(field='status', op='eq', value='active'), ...]

# Use with HTTP client
response = await client.http_client.get_with_filters(
    '/api/items',
    filter_builder=filter_builder
)
```

**Building Complete Filter Queries:**

```python
from miso_client import FilterQuery, FilterOption, build_query_string

# Create filter query with filters, sort, pagination, and fields
filter_query = FilterQuery(
    filters=[
        FilterOption(field='status', op='eq', value='active'),
        FilterOption(field='region', op='in', value=['eu', 'us'])
    ],
    sort=['-updated_at', 'created_at'],
    page=1,
    page_size=20,
    fields=['id', 'name', 'status']
)

# Build query string
query_string = build_query_string(filter_query)
```

#### Sorting

**Sort Format:** `-field` for descending, `field` for ascending (e.g., `-updated_at`, `created_at`)

```python
from miso_client import parse_sort_params, build_sort_string, SortOption

# Parse sort parameters
params = {'sort': '-updated_at'}
sort_options = parse_sort_params(params)
# Returns: [SortOption(field='updated_at', order='desc')]

# Parse multiple sorts
params = {'sort': ['-updated_at', 'created_at']}
sort_options = parse_sort_params(params)
# Returns: [
#   SortOption(field='updated_at', order='desc'),
#   SortOption(field='created_at', order='asc')
# ]

# Build sort string
sort_options = [
    SortOption(field='updated_at', order='desc'),
    SortOption(field='created_at', order='asc')
]
sort_string = build_sort_string(sort_options)
# Returns: "-updated_at,created_at"
```

#### Combined Usage

**Pagination + Filter + Sort:**

```python
from miso_client import (
    FilterBuilder,
    FilterQuery,
    build_query_string,
    parse_pagination_params,
)

# Build filters
filter_builder = FilterBuilder() \
    .add('status', 'eq', 'active') \
    .add('region', 'in', ['eu', 'us'])

# Parse pagination
params = {'page': '1', 'page_size': '20'}
current_page, page_size = parse_pagination_params(params)

# Create complete query
filter_query = FilterQuery(
    filters=filter_builder.build(),
    sort=['-updated_at'],
    page=current_page,
    page_size=page_size
)

# Build query string
query_string = build_query_string(filter_query)

# Use with HTTP client
response = await client.http_client.get_with_filters(
    '/api/items',
    filter_builder=filter_builder,
    params={'page': current_page, 'page_size': page_size}
)
```

**Or use pagination helper:**

```python
# Get paginated response
response = await client.http_client.get_paginated(
    '/api/items',
    page=1,
    page_size=20
)

# Response is automatically parsed as PaginatedListResponse
print(response.meta.total_items)  # 120
print(response.meta.current_page)  # 1
print(len(response.data))  # 25
```

#### Metadata Filter Integration

**Working with `/metadata/filter` endpoint:**

```python
# Get metadata filters from endpoint
metadata_response = await client.http_client.post(
    "/api/v1/metadata/filter",
    {"documentStorageKey": "my-doc-storage"}
)

# Convert AccessFieldFilter to FilterBuilder
filter_builder = FilterBuilder()
for access_filter in metadata_response.mandatoryFilters:
    filter_builder.add(access_filter.field, 'in', access_filter.values)

# Use with query utilities
query_string = filter_builder.to_query_string()

# Apply to API requests
response = await client.http_client.get_with_filters(
    '/api/items',
    filter_builder=filter_builder
)
```

**Features:**

- **Snake_case Convention**: All utilities use snake_case to match Miso/Dataplane API
- **camelCase Alternatives**: camelCase function names are available for all utilities (backward compatible)
  - `parsePaginationParams()` - Returns dict with `currentPage`/`pageSize` keys (alias: `parse_pagination_params()`)
  - `createMetaObject()` - Creates `Meta` objects with camelCase fields (alias: `create_meta_object()`)
  - `applyPaginationToArray()` - Applies pagination to arrays (alias: `apply_pagination_to_array()`)
  - `createPaginatedListResponse()` - Creates paginated list responses (alias: `create_paginated_list_response()`)
  - `transformError()` - Transforms error dictionaries to `ErrorResponse` objects (alias: `transform_error_to_snake_case()`)
  - `handleApiError()` - Creates `ApiErrorException` from API error responses (alias: `handle_api_error_snake_case()`)
- **Type Safety**: Full type hints with Pydantic models
- **Dynamic Filtering**: FilterBuilder supports method chaining for complex filters
- **Local Testing**: `apply_filters()` and `apply_pagination_to_array()` for local filtering/pagination in tests
- **URL Encoding**: Automatic URL encoding for field names and values
- **Backward Compatible**: Works alongside existing HTTP client methods

---

### Common Tasks

**Add authentication middleware (FastAPI):**

```python
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer
from miso_client import MisoClient

security = HTTPBearer()
client = MisoClient(load_config())

async def get_current_user(credentials = Security(security)):
    token = credentials.credentials
    is_valid = await client.validate_token(token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid token")
    return await client.get_user(token)
```

**Protect routes by role (FastAPI):**

```python
@app.get('/admin')
async def admin_panel(user = Depends(get_current_user), credentials = Security(security)):
    token = credentials.credentials
    is_admin = await client.has_role(token, 'admin')
    if not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Admin only code
    return {"message": "Admin panel"}
```

**Use environment variables:**

```bash
MISO_CLIENTID=ctrl-dev-my-app
MISO_CLIENTSECRET=your-secret
MISO_CONTROLLER_URL=http://localhost:3000
REDIS_HOST=localhost
REDIS_PORT=6379
MISO_LOG_LEVEL=info
API_KEY=your-test-api-key  # Optional: For testing (bypasses OAuth2)
```

---

## 🐛 Troubleshooting

**"Cannot connect to controller"**  
→ Verify `controllerUrl` is correct and accessible  
→ Check network connectivity

**"Redis connection failed"**  
→ SDK falls back to controller-only mode (slower but works)  
→ Fix: `aifabrix up` to start Redis

**"Client token fetch failed"**  
→ Check `MISO_CLIENTID` and `MISO_CLIENTSECRET` are correct  
→ Verify credentials are configured in controller  
→ Ensure `ENCRYPTION_KEY` environment variable is set (required for encryption service)

**"Token validation fails"**  
→ Ensure Keycloak is running and configured correctly  
→ Verify token is from correct Keycloak instance  
→ Check that `python-dotenv` is installed if using `.env` files

→ [More Help](docs/troubleshooting.md)

---

## 📦 Installation

```bash
# pip
pip install miso-client

# Development mode
pip install -e .

# With dev dependencies
pip install "miso-client[dev]"
```

---

## 🔗 Links

- **GitHub Repository**: [https://github.com/esystemsdev/aifabrix-miso-client-python](https://github.com/esystemsdev/aifabrix-miso-client-python)
- **PyPI Package**: [https://pypi.org/project/miso-client/](https://pypi.org/project/miso-client/)
- **Builder Documentation**: [https://github.com/esystemsdev/aifabrix-builder](https://github.com/esystemsdev/aifabrix-builder)
- **Issues**: [https://github.com/esystemsdev/aifabrix-miso-client-python/issues](https://github.com/esystemsdev/aifabrix-miso-client-python/issues)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

---

**Made with ❤️ by eSystems Nordic Ltd.**
