"""Texture slot name resolution from file paths."""

import re
from typing import Optional


_TOKEN_SLOTS = [
    ("base_color", "basecolor"),
    ("basecolor", "basecolor"),
    ("albedo", "basecolor"),
    ("diffuse", "basecolor"),
    ("emission", "emission"),
    ("emissive", "emission"),
    ("glow", "emission"),
    ("metalness", "metalness"),
    ("metallic", "metalness"),
    ("roughness", "roughness"),
    ("normal", "normal"),
    ("opacity", "opacity"),
    ("alpha", "opacity"),
    ("occlusion", "occlusion"),
    ("ao", "occlusion"),
    ("displacement", "displacement"),
    ("height", "displacement"),
]

# Pre-compile patterns at module load to avoid rebuilding on every call.
_COMPILED_SLOTS = [
    (re.compile(rf"(^|[^a-z0-9]){re.escape(token)}([^a-z0-9]|$)"), slot)
    for token, slot in _TOKEN_SLOTS
]


def slot_from_path(path: str) -> Optional[str]:
    """Resolve a texture slot name from a file path.

    Args:
        path: Texture file path to inspect.

    Returns:
        Optional[str]: The normalized slot name if matched.
    """
    lower_path = path.lower()
    for pattern, slot in _COMPILED_SLOTS:
        if pattern.search(lower_path):
            return slot
    return None
