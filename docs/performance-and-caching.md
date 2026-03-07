# Performance and Reducing Controller Calls

This document describes how the Miso Client SDK reduces the number of calls to the miso-controller through caching and batching. Fewer controller calls improve performance and help avoid rate limits (e.g. HTTP 429).

## Cached Operations

The following operations use the shared cache (Redis when configured, plus in-memory fallback) so that repeated requests with the same inputs can be served from cache instead of calling the controller:

| Operation            | Cache key / scope              | Default TTL | Config key / note                    |
|----------------------|---------------------------------|------------|--------------------------------------|
| Token validation     | Token hash                      | 120 s      | `validationTTL` / `validation_ttl`   |
| User info            | User ID                         | 300 s      | `userTTL` / `user_ttl`               |
| Roles                | User ID                         | 900 s      | `roleTTL` / `role_ttl`               |
| Permissions          | User ID                         | 900 s      | `permissionTTL` / `permission_ttl`   |
| Token exchange       | Delegated token hash            | From token | —                                    |
| **Encryption (encrypt/decrypt)** | Hash-based (see below) | 300 s      | `encryptionCacheTTL` / `encryption_cache_ttl` (0 = disabled) |

Encryption cache is optional. When enabled, repeated encrypt or decrypt with the same inputs (same plaintext+parameter for encrypt, same value+parameter for decrypt) returns the cached result without calling the controller. Set `encryption_cache_ttl` to `0` (or do not provide a cache) to disable encryption caching.

## Encryption Cache

- **Encrypt**: Cache key is a hash of `(plaintext, parameter_name)`; no plaintext is stored in the key. Same input always yields the same encrypted reference, so caching is safe until key rotation.
- **Decrypt**: Cache key is derived from `(value, parameter_name)` (value is the encrypted reference). Same ciphertext + parameter yields the same plaintext.
- **Key rotation**: If the controller or Key Vault rotates keys, cached results may be stale until the TTL expires. For environments with frequent key rotation, use a lower `encryption_cache_ttl` or set it to `0` to disable encryption caching.

## Enabling Redis

For multi-process or multi-instance deployments, configure Redis so that the cache is shared:

- Set `REDIS_HOST` (and optionally `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`) in your environment or config.
- The SDK uses the same Redis-backed `CacheService` for roles, permissions, token validation, user info, and encryption cache.

When Redis is unavailable, the SDK falls back to in-memory caching per process and still reduces controller calls for that process.

## Log Batching

Audit logs are sent to the controller in batches when the audit log queue is enabled:

- Configure `audit.batchSize` and `audit.batchInterval` (see audit configuration).
- Log entries are queued and sent as a single request to `/api/v1/logs/batch` when the batch size or interval is reached.
- This reduces the number of HTTP requests for high-volume logging.

## TTL Configuration

Cache TTLs can be set in the `cache` section of the client config (e.g. when building `MisoClientConfig`):

- `encryptionCacheTTL` or `encryption_cache_ttl`: Encryption result cache in seconds; `0` = disabled (default when enabled: 300).
- `validationTTL` / `validation_ttl`: Token validation cache (default 120).
- `userTTL` / `user_ttl`: User info cache (default 300).
- `roleTTL` / `role_ttl`: Roles cache (default 900).
- `permissionTTL` / `permission_ttl`: Permissions cache (default 900).

For high-throughput scenarios where consistency can be relaxed, longer TTLs can further reduce controller calls. Prefer shorter TTLs (or disable encryption cache) when keys or permissions change frequently.
