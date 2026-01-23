"""
Substance Painter entry point for the AxeFX USD plugin.
"""
from pathlib import Path
import sys

PLUGIN_DIR = Path(__file__).resolve().parent

if str(PLUGIN_DIR) not in sys.path:
    sys.path.append(str(PLUGIN_DIR))

PACKAGE_DIR = PLUGIN_DIR / "sp_usd_creator"
if not PACKAGE_DIR.exists():
    raise ModuleNotFoundError(
        "sp_usd_creator package not found. Ensure sp_usd_creator/ is next to AxeFX_usd_plugin.py."
    )

from sp_usd_creator.dcc.substance_plugin import start_plugin, close_plugin

__all__ = ["start_plugin", "close_plugin"]
