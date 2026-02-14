#!/usr/bin/env python3
"""
Manual test script for the Encryption Service (docs/encryption.md).

Run against a real miso-controller with client credentials and MISO_ENCRYPTION_KEY
set in .env. Performs encrypt/decrypt round-trip and optional validation checks.

Usage:
    # From project root with SDK installed (e.g. pip install -e . or venv)
    python tests/integration/manual_test_encryption.py

    # Validate-only: skip round-trip (no controller needed for ENCRYPTION_KEY_REQUIRED / INVALID_PARAMETER_NAME)
    python tests/integration/manual_test_encryption.py --validate-only

Requires in .env:
    MISO_CONTROLLER_URL, MISO_CLIENTID, MISO_CLIENTSECRET,
    MISO_ENCRYPTION_KEY or ENCRYPTION_KEY
"""

import asyncio
import sys
from pathlib import Path

# Load .env from project root so load_config() sees MISO_* and MISO_ENCRYPTION_KEY
_project_root = Path(__file__).resolve().parent.parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_path)
    except ImportError:
        pass

from miso_client import EncryptionError, MisoClient, load_config  # noqa: E402


async def run_round_trip() -> bool:
    """Run encrypt then decrypt and verify plaintext matches. Returns True on success."""
    print("=" * 60)
    print("Encryption Service – manual round-trip test")
    print("=" * 60)
    print()

    config = load_config()
    if not config.encryption_key:
        print(
            "Encryption key is not set. Set MISO_ENCRYPTION_KEY or ENCRYPTION_KEY in .env and re-run."
        )
        print("See docs/encryption.md for configuration.")
        return False

    print("Config:")
    print(f"  Controller URL: {config.controller_url}")
    print(f"  Encryption key: {'*' * 8} (set)")
    print()

    try:
        client = MisoClient(config)
        await client.initialize()
    except Exception as e:
        print(f"Failed to initialize MisoClient: {e}")
        return False

    parameter_name = "manual-test-param"
    plaintext = "manual-test-secret-value"

    print("Step 1: Encrypt")
    try:
        result = await client.encrypt(plaintext, parameter_name)
        print(f"  value:   {result.value}")
        print(f"  storage: {result.storage}")
    except EncryptionError as e:
        print(f"  EncryptionError: {e}")
        print(f"  code={e.code}, parameter_name={e.parameter_name}, status_code={e.status_code}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False

    print()
    print("Step 2: Decrypt")
    try:
        decrypted = await client.decrypt(result.value, parameter_name)
        print(f"  plaintext: {decrypted!r}")
    except EncryptionError as e:
        print(f"  EncryptionError: {e}")
        print(f"  code={e.code}, parameter_name={e.parameter_name}, status_code={e.status_code}")
        return False
    except Exception as e:
        print(f"  Error: {e}")
        return False

    print()
    if decrypted == plaintext:
        print("Result: round-trip OK (encrypt -> decrypt matches original).")
        return True
    print("Result: FAIL (decrypted value does not match original).")
    return False


async def run_validate_only() -> bool:
    """Run client-side validation checks only (no controller calls). Returns True if all pass."""
    print("=" * 60)
    print("Encryption Service – manual validation-only test")
    print("=" * 60)
    print()

    config = load_config()

    # ENCRYPTION_KEY_REQUIRED when key is missing
    if config.encryption_key:
        print("Encryption key is set; skipping ENCRYPTION_KEY_REQUIRED check.")
        print(
            "To test it, unset MISO_ENCRYPTION_KEY and ENCRYPTION_KEY and re-run with --validate-only."
        )
    else:
        print("Check: ENCRYPTION_KEY_REQUIRED when MISO_ENCRYPTION_KEY is not set")
        try:
            client = MisoClient(config)
            await client.initialize()
            await client.encrypt("secret", "param")
            print("  FAIL: expected EncryptionError(ENCRYPTION_KEY_REQUIRED)")
            return False
        except EncryptionError as e:
            if e.code == "ENCRYPTION_KEY_REQUIRED":
                print("  OK")
            else:
                print(f"  FAIL: got code={e.code}")
                return False
        except Exception as e:
            print(f"  FAIL: {e}")
            return False

    # INVALID_PARAMETER_NAME
    print()
    print("Check: INVALID_PARAMETER_NAME for invalid parameter name")
    if not config.encryption_key:
        print("  Skipped (no encryption key in .env).")
    else:
        try:
            client = MisoClient(config)
            await client.initialize()
            await client.encrypt("secret", "invalid name!")
            print("  FAIL: expected EncryptionError(INVALID_PARAMETER_NAME)")
            return False
        except EncryptionError as e:
            if e.code == "INVALID_PARAMETER_NAME":
                print("  OK")
            else:
                print(f"  FAIL: got code={e.code}")
                return False
        except Exception as e:
            print(f"  FAIL: {e}")
            return False

    print()
    print("Result: validation checks OK.")
    return True


def main() -> int:
    validate_only = "--validate-only" in sys.argv
    if validate_only:
        ok = asyncio.run(run_validate_only())
    else:
        ok = asyncio.run(run_round_trip())
    print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
