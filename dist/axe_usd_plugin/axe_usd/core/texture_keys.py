import re
from typing import Optional


_TOKEN_SLOTS = [
    ("base_color", "basecolor"),
    ("basecolor", "basecolor"),
    ("albedo", "basecolor"),
    ("diffuse", "basecolor"),
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


def slot_from_path(path: str) -> Optional[str]:
    """Resolve a texture slot name from a file path.

    Args:
        path: Texture file path to inspect.

    Returns:
        Optional[str]: The normalized slot name if matched.
    """
    lower_path = path.lower()
    for token, slot in _TOKEN_SLOTS:
        pattern = rf"(^|[^a-z0-9]){re.escape(token)}([^a-z0-9]|$)"
        if re.search(pattern, lower_path):
            return slot
    return None
