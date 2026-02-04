"""Preset storage and matching helpers for the Substance Painter UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional


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


def load_presets(path: Path, logger) -> Dict[str, Dict[str, object]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load presets: %s", exc)
        return {}
    if not isinstance(data, dict):
        return {}
    for preset in data.values():
        if isinstance(preset, dict):
            preset.pop("primitive_path", None)
            preset.pop("publish_directory", None)
    return data


def save_presets(path: Path, presets: Dict[str, Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, indent=2), encoding="utf-8")


def match_preset_name(
    data: Dict[str, object], presets: Dict[str, Dict[str, object]]
) -> Optional[str]:
    for name, preset in presets.items():
        if preset == data:
            return name
    for name, preset in BUILTIN_PRESETS.items():
        if _matches_builtin(data, preset):
            return name
    return None


def _matches_builtin(data: Dict[str, object], preset: Dict[str, object]) -> bool:
    for key in ("usdpreview", "arnold", "materialx", "openpbr"):
        if bool(data.get(key)) != bool(preset.get(key)):
            return False
    return True
