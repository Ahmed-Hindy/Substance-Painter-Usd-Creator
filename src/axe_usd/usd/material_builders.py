"""USD shader network builders."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

from pxr import Gf, Sdf, Usd, UsdShade

from .material_model import TextureFormatOverrides, apply_texture_format_override
from .types import MaterialTextureDict


RENDERER_USD_PREVIEW = "usd_preview"
RENDERER_ARNOLD = "arnold"
RENDERER_MTLX = "mtlx"
RENDERER_OPENPBR = "openpbr"
PREVIEW_TEXTURE_DIRNAME = "previewTextures"
PREVIEW_TEXTURE_SUFFIX = ".jpg"

USD_PREVIEW_INPUTS = {
    "basecolor": "diffuseColor",
    "metalness": "metallic",
    "roughness": "roughness",
    "normal": "normal",
    "opacity": "opacity",
    "occlusion": "occlusion",
    "displacement": "displacement",
}
USD_PREVIEW_SCALAR_SLOTS = {"metalness", "roughness", "opacity", "occlusion", "displacement"}

ARNOLD_INPUTS = {
    "basecolor": "base_color",
    "metalness": "metalness",
    "roughness": "specular_roughness",
    "normal": "normal",
    "opacity": "opacity",
    "displacement": "height",
}

MTLX_INPUTS = {
    "basecolor": "base_color",
    "metalness": "metalness",
    "roughness": "specular_roughness",
    "normal": "normal",
    "opacity": "opacity",
    "displacement": "displacement",
}

OPENPBR_INPUTS = {
    "basecolor": "base_color",
    "metalness": "base_metalness",
    "roughness": "specular_roughness",
    "normal": "geometry_normal",
    "opacity": "opacity",
    "displacement": "displacement",
}


@dataclass(frozen=True)
class MaterialBuildContext:
    stage: Usd.Stage
    material_dict: MaterialTextureDict
    is_transmissive: bool
    texture_format_overrides: TextureFormatOverrides
    logger: logging.Logger


def _iter_textures(
    context: MaterialBuildContext,
    input_map: Dict[str, str],
    renderer_name: str,
) -> Iterable[Tuple[str, str, str]]:
    for slot, info in context.material_dict.items():
        input_name = input_map.get(slot)
        if not input_name:
            context.logger.warning("Texture slot '%s' not supported for %s.", slot, renderer_name)
            continue
        path = info.get("path")
        if not path:
            context.logger.warning("Texture slot '%s' missing path; skipping.", slot)
            continue
        yield slot, input_name, path


def _preview_texture_path(path: str, mat_name: str) -> str:
    source_path = Path(path)
    preview_name = f"{mat_name}_BaseColor{PREVIEW_TEXTURE_SUFFIX}"
    preview_dir = source_path.parent / PREVIEW_TEXTURE_DIRNAME
    preview_path = preview_dir / preview_name
    if source_path.is_absolute():
        return preview_path.as_posix()
    prefix = "./" if path.startswith("./") else ""
    return f"{prefix}{preview_path.as_posix()}"


class UsdPreviewBuilder:
    def __init__(self, context: MaterialBuildContext) -> None:
        self._context = context

    def build(self, collect_path: str) -> UsdShade.Shader:
        stage = self._context.stage

        nodegraph_path = f"{collect_path}/UsdPreviewNodeGraph"
        nodegraph = UsdShade.NodeGraph.Define(stage, nodegraph_path)

        shader_path = f"{nodegraph_path}/UsdPreviewSurface"
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("UsdPreviewSurface")

        material = UsdShade.Material.Get(stage, collect_path)
        nodegraph_output = nodegraph.CreateOutput(
            "surface", Sdf.ValueTypeNames.Token
        )
        nodegraph_output.ConnectToSource(shader.ConnectableAPI(), "surface")
        material.CreateSurfaceOutput().ConnectToSource(
            nodegraph.ConnectableAPI(), "surface"
        )

        st_reader_path = f"{nodegraph_path}/TexCoordReader"
        st_reader = UsdShade.Shader.Define(stage, st_reader_path)
        st_reader.CreateIdAttr("UsdPrimvarReader_float2")
        st_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

        base_info = self._context.material_dict.get("basecolor")
        if not base_info:
            return shader
        path = base_info.get("path")
        if not path:
            return shader

        mat_name = base_info.get("mat_name", "")
        tex_filepath = _preview_texture_path(path, mat_name)
        texture_prim_path = f"{nodegraph_path}/basecolorTexture"
        texture_prim = UsdShade.Shader.Define(stage, texture_prim_path)
        texture_prim.CreateIdAttr("UsdUVTexture")
        texture_prim.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(tex_filepath)
        texture_prim.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
        texture_prim.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")
        texture_prim.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            st_reader.ConnectableAPI(), "result"
        )
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Float3).ConnectToSource(
            texture_prim.ConnectableAPI(),
            "rgb",
        )

        return shader


class ArnoldBuilder:
    def __init__(self, context: MaterialBuildContext) -> None:
        self._context = context

    def build(self, collect_path: str) -> UsdShade.NodeGraph:
        stage = self._context.stage
        override = self._context.texture_format_overrides.for_renderer(RENDERER_ARNOLD)

        nodegraph_path = f"{collect_path}/ArnoldNodeGraph"
        nodegraph = UsdShade.NodeGraph.Define(stage, nodegraph_path)

        shader_path = f"{nodegraph_path}/arnold_standard_surface1"
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("arnold:standard_surface")

        nodegraph_output = nodegraph.CreateOutput("surface", Sdf.ValueTypeNames.Token)
        nodegraph_output.ConnectToSource(shader.ConnectableAPI(), "surface")

        self._initialize_standard_surface(shader)
        self._wire_textures(nodegraph_path, shader, override)

        if self._context.is_transmissive:
            self._enable_transmission(shader)

        return nodegraph

    def _initialize_standard_surface(self, shader: UsdShade.Shader) -> None:
        shader.CreateInput("aov_id1", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("aov_id2", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("aov_id3", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("aov_id4", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("aov_id5", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("aov_id6", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("aov_id7", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("aov_id8", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("base", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("base_color", Sdf.ValueTypeNames.Float3).Set((0.8, 0.8, 0.8))
        shader.CreateInput("base_metalness", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("specular_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("specular_roughness", Sdf.ValueTypeNames.Float).Set(0.2)
        shader.CreateInput("specular_IOR", Sdf.ValueTypeNames.Float).Set(1.5)
        shader.CreateInput("specular_anisotropy", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("specular_rotation", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("caustics", Sdf.ValueTypeNames.Bool).Set(False)
        shader.CreateInput("coat", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("coat_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("coat_roughness", Sdf.ValueTypeNames.Float).Set(0.1)
        shader.CreateInput("coat_IOR", Sdf.ValueTypeNames.Float).Set(1.5)
        shader.CreateInput("coat_normal", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("coat_affect_color", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("coat_affect_roughness", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("indirect_diffuse", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("indirect_specular", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("indirect_reflections", Sdf.ValueTypeNames.Bool).Set(True)
        shader.CreateInput("subsurface", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("subsurface_anisotropy", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("subsurface_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("subsurface_radius", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("subsurface_scale", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("subsurface_type", Sdf.ValueTypeNames.String).Set("randomwalk")
        shader.CreateInput("emission", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("emission_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("normal", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("sheen", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("sheen_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("sheen_roughness", Sdf.ValueTypeNames.Float).Set(0.3)
        shader.CreateInput("internal_reflections", Sdf.ValueTypeNames.Bool).Set(True)
        shader.CreateInput("exit_to_background", Sdf.ValueTypeNames.Bool).Set(False)
        shader.CreateInput("tangent", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("transmission", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("transmission_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("transmission_depth", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("transmission_scatter", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("transmission_scatter_anisotropy", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("transmission_dispersion", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("transmission_extra_roughness", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("thin_film_IOR", Sdf.ValueTypeNames.Float).Set(1.5)
        shader.CreateInput("thin_film_thickness", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("thin_walled", Sdf.ValueTypeNames.Bool).Set(False)
        shader.CreateInput("transmit_aovs", Sdf.ValueTypeNames.Bool).Set(False)

    def _initialize_image_shader(self, image_path: str) -> UsdShade.Shader:
        image_shader = UsdShade.Shader.Define(self._context.stage, image_path)
        image_shader.CreateIdAttr("arnold:image")
        image_shader.CreateInput("color_space", Sdf.ValueTypeNames.String).Set("auto")
        image_shader.CreateInput("filename", Sdf.ValueTypeNames.Asset)
        image_shader.CreateInput("filter", Sdf.ValueTypeNames.String).Set("smart_bicubic")
        image_shader.CreateInput("ignore_missing_textures", Sdf.ValueTypeNames.Bool).Set(False)
        image_shader.CreateInput("mipmap_bias", Sdf.ValueTypeNames.Int).Set(0)
        image_shader.CreateInput("missing_texture_color", Sdf.ValueTypeNames.Float4).Set((0, 0, 0, 0))
        image_shader.CreateInput("multiply", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        image_shader.CreateInput("offset", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        image_shader.CreateInput("sflip", Sdf.ValueTypeNames.Bool).Set(False)
        image_shader.CreateInput("single_channel", Sdf.ValueTypeNames.Bool).Set(False)
        image_shader.CreateInput("soffset", Sdf.ValueTypeNames.Float).Set(0)
        image_shader.CreateInput("sscale", Sdf.ValueTypeNames.Float).Set(1)
        image_shader.CreateInput("start_channel", Sdf.ValueTypeNames.Int).Set(0)
        image_shader.CreateInput("swap_st", Sdf.ValueTypeNames.Bool).Set(False)
        image_shader.CreateInput("swrap", Sdf.ValueTypeNames.String).Set("periodic")
        image_shader.CreateInput("tflip", Sdf.ValueTypeNames.Bool).Set(False)
        image_shader.CreateInput("toffset", Sdf.ValueTypeNames.Float).Set(0)
        image_shader.CreateInput("tscale", Sdf.ValueTypeNames.Float).Set(1)
        image_shader.CreateInput("twrap", Sdf.ValueTypeNames.String).Set("periodic")
        image_shader.CreateInput("uvcoords", Sdf.ValueTypeNames.Float2).Set((0, 0))
        image_shader.CreateInput("uvset", Sdf.ValueTypeNames.String).Set("")
        return image_shader

    def _initialize_color_correct_shader(self, color_correct_path: str) -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, color_correct_path)
        shader.CreateIdAttr("arnold:color_correct")
        shader.CreateInput("add", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("contrast", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("exposure", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("gamma", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("hue_shift", Sdf.ValueTypeNames.Float).Set(0)
        return shader

    def _initialize_range_shader(self, range_path: str) -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, range_path)
        shader.CreateIdAttr("arnold:range")
        shader.CreateInput("bias", Sdf.ValueTypeNames.Float).Set(0.5)
        shader.CreateInput("contrast", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("contrast_pivot", Sdf.ValueTypeNames.Float).Set(0.5)
        shader.CreateInput("gain", Sdf.ValueTypeNames.Float).Set(0.5)
        shader.CreateInput("input_min", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("input_max", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("output_min", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("output_max", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("smoothstep", Sdf.ValueTypeNames.Bool).Set(False)
        return shader

    def _initialize_normal_map_shader(self, normal_map_path: str) -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, normal_map_path)
        shader.CreateIdAttr("arnold:normal_map")
        shader.CreateInput("color_to_signed", Sdf.ValueTypeNames.Bool).Set(True)
        shader.CreateInput("input", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("invert_x", Sdf.ValueTypeNames.Bool).Set(False)
        shader.CreateInput("invert_y", Sdf.ValueTypeNames.Bool).Set(False)
        shader.CreateInput("invert_z", Sdf.ValueTypeNames.Bool).Set(False)
        shader.CreateInput("normal", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("order", Sdf.ValueTypeNames.String).Set("XYZ")
        shader.CreateInput("strength", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("tangent", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        shader.CreateInput("tangent_space", Sdf.ValueTypeNames.Bool).Set(True)
        return shader

    def _initialize_bump2d_shader(self, bump2d_path: str) -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, bump2d_path)
        shader.CreateIdAttr("arnold:bump2d")
        shader.CreateInput("bump_height", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("bump_map", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("normal", Sdf.ValueTypeNames.Float3).Set((0, 0, 0))
        return shader

    def _enable_transmission(self, shader: UsdShade.Shader) -> None:
        shader.GetInput("transmission").Set(0.9)
        shader.GetInput("thin_walled").Set(True)

    def _wire_textures(
        self,
        collect_path: str,
        std_surf_shader: UsdShade.Shader,
        override: Optional[str],
    ) -> None:
        bump2d_path = f"{collect_path}/arnold_Bump2d"
        bump2d_shader = None

        for slot, input_name, path in _iter_textures(self._context, ARNOLD_INPUTS, "arnold"):
            tex_filepath = apply_texture_format_override(path, override)
            texture_prim_path = f"{collect_path}/arnold_{slot}Texture"
            texture_shader = self._initialize_image_shader(texture_prim_path)
            texture_shader.GetInput("filename").Set(tex_filepath)

            if slot == "basecolor":
                color_correct_path = f"{collect_path}/arnold_{slot}ColorCorrect"
                color_correct_shader = self._initialize_color_correct_shader(color_correct_path)
                color_correct_shader.CreateInput("input", Sdf.ValueTypeNames.Float4).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(
                    color_correct_shader.ConnectableAPI(),
                    "rgb",
                )
            elif slot == "metalness":
                if self._context.is_transmissive:
                    continue
                range_path = f"{collect_path}/arnold_{slot}Range"
                range_shader = self._initialize_range_shader(range_path)
                range_shader.CreateInput("input", Sdf.ValueTypeNames.Float4).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(
                    range_shader.ConnectableAPI(),
                    "r",
                )
            elif slot == "roughness":
                range_path = f"{collect_path}/arnold_{slot}Range"
                range_shader = self._initialize_range_shader(range_path)
                range_shader.CreateInput("input", Sdf.ValueTypeNames.Float4).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(
                    range_shader.ConnectableAPI(),
                    "r",
                )
            elif slot == "opacity":
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgb",
                )
            elif slot == "displacement":
                range_path = f"{collect_path}/arnold_{slot}Range"
                range_shader = self._initialize_range_shader(range_path)
                range_shader.CreateInput("input", Sdf.ValueTypeNames.Float4).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                if not bump2d_shader:
                    bump2d_shader = self._initialize_bump2d_shader(bump2d_path)
                bump_map_input = bump2d_shader.GetInput("bump_map")
                if not bump_map_input:
                    bump_map_input = bump2d_shader.CreateInput("bump_map", Sdf.ValueTypeNames.Float)
                bump_map_input.ConnectToSource(range_shader.ConnectableAPI(), "r")
            elif slot == "normal":
                normal_map_path = f"{collect_path}/arnold_NormalMap"
                normal_map_shader = self._initialize_normal_map_shader(normal_map_path)
                normal_map_shader.CreateInput("input", Sdf.ValueTypeNames.Float3).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "vector",
                )
                if not bump2d_shader:
                    bump2d_shader = self._initialize_bump2d_shader(bump2d_path)
                normal_input = bump2d_shader.GetInput("normal")
                if not normal_input:
                    normal_input = bump2d_shader.CreateInput("normal", Sdf.ValueTypeNames.Float3)
                normal_input.ConnectToSource(normal_map_shader.ConnectableAPI(), "vector")

        if bump2d_shader:
            std_surf_shader.CreateInput("normal", Sdf.ValueTypeNames.Float3).ConnectToSource(
                bump2d_shader.ConnectableAPI(),
                "vector",
            )


class MtlxBuilder:
    def __init__(self, context: MaterialBuildContext) -> None:
        self._context = context

    def build(self, collect_path: str) -> UsdShade.NodeGraph:
        stage = self._context.stage
        override = self._context.texture_format_overrides.for_renderer(RENDERER_MTLX)

        nodegraph_path = f"{collect_path}/MtlxNodeGraph"
        nodegraph = UsdShade.NodeGraph.Define(stage, nodegraph_path)

        shader_path = f"{nodegraph_path}/mtlx_mtlxstandard_surface1"
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("ND_standard_surface_surfaceshader")

        nodegraph_output = nodegraph.CreateOutput("surface", Sdf.ValueTypeNames.Token)
        nodegraph_output.ConnectToSource(shader.ConnectableAPI(), "surface")

        self._initialize_standard_surface(shader)
        self._wire_textures(nodegraph_path, shader, override)

        if self._context.is_transmissive:
            self._enable_transmission(shader)

        return nodegraph

    def _initialize_standard_surface(self, shader: UsdShade.Shader) -> None:
        shader.CreateInput("base", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.8, 0.8, 0.8))
        shader.CreateInput("coat", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("coat_roughness", Sdf.ValueTypeNames.Float).Set(0.1)
        shader.CreateInput("emission", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("emission_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("metalness", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("specular_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("specular_IOR", Sdf.ValueTypeNames.Float).Set(1.5)
        shader.CreateInput("specular_roughness", Sdf.ValueTypeNames.Float).Set(0.2)
        shader.CreateInput("transmission", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("thin_walled", Sdf.ValueTypeNames.Int).Set(0)
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1, 1, 1))

    def _initialize_image_shader(self, image_path: str, signature: str = "color3") -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, image_path)
        shader.CreateIdAttr(f"ND_image_{signature}")
        shader.CreateInput("file", Sdf.ValueTypeNames.Asset)
        return shader

    def _initialize_color_correct_shader(
        self,
        color_correct_path: str,
        signature: str = "color3",
    ) -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, color_correct_path)
        shader.CreateIdAttr(f"ND_colorcorrect_{signature}")
        return shader

    def _initialize_range_shader(self, range_path: str, signature: str = "color3") -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, range_path)
        shader.CreateIdAttr(f"ND_range_{signature}")
        return shader

    def _initialize_normal_map_shader(self, normal_map_path: str) -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, normal_map_path)
        shader.CreateIdAttr("ND_normalmap")
        return shader

    def _enable_transmission(self, shader: UsdShade.Shader) -> None:
        shader.GetInput("transmission").Set(0.9)
        shader.GetInput("thin_walled").Set(1)

    def _wire_textures(
        self,
        collect_path: str,
        std_surf_shader: UsdShade.Shader,
        override: Optional[str],
    ) -> None:
        mtlx_image_signature = {
            "basecolor": "color3",
            "normal": "vector3",
            "metalness": "float",
            "opacity": "color3",
            "roughness": "float",
            "displacement": "float",
        }

        for slot, input_name, path in _iter_textures(self._context, MTLX_INPUTS, "mtlx"):
            tex_filepath = apply_texture_format_override(path, override)
            texture_prim_path = f"{collect_path}/mtlx_{slot}Texture"
            texture_shader = self._initialize_image_shader(
                texture_prim_path,
                signature=mtlx_image_signature[slot],
            )
            texture_shader.GetInput("file").Set(tex_filepath)

            if slot == "basecolor":
                color_correct_path = f"{collect_path}/mtlx_{slot}ColorCorrect"
                color_correct_shader = self._initialize_color_correct_shader(color_correct_path)
                color_correct_shader.CreateInput("in", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    color_correct_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "metalness":
                if self._context.is_transmissive:
                    continue
                range_path = f"{collect_path}/mtlx_{slot}Range"
                range_shader = self._initialize_range_shader(range_path, signature="float")
                range_shader.CreateInput("in", Sdf.ValueTypeNames.Float).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(
                    range_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "roughness":
                range_path = f"{collect_path}/mtlx_{slot}Range"
                range_shader = self._initialize_range_shader(range_path, signature="float")
                range_shader.CreateInput("in", Sdf.ValueTypeNames.Float).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(
                    range_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "opacity":
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "normal":
                normal_map_path = f"{collect_path}/mtlx_NormalMap"
                normal_map_shader = self._initialize_normal_map_shader(normal_map_path)
                normal_map_shader.CreateInput("in", Sdf.ValueTypeNames.Float3).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(
                    normal_map_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "displacement":
                continue


class OpenPbrBuilder:
    def __init__(self, context: MaterialBuildContext) -> None:
        self._context = context

    def build(self, collect_path: str) -> UsdShade.NodeGraph:
        stage = self._context.stage
        override = self._context.texture_format_overrides.for_renderer(RENDERER_OPENPBR)

        nodegraph_path = f"{collect_path}/OpenPbrNodeGraph"
        nodegraph = UsdShade.NodeGraph.Define(stage, nodegraph_path)

        shader_path = f"{nodegraph_path}/openpbr_surface1"
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("ND_open_pbr_surface_surfaceshader")

        nodegraph_output = nodegraph.CreateOutput("surface", Sdf.ValueTypeNames.Token)
        nodegraph_output.ConnectToSource(shader.ConnectableAPI(), "surface")

        self._initialize_surface(shader)
        self._wire_textures(nodegraph_path, shader, override)

        if self._context.is_transmissive:
            self._enable_transmission(shader)

        return nodegraph

    def _initialize_surface(self, shader: UsdShade.Shader) -> None:
        shader.CreateInput("base", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.8, 0.8, 0.8))
        shader.CreateInput("coat", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("coat_roughness", Sdf.ValueTypeNames.Float).Set(0.1)
        shader.CreateInput("emission", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("emission_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("metalness", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("specular", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("specular_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("specular_IOR", Sdf.ValueTypeNames.Float).Set(1.5)
        shader.CreateInput("specular_roughness", Sdf.ValueTypeNames.Float).Set(0.2)
        shader.CreateInput("transmission", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("thin_walled", Sdf.ValueTypeNames.Int).Set(0)
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1, 1, 1))

    def _initialize_image_shader(self, image_path: str, signature: str = "color3") -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, image_path)
        shader.CreateIdAttr(f"ND_image_{signature}")
        shader.CreateInput("file", Sdf.ValueTypeNames.Asset)
        return shader

    def _initialize_color_correct_shader(
        self,
        color_correct_path: str,
        signature: str = "color3",
    ) -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, color_correct_path)
        shader.CreateIdAttr(f"ND_colorcorrect_{signature}")
        return shader

    def _initialize_range_shader(self, range_path: str, signature: str = "color3") -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, range_path)
        shader.CreateIdAttr(f"ND_range_{signature}")
        return shader

    def _initialize_normal_map_shader(self, normal_map_path: str) -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, normal_map_path)
        shader.CreateIdAttr("ND_normalmap")
        return shader

    def _enable_transmission(self, shader: UsdShade.Shader) -> None:
        shader.GetInput("transmission").Set(0.9)
        shader.GetInput("thin_walled").Set(1)

    def _wire_textures(
        self,
        collect_path: str,
        std_surf_shader: UsdShade.Shader,
        override: Optional[str],
    ) -> None:
        image_signature = {
            "basecolor": "color3",
            "normal": "vector3",
            "metalness": "float",
            "opacity": "color3",
            "roughness": "float",
            "displacement": "float",
        }

        for slot, input_name, path in _iter_textures(self._context, OPENPBR_INPUTS, "openpbr"):
            tex_filepath = apply_texture_format_override(path, override)
            texture_prim_path = f"{collect_path}/openpbr_{slot}Texture"
            texture_shader = self._initialize_image_shader(
                texture_prim_path,
                signature=image_signature[slot],
            )
            texture_shader.GetInput("file").Set(tex_filepath)

            if slot == "basecolor":
                color_correct_path = f"{collect_path}/openpbr_{slot}ColorCorrect"
                color_correct_shader = self._initialize_color_correct_shader(color_correct_path)
                color_correct_shader.CreateInput("in", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    color_correct_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "metalness":
                if self._context.is_transmissive:
                    continue
                range_path = f"{collect_path}/openpbr_{slot}Range"
                range_shader = self._initialize_range_shader(range_path, signature="float")
                range_shader.CreateInput("in", Sdf.ValueTypeNames.Float).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(
                    range_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "roughness":
                range_path = f"{collect_path}/openpbr_{slot}Range"
                range_shader = self._initialize_range_shader(range_path, signature="float")
                range_shader.CreateInput("in", Sdf.ValueTypeNames.Float).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float).ConnectToSource(
                    range_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "opacity":
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "normal":
                normal_map_path = f"{collect_path}/openpbr_NormalMap"
                normal_map_shader = self._initialize_normal_map_shader(normal_map_path)
                normal_map_shader.CreateInput("in", Sdf.ValueTypeNames.Float3).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
                std_surf_shader.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(
                    normal_map_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "displacement":
                continue
