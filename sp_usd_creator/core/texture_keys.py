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
    lower_path = path.lower()
    for token, slot in _TOKEN_SLOTS:
        if token in lower_path:
            return slot
    return None
