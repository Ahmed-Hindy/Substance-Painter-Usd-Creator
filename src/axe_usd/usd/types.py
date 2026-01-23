from typing import Dict, List, TypedDict


class MaterialTextureInfo(TypedDict):
    mat_name: str
    path: str


MaterialTextureDict = Dict[str, MaterialTextureInfo]
MaterialTextureList = List[MaterialTextureDict]
