"""
Integration test conftest: load .env and optionally apply aifabrix config.

- Loads .env from project root.
- If .aifabrix/config.yaml exists (AIFABRIX_HOME, /workspace/.aifabrix, or ~/.aifabrix),
  sets MISO_CONTROLLER_URL from config's "controller" so tests hit the right controller.
- If TEST_REFRESH_TOKEN is not set but TEST_REFRESH_TOKEN_FILE is set, reads refresh
  token from that file (e.g. after decrypting with aifabrix CLI).
- Before any test runs, runs `aifabrix auth status --validate`. If it fails (non-zero exit),
  the session is aborted and the command output is shown (no tests are skipped).

To run the refresh-token test: set TEST_REFRESH_TOKEN or TEST_REFRESH_TOKEN_FILE, or use the decrypted refresh token from .aifabrix/config.yaml (conftest tries to decrypt via aifabrix-builder/lib/utils/secrets-encryption.js). Alternatively set TEST_REFRESH_TOKEN or TEST_REFRESH_TOKEN_FILE to a
file path containing the decrypted refresh token (from aifabrix config.yaml / device).
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

# Project root: tests/integration/conftest.py -> project root
_project_root = Path(__file__).resolve().parent.parent.parent
_env_path = _project_root / ".env"

# Load .env first so aifabrix config can fill in only what's missing
if _env_path.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env_path)
    except ImportError:
        pass


def _aifabrix_config_paths():
    """Yield candidate paths for .aifabrix/config.yaml."""
    home = Path.home()
    yield os.environ.get("AIFABRIX_HOME")
    yield "/workspace/.aifabrix"
    yield str(home / ".aifabrix")
    yield str(_project_root / ".aifabrix")


def _read_controller_from_config(path: Path) -> str | None:
    """Read controller URL from aifabrix config.yaml without PyYAML."""
    if not path.exists() or not path.is_file():
        return None
    try:
        text = path.read_text()
    except Exception:
        return None
    # Match controller: 'http://...' or controller: "http://..."
    m = re.search(r"controller:\s*['\"]([^'\"]+)['\"]", text)
    return m.group(1).strip() if m else None


def _apply_aifabrix_config():
    """Set MISO_CONTROLLER_URL from .aifabrix/config.yaml when that file exists.

    When running in an aifabrix workspace (e.g. /workspace/.aifabrix/config.yaml),
    use the controller URL from config so integration tests hit the right controller.
    """
    for base in _aifabrix_config_paths():
        if not base:
            continue
        config_path = Path(base) / "config.yaml"
        url = _read_controller_from_config(config_path)
        if url:
            os.environ["MISO_CONTROLLER_URL"] = url
            break


def _decrypt_refresh_token_from_config(
    config_path: Path, encryption_key: str, encrypted_value: str
) -> str | None:
    """Decrypt refresh token using aifabrix-builder secrets-encryption.js (AES-256-GCM, secure:// format)."""
    script_candidates = [
        Path(os.environ.get("AIFABRIX_BUILDER_ROOT", ""))
        / "lib"
        / "utils"
        / "secrets-encryption.js",
        _project_root.parent / "aifabrix-builder" / "lib" / "utils" / "secrets-encryption.js",
        Path("/workspace/aifabrix-builder/lib/utils/secrets-encryption.js"),
    ]
    script_path = None
    for p in script_candidates:
        if p and p.exists() and p.is_file():
            script_path = p
            break
    if not script_path:
        return None
    import tempfile

    decrypt_js = _project_root / "scripts" / "decrypt-secret.js"
    if not decrypt_js.exists():
        return None
    builder_root = str(script_path.parent.parent.parent)
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".enc", delete=False) as f:
            f.write(encrypted_value)
            enc_file = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as f:
            f.write(encryption_key)
            key_file = f.name
        try:
            result = subprocess.run(
                ["node", str(decrypt_js), builder_root, enc_file, key_file],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(_project_root),
            )
            if result.returncode == 0 and result.stdout:
                return result.stdout.strip()
        finally:
            os.unlink(enc_file)
            os.unlink(key_file)
    except Exception:
        pass
    return None


def _apply_refresh_token_from_aifabrix_config():
    """Set TEST_REFRESH_TOKEN by decrypting device.refreshToken from .aifabrix/config.yaml using secrets-encryption.js."""
    if os.environ.get("TEST_REFRESH_TOKEN"):
        return
    for base in _aifabrix_config_paths():
        if not base:
            continue
        config_path = Path(base) / "config.yaml"
        if not config_path.exists() or not config_path.is_file():
            continue
        try:
            text = config_path.read_text()
        except Exception:
            continue
        key_m = re.search(r'secrets-encryption:\s*["\']?([0-9a-fA-F]{64})["\']?', text)
        ref_m = re.search(r'refreshToken:\s*["\'](secure://[^\'"]+)["\']', text)
        if not key_m or not ref_m:
            continue
        encryption_key = key_m.group(1)
        encrypted_refresh = ref_m.group(1)
        decrypted = _decrypt_refresh_token_from_config(
            config_path, encryption_key, encrypted_refresh
        )
        if decrypted:
            os.environ["TEST_REFRESH_TOKEN"] = decrypted
            return


def _apply_refresh_token_file():
    """Set TEST_REFRESH_TOKEN from env, file, or decrypted .aifabrix/config.yaml (via secrets-encryption.js)."""
    if os.environ.get("TEST_REFRESH_TOKEN"):
        return
    token = os.environ.get("REFRESH_TOKEN") or os.environ.get("MISO_REFRESH_TOKEN")
    if token:
        os.environ["TEST_REFRESH_TOKEN"] = token
        return
    path = os.environ.get("TEST_REFRESH_TOKEN_FILE")
    if not path:
        _apply_refresh_token_from_aifabrix_config()
        return
    p = Path(path)
    if not p.exists() or not p.is_file():
        _apply_refresh_token_from_aifabrix_config()
        return
    try:
        token = p.read_text().strip()
        if token:
            os.environ["TEST_REFRESH_TOKEN"] = token
    except Exception:
        _apply_refresh_token_from_aifabrix_config()


def _validate_aifabrix_auth() -> None:
    """Run aifabrix auth status --validate; exit with error if not OK (no skips allowed)."""
    try:
        result = subprocess.run(
            ["aifabrix", "auth", "status", "--validate"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_project_root),
        )
    except FileNotFoundError:
        pytest.exit(
            "Integration tests require 'aifabrix auth status --validate' to succeed. "
            "aifabrix CLI not found. Install it and run: aifabrix auth status --validate",
            returncode=1,
        )
    except subprocess.TimeoutExpired:
        pytest.exit("aifabrix auth status --validate timed out.", returncode=1)
    except Exception as e:
        pytest.exit("aifabrix auth status --validate failed: %s" % e, returncode=1)

    if result.returncode != 0:
        msg = (
            "aifabrix auth status --validate failed (exit code %d). Fix auth and re-run."
            % result.returncode
        )
        if result.stdout:
            msg += "\nstdout:\n%s" % result.stdout
        if result.stderr:
            msg += "\nstderr:\n%s" % result.stderr
        pytest.exit(msg, returncode=1)


# Run once at import time (before any integration test collects)
_apply_aifabrix_config()
_apply_refresh_token_file()


def pytest_sessionstart(session):
    """Validate auth before any integration test runs. No skips: fail fast if auth invalid."""
    _validate_aifabrix_auth()
