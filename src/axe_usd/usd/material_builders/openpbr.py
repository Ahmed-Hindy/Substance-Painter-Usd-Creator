"""OpenPBR shader network builder."""

from pxr import Gf, Sdf, UsdShade

from .base import (
    RENDERER_OPENPBR,
    _MtlxLikeBuilder,
    _connect_nodegraph_output,
)

OPENPBR_INPUTS = {
    "basecolor": "base_color",
    "emission": "emission_color",
    "metalness": "base_metalness",
    "roughness": "specular_roughness",
    "normal": "geometry_normal",
    "opacity": "geometry_opacity",
    "displacement": "displacement",
}

OPENPBR_IMAGE_SIGNATURES = {
    "basecolor": "color3",
    "emission": "color3",
    "normal": "vector3",
    "metalness": "float",
    "opacity": "float",
    "roughness": "float",
    "displacement": "float",
}


class OpenPbrBuilder(_MtlxLikeBuilder):
    input_map = OPENPBR_INPUTS
    renderer_name = "openpbr"
    texture_prefix = "openpbr"
    image_signatures = OPENPBR_IMAGE_SIGNATURES
    emission_intensity_input = "emission_luminance"

    def build(self, collect_path: str) -> UsdShade.NodeGraph:
        stage = self._context.stage
        override = self._context.texture_format_overrides.for_renderer(RENDERER_OPENPBR)

        nodegraph_path = f"{collect_path}/OpenPbrNodeGraph"
        nodegraph = UsdShade.NodeGraph.Define(stage, nodegraph_path)

        shader_path = f"{nodegraph_path}/openpbr_surface1"
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("ND_open_pbr_surface_surfaceshader")

        _connect_nodegraph_output(
            nodegraph, "surface", Sdf.ValueTypeNames.Token, shader, "out"
        )

        self._initialize_surface(shader)
        self._wire_textures(nodegraph, nodegraph_path, shader, override)

        if self._context.is_transmissive:
            self._enable_transmission(shader)

        return nodegraph

    def _initialize_surface(self, shader: UsdShade.Shader) -> None:
        shader.CreateInput("base_weight", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(0.8, 0.8, 0.8)
        )
        shader.CreateInput("base_diffuse_roughness", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("base_metalness", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("specular_weight", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("specular_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("specular_ior", Sdf.ValueTypeNames.Float).Set(1.5)
        shader.CreateInput("specular_roughness", Sdf.ValueTypeNames.Float).Set(0.2)
        shader.CreateInput("coat_weight", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("coat_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("coat_roughness", Sdf.ValueTypeNames.Float).Set(0.1)
        shader.CreateInput("coat_ior", Sdf.ValueTypeNames.Float).Set(1.6)
        shader.CreateInput("emission_color", Sdf.ValueTypeNames.Float3).Set((1, 1, 1))
        shader.CreateInput("emission_luminance", Sdf.ValueTypeNames.Float).Set(0)
        shader.CreateInput("geometry_opacity", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("geometry_thin_walled", Sdf.ValueTypeNames.Bool).Set(False)

    def _connect_displacement(
        self,
        nodegraph: UsdShade.NodeGraph,
        _std_surf_shader: UsdShade.Shader,
        _input_name: str,
        texture_shader: UsdShade.Shader,
    ) -> None:
        _connect_nodegraph_output(
            nodegraph, "displacement", Sdf.ValueTypeNames.Float, texture_shader, "out"
        )
