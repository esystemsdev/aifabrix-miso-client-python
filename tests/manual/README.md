# Manual tests

Default pytest discovery, CI, release validation, and `make test` run unit tests only.
Unit tests block network sockets; mock controller HTTP and Redis calls. Live tests
require an explicit command and configured services. Run manual tests when needed:

    pytest tests/manual/ -v

They cover behavior excluded from the default unit test run (e.g. ENCRYPTION_KEY env fallback).

## Client-credential bootstrap

Use a test application on a compatible controller. Supply `MISO_CONTROLLER_URL` (HTTPS),
`MISO_CLIENTID`, `MISO_CLIENTSECRET`, and `BOOTSTRAP_SMOKE_KEY` (the name of a known,
nonempty configuration value the application is permitted to receive). Existing process
variables take precedence over `.env`. The smoke does not rotate credentials or modify
application configuration.

```bash
venv/bin/python -m pytest tests/manual/test_client_credential_bootstrap.py -q --no-cov --tb=short
```

The first case initializes, reads the key, refreshes using the snapshot token, reads again
and closes. The second uses a synthetic invalid secret and expects terminal denial.
Record the environment, controller/SDK revisions, outcomes and safe controller audit/correlation
identifiers in `.temp/validation/51.0-bootstrap-smoke.md`. Never copy tokens, credential values,
response bodies or secret values into evidence. Live audit verification remains an operator
check because access to controller logs varies by deployment.

## Encryption round trip (plan 52.0)

Run `make test-encryption-e2e` with `MISO_CONTROLLER_URL`, `MISO_CLIENTID`,
`MISO_CLIENTSECRET`, and `MISO_ENCRYPTION_E2E_KEY` set for a dedicated test app.
The key must be valid for that application on the selected controller; never use
shared synthetic values from test fixtures. Missing settings fail rather than skip.

The two cases exercise local credentials and managed bootstrap. Each creates a
unique `sdk-smoke-*` parameter with throwaway plaintext, calls public SDK encrypt
and decrypt with caching disabled, verifies equality, and closes its clients/runtime.
Depending on the controller's storage configuration this can persist a throwaway
parameter; use a disposable app and clean up through the controller's supported
administrative tooling. The SDK does not expose a parameter-delete operation here.
Only endpoint names, statuses, and a generated correlation ID are recorded in
`.temp/validation/52-encryption-live.xml`; credentials and values are never reported.

Offline acceptance tests are in `tests/unit/test_auth_encryption_transport_contract.py`:

```bash
venv/bin/python -m pytest tests/unit/test_auth_encryption_transport_contract.py -o addopts= --no-cov --tb=short
```

They replace only HTTP transports and the managed token provider, keeping SDK
routing, fallback, error conversion and encryption wrappers real. The suite covers fallback and preserved diagnostics in local and managed modes,
including sanitization and terminal bootstrap denials. No cases use `xfail` or skips.
