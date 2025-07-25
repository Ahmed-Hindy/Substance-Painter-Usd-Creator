from dataclasses import dataclass, field
from typing import Optional, Dict, List

from pxr import UsdShade, Usd


@dataclass
class TextureInfo:
    file_path: str
    traversal_path: str
    connected_input: Optional[str] = None

    def __str__(self):
        return f"TextureInfo(file_path={self.file_path}, traversal_path={self.traversal_path}, connected_input={self.connected_input})"


@dataclass
class MaterialData:
    material_name: str
    material_path: Optional[str] = None
    usd_material: Optional[UsdShade.Material] = None
    textures: Dict[str, TextureInfo] = field(default_factory=dict)  # e.g. {'albedo:TextureInfo(file_path='F:\\unsplash.jpg', traversal_path='', connected_input='')}
    prims_assigned_to_material: List[Usd.Prim] = field(default_factory=list)


    def __str__(self):
        return self._pretty_print()

    def __repr__(self):
        return self._pretty_print()

    def _pretty_print(self):
        return f"MaterialData(prim_path={self.material_path})"
        # data_dict = asdict(self)
        # return pformat(data_dict, indent=4)
