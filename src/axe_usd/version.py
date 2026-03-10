"""Version helpers for the Axe USD plugin."""

from __future__ import annotations

from importlib import metadata

from ._project_version import read_project_version


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

    return read_project_version() or "unknown"


__all__ = ["get_version"]
