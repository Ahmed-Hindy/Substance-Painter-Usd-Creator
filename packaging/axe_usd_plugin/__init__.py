"""
Substance Painter entry point for the Axe USD plugin.
"""
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent
PACKAGE_DIR = PLUGIN_DIR / "axe_usd"

if not PACKAGE_DIR.exists():
    raise ModuleNotFoundError(
        "axe_usd package not found. Ensure axe_usd/ is inside the axe_usd_plugin folder."
    )

from .axe_usd.dcc.substance_painter.substance_plugin import start_plugin, close_plugin  # noqa: E402

__all__ = ["start_plugin", "close_plugin"]
