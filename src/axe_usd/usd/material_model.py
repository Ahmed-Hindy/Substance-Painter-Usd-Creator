"""Shared data helpers for USD material processing."""

from dataclasses import dataclass
import logging
from pathlib import Path, PurePosixPath
from typing import Dict, Mapping, Optional

from .types import MaterialTextureDict


SLOT_ALIASES = {
    "height": "displacement",
}

_LOGGER = logging.getLogger(__name__)


def normalize_slot_name(
    slot: str, slot_aliases: Mapping[str, str] = SLOT_ALIASES
) -> str:
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
            active_logger.debug(
                "Overriding texture slot '%s' with '%s'.", normalized_slot, slot
            )
        normalized[normalized_slot] = info
    return normalized


def normalize_asset_path(path: str) -> str:
    if not path:
        return path
    path_str = str(path)
    is_absolute = Path(path_str).is_absolute()
    normalized = path_str.replace("\\", "/")
    if normalized.startswith("./") or normalized.startswith("../"):
        return normalized
    if is_absolute:
        return normalized
    return f"./{normalized}"


def apply_texture_format_override(path: str, override: Optional[str]) -> str:
    normalized = normalize_asset_path(path)
    if not override:
        return normalized
    ext = override if override.startswith(".") else f".{override}"
    prefix = "./" if normalized.startswith("./") else ""
    working = normalized[2:] if prefix else normalized
    posix_path = PurePosixPath(working)
    if posix_path.suffix:
        posix_path = posix_path.with_suffix(ext)
    else:
        posix_path = PurePosixPath(f"{posix_path}{ext}")
    return f"{prefix}{posix_path.as_posix()}"


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
    def from_mapping(
        cls, texture_format_overrides: Optional[Mapping[str, str]]
    ) -> "TextureFormatOverrides":
        if not texture_format_overrides:
            return cls({})
        normalized: Dict[str, str] = {}
        for key, value in texture_format_overrides.items():
            normalized[key.lower()] = value
        return cls(normalized)

    def for_renderer(self, renderer: str) -> Optional[str]:
        if renderer == "usd_preview":
            return self.overrides.get(renderer)
        if renderer in self.overrides:
            return self.overrides.get(renderer)
        return "png"
