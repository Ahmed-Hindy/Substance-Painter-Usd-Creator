import logging
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

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


def parse_textures(
    textures_dict: TexturePathMap,
    mesh_name_map: Optional[Mapping[str, Sequence[str]]] = None,
) -> List[MaterialBundle]:
    """Parse texture exports into material bundles.

    Args:
        textures_dict: Mapping of texture set keys to file paths.
        mesh_name_map: Optional mapping of texture set name to mesh names.

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

    if mesh_name_map is not None and not isinstance(mesh_name_map, Mapping):
        raise TextureParsingError(
            "Invalid mesh name mapping type",
            details={"type": type(mesh_name_map).__name__},
        )

    mesh_name_map = mesh_name_map or {}

    material_bundles: List[MaterialBundle] = []

    for key, paths in textures_dict.items():
        material_name = _material_name_from_key(key)
        textures: Dict[str, str] = {}
        mesh_names: Tuple[str, ...] = ()

        if mesh_name_map:
            raw_mesh_names = mesh_name_map.get(material_name, ())
            if raw_mesh_names:
                if isinstance(raw_mesh_names, (str, bytes)):
                    raw_mesh_names = [raw_mesh_names]
                cleaned: list[str] = []
                for mesh_name in raw_mesh_names:
                    mesh_str = str(mesh_name)
                    if mesh_str and mesh_str not in cleaned:
                        cleaned.append(mesh_str)
                mesh_names = tuple(cleaned)

        for path in paths:
            slot = slot_from_path(str(path))
            if not slot:
                logger.debug("Skipping unrecognized texture path: %s", path)
                continue
            textures[slot] = str(path)

        if textures:
            material_bundles.append(
                MaterialBundle(
                    name=material_name, textures=textures, mesh_names=mesh_names
                )
            )
        else:
            logger.info(
                "Skipping material '%s' with no recognized textures.", material_name
            )

    return material_bundles
