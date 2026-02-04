from typing import Dict, List, TypedDict


class MaterialTextureInfo(TypedDict):
    """Texture metadata for a material slot.

    Attributes:
        mat_name: Material identifier.
        path: File path to the texture.
    """

    mat_name: str
    path: str


MaterialTextureDict = Dict[str, MaterialTextureInfo]
MaterialTextureList = List[MaterialTextureDict]
