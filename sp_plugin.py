"""
Thin wrapper to expose the Substance Painter entry points.
"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

PACKAGE_DIR = ROOT_DIR / "sp_usd_creator"
if not PACKAGE_DIR.exists():
    raise ModuleNotFoundError(
        "sp_usd_creator package not found. Ensure sp_usd_creator/ exists next to sp_plugin.py."
    )

from sp_usd_creator.dcc.substance_plugin import start_plugin, close_plugin

__all__ = ["start_plugin", "close_plugin"]
