"""
Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

from pxr import UsdShade, Usd


@dataclass
class TextureInfo:
    file_path: str
    traversal_path: str
    connected_input: Optional[str] = None

    def __str__(self):
        return f"TextureInfo(file_path={self.file_path}, traversal_path={self.traversal_path}, connected_input={self.connected_input})"


@dataclass
class NodeParameter:
    """
    Represents a parameter of a node in a material network.

    Attributes:
        generic_name (Optional[str]): A standardized name for the parameter, if applicable.
        value (Optional[str]): The value of the parameter.
    """
    generic_name: Optional[str] = None
    generic_type: Optional[str] = None
    direction: Optional[str] = None  # 'input' or 'output'
    value: Optional[any] = None

    def __repr__(self):
        return f"NodeParameter(generic_name={self.generic_name}, value={self.value})"

@dataclass
class NodeInfo:
    """
    Represents a node in a material network.

    Attributes:
        node_type (str): The type of the node.
        node_name (str): The name of the node.
        node_path (str): The path for the node.
        parameters (List[NodeParameter]): A list of parameters associated with the node.
        connection_info: (dict[str, dict[str, Any]]): a dictionary for node connection information.
        children_list (List['NodeInfo']): A list of child nodes connected to this node.
        is_output_node (bool): Whether this node is an output node.
        output_type (Optional[str]): The type of output, e.g., 'surface', 'displacement', etc.
        position (Optional[int, int]): Position of the node in the material network.
    """
    node_type: str
    node_name: str
    node_path: str
    parameters: List[NodeParameter]
    connection_info: dict[str, dict[str, Any]] = field(default_factory=dict)  # {"input": {"index": int, "parm": str}, "output": {...}}
    children_list: list['NodeInfo'] = field(default_factory=list)
    is_output_node: bool = False
    output_type: Optional[str] = None
    position: Optional[list[float, float]] = None



@dataclass
class MaterialData:
    """
    Represents the data for a material, including its textures and nodes.

    Attributes:
        material_name (str): The name of the material.
        material_path (Optional[str]): The path to the material in the USD stage.
        textures (Dict[str, TextureInfo]): A dictionary mapping texture names to their TextureInfo objects.
    """
    material_name: str
    material_path: Optional[str] = None
    textures: Dict[str, TextureInfo] = field(default_factory=dict)  # e.g. {'albedo:TextureInfo(file_path='F:\\unsplash.jpg', traversal_path='', connected_input='')}

    def __repr__(self):
        return self._pretty_print()

    def _pretty_print(self):
        return f"MaterialData(material_name={self.material_name}, textures={self.textures})"

