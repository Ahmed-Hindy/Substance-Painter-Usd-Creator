"""USD Preview texture format helpers."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from .exceptions import ValidationError


class PreviewTextureFormat(Enum):
    JPG = ".jpg"
    JPEG = ".jpeg"
    PNG = ".png"

    @property
    def extension(self) -> str:
        return self.value

    @property
    def substance_file_format(self) -> str:
        if self is PreviewTextureFormat.JPG:
            return "jpg"
        if self is PreviewTextureFormat.JPEG:
            return "jpeg"
        return "png"


_SUPPORTED_PREVIEW_FORMATS = {
    ".jpg": PreviewTextureFormat.JPG,
    "jpeg": PreviewTextureFormat.JPEG,
    "png": PreviewTextureFormat.PNG,
}


def parse_preview_texture_format(
    value: Optional[str],
) -> PreviewTextureFormat:
    if value is None:
        return PreviewTextureFormat.JPG
    normalized = str(value).strip().lower()
    if not normalized:
        return PreviewTextureFormat.JPG
    preview_format = _SUPPORTED_PREVIEW_FORMATS.get(normalized)
    if preview_format:
        return preview_format
    raise ValidationError(
        "Unsupported USD Preview texture format.",
        details={
            "format": value,
            "supported_formats": [".jpg", "jpeg", "png"],
        },
    )
