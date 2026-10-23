"""Static package metadata mirror tests."""

import ast
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _setup_keywords() -> dict[str, Any]:
    """Return literal setup() keyword values without executing setup.py."""
    tree = ast.parse((ROOT / "setup.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "setup"
    ]
    assert len(calls) == 1
    return {
        keyword.arg: ast.literal_eval(keyword.value)
        for keyword in calls[0].keywords
        if keyword.arg is not None
        and keyword.arg
        in {
            "version",
            "python_requires",
            "install_requires",
            "extras_require",
            "classifiers",
        }
    }


def test_setup_metadata_mirrors_pyproject() -> None:
    """Keep legacy setup metadata aligned with effective PEP 621 metadata."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    setup = _setup_keywords()

    assert setup["version"] == project["version"]
    assert setup["python_requires"] == project["requires-python"]
    assert setup["install_requires"] == project["dependencies"]
    assert setup["extras_require"] == project["optional-dependencies"]


def test_supported_python_classifiers_match() -> None:
    """Keep the supported Python classifier set identical in both manifests."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    setup = _setup_keywords()
    prefix = "Programming Language :: Python :: 3."

    pyproject_versions = {item for item in project["classifiers"] if item.startswith(prefix)}
    setup_versions = {item for item in setup["classifiers"] if item.startswith(prefix)}

    assert pyproject_versions == setup_versions
    assert pyproject_versions == {f"{prefix}{minor}" for minor in (11, 12, 13, 14)}


def test_pyproject_declares_every_importable_package() -> None:
    """Keep explicit setuptools package declarations complete."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = set(config["tool"]["setuptools"]["packages"])
    discovered = {
        str(init_file.parent.relative_to(ROOT)).replace("/", ".")
        for init_file in (ROOT / "miso_client").rglob("__init__.py")
    }

    assert declared == discovered
