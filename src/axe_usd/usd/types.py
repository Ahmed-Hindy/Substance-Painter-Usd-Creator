from typing import Dict, List, TypedDict


class MaterialTextureInfo(TypedDict):
    """Texture metadata for a material slot.

    Attributes:
        mat_name: Material identifier.
        path: File path to the texture.
    """

    mat_name: str
    path: str


class MaterialTextureInfoWithMeshes(MaterialTextureInfo, total=False):
    """Optional mesh name assignments for a material slot."""

    mesh_names: List[str]


MaterialTextureDict = Dict[str, MaterialTextureInfoWithMeshes]
MaterialTextureList = List[MaterialTextureDict]
