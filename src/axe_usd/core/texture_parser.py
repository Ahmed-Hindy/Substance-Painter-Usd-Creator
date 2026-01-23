import logging
from typing import List

from .models import MaterialBundle
from .texture_keys import slot_from_path


logger = logging.getLogger(__name__)


def _material_name_from_key(key) -> str:
    if isinstance(key, (list, tuple)) and key:
        return str(key[0])
    return str(key)


def parse_textures(textures_dict) -> List[MaterialBundle]:
    material_bundles: List[MaterialBundle] = []

    for key, paths in textures_dict.items():
        material_name = _material_name_from_key(key)
        textures = {}

        for path in paths:
            slot = slot_from_path(str(path))
            if not slot:
                logger.debug("Skipping unrecognized texture path: %s", path)
                continue
            textures[slot] = str(path)

        if textures:
            material_bundles.append(MaterialBundle(name=material_name, textures=textures))
        else:
            logger.info("Skipping material '%s' with no recognized textures.", material_name)

    return material_bundles
