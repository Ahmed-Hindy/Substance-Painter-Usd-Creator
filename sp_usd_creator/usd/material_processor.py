"""
Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

import os
import logging
import re
import tempfile
from typing import Dict

from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

from . import utils as usd_utils



# Configure module-level logger
logger = logging.getLogger(__name__)





# Mapping of shader identifiers to their texture input bindings:
TEXTURE_BINDINGS: Dict[str, Dict[str, tuple]] = {
    'UsdPreviewSurface': {
        'basecolor': ('diffuseColor', 'rgb'),
        'metalness': ('metallic', 'r'),
        'roughness': ('roughness', 'r'),
        'normal': ('normal', 'rgb'),
        'opacity': ('opacity', 'rgb'),
        'occlusion': ('occlusion', 'r'),
    },
    'arnold:standard_surface': {
        'basecolor': ('base_color', 'rgba'),
        'metalness': ('metalness', 'r'),
        'roughness': ('specular_roughness', 'r'),
        'normal': ('normal', 'rgb'),
        'opacity': ('opacity', 'r'),
    },
    'ND_standard_surface_surfaceshader': {
        'basecolor': ('base_color', 'rgba'),
        'metalness': ('metalness', 'r'),
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


class USDShaderCreate:
    """
    Creates material prim on usd stage with Arnold, MTLX and/or UsdPreview material_dict_list. Assigns material to prims
    """

    def __init__(self, stage, material_name: str, material_dict: Dict, parent_primpath='/root/material',
                 create_usd_preview=False, usd_preview_format=None, create_arnold=False, create_mtlx=False):
        """
        :param material_dict: example:
         {
          'basecolor': 'C:/~/Documents/~/textures/03_Base_Base_color.png',
          'metalness': 'C:/~/Documents/~/textures/03_Base_Metalness.png',
          'roughness': 'C:/~/Documents/~/textures/03_Base_Roughness.png',
          'normal': 'C:/~/Documents/~/textures/03_Base_Normal_DirectX.png',
          'displacement': 'C:/~/Documents/~/textures/03_Base_Height.png',
          'occlusion': 'C:/~/Documents/~/textures/03_Base_Mixed_AO.png'
         }
        """
        self.stage = stage

        self.material_dict = material_dict
        self.material_name = material_name
        self.parent_primpath = parent_primpath
        self.create_usd_preview = create_usd_preview
        self.usd_preview_format = usd_preview_format
        self.create_arnold = create_arnold
        self.create_mtlx = create_mtlx

        # detect if it's a transmissive material:
        self.is_transmissive = self.detect_if_transmissive(self.material_name)

        self.run()


    def detect_if_transmissive(self, material_name):
        """
        detects if a material should have transmission or not based on material name,
        if a material has "glass" in its name, then transmission should be on!
        :rtype: bool
        """
        transmissive_matnames_list = ['glass', 'glas']
        is_transmissive = any(substring in material_name.lower() for substring in transmissive_matnames_list)
        if is_transmissive:
            print(f"DEBUG:  Detected Transmissive Material: '{material_name}'")

        return is_transmissive


    ###  usd_preview ###
    def _create_usd_preview_material(self, parent_path, usd_preview_format):
        material_path = f'{parent_path}/UsdPreviewMaterial'
        material = UsdShade.Material.Define(self.stage, material_path)

        nodegraph_path = f'{material_path}/UsdPreviewNodeGraph'
        self.stage.DefinePrim(nodegraph_path, 'NodeGraph')

        shader_path = f'{nodegraph_path}/UsdPreviewSurface'
        shader = UsdShade.Shader.Define(self.stage, shader_path)
        shader.CreateIdAttr("UsdPreviewSurface")

        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

        # Create textures for USD Preview Shader
        texture_types_to_inputs = {
            'basecolor': 'diffuseColor',
            'metalness': 'metallic',
            'roughness': 'roughness',
            'normal': 'normal',
            'opacity': 'opacity',
            'displacement': 'displacement',
            'height': 'displacement',
        }
        scalar_slots = {'opacity', 'metalness', 'roughness', 'displacement', 'height'}

        for tex_type, tex_dict in self.material_dict.items():
            tex_filepath = tex_dict['path']
            tex_type = tex_type.lower()  # assume all lowercase
            if tex_type not in texture_types_to_inputs:
                print(f"WARNING:  tex_type: '{tex_type}' not supported yet for usdpreview")
                continue

            if usd_preview_format:
                file_format = os.path.splitext(tex_filepath)[1].rsplit('.', 1)[1]  # e.g. 'exr'
                tex_filepath = tex_filepath.replace(file_format, usd_preview_format)

            # print(f"DEBUG:  tex_filepath: {tex_filepath}")
            input_name = texture_types_to_inputs[tex_type]
            texture_prim_path = f'{nodegraph_path}/{tex_type}Texture'
            texture_prim = UsdShade.Shader.Define(self.stage, texture_prim_path)
            texture_prim.CreateIdAttr("UsdUVTexture")
            file_input = texture_prim.CreateInput("file", Sdf.ValueTypeNames.Asset)
            file_input.Set(tex_filepath)
            # print(f"DEBUG: texture_prim_path: {texture_prim_path}")
            # print(f"DEBUG: tex_filepath: {tex_filepath}")

            wrapS = texture_prim.CreateInput("wrapS", Sdf.ValueTypeNames.Token)
            wrapT = texture_prim.CreateInput("wrapT", Sdf.ValueTypeNames.Token)
            wrapS.Set('repeat')
            wrapT.Set('repeat')

            # Create Primvar Reader for ST coordinates
            st_reader_path = f'{nodegraph_path}/TexCoordReader'  # TODO: remove it from the for loop.
            st_reader = UsdShade.Shader.Define(self.stage, st_reader_path)
            st_reader.CreateIdAttr("UsdPrimvarReader_float2")
            st_input = st_reader.CreateInput("varname", Sdf.ValueTypeNames.Token)
            st_input.Set("st")
            texture_prim.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_reader.ConnectableAPI(), "result")

            if tex_type in scalar_slots:
                value_type = Sdf.ValueTypeNames.Float
                channel = "r"
            else:
                value_type = Sdf.ValueTypeNames.Float3
                channel = "rgb"

            shader.CreateInput(input_name, value_type).ConnectToSource(
                texture_prim.ConnectableAPI(), channel
            )

        return material


    ###  arnold ###
    def _arnold_create_material(self, parent_path, enable_transmission=False):
        """
        example prints for variables created by the script:
            shader: UsdShade.Shader(Usd.Prim(</root/material/mat_hello_world_collect/standard_surface1>))
            material_prim: Usd.Prim(</root/material/mat_hello_world_collect>)
            material_usdshade: UsdShade.Material(Usd.Prim(</root/material/mat_hello_world_collect>))
        """
        shader_path = f'{parent_path}/arnold_standard_surface1'
        shader_usdshade = UsdShade.Shader.Define(self.stage, shader_path)
        shader_usdshade.CreateIdAttr("arnold:standard_surface")
        material_prim = self.stage.GetPrimAtPath(parent_path)

        material_usdshade = UsdShade.Material.Define(self.stage, material_prim.GetPath())
        material_usdshade.CreateOutput("arnold:surface", Sdf.ValueTypeNames.Token).ConnectToSource(shader_usdshade.ConnectableAPI(), "surface")
        # print(f"DEBUG: shader: {shader}\n")

        self._arnold_initialize_standard_surface_shader(shader_usdshade)
        self._arnold_fill_texture_file_paths(material_prim, shader_usdshade)

        if enable_transmission:
            self._arnold_enable_transmission(shader_usdshade)

        return material_usdshade

    def _arnold_initialize_standard_surface_shader(self, shader_usdshade):
        """
        initializes Arnold Standard Surface inputs
        """
        shader_usdshade.CreateInput('aov_id1', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('aov_id2', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('aov_id3', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('aov_id4', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('aov_id5', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('aov_id6', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('aov_id7', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('aov_id8', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('base', Sdf.ValueTypeNames.Float).Set(1)
        shader_usdshade.CreateInput('base_color', Sdf.ValueTypeNames.Float3).Set((0.8, 0.8, 0.8))
        shader_usdshade.CreateInput('metalness', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('specular', Sdf.ValueTypeNames.Float).Set(1)
        shader_usdshade.CreateInput('specular_color', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('specular_roughness', Sdf.ValueTypeNames.Float).Set(0.2)
        shader_usdshade.CreateInput('specular_IOR', Sdf.ValueTypeNames.Float).Set(1.5)
        shader_usdshade.CreateInput('specular_anisotropy', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('specular_rotation', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('caustics', Sdf.ValueTypeNames.Bool).Set(False)
        shader_usdshade.CreateInput('coat', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('coat_color', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('coat_roughness', Sdf.ValueTypeNames.Float).Set(0.1)
        shader_usdshade.CreateInput('coat_IOR', Sdf.ValueTypeNames.Float).Set(1.5)
        shader_usdshade.CreateInput('coat_normal', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('coat_affect_color', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('coat_affect_roughness', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('indirect_diffuse', Sdf.ValueTypeNames.Float).Set(1)
        shader_usdshade.CreateInput('indirect_specular', Sdf.ValueTypeNames.Float).Set(1)
        shader_usdshade.CreateInput('indirect_reflections', Sdf.ValueTypeNames.Bool).Set(True)
        shader_usdshade.CreateInput('subsurface', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('subsurface_anisotropy', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('subsurface_color', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('subsurface_radius', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('subsurface_scale', Sdf.ValueTypeNames.Float).Set(1)
        shader_usdshade.CreateInput('subsurface_type', Sdf.ValueTypeNames.String).Set("randomwalk")
        shader_usdshade.CreateInput('emission', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('emission_color', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('normal', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('opacity', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('sheen', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('sheen_color', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('sheen_roughness', Sdf.ValueTypeNames.Float).Set(0.3)
        shader_usdshade.CreateInput('indirect_diffuse', Sdf.ValueTypeNames.Float).Set(1)
        shader_usdshade.CreateInput('indirect_specular', Sdf.ValueTypeNames.Float).Set(1)
        shader_usdshade.CreateInput('internal_reflections', Sdf.ValueTypeNames.Bool).Set(True)
        shader_usdshade.CreateInput('caustics', Sdf.ValueTypeNames.Bool).Set(False)
        shader_usdshade.CreateInput('exit_to_background', Sdf.ValueTypeNames.Bool).Set(False)
        shader_usdshade.CreateInput('tangent', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('transmission', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('transmission_color', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('transmission_depth', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('transmission_scatter', Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader_usdshade.CreateInput('transmission_scatter_anisotropy', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('transmission_dispersion', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('transmission_extra_roughness', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('thin_film_IOR', Sdf.ValueTypeNames.Float).Set(1.5)
        shader_usdshade.CreateInput('thin_film_thickness', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('thin_walled', Sdf.ValueTypeNames.Bool).Set(False)
        shader_usdshade.CreateInput('transmit_aovs', Sdf.ValueTypeNames.Bool).Set(False)

    def _arnold_initialize_image_shader(self, image_path: str):
        image_shader = UsdShade.Shader.Define(self.stage, image_path)
        image_shader.CreateIdAttr("arnold:image")

        color_space = image_shader.CreateInput("color_space", Sdf.ValueTypeNames.String)
        color_space.Set("auto")
        image_shader.CreateInput("filename", Sdf.ValueTypeNames.Asset)
        filter = image_shader.CreateInput("filter", Sdf.ValueTypeNames.String)
        filter.Set("smart_bicubic")
        ignore_missing_textures = image_shader.CreateInput("ignore_missing_textures", Sdf.ValueTypeNames.Bool)
        ignore_missing_textures.Set(False)
        mipmap_bias = image_shader.CreateInput("mipmap_bias", Sdf.ValueTypeNames.Int)
        mipmap_bias.Set(0)
        missing_texture_color = image_shader.CreateInput("missing_texture_color", Sdf.ValueTypeNames.Float4)
        missing_texture_color.Set((0,0,0,0))
        multiply = image_shader.CreateInput("multiply", Sdf.ValueTypeNames.Float3)
        multiply.Set((1,1,1))
        offset = image_shader.CreateInput("offset", Sdf.ValueTypeNames.Float3)
        offset.Set((0,0,0))
        sflip = image_shader.CreateInput("sflip", Sdf.ValueTypeNames.Bool)
        sflip.Set(False)
        single_channel = image_shader.CreateInput("single_channel", Sdf.ValueTypeNames.Bool)
        single_channel.Set(False)
        soffset = image_shader.CreateInput("soffset", Sdf.ValueTypeNames.Float)
        soffset.Set(0)
        sscale = image_shader.CreateInput("sscale", Sdf.ValueTypeNames.Float)
        sscale.Set(1)
        start_channel = image_shader.CreateInput("start_channel", Sdf.ValueTypeNames.Int)
        start_channel.Set(0)
        swap_st = image_shader.CreateInput("swap_st", Sdf.ValueTypeNames.Bool)
        swap_st.Set(False)
        swrap = image_shader.CreateInput("swrap", Sdf.ValueTypeNames.String)
        swrap.Set("periodic")
        tflip = image_shader.CreateInput("tflip", Sdf.ValueTypeNames.Bool)
        tflip.Set(False)
        toffset = image_shader.CreateInput("toffset", Sdf.ValueTypeNames.Float)
        toffset.Set(0)
        tscale = image_shader.CreateInput("tscale", Sdf.ValueTypeNames.Float)
        tscale.Set(1)
        twrap = image_shader.CreateInput("twrap", Sdf.ValueTypeNames.String)
        twrap.Set("periodic")
        uvcoords = image_shader.CreateInput("uvcoords", Sdf.ValueTypeNames.Float2)
        uvcoords.Set((0,0))
        uvset = image_shader.CreateInput("uvset", Sdf.ValueTypeNames.String)
        uvset.Set("")

        return image_shader

    def _arnold_initialize_color_correct_shader(self, color_correct_path: str):
        color_correct_shader = UsdShade.Shader.Define(self.stage, color_correct_path)
        color_correct_shader.CreateIdAttr("arnold:color_correct")
        cc_add_input = color_correct_shader.CreateInput("add", Sdf.ValueTypeNames.Float3)
        cc_add_input.Set((0, 0, 0))
        cc_contrast_input = color_correct_shader.CreateInput("contrast", Sdf.ValueTypeNames.Float)
        cc_contrast_input.Set(1)
        cc_exposure_input = color_correct_shader.CreateInput("exposure", Sdf.ValueTypeNames.Float)
        cc_exposure_input.Set(0)
        cc_gamma_input = color_correct_shader.CreateInput("gamma", Sdf.ValueTypeNames.Float)
        cc_gamma_input.Set(1)
        cc_hue_shift_input = color_correct_shader.CreateInput("hue_shift", Sdf.ValueTypeNames.Float)
        cc_hue_shift_input.Set(0)

        return color_correct_shader

    def _arnold_initialize_range_shader(self, range_path: str):
        range_shader = UsdShade.Shader.Define(self.stage, range_path)
        range_shader.CreateIdAttr("arnold:range")

        bias_input = range_shader.CreateInput("bias", Sdf.ValueTypeNames.Float)
        bias_input.Set(0.5)
        contrast_input = range_shader.CreateInput("contrast", Sdf.ValueTypeNames.Float)
        contrast_input.Set(1)
        contrast_pivot_input = range_shader.CreateInput("contrast_pivot", Sdf.ValueTypeNames.Float)
        contrast_pivot_input.Set(0.5)
        gain_input = range_shader.CreateInput("gain", Sdf.ValueTypeNames.Float)
        gain_input.Set(0.5)
        input_min_input = range_shader.CreateInput("input_min", Sdf.ValueTypeNames.Float)
        input_min_input.Set(0)
        input_max_input = range_shader.CreateInput("input_max", Sdf.ValueTypeNames.Float)
        input_max_input.Set(1)
        output_min_input = range_shader.CreateInput("output_min", Sdf.ValueTypeNames.Float)
        output_min_input.Set(0)
        output_max_input = range_shader.CreateInput("output_max", Sdf.ValueTypeNames.Float)
        output_max_input.Set(1)
        output_max_input = range_shader.CreateInput("smoothstep", Sdf.ValueTypeNames.Bool)
        output_max_input.Set(False)

        return range_shader


    def _arnold_initialize_normal_map_shader(self, normal_map_path: str):
        normal_map_shader = UsdShade.Shader.Define(self.stage, normal_map_path)
        normal_map_shader.CreateIdAttr("arnold:normal_map")

        color_to_signed_input = normal_map_shader.CreateInput("color_to_signed", Sdf.ValueTypeNames.Bool)
        color_to_signed_input.Set(True)
        input_input = normal_map_shader.CreateInput("input", Sdf.ValueTypeNames.Float3)
        input_input.Set((0, 0, 0))
        invert_x_input = normal_map_shader.CreateInput("invert_x", Sdf.ValueTypeNames.Bool)
        invert_x_input.Set(False)
        invert_y_input = normal_map_shader.CreateInput("invert_y", Sdf.ValueTypeNames.Bool)
        invert_y_input.Set(False)
        invert_z_input = normal_map_shader.CreateInput("invert_z", Sdf.ValueTypeNames.Bool)
        invert_z_input.Set(False)
        normal_input = normal_map_shader.CreateInput("normal", Sdf.ValueTypeNames.Float3)
        normal_input.Set((0, 0, 0))
        order_input = normal_map_shader.CreateInput("order", Sdf.ValueTypeNames.String)
        order_input.Set('XYZ')
        strength_input = normal_map_shader.CreateInput("strength", Sdf.ValueTypeNames.Float)
        strength_input.Set(1)
        tangent_input = normal_map_shader.CreateInput("tangent", Sdf.ValueTypeNames.Float3)
        tangent_input.Set((0, 0, 0))
        tangent_space_input = normal_map_shader.CreateInput("tangent_space", Sdf.ValueTypeNames.Bool)
        tangent_space_input.Set(True)

        return normal_map_shader

    def _arnold_initialize_bump2d_shader(self, bump2d_path: str):
        bump2d_shader = UsdShade.Shader.Define(self.stage, bump2d_path)
        bump2d_shader.CreateIdAttr("arnold:bump2d")

        bump_height_input = bump2d_shader.CreateInput("bump_height", Sdf.ValueTypeNames.Float)
        bump_height_input.Set(1)
        bump_map_input = bump2d_shader.CreateInput("bump_map", Sdf.ValueTypeNames.Float)
        bump_map_input.Set(0)
        normal_input = bump2d_shader.CreateInput("normal", Sdf.ValueTypeNames.Float3)
        normal_input.Set((0, 0, 0))

        return bump2d_shader


    def _arnold_enable_transmission(self, shader_usdshade):
        """
        given the mtlx standard surface, will set input primvar 'transmission' to value '0.9'
        """
        shader_usdshade.GetInput('transmission').Set(0.9)
        shader_usdshade.GetInput('thin_walled').Set(True)


    def _arnold_fill_texture_file_paths(self, material_prim, std_surf_shader):
        """
        Fills the texture file paths for the given shader using the material_data.
        """
        # map of tex_type to it's name on an Arnold Standard Surface shader.
        texture_types_to_inputs = {
            'basecolor': 'base_color',
            'metalness': 'metalness',
            'roughness': 'specular_roughness',
            'normal': 'normal',
            'opacity': 'opacity',
            'displacement': 'height',
            'height': 'height',
        }

        bump2d_path = f"{material_prim.GetPath()}/arnold_Bump2d"
        bump2d_shader = None

        for tex_type, tex_dict in self.material_dict.items():
            tex_filepath = tex_dict['path']
            tex_type = tex_type.lower()  # assume all lowercase
            if tex_type not in texture_types_to_inputs:
                print(f"WARNING:  tex_type: '{tex_type}' not supported yet for arnold")
                continue

            input_name = texture_types_to_inputs[tex_type]

            # create arnold::image prim
            texture_prim_path = f'{material_prim.GetPath()}/arnold_{tex_type}Texture'
            texture_shader = self._arnold_initialize_image_shader(texture_prim_path)
            texture_shader.GetInput("filename").Set(tex_filepath)

            if tex_type in ['basecolor']:
                color_correct_path = f"{material_prim.GetPath()}/arnold_{tex_type}ColorCorrect"
                color_correct_shader = self._arnold_initialize_color_correct_shader(color_correct_path)
                color_correct_shader.CreateInput("input", Sdf.ValueTypeNames.Float4).ConnectToSource(texture_shader.ConnectableAPI(), "rgba")
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(color_correct_shader.ConnectableAPI(), "rgb")

            elif tex_type in ['metalness']:
                # disable metalness if material is transmissive like glass:
                if self.is_transmissive:
                    continue
                range_path = f"{material_prim.GetPath()}/arnold_{tex_type}Range"
                range_shader = self._arnold_initialize_range_shader(range_path)
                range_shader.CreateInput("input", Sdf.ValueTypeNames.Float4).ConnectToSource(texture_shader.ConnectableAPI(), "rgba")
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(range_shader.ConnectableAPI(), "r")

            elif tex_type in ['roughness']:
                range_path = f"{material_prim.GetPath()}/arnold_{tex_type}Range"
                range_shader = self._arnold_initialize_range_shader(range_path)
                range_shader.CreateInput("input", Sdf.ValueTypeNames.Float4).ConnectToSource(texture_shader.ConnectableAPI(), "rgba")
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(range_shader.ConnectableAPI(), "r")

            elif tex_type in ['displacement', 'height']:
                range_path = f"{material_prim.GetPath()}/arnold_{tex_type}Range"
                range_shader = self._arnold_initialize_range_shader(range_path)
                range_shader.CreateInput("input", Sdf.ValueTypeNames.Float4).ConnectToSource(texture_shader.ConnectableAPI(), "rgba")
                if not bump2d_shader:
                    bump2d_shader = self._arnold_initialize_bump2d_shader(bump2d_path)
                bump2d_shader.CreateInput("bump_map", Sdf.ValueTypeNames.Float).ConnectToSource(range_shader.ConnectableAPI(), "r")

            elif tex_type in ['normal']:
                normal_map_path = f"{material_prim.GetPath()}/arnold_NormalMap"
                normal_map_shader = self._arnold_initialize_normal_map_shader(normal_map_path)
                normal_map_shader.CreateInput("input", Sdf.ValueTypeNames.Float3).ConnectToSource(texture_shader.ConnectableAPI(), "vector")
                if not bump2d_shader:
                    bump2d_shader = self._arnold_initialize_bump2d_shader(bump2d_path)
                bump2d_shader.CreateInput("normal", Sdf.ValueTypeNames.Float4).ConnectToSource(normal_map_shader.ConnectableAPI(), "vector")

        if bump2d_shader:
            std_surf_shader.CreateInput('normal', Sdf.ValueTypeNames.Float3).ConnectToSource(bump2d_shader.ConnectableAPI(), "vector")


    ###  mtlx ###
    def _mtlx_create_material(self, parent_path, enable_transmission=False):
        shader_path = f'{parent_path}/mtlx_mtlxstandard_surface1'
        shader_usdshade = UsdShade.Shader.Define(self.stage, shader_path)
        material_prim = self.stage.GetPrimAtPath(parent_path)
        material_usdshade = UsdShade.Material.Define(self.stage, material_prim.GetPath())
        material_usdshade.CreateOutput("mtlx:surface", Sdf.ValueTypeNames.Token).ConnectToSource(shader_usdshade.ConnectableAPI(), "surface")

        self._mtlx_initialize_standard_surface_shader(shader_usdshade)
        self._mtlx_fill_texture_file_paths(material_prim, shader_usdshade)
        if enable_transmission:
            self._mtlx_enable_transmission(shader_usdshade)

        return material_usdshade


    def _mtlx_initialize_standard_surface_shader(self, shader_usdshade):
        shader_usdshade.CreateIdAttr("ND_standard_surface_surfaceshader")

        shader_usdshade.CreateInput('base', Sdf.ValueTypeNames.Float).Set(1)
        shader_usdshade.CreateInput('base_color', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.8, 0.8, 0.8))
        shader_usdshade.CreateInput('coat', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('coat_roughness', Sdf.ValueTypeNames.Float).Set(0.1)
        shader_usdshade.CreateInput('emission', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('emission_color', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('metalness', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('specular', Sdf.ValueTypeNames.Float).Set(1)
        shader_usdshade.CreateInput('specular_color', Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader_usdshade.CreateInput('specular_IOR', Sdf.ValueTypeNames.Float).Set(1.5)
        shader_usdshade.CreateInput('specular_roughness', Sdf.ValueTypeNames.Float).Set(0.2)
        shader_usdshade.CreateInput('transmission', Sdf.ValueTypeNames.Float).Set(0)
        shader_usdshade.CreateInput('thin_walled', Sdf.ValueTypeNames.Int).Set(0)
        shader_usdshade.CreateInput('opacity',  Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1, 1, 1))


    def _mtlx_initialize_image_shader(self, image_path: str, signature="color3"):
        image_shader = UsdShade.Shader.Define(self.stage, image_path)
        image_shader.CreateIdAttr(f"ND_image_{signature}")
        image_shader.CreateInput("file", Sdf.ValueTypeNames.Asset)
        return image_shader


    def _mtlx_initialize_color_correct_shader(self, color_correct_path: str, signature="color3"):
        color_correct_shader = UsdShade.Shader.Define(self.stage, color_correct_path)
        color_correct_shader.CreateIdAttr(f"ND_colorcorrect_{signature}")

        return color_correct_shader

    def _mtlx_initialize_range_shader(self, range_path: str, signature="color3"):
        range_shader = UsdShade.Shader.Define(self.stage, range_path)
        range_shader.CreateIdAttr(f"ND_range_{signature}")
        return range_shader


    def _mtlx_initialize_normal_map_shader(self, normal_map_path: str):
        normal_map_shader = UsdShade.Shader.Define(self.stage, normal_map_path)
        normal_map_shader.CreateIdAttr("ND_normalmap")

        return normal_map_shader

    def _mtlx_initialize_bump2d_shader(self, bump2d_path: str):
        bump2d_shader = UsdShade.Shader.Define(self.stage, bump2d_path)
        bump2d_shader.CreateIdAttr("ND_bump_vector3")

        bump_height_input = bump2d_shader.CreateInput("bump_height", Sdf.ValueTypeNames.Float)
        bump_height_input.Set(1)
        bump_map_input = bump2d_shader.CreateInput("bump_map", Sdf.ValueTypeNames.Float)
        bump_map_input.Set(0)
        normal_input = bump2d_shader.CreateInput("normal", Sdf.ValueTypeNames.Float3)
        normal_input.Set((0, 0, 0))

        return bump2d_shader


    def _mtlx_enable_transmission(self, shader_usdshade):
        """
        given the mtlx standard surface, will set input primvar 'transmission' to value '0.9'
        """
        shader_usdshade.GetInput('transmission').Set(0.9)
        shader_usdshade.GetInput('thin_walled').Set(1)


    def _mtlx_fill_texture_file_paths(self, material_prim, std_surf_shader):
        """
        Fills the texture file paths for the given shader using the material_data.
        """
        texture_types_to_inputs = {
            'basecolor': 'base_color',
            'metalness': 'metalness',
            'roughness': 'specular_roughness',
            'opacity': 'opacity',
            'normal': 'normal',
            'displacement': 'displacement',
            # 'height': '',  # legacy alias for displacement
        }
        mtlx_image_signature = {
            'basecolor': "color3",
            'normal': "vector3",
            'metalness': "float",
            'opacity': "float",
            'roughness': "float",
            'displacement': "float",
            'height': "float",
        }

        bump2d_shader = None

        for tex_type, tex_dict in self.material_dict.items():
            tex_filepath = tex_dict['path']
            tex_type = tex_type.lower()  # assume all lowercase
            if tex_type not in texture_types_to_inputs:
                print(f"WARNING:  tex_type: '{tex_type}' not supported yet for MTLX")
                continue

            input_name = texture_types_to_inputs[tex_type]

            # create 'ND_image_<signature>' prim
            texture_prim_path = f'{material_prim.GetPath()}/mtlx_{tex_type}Texture'
            texture_shader = self._mtlx_initialize_image_shader(texture_prim_path, signature=mtlx_image_signature[tex_type])
            texture_shader.GetInput("file").Set(tex_filepath)

            if tex_type in ['basecolor']:
                color_correct_path = f"{material_prim.GetPath()}/mtlx_{tex_type}ColorCorrect"
                color_correct_shader = self._mtlx_initialize_color_correct_shader(color_correct_path)
                color_correct_shader.CreateInput("in", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    texture_shader.ConnectableAPI(), "out")
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    color_correct_shader.ConnectableAPI(), "out")

            elif tex_type in ['metalness']:
                # disable metalness if material is transmissive like glass:
                if self.is_transmissive:
                    continue
                range_path = f"{material_prim.GetPath()}/mtlx_{tex_type}Range"
                range_shader = self._mtlx_initialize_range_shader(range_path)
                range_shader.CreateInput("in", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    texture_shader.ConnectableAPI(), "out")
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(
                    range_shader.ConnectableAPI(), "out")

            elif tex_type in ['roughness']:
                range_path = f"{material_prim.GetPath()}/mtlx_{tex_type}Range"
                range_shader = self._mtlx_initialize_range_shader(range_path)
                range_shader.CreateInput("in", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    texture_shader.ConnectableAPI(), "out")
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(
                    range_shader.ConnectableAPI(), "out")

            ###### BUMP MAP + NORMAL MAPS AREN'T SUPPORTED IN MTLX
            # elif tex_type in ['height']:
            #     range_path = f"{material_prim.GetPath()}/{tex_type}Range"
            #     range_shader = self._mtlx_initialize_range_shader(range_path)
            #     range_shader.CreateInput("in", Sdf.ValueTypeNames.Float4).ConnectToSource(
            #         texture_shader.ConnectableAPI(), "out")
            #     if not bump2d_shader:
            #         bump2d_shader = self._mtlx_initialize_bump2d_shader(bump2d_path)
            #     bump2d_shader.CreateInput("height", Sdf.ValueTypeNames.Float).ConnectToSource(
            #         range_shader.ConnectableAPI(), "out")

            elif tex_type in ['normal']:
                normal_map_path = f"{material_prim.GetPath()}/mtlx_NormalMap"
                normal_map_shader = self._mtlx_initialize_normal_map_shader(normal_map_path)
                normal_map_shader.CreateInput("in", Sdf.ValueTypeNames.Float3).ConnectToSource(
                    texture_shader.ConnectableAPI(), "out")
                # if not bump2d_shader:
                #     bump2d_shader = self._mtlx_initialize_bump2d_shader(bump2d_path)
                std_surf_shader.CreateInput("normal", Sdf.ValueTypeNames.Float4).ConnectToSource(
                    normal_map_shader.ConnectableAPI(), "out")
            elif tex_type in ['displacement']:
                # Displacement not supported for MTLX in this pipeline yet.
                continue

        if bump2d_shader:
            std_surf_shader.CreateInput('normal', Sdf.ValueTypeNames.Float3).ConnectToSource(
                bump2d_shader.ConnectableAPI(), "out")


    def _create_collect_prim(self, parent_primpath: str, create_usd_preview=False, usd_preview_format=None,
                             create_arnold=False, create_mtlx=False, enable_transmission=False):
        """
        creates a collect material prim on stage
        :return: collect prim
        :rtype: UsdShade.Material
        """
        # parent = self.stage.GetPrimAtPath(parent_primpath)
        # if not parent or not parent.IsDefined():
        #     self.stage.DefinePrim(parent_primpath, 'Scope')

        collect_prim_path = f'{parent_primpath}/mat_{self.material_name}_collect'
        collect_usd_material = UsdShade.Material.Define(self.stage, collect_prim_path)
        collect_usd_material.CreateInput("inputnum", Sdf.ValueTypeNames.Int).Set(2)

        if create_usd_preview:
            # Create the USD Preview Shader under the collect material
            usd_preview_material = self._create_usd_preview_material(collect_prim_path, usd_preview_format=usd_preview_format)
            usd_preview_shader = usd_preview_material.GetSurfaceOutput().GetConnectedSource()[0]
            collect_usd_material.CreateOutput("surface", Sdf.ValueTypeNames.Token).ConnectToSource(usd_preview_shader, "surface")

        if create_arnold:
            # Create the Arnold Shader under the collect material
            arnold_material = self._arnold_create_material(collect_prim_path, enable_transmission=enable_transmission)
            arnold_shader = arnold_material.GetOutput("arnold:surface").GetConnectedSource()[0]
            collect_usd_material.CreateOutput("arnold:surface", Sdf.ValueTypeNames.Token).ConnectToSource(arnold_shader, "surface")

        if create_mtlx:
            # Create the mtlx Shader under the collect material
            mtlx_material = self._mtlx_create_material(collect_prim_path, enable_transmission=enable_transmission)
            mtlx_shader = mtlx_material.GetOutput("mtlx:surface").GetConnectedSource()[0]
            collect_usd_material.CreateOutput("mtlx:surface", Sdf.ValueTypeNames.Token).ConnectToSource(mtlx_shader, "surface")

        return collect_usd_material



    def run(self):
        """
        Main run function. will create a collect material with Arnold and usdPreview shaders in stage.
        """
        self._create_collect_prim(parent_primpath=self.parent_primpath,
                                  create_usd_preview=self.create_usd_preview,
                                  usd_preview_format=self.usd_preview_format,
                                  create_arnold=self.create_arnold,
                                  create_mtlx=self.create_mtlx,
                                  enable_transmission=self.is_transmissive,
                                  )



class USDShaderAssign:
    def __init__(self, stage):
        self.stage = stage


    def assign_material_to_primitives(self, material_prim, prims_to_assign_to):
        """
        Assigns a new USD material to a list of primitives.
        :param material_prim: Usd.Prim primitive to assign to the primitives
        :type material_prim: Usd.Prim
        :param prims_to_assign_to: list of prims which we will assign the material to them
        :type prims_to_assign_to: list[Usd.Prim]
        """
        material = UsdShade.Material(material_prim)

        if not material or not isinstance(material, UsdShade.Material):
            raise ValueError(f"New material is not a <UsdShade.Material> object, instead it's a {type(material)}.")

        # if not prims_to_assign_to or not isinstance(prims_to_assign_to, list(Usd.Prim)):
        #     raise ValueError(f"primitives are not a <list(Usd.Prim)> object, instead it's a {type(prims_to_assign_to)}.")

        for prim in prims_to_assign_to:
            UsdShade.MaterialBindingAPI(prim).Bind(material)


    def run(self, mats_parent_path: str, mesh_parent_path: str):
        """
        run function for  class, steps:
            1. get list of Materials under a parent prim
            for each material found:
                i. clean material name
                ii. collect all meshes that have the mat name as part of its name
                iii. assign the material to the list of mesh prims
        """
        mats_parent_prim = self.stage.GetPrimAtPath(mats_parent_path)

        # 1. get list of Materials under a parent prim:
        check, found_mats = usd_utils.collect_prims_of_type(mats_parent_prim, prim_type=UsdShade.Material,
                                                            recursive=False)
        if not check:
            print(f"No UsdShade.Material Found under prim: '{mats_parent_path}'")
            return

        for mat_prim in found_mats:
            # 2. cleaning material name:
            mat_name = mat_prim.GetName().replace('_ShaderSG', '')
            mat_name = mat_name.replace('mat_', '').replace('_collect', '')
            mesh_parent_prim = self.stage.GetPrimAtPath(mesh_parent_path)

            # 3. collect all meshes that have the mat name as part of its name:
            check, asset_prims = usd_utils.collect_prims_of_type(mesh_parent_prim, prim_type=UsdGeom.Mesh,
                                                                 contains_str=mat_name, recursive=True)
            if not asset_prims:
                print(f"WARNING: No meshes found with name: {mat_name}")
                continue

            asset_names = [x.GetName() for x in asset_prims]
            print(f"DEBUG: mat_name: {mat_name}, asset_names: {asset_names[0]}")



            # 4. assign the material to the list of mesh prims:
            self.assign_material_to_primitives(mat_prim, asset_prims)



class USDMeshConfigure:
    """
    TODO:     - add transmission support to mtlx
    TODO:     - add rgs for karma: caustics, double sided,
    TODO:     - set subdiv schema to: "__none__"

    """
    def __init__(self, stage):
        self.stage = stage

    def add_karma_primvars(self, prim):
        karma_primvars = {
            "primvars:karma:object:causticsenable": (True, Sdf.ValueTypeNames.Bool),
            # "karma:customShading": (0.5, Sdf.ValueTypeNames.Float),
            # "karma:shadowBias": (0.05, Sdf.ValueTypeNames.Float)
        }

        for attrName, (value, typeName) in karma_primvars.items():
            # Check if the attribute already exists; if not, create it.
            attr = prim.GetAttribute(attrName)
            if not attr:
                attr = prim.CreateAttribute(attrName, typeName)

            # Set the attribute value.
            attr.Set(value)
            print(f"Set attribute {attrName} to {value} (Type: {typeName})")




def create_shaded_asset_publish(material_dict_list, stage=None, geo_file=None, parent_path="/ASSET",
                                layer_save_path=None, main_layer_name='main.usda',
                                create_usd_preview=True, create_arnold=False, create_mtlx=True):
    """
    Main run method.
    """
    if not layer_save_path:
        layer_save_path = f"{tempfile.gettempdir()}/temp_usd_export"
        os.makedirs(layer_save_path, exist_ok=True)
    layer_save_path = str(layer_save_path)
    os.makedirs(f"{layer_save_path}/layers", exist_ok=True)

    # create stage:
    if not stage:
        stage = Usd.Stage.CreateNew(f"{layer_save_path}/{main_layer_name}")

    # create layers:
    layer_root = stage.GetRootLayer()

    layer_mats_path_abs = f"{layer_save_path}/layers/layer_mats.usda"
    layer_mats_rel_paths = os.path.relpath(layer_mats_path_abs, layer_save_path)
    layer_mats = Sdf.Layer.CreateNew(layer_mats_path_abs)
    layer_root.subLayerPaths.append(layer_mats_rel_paths)

    layer_assign_path_abs = f"{layer_save_path}/layers/layer_assign.usda"
    layer_assign_rel_paths = os.path.relpath(layer_assign_path_abs, layer_save_path)
    layer_assign = Sdf.Layer.CreateNew(layer_assign_path_abs)
    layer_root.subLayerPaths.append(layer_assign_rel_paths)


    if geo_file:
        # payload geo:
        stage.SetEditTarget(layer_root)
        geo_prim = stage.DefinePrim(f'{parent_path}', 'Xform')
        mesh_rel_path = os.path.relpath(geo_file, layer_save_path)
        geo_prim.GetPayloads().AddPayload(mesh_rel_path, f"{parent_path}/mesh/")

        # # set kinds for geo prims:
        # for asset_name_prim in geo_prim.GetChildren():
        #     asset_name_prim.SetMetadata('kind', 'group')
        #     for child_prim in asset_name_prim.GetChildren():
        #         if child_prim.IsA(UsdGeom.Xform):
        #             child_prim.SetMetadata('kind', 'component')


    # create material_dict_list:
    stage.SetEditTarget(layer_mats)
    material_primitive_path = f"{parent_path}/material"

    for material_dict in material_dict_list:
        material_name = "UnknownMaterialName"
        for x in material_dict.values():
            material_name = x['mat_name']
            # break
        USDShaderCreate(stage=stage, material_name=material_name, material_dict=material_dict,
                        parent_primpath=material_primitive_path,
                        create_usd_preview=create_usd_preview,
                        create_arnold=create_arnold,
                        create_mtlx=create_mtlx
                        )


    if geo_file:
        # assign material_dict_list:
        stage.SetEditTarget(layer_assign)
        USDShaderAssign(stage).run(mats_parent_path=material_primitive_path, mesh_parent_path=parent_path)

    # Save all layers:
    layer_mats.Save()
    layer_assign.Save()
    layer_root.Save()

    print(f"INFO: Finished creating usd asset: '{layer_save_path}/{main_layer_name}'.")
    print("INFO: Success")


