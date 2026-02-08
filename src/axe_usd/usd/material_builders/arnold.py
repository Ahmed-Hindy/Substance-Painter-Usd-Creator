"""Arnold shader network builder."""

from typing import Optional

from pxr import Sdf, UsdShade

from .base import (
    ARNOLD_DISPLACEMENT_BUMP,
    MaterialBuildContext,
    RENDERER_ARNOLD,
    _connect_nodegraph_output,
    _iter_textures,
)
from .arnold_defaults import initialize_standard_surface
from ..material_model import apply_texture_format_override

ARNOLD_INPUTS = {
    "basecolor": "base_color",
    "emission": "emission_color",
    "metalness": "base_metalness",
    "roughness": "specular_roughness",
    "normal": "normal",
    "opacity": "opacity",
    "displacement": "height",
}


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

        _connect_nodegraph_output(
            nodegraph, "surface", Sdf.ValueTypeNames.Token, shader, "surface"
        )

        initialize_standard_surface(shader)
        self._wire_textures(nodegraph, nodegraph_path, shader, override)

        if self._context.is_transmissive:
            self._enable_transmission(shader)

        return nodegraph

    def _initialize_image_shader(self, image_path: str) -> UsdShade.Shader:
        image_shader = UsdShade.Shader.Define(self._context.stage, image_path)
        image_shader.CreateIdAttr("arnold:image")
        image_shader.CreateInput("color_space", Sdf.ValueTypeNames.String).Set("auto")
        image_shader.CreateInput("filename", Sdf.ValueTypeNames.Asset)
        image_shader.CreateInput("filter", Sdf.ValueTypeNames.String).Set(
            "smart_bicubic"
        )
        image_shader.CreateInput(
            "ignore_missing_textures", Sdf.ValueTypeNames.Bool
        ).Set(False)
        image_shader.CreateInput("mipmap_bias", Sdf.ValueTypeNames.Int).Set(0)
        image_shader.CreateInput(
            "missing_texture_color", Sdf.ValueTypeNames.Float4
        ).Set((0, 0, 0, 0))
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

    def _initialize_color_correct_shader(
        self, color_correct_path: str
    ) -> UsdShade.Shader:
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

    def _initialize_displacement_shader(
        self, displacement_path: str
    ) -> UsdShade.Shader:
        shader = UsdShade.Shader.Define(self._context.stage, displacement_path)
        shader.CreateIdAttr("arnold:displacement")
        return shader

    def _enable_transmission(self, shader: UsdShade.Shader) -> None:
        shader.GetInput("transmission").Set(0.9)
        shader.GetInput("thin_walled").Set(True)

    def _wire_textures(
        self,
        nodegraph: UsdShade.NodeGraph,
        collect_path: str,
        std_surf_shader: UsdShade.Shader,
        override: Optional[str],
    ) -> None:
        bump2d_path = f"{collect_path}/arnold_Bump2d"
        bump2d_shader = None

        for slot, input_name, path in _iter_textures(
            self._context, ARNOLD_INPUTS, "arnold"
        ):
            tex_filepath = apply_texture_format_override(path, override)
            texture_prim_path = f"{collect_path}/arnold_{slot}Texture"
            texture_shader = self._initialize_image_shader(texture_prim_path)
            texture_shader.GetInput("filename").Set(tex_filepath)

            if slot == "basecolor":
                color_correct_path = f"{collect_path}/arnold_{slot}ColorCorrect"
                color_correct_shader = self._initialize_color_correct_shader(
                    color_correct_path
                )
                color_correct_shader.CreateInput(
                    "input", Sdf.ValueTypeNames.Float4
                ).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                std_surf_shader.CreateInput(
                    input_name, Sdf.ValueTypeNames.Float3
                ).ConnectToSource(
                    color_correct_shader.ConnectableAPI(),
                    "rgb",
                )
            elif slot == "emission":
                color_correct_path = f"{collect_path}/arnold_{slot}ColorCorrect"
                color_correct_shader = self._initialize_color_correct_shader(
                    color_correct_path
                )
                color_correct_shader.CreateInput(
                    "input", Sdf.ValueTypeNames.Float4
                ).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                std_surf_shader.CreateInput(
                    input_name, Sdf.ValueTypeNames.Float3
                ).ConnectToSource(
                    color_correct_shader.ConnectableAPI(),
                    "rgb",
                )
                emission_input = std_surf_shader.GetInput("emission")
                if emission_input:
                    emission_input.Set(1)
            elif slot == "metalness":
                if self._context.is_transmissive:
                    continue
                range_path = f"{collect_path}/arnold_{slot}Range"
                range_shader = self._initialize_range_shader(range_path)
                range_shader.CreateInput(
                    "input", Sdf.ValueTypeNames.Float4
                ).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                std_surf_shader.CreateInput(
                    input_name, Sdf.ValueTypeNames.Float
                ).ConnectToSource(
                    range_shader.ConnectableAPI(),
                    "r",
                )
            elif slot == "roughness":
                range_path = f"{collect_path}/arnold_{slot}Range"
                range_shader = self._initialize_range_shader(range_path)
                range_shader.CreateInput(
                    "input", Sdf.ValueTypeNames.Float4
                ).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                std_surf_shader.CreateInput(
                    input_name, Sdf.ValueTypeNames.Float
                ).ConnectToSource(
                    range_shader.ConnectableAPI(),
                    "r",
                )
            elif slot == "opacity":
                range_path = f"{collect_path}/arnold_{slot}Range"
                range_shader = self._initialize_range_shader(range_path)
                range_shader.CreateInput(
                    "input", Sdf.ValueTypeNames.Float4
                ).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                std_surf_shader.CreateInput(
                    input_name, Sdf.ValueTypeNames.Float3
                ).ConnectToSource(
                    range_shader.ConnectableAPI(),
                    "rgb",
                )
            elif slot == "displacement":
                range_path = f"{collect_path}/arnold_{slot}Range"
                range_shader = self._initialize_range_shader(range_path)
                range_shader.CreateInput(
                    "input", Sdf.ValueTypeNames.Float4
                ).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "rgba",
                )
                if self._context.arnold_displacement_mode == ARNOLD_DISPLACEMENT_BUMP:
                    if not bump2d_shader:
                        bump2d_shader = self._initialize_bump2d_shader(bump2d_path)
                    bump_map_input = bump2d_shader.GetInput("bump_map")
                    if not bump_map_input:
                        bump_map_input = bump2d_shader.CreateInput(
                            "bump_map", Sdf.ValueTypeNames.Float
                        )
                    bump_map_input.ConnectToSource(range_shader.ConnectableAPI(), "r")
                else:
                    displacement_path = f"{collect_path}/arnold_Displacement"
                    displacement_shader = self._initialize_displacement_shader(
                        displacement_path
                    )
                    displacement_shader.CreateInput(
                        "height", Sdf.ValueTypeNames.Float
                    ).ConnectToSource(
                        range_shader.ConnectableAPI(),
                        "r",
                    )
                    _connect_nodegraph_output(
                        nodegraph,
                        "displacement",
                        Sdf.ValueTypeNames.Token,
                        displacement_shader,
                        "out",
                    )
            elif slot == "normal":
                normal_map_path = f"{collect_path}/arnold_NormalMap"
                normal_map_shader = self._initialize_normal_map_shader(normal_map_path)
                normal_map_shader.CreateInput(
                    "input", Sdf.ValueTypeNames.Float3
                ).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "vector",
                )
                if not bump2d_shader:
                    bump2d_shader = self._initialize_bump2d_shader(bump2d_path)
                normal_input = bump2d_shader.GetInput("normal")
                if not normal_input:
                    normal_input = bump2d_shader.CreateInput(
                        "normal", Sdf.ValueTypeNames.Float3
                    )
                normal_input.ConnectToSource(
                    normal_map_shader.ConnectableAPI(), "vector"
                )

        if bump2d_shader:
            std_surf_shader.CreateInput(
                "normal", Sdf.ValueTypeNames.Float3
            ).ConnectToSource(
                bump2d_shader.ConnectableAPI(),
                "vector",
            )
