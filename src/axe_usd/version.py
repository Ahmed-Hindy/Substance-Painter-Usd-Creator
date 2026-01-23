"""Version helpers for the Axe USD plugin."""
from __future__ import annotations

from importlib import metadata
from pathlib import Path
from typing import Optional
import re


def _version_from_pyproject() -> Optional[str]:
    repo_root = Path(__file__).resolve().parents[2]
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        content = pyproject.read_text(encoding="utf-8")
    except Exception:
        return None

    in_project = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project or not stripped.startswith("version"):
            continue
        match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
        if match:
            return match.group(1)
    return None


def get_version() -> str:
    """Return the plugin version string with safe fallbacks."""
    try:
        from . import _version  # type: ignore

        version = getattr(_version, "__version__", None)
        if version:
            return str(version)
    except Exception:
        pass

    try:
        return metadata.version("sp-usd-creator")
    except Exception:
        pass

    return _version_from_pyproject() or "unknown"


__all__ = ["get_version"]
