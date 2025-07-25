"""
Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Optional

from pxr import UsdShade, UsdGeom, Sdf
from material_classes import MaterialData

# Configure module-level logger
logger = logging.getLogger(__name__)





# Mapping of shader identifiers to their texture input bindings:
TEXTURE_BINDINGS: Dict[str, Dict[str, tuple]] = {
    'UsdPreviewSurface': {
        'albedo': ('diffuseColor', 'rgb'),
        'metallic': ('metallic', 'r'),
        'roughness': ('roughness', 'r'),
        'normal': ('normal', 'rgb'),
        'opacity': ('opacity', 'rgb'),
        'occlusion': ('occlusion', 'r'),
    },
    'arnold:standard_surface': {
        'albedo': ('base_color', 'rgba'),
        'metallic': ('metalness', 'r'),
        'roughness': ('specular_roughness', 'r'),
        'normal': ('normal', 'rgb'),
        'opacity': ('opacity', 'r'),
    },
    'ND_standard_surface_surfaceshader': {
        'albedo': ('base_color', 'rgba'),
        'metallic': ('metalness', 'r'),
        'roughness': ('specular_roughness', 'r'),
        'normal': ('normal', 'rgb'),
    },
}



def sanitize_identifier(name):
    """
    Convert an arbitrary string into a valid USD identifier.

    Args:
        name (str): Original name string.

    Returns:
        str: A sanitized identifier.
    """
    sanitized = re.sub(r"[^\w/]+", "_", name)
    if not sanitized:
        sanitized = '_'

    if not sanitized[0].isalpha() and sanitized[0] not in ['/', '_']:
        sanitized = f"_{sanitized}"
    return sanitized


def ensure_scope(stage, path):
    """
    Ensure that a Scope prim exists at the given path. If not, define it.

    Args:
        stage (Usd.Stage): The USD stage.
        path (str): Absolute prim path for the Scope.

    Returns:
        UsdGeom.Scope: The existing or newly defined Scope.
    """
    prim = stage.GetPrimAtPath(path)
    if not prim:
        return UsdGeom.Scope.Define(stage, path)
    return UsdGeom.Scope(prim)



class USDShaderCreator:
    """
    Creates a collect-material prim on a USD stage with UsdPreview, Arnold, and MaterialX shaders.
    """
    def __init__(self, stage, material_data, parent_prim='/scene/material_py', create_usd_preview=True, create_arnold=True, create_mtlx=False):
        """
        Initialize the shader creator.

        Args:
            stage (Usd.Stage): The USD stage to modify.
            material_data (MaterialData): Textures and prim assignments.
            parent_prim (str): Base prim path under which to create materials.
            create_usd_preview (bool): Add UsdPreviewSurface shader if True.
            create_arnold (bool): Add Arnold standard_surface shader if True.
            create_mtlx (bool): Add MaterialX standard_surface shader if True.
        """
        self.stage = stage
        self.material_data = material_data
        self.parent_prim = sanitize_identifier(parent_prim)
        self.engines = {'usdpreview': create_usd_preview, 'arnold': create_arnold, 'materialx': create_mtlx}

    def create(self):
        """
        Create the collect-material, attach shaders, and bind to prims.

        Returns:
            UsdShade.Material: The newly created collect-material.
        """
        ensure_scope(self.stage, self.parent_prim)
        collect_path = f"{self.parent_prim}/{sanitize_identifier(self.material_data.material_name)}_collect"
        logger.debug("Defining collect-material at %s", collect_path)
        material = UsdShade.Material.Define(self.stage, collect_path)
        material.CreateInput('inputnum', Sdf.ValueTypeNames.Int).Set(2)
        if self.engines['usdpreview']:
            self._add_usdpreview(material, collect_path)
        if self.engines['arnold']:
            self._add_arnold(material, collect_path)
        if self.engines['materialx']:
            self._add_mtlx(material, collect_path)
        self._bind_to_prims(material)
        return material

    def _add_usdpreview(self, collect_mat, collect_path):
        """
        Create and connect a UsdPreviewSurface shader network.
        """
        nodegraph_path = f"{collect_path}/UsdPreviewNodeGraph"
        self.stage.DefinePrim(nodegraph_path, 'NodeGraph')
        shader_path = f"{nodegraph_path}/UsdPreviewSurface"
        shader = UsdShade.Shader.Define(self.stage, shader_path)
        shader.CreateIdAttr('UsdPreviewSurface')
        collect_mat.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
        self._populate_textures(shader, 'UsdPreviewSurface')

    def _add_arnold(self, collect_mat, collect_path):
        """
        Create and connect an Arnold standard_surface shader network.
        """
        shader_path = f"{collect_path}/arnold_standard_surface"
        shader = UsdShade.Shader.Define(self.stage, shader_path)
        shader.CreateIdAttr('arnold:standard_surface')
        material_prim = shader.GetPrim().GetParent()
        arnold_mat = UsdShade.Material.Define(self.stage, material_prim.GetPath())
        arnold_mat.CreateOutput('arnold:surface', Sdf.ValueTypeNames.Token).ConnectToSource(shader.ConnectableAPI(), 'surface')
        self._initialize_arnold_defaults(shader)
        self._populate_textures(shader, 'arnold:standard_surface', material_prim)
        collect_mat.CreateOutput('arnold:surface', Sdf.ValueTypeNames.Token).ConnectToSource(shader.ConnectableAPI(), 'surface')

    def _add_mtlx(self, collect_mat, collect_path):
        """
        Create and connect a MaterialX standard_surface shader network.
        """
        shader_path = f"{collect_path}/mtlx_standard_surface"
        shader = UsdShade.Shader.Define(self.stage, shader_path)
        shader.CreateIdAttr('ND_standard_surface_surfaceshader')
        material_prim = shader.GetPrim().GetParent()
        mtlx_mat = UsdShade.Material.Define(self.stage, material_prim.GetPath())
        mtlx_mat.CreateOutput('mtlx:surface', Sdf.ValueTypeNames.Token).ConnectToSource(shader.ConnectableAPI(), 'surface')
        self._initialize_mtlx_defaults(shader)
        self._populate_textures(shader, 'ND_standard_surface_surfaceshader', material_prim)
        collect_mat.CreateOutput('mtlx:surface', Sdf.ValueTypeNames.Token).ConnectToSource(shader.ConnectableAPI(), 'surface')

    def _populate_textures(self, shader, shader_id, material_prim=None):
        """
        Create texture shaders and connect them based on TEXTURE_BINDINGS.

        Args:
            shader (UsdShade.Shader): Target shader.
            shader_id (str): Identifier key in TEXTURE_BINDINGS.
            material_prim (Usd.Prim, optional): Parent prim for textures.
        """
        bindings = TEXTURE_BINDINGS.get(shader_id, {})
        parent = material_prim or shader.GetPrim().GetParent()
        for tex_key, tex_info in self.material_data.textures.items():
            binding = bindings.get(tex_key)
            if not binding:
                logger.warning("No binding for %s on shader %s", tex_key, shader_id)
                continue
            usd_input, channel = binding
            tex_path = f"{parent.GetPath()}/{sanitize_identifier(tex_key)}Texture"
            tex_shader = UsdShade.Shader.Define(self.stage, tex_path)
            node_id = 'UsdUVTexture' if 'Preview' in shader_id else ('arnold:image' if 'arnold' in shader_id else 'ND_image_color3')
            tex_shader.CreateIdAttr(node_id)
            file_attr = 'file' if node_id == 'UsdUVTexture' else ('filename' if 'arnold' in shader_id else 'file')
            tex_shader.CreateInput(file_attr, Sdf.ValueTypeNames.Asset).Set(tex_info.file_path)
            if node_id == 'UsdUVTexture':
                reader = UsdShade.Shader.Define(self.stage, f"{parent.GetPath()}/TexCoordReader")
                reader.CreateIdAttr('UsdPrimvarReader_float2')
                reader.CreateInput('varname', Sdf.ValueTypeNames.Token).Set('st')
                tex_shader.CreateInput('st', Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(), 'result')
            shader.CreateInput(usd_input, Sdf.ValueTypeNames.Float3).ConnectToSource(tex_shader.ConnectableAPI(), channel)

    def _initialize_arnold_defaults(self, shader):
        """
        Set default inputs for Arnold standard_surface.
        """
        defaults = {'base': 1.0, 'base_color': (0.8, 0.8, 0.8), 'metalness': 0.0, 'specular': 1.0, 'opacity': (1.0, 1.0, 1.0)}
        for name, val in defaults.items():
            ty = Sdf.ValueTypeNames.Float3 if isinstance(val, tuple) else Sdf.ValueTypeNames.Float
            shader.CreateInput(name, ty).Set(val)

    def _initialize_mtlx_defaults(self, shader):
        """
        Set default inputs for MaterialX standard_surface.
        """
        defaults = {'base': 1.0, 'base_color': (0.8, 0.8, 0.8), 'coat': 0.0, 'coat_roughness': 0.1, 'emission': 0.0}
        for name, val in defaults.items():
            ty = Sdf.ValueTypeNames.Float3 if isinstance(val, tuple) else Sdf.ValueTypeNames.Float
            shader.CreateInput(name, ty).Set(val)

    def _bind_to_prims(self, material):
        """
        Bind the material to all prims in material_data.

        Args:
            material (UsdShade.Material): The material to bind.
        """
        for prim in self.material_data.prims_assigned_to_material:
            UsdShade.MaterialBindingAPI(prim).Bind(material)
            logger.debug("Bound material %s to prim %s", material.GetPath(), prim.GetPath())
