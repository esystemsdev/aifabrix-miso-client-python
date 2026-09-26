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
