# Manual tests

Tests in this folder are not run by make test. Run them manually when needed:

    pytest tests/manual/ -v

They cover behavior excluded from the default unit test run (e.g. ENCRYPTION_KEY env fallback).
