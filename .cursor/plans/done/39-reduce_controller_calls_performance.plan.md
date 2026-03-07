---
name: Reduce controller calls performance
overview: Reduce the number of calls from this Python client to the miso-controller by adding encryption response caching and reinforcing existing cache-and-batch behavior, aligning with the controller plan's open question on call volume and caching.
todos: []
isProject: false
---

# Reduce controller calls and improve performance

## Context: Controller plan 163

The miso-controller plan [163-rate-limit-with-internal-app](/workspace/aifabrix-miso/.cursor/plans/163-rate-limit-with-internal-app.plan.md) aims to disable rate-limiting for internal applications to avoid HTTP 429 (e.g. "Too many encryption/decryption requests"). It explicitly asks:

1. **Why do we call the controller that many times?** Root cause may be call pattern, not only rate-limit thresholds.
2. **Can we cache?** Which endpoints are called repeatedly (encrypt/decrypt, token exchange), whether responses can be cached (by key id, scope, or request fingerprint), and what would be cache-missing.

This plan addresses the **client side**: reduce call volume from this SDK so that fewer requests hit the controller, improving performance and making 429 less likely even before or in addition to controller-side rate-limit changes.

---

## Rules and Standards

This plan must comply with [Project Rules](.cursor/rules/project-rules.mdc). Applicable sections:

- **[Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns)** – Service layer (EncryptionService), Redis/CacheService usage, cache key format and TTL.
- **[Code Style](.cursor/rules/project-rules.mdc#code-style)** – Type hints, error handling (try/except, return defaults), Google-style docstrings for public methods.
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** – pytest, pytest-asyncio, mock HttpClient/CacheService, test cache hit/miss and error paths, ≥80% coverage for new code.
- **[Configuration](.cursor/rules/project-rules.mdc#configuration)** – Config in `models/config.py`, optional `encryption_cache_ttl`, env var if needed.
- **[Common Patterns](.cursor/rules/project-rules.mdc#common-patterns)** – Service method pattern (cache-first, then controller, cache result on success).
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** – No logging of plaintext/secrets; cache keys for encrypt use hash only; audit/masking unchanged.
- **[Performance Guidelines](.cursor/rules/project-rules.mdc#performance-guidelines)** – Use cache when available, fallback to controller, async/await.
- **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** – Files ≤500 lines, methods ≤20–30 lines; split if needed.
- **[Documentation](.cursor/rules/project-rules.mdc#documentation)** – Docstrings for new/updated public methods; update docs for “reducing controller calls” and TTLs.
- **[When Adding New Features](.cursor/rules/project-rules.mdc#when-adding-new-features)** – Update models first, then service, tests, and documentation.

**Key requirements**

- EncryptionService: optional `CacheService` dependency; cache key for decrypt `(value, parameter_name)`; for encrypt use hash of `(plaintext, parameter_name)` (do not use raw plaintext in key).
- Use try/except in async paths; on controller errors do not cache; log with `exc_info=error`.
- New tests in `tests/unit/` for encryption cache (hit, miss, TTL, disabled); mock `HttpClient` and `CacheService`; use `AsyncMock` for async methods.
- All new code: type hints, Google-style docstrings; keep files and methods within size limits.

---

## Before Development

- Read Architecture Patterns and Redis Caching Pattern in project-rules.mdc.
- Review [RoleService](miso_client/services/role.py) / [PermissionService](miso_client/services/permission.py) cache-first pattern and [CacheService](miso_client/services/cache.py) API.
- Review [EncryptionService](miso_client/services/encryption.py) and [EncryptResult](miso_client/models/encryption.py) (or equivalent) for integration points.
- Confirm testing requirements: pytest-asyncio, mocking HttpClient/CacheService, cache hit/miss and TTL/disabled cases.
- Confirm config shape in [MisoClientConfig](miso_client/models/config.py) for optional `encryption_cache_ttl`.

---

## Current state: where the client calls the controller


| Area                 | Controller calls                                       | Caching today                                                                                                                                                                                    |
| -------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Client token**     | 1× on first use, then refresh on expiry/401            | In-memory in [ClientTokenManager](miso_client/utils/client_token_manager.py); single token reused                                                                                                |
| **Token validation** | POST `/api/v1/auth/validate`                           | Cached in [AuthService](miso_client/services/auth.py) via [CacheService](miso_client/services/cache.py) (Redis + in-memory), TTL from token expiry / `validation_ttl` (default 120s)             |
| **User info**        | From validate or GET user                              | Cached by user, `user_ttl` (default 300s)                                                                                                                                                        |
| **Roles**            | GET `/api/v1/auth/roles`                               | Cache-first in [RoleService](miso_client/services/role.py) by `userId`, `role_ttl` (default 900s); JWT used to get userId before calling API                                                     |
| **Permissions**      | GET `/api/v1/auth/permissions`                         | Same pattern in [PermissionService](miso_client/services/permission.py), `permission_ttl` (900s)                                                                                                 |
| **Token exchange**   | POST token exchange                                    | Cached by delegated token hash in AuthService                                                                                                                                                    |
| **Encryption**       | POST `/api/security/parameters/encrypt` and `/decrypt` | **No caching** — every encrypt/decrypt = one controller call                                                                                                                                     |
| **Logs**             | POST `/api/v1/logs` or `/api/v1/logs/batch`            | [LoggerService](miso_client/services/logger.py): events → [AuditLogQueue](miso_client/utils/audit_log_queue.py) (batch) → Redis queue → HTTP. When audit queue is used, batch endpoint is called |


So the **main gap** is **encryption**: repeated per-item encrypt/decrypt (e.g. in upload or bulk flows) can generate a high volume of calls and directly matches the controller plan’s “per-item encryption/decryption” concern.

---

## Proposed changes

### 1. Add encryption response caching (high impact)

**Goal:** Avoid repeated controller calls when the same value is encrypted or decrypted multiple times (e.g. same parameter name + same plaintext/ciphertext).

- **Decrypt cache**  
  - Key: `(value, parameter_name)` (value = encrypted reference string).  
  - Same ciphertext + same parameter → same plaintext; cache the plaintext.  
  - Use [CacheService](miso_client/services/cache.py) (Redis + in-memory fallback).  
  - TTL: configurable (e.g. `encryption_cache_ttl`, default 300s). Short TTL or invalidation if key rotation is a concern.
- **Encrypt cache**  
  - Key: hash of `(plaintext, parameter_name)` (e.g. SHA-256 of `plaintext + parameter_name`).  
  - Same input → same `EncryptResult`; cache the result.  
  - Same TTL as decrypt (or single config key `encryption_cache_ttl`).
- **Implementation**  
  - In [EncryptionService](miso_client/services/encryption.py): inject optional `CacheService`; before calling controller, check cache; on success, store in cache with TTL.  
  - Config: add optional `encryption_cache_ttl` (seconds, 0 = disabled) on [MisoClientConfig](miso_client/models/config.py) (or equivalent) and wire in [MisoClient](miso_client/client.py) when constructing EncryptionService.  
  - Keep existing validation and error handling; on controller errors, do not cache.
- **Safety**  
  - Document that with key rotation, cache may serve stale results until TTL expires; recommend lower TTL or disabling cache when rotation is frequent.  
  - Optional: method or config to clear encryption cache (e.g. on logout or key rotation).

**Tests (unit, in `tests/unit/test_encryption_service.py` or equivalent)**

- **Encrypt cache**  
  - Cache miss: first `encrypt(plaintext, param)` calls controller, stores result in cache, returns `EncryptResult`; assert `http_client.post` called once and `cache.set` called once.  
  - Cache hit: second `encrypt(same_plaintext, same_param)` returns cached result without calling controller; assert `http_client.post` not called again and `cache.get` returned value.  
  - Cache disabled: `encryption_cache_ttl=0` or no cache injected → every encrypt calls controller; assert no `cache.set`/`cache.get` or controller called each time.  
  - Controller error: encrypt when controller returns error → exception raised and no `cache.set` (do not cache failures).  
  - Cache key does not contain plaintext: assert cache key is hash-based (e.g. contains no raw plaintext).
- **Decrypt cache**  
  - Cache miss: first `decrypt(value, param)` calls controller, stores plaintext in cache, returns plaintext; assert `http_client.post` once, `cache.set` once.  
  - Cache hit: second `decrypt(same_value, same_param)` returns cached plaintext without controller call; assert `http_client.post` not called again.  
  - Cache disabled: same as encrypt (no cache or TTL=0 → controller every time).  
  - Controller error: decrypt when controller returns error → exception raised and no `cache.set`.
- **Integration with existing behavior**  
  - `EncryptionService(cache=None)` or no cache: behavior unchanged from current (no cache get/set; every request hits controller).  
  - Cache get/set failure (e.g. mock `cache.get`/`cache.set` to raise or return False): service falls back to controller and does not crash; optional: assert controller was called.  
  - Config: `encryption_cache_ttl` is passed to cache (e.g. `cache.set(..., ttl=config.encryption_cache_ttl)` or equivalent).
- **Optional (if clear_encryption_cache is added)**  
  - `clear_encryption_cache()` clears encrypt/decrypt entries so next encrypt/decrypt calls controller again.

### 2. Ensure audit log queue is used when available

- Logger already prefers audit queue then Redis then HTTP.  
- Confirm [AuditLogQueue](miso_client/utils/audit_log_queue.py) is attached when audit config is present (already done in [client.py](miso_client/client.py) with `audit_log_queue`).  
- No code change required if already wired; optionally document in “Reducing controller calls” that batch logging is used when audit queue is enabled, and mention default batch size/interval (e.g. batch size 10, interval 100 ms from [audit_log_queue.py](miso_client/utils/audit_log_queue.py)).

### 3. Document cache usage and TTLs

- Add a short “Performance and reducing controller calls” section (e.g. in `docs/` or main README) that:  
  - Lists which operations are cached (validation, user, roles, permissions, token exchange, and after this plan: encryption).  
  - Recommends enabling Redis for shared cache across processes.  
  - Documents `encryption_cache_ttl`, `validation_ttl`, `user_ttl`, `role_ttl`, `permission_ttl` and suggests values for high-throughput scenarios (e.g. longer TTLs where consistency allows).  
  - Mentions that log batching (audit queue) reduces log endpoint calls.

### 4. Future / controller coordination

- If miso-controller later adds **batch encrypt/decrypt** endpoints, this client can add batch methods that call them to further reduce round-trips. Out of scope for this plan but worth noting in docs or a short “Future work” subsection.

---

## Out of scope

- Changes inside miso-controller (rate-limit or batch APIs) — see plan 163.  
- Changing validation/roles/permissions cache semantics; only documenting and, if needed, making TTLs easier to tune.

---

## Definition of Done

Before marking this plan complete, ensure:

1. **Lint**: Run `ruff check` and `mypy` (must pass with zero errors/warnings).
2. **Format**: Run `black` and `isort` (code must be formatted).
3. **Test**: Run `pytest` **after** lint and format (all tests must pass; ≥80% coverage for new code).
4. **Validation order**: LINT → FORMAT → TEST (mandatory sequence; do not skip steps).
5. **File size**: New/updated files ≤500 lines; methods ≤20–30 lines (split or extract helpers if needed).
6. **Type hints**: All new functions/methods have parameter and return type hints.
7. **Docstrings**: All new or changed public methods have Google-style docstrings (Args, Returns, Raises as needed).
8. **EncryptionService**: Optional response caching (encrypt + decrypt) with configurable TTL and CacheService integration; cache key for encrypt uses hash of (plaintext, parameter_name); decrypt cache key (value, parameter_name); on controller errors do not cache.
9. **Cache key and TTL**: Documented; key-rotation recommendation (lower TTL or disable) documented.
10. **Documentation**: “Performance and reducing controller calls” (or equivalent) added/updated in `docs/` or README with cached operations, TTLs, and log batching.
11. **Tests**: Unit tests as in **Tests (unit)** above: encrypt/decrypt cache hit and miss, cache disabled (TTL=0 or no cache), no cache on controller error, cache key without plaintext, service with `cache=None` unchanged, cache failure fallback, TTL passed to cache; mock HttpClient and CacheService; use AsyncMock for async methods.
12. **No regression**: Existing encrypt/decrypt behavior unchanged when cache is disabled or not configured.
13. **Security**: No plaintext or secrets in cache keys or logs; existing audit/masking unchanged.
14. **Rule compliance**: Meets applicable requirements from Rules and Standards above.

---

## Validation

**Date**: 2025-03-07  
**Status**: ✅ COMPLETE

### Executive Summary

Implementation is complete. All proposed changes are in place: encryption response caching (encrypt/decrypt) with optional CacheService, configurable `encryption_cache_ttl`, cache keys using hash only (no plaintext), documentation in `docs/performance-and-caching.md`, and full unit test coverage for cache hit/miss, disabled cache, controller errors, and fallback. Format, lint, type-check, and tests all pass. Cursor rules compliance verified.

### File Existence Validation

- ✅ `miso_client/services/encryption.py` – EncryptionService with optional CacheService, _cache_key_encrypt/_cache_key_decrypt (hash-based), cache-first encrypt/decrypt, TTL from config
- ✅ `miso_client/services/cache.py` – CacheService (Redis + in-memory) used by EncryptionService
- ✅ `miso_client/models/config.py` – `encryption_cache_ttl` property (from cache dict, default 300, 0 = disabled)
- ✅ `miso_client/client.py` – EncryptionService wired with `self.cache`; AuditLogQueue attached when audit config present
- ✅ `docs/performance-and-caching.md` – "Performance and Reducing Controller Calls" with cached operations, encryption cache, TTLs, Redis, log batching
- ✅ `tests/unit/test_encryption_service.py` – Cache tests: encrypt/decrypt cache miss/hit, cache disabled (TTL=0, no cache), no cache on controller error, cache key hash-based, cache=None unchanged, cache get/set failure fallback, TTL passed to cache

### Test Coverage

- ✅ Unit tests exist for encryption cache in `tests/unit/test_encryption_service.py`
- ✅ Encrypt: cache miss (controller + cache.set), cache hit (no controller), cache disabled (TTL=0, no cache), controller error (no cache.set), cache key hash-based, cache get/set failure fallback, TTL=300 passed to cache
- ✅ Decrypt: cache miss, cache hit, controller error (no cache.set)
- ✅ Integration tests not required by plan (unit only)
- ✅ Test run: 1351 passed (pytest, excludes integration/manual)
- ✅ Coverage: `miso_client/services/encryption.py` 96%; overall 93%

### Code Quality Validation

**STEP 1 - FORMAT**: ✅ PASSED (`make format` – black, isort)  
**STEP 2 - LINT**: ✅ PASSED (ruff check – 0 errors, 0 warnings)  
**STEP 3 - TYPE CHECK**: ✅ PASSED (mypy miso_client/ – no issues)  
**STEP 4 - TEST**: ✅ PASSED (1351 tests, ~10s)

### Cursor Rules Compliance

- ✅ Code reuse: Cache pattern aligned with RoleService/PermissionService; CacheService used for encrypt/decrypt
- ✅ Error handling: try/except in encrypt/decrypt; on controller error no cache.set; log with exc_info
- ✅ Logging: No plaintext/secrets in logs; correlation ID in error logs
- ✅ Type safety: Type hints and EncryptResult used throughout
- ✅ Async patterns: async/await for encrypt/decrypt and cache get/set
- ✅ HTTP client: Uses http_client.post for encrypt/decrypt endpoints
- ✅ Token management: N/A for encryption service
- ✅ Redis/cache: CacheService optional; cache key hash-only; TTL from config; fallback to controller on cache failure
- ✅ Service layer: EncryptionService receives HttpClient, config, optional CacheService; config via public property
- ✅ Security: Encrypt cache key = hash(plaintext, parameter_name); decrypt key from value+param (hashed); no plaintext in keys
- ✅ API data conventions: Request bodies use camelCase (parameterName, encryptionKey, etc.)
- ✅ File size: encryption.py ~245 lines; methods under 30 lines

### Implementation Completeness

- ✅ EncryptionService: Optional CacheService; cache-first encrypt/decrypt; _cache_key_encrypt (hash), _cache_key_decrypt (hash); TTL from config; no cache on controller error
- ✅ Config: `encryption_cache_ttl` property on MisoClientConfig (cache dict, default 300, 0 = disabled)
- ✅ Client: EncryptionService(self.http_client, config, self.cache); AuditLogQueue attached when audit config present
- ✅ Documentation: `docs/performance-and-caching.md` – cached operations (including encryption), TTLs, key rotation note, log batching
- ✅ Exports: EncryptionService used internally; no new public exports required

### Issues and Recommendations

- None. Optional future work: `clear_encryption_cache()` (or clear by prefix) for key-rotation/logout; plan already notes as optional.

### Final Validation Checklist

- [x] All tasks completed (encryption caching, config, client wiring, docs, tests)
- [x] All files exist and implement plan
- [x] Tests exist and pass (1351 passed; encryption cache tests in test_encryption_service.py)
- [x] Code quality validation passes (format → lint → type-check → test)
- [x] Cursor rules compliance verified
- [x] Implementation complete

**Result**: ✅ **VALIDATION PASSED** – Plan 39 (Reduce controller calls performance) is fully implemented: encryption response caching with hash-based keys, configurable TTL, CacheService integration, documentation, and comprehensive unit tests; all quality gates pass.

