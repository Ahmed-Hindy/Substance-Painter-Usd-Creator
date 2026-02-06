"""
Substance Painter entry point for the Axe USD plugin.
"""

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

PLUGIN_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = PLUGIN_DIR / "axe_usd"

if not PACKAGE_DIR.exists():
    raise ModuleNotFoundError(
        "axe_usd package not found. Ensure axe_usd/ is inside the axe_usd_plugin folder."
    )


def _ensure_dependencies() -> None:
    # Load USD dependencies before any imports that require pxr.
    from .axe_usd.dcc.substance_painter import pxr_loader

    if not pxr_loader.load_dependencies(PLUGIN_DIR):
        raise ImportError(
            "USD dependencies could not be loaded. "
            "Verify the plugin bundle includes the correct USD binaries."
        )


_ensure_dependencies()

_SUBSTANCE_PLUGIN_NAME = (
    f"{__name__}.axe_usd.dcc.substance_painter.substance_plugin"
)
_PXR_LOADER_NAME = f"{__name__}.axe_usd.dcc.substance_painter.pxr_loader"
_substance_plugin: Optional[ModuleType] = None


def _get_substance_plugin() -> Optional[ModuleType]:
    global _substance_plugin
    if _substance_plugin is not None:
        return _substance_plugin
    module = sys.modules.get(_SUBSTANCE_PLUGIN_NAME)
    if module is not None:
        _substance_plugin = module
    return module


def _import_substance_plugin() -> ModuleType:
    global _substance_plugin
    if _substance_plugin is None:
        _ensure_dependencies()
        _substance_plugin = importlib.import_module(_SUBSTANCE_PLUGIN_NAME)
    return _substance_plugin


def _clear_plugin_modules(keep_dependencies: bool = True) -> None:
    prefix = f"{__name__}.axe_usd"
    keep = set()
    if keep_dependencies:
        keep.add(_PXR_LOADER_NAME)
    for name in list(sys.modules):
        if name == prefix or name.startswith(prefix + "."):
            if name in keep:
                continue
            sys.modules.pop(name, None)
    global _substance_plugin
    _substance_plugin = None
    importlib.invalidate_caches()


def reload_plugin_modules(keep_dependencies: bool = True) -> None:
    """Helper for dev hot-reload when toggling the plugin."""
    _clear_plugin_modules(keep_dependencies=keep_dependencies)


def start_plugin() -> None:
    _import_substance_plugin().start_plugin()


def close_plugin() -> None:
    module = _get_substance_plugin()
    if module is None:
        return
    try:
        module.close_plugin()
    finally:
        _clear_plugin_modules(keep_dependencies=True)


__all__ = ["start_plugin", "close_plugin", "reload_plugin_modules"]
