"""
Integration test conftest: load .env and optionally apply aifabrix config.

- Loads .env from project root.
- If .aifabrix/config.yaml exists (AIFABRIX_HOME, /workspace/.aifabrix, or ~/.aifabrix),
  sets MISO_CONTROLLER_URL from config's "controller" so tests hit the right controller.
- If TEST_REFRESH_TOKEN is not set but TEST_REFRESH_TOKEN_FILE is set, reads refresh
  token from that file (e.g. after decrypting with aifabrix CLI).

To run the refresh-token test: set TEST_REFRESH_TOKEN or TEST_REFRESH_TOKEN_FILE to a
file path containing the decrypted refresh token (from aifabrix config.yaml / device).
"""

import os
import re
from pathlib import Path

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


def _apply_refresh_token_file():
    """Set TEST_REFRESH_TOKEN from file if TEST_REFRESH_TOKEN_FILE is set."""
    if os.environ.get("TEST_REFRESH_TOKEN"):
        return
    path = os.environ.get("TEST_REFRESH_TOKEN_FILE")
    if not path:
        return
    p = Path(path)
    if not p.exists() or not p.is_file():
        return
    try:
        token = p.read_text().strip()
        if token:
            os.environ["TEST_REFRESH_TOKEN"] = token
    except Exception:
        pass


# Run once at import time (before any integration test collects)
_apply_aifabrix_config()
_apply_refresh_token_file()
