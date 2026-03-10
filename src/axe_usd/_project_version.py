"""Helpers for reading project version metadata from pyproject.toml."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import re


_VERSION_RE = re.compile(r'version\s*=\s*"([^"]+)"')


def read_project_version(pyproject: Optional[Path] = None) -> Optional[str]:
    """Read the project version from pyproject.toml if available."""
    if pyproject is None:
        repo_root = Path(__file__).resolve().parents[2]
        pyproject = repo_root / "pyproject.toml"

    if not pyproject.exists():
        return None

    try:
        content = pyproject.read_text(encoding="utf-8")
    except OSError:
        return None

    in_project = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project or not stripped.startswith("version"):
            continue
        match = _VERSION_RE.match(stripped)
        if match:
            return match.group(1)
    return None


__all__ = ["read_project_version"]
