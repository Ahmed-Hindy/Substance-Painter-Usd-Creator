"""
Substance Painter entry point for the Axe USD plugin.
"""
from pathlib import Path
import sys

PLUGIN_DIR = Path(__file__).resolve().parent

if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

PACKAGE_DIR = PLUGIN_DIR / "axe_usd"
if not PACKAGE_DIR.exists():
    raise ModuleNotFoundError(
        "axe_usd package not found. Ensure axe_usd/ is next to axe_usd_plugin.py."
    )

from axe_usd.dcc.substance_plugin import start_plugin, close_plugin  # noqa: E402

__all__ = ["start_plugin", "close_plugin"]
