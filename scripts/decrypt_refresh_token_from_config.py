#!/usr/bin/env python3
"""
Decrypt the refresh token from .aifabrix/config.yaml using aifabrix-builder's
secrets-encryption.js (AES-256-GCM, secure:// format).

Usage:
  python scripts/decrypt_refresh_token_from_config.py

  Then set TEST_REFRESH_TOKEN in the environment or set TEST_REFRESH_TOKEN_FILE
  to a file containing the output before running integration tests.

Requires: Node.js, and aifabrix-builder at ../aifabrix-builder or
  AIFABRIX_BUILDER_ROOT pointing to it.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

def _find_config_paths():
    yield os.environ.get("AIFABRIX_HOME")
    yield "/workspace/.aifabrix"
    yield str(Path.home() / ".aifabrix")
    yield str(PROJECT_ROOT / ".aifabrix")

def _find_secrets_script():
    for p in [
        Path(os.environ.get("AIFABRIX_BUILDER_ROOT", "")) / "lib" / "utils" / "secrets-encryption.js",
        PROJECT_ROOT.parent / "aifabrix-builder" / "lib" / "utils" / "secrets-encryption.js",
        Path("/workspace/aifabrix-builder/lib/utils/secrets-encryption.js"),
    ]:
        if p and p.exists() and p.is_file():
            return p
    return None

def main():
    script_path = _find_secrets_script()
    if not script_path:
        print("secrets-encryption.js not found. Set AIFABRIX_BUILDER_ROOT or run from workspace with aifabrix-builder.", file=sys.stderr)
        return 1
    for base in _find_config_paths():
        if not base:
            continue
        config_path = Path(base) / "config.yaml"
        if not config_path.exists():
            continue
        text = config_path.read_text()
        key_m = re.search(r'secrets-encryption:\s*["\']?([0-9a-fA-F]{64})["\']?', text)
        ref_m = re.search(r'refreshToken:\s*["\'](secure://[^\'"]+)["\']', text)
        if not key_m or not ref_m:
            continue
        encryption_key = key_m.group(1)
        encrypted_refresh = ref_m.group(1)
        decrypt_js = PROJECT_ROOT / "scripts" / "decrypt-secret.js"
        if not decrypt_js.exists():
            print("scripts/decrypt-secret.js not found", file=sys.stderr)
            continue
        builder_root = str(script_path.parent.parent.parent)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".enc", delete=False) as f:
            f.write(encrypted_refresh)
            enc_file = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as f:
            f.write(encryption_key)
            key_file = f.name
        try:
            result = subprocess.run(["node", str(decrypt_js), builder_root, enc_file, key_file], capture_output=True, text=True, timeout=10, cwd=str(PROJECT_ROOT))
            if result.returncode == 0 and result.stdout:
                print(result.stdout.strip())
                return 0
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        finally:
            os.unlink(enc_file)
            os.unlink(key_file)
        break
    print("No config with refreshToken found or decryption failed.", file=sys.stderr)
    return 1

if __name__ == "__main__":
    sys.exit(main())
