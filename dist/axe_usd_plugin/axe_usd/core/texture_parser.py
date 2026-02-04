import logging
from typing import Dict, List, Mapping, Sequence, Tuple, Union

from .exceptions import TextureParsingError
from .models import MaterialBundle
from .texture_keys import slot_from_path


logger = logging.getLogger(__name__)


TextureKey = Union[str, Tuple[str, ...]]
TexturePathMap = Mapping[TextureKey, Sequence[str]]


def _material_name_from_key(key: TextureKey) -> str:
    """Normalize a material name from a texture map key.

    Args:
        key: Texture dictionary key from Substance export.

    Returns:
        str: Material name string.
    """
    if isinstance(key, (list, tuple)) and key:
        return str(key[0])
    return str(key)


def parse_textures(textures_dict: TexturePathMap) -> List[MaterialBundle]:
    """Parse texture exports into material bundles.

    Args:
        textures_dict: Mapping of texture set keys to file paths.

    Returns:
        List[MaterialBundle]: Bundles with normalized texture slots.

    Raises:
        TextureParsingError: If textures_dict is None or not a mapping.
    """
    if textures_dict is None:
        raise TextureParsingError("Texture dictionary cannot be None")

    if not isinstance(textures_dict, Mapping):
        raise TextureParsingError(
            "Invalid texture dictionary type",
            details={"type": type(textures_dict).__name__},
        )

    material_bundles: List[MaterialBundle] = []

    for key, paths in textures_dict.items():
        material_name = _material_name_from_key(key)
        textures: Dict[str, str] = {}

        for path in paths:
            slot = slot_from_path(str(path))
            if not slot:
                logger.debug("Skipping unrecognized texture path: %s", path)
                continue
            textures[slot] = str(path)

        if textures:
            material_bundles.append(
                MaterialBundle(name=material_name, textures=textures)
            )
        else:
            logger.info(
                "Skipping material '%s' with no recognized textures.", material_name
            )

    return material_bundles
