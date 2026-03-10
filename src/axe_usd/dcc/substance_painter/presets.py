"""Preset storage and matching helpers for the Substance Painter UI."""

from __future__ import annotations

from typing import Dict


BUILTIN_PRESETS: Dict[str, Dict[str, object]] = {
    "USD Preview Only": {
        "usdpreview": True,
        "arnold": False,
        "materialx": False,
        "openpbr": False,
    },
    "OpenPBR Only": {
        "usdpreview": False,
        "arnold": False,
        "materialx": False,
        "openpbr": True,
    },
    "Full": {
        "usdpreview": True,
        "arnold": True,
        "materialx": True,
        "openpbr": True,
    },
}


def _matches_builtin(data: Dict[str, object], preset: Dict[str, object]) -> bool:
    for key in ("usdpreview", "arnold", "materialx", "openpbr"):
        if bool(data.get(key)) != bool(preset.get(key)):
            return False
    return True
