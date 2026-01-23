"""Shared data helpers for USD material processing."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, Mapping, Optional

from .types import MaterialTextureDict


SLOT_ALIASES = {
    "height": "displacement",
}

_LOGGER = logging.getLogger(__name__)


def normalize_slot_name(slot: str, slot_aliases: Mapping[str, str] = SLOT_ALIASES) -> str:
    normalized = slot.strip().lower()
    return slot_aliases.get(normalized, normalized)


def normalize_material_dict(
    material_dict: MaterialTextureDict,
    logger: Optional[logging.Logger] = None,
    slot_aliases: Mapping[str, str] = SLOT_ALIASES,
) -> MaterialTextureDict:
    active_logger = logger or _LOGGER
    normalized: MaterialTextureDict = {}
    for slot, info in material_dict.items():
        normalized_slot = normalize_slot_name(slot, slot_aliases=slot_aliases)
        if normalized_slot in normalized and normalized_slot != slot:
            active_logger.debug("Overriding texture slot '%s' with '%s'.", normalized_slot, slot)
        normalized[normalized_slot] = info
    return normalized


def apply_texture_format_override(path: str, override: Optional[str]) -> str:
    if not override:
        return path
    ext = override if override.startswith(".") else f".{override}"
    path_obj = Path(path)
    if path_obj.suffix:
        return str(path_obj.with_suffix(ext))
    return f"{path}{ext}"


def is_transmissive_material(
    material_name: str,
    tokens: Optional[tuple[str, ...]] = None,
) -> bool:
    if not material_name:
        return False
    active_tokens = tokens or ("glass", "glas")
    lower_name = material_name.lower()
    return any(token in lower_name for token in active_tokens)


@dataclass(frozen=True)
class TextureFormatOverrides:
    overrides: Dict[str, str]

    @classmethod
    def from_mapping(cls, texture_format_overrides: Optional[Mapping[str, str]]) -> "TextureFormatOverrides":
        if not texture_format_overrides:
            return cls({})
        normalized: Dict[str, str] = {}
        for key, value in texture_format_overrides.items():
            normalized[key.lower()] = value
        return cls(normalized)

    def for_renderer(self, renderer: str) -> Optional[str]:
        return self.overrides.get(renderer)
