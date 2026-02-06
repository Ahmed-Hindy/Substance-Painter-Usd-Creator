"""MaterialX standard surface shader builder."""

from pxr import Gf, Sdf, UsdShade

from .base import (
    MaterialBuildContext,
    RENDERER_MTLX,
    _MtlxLikeBuilder,
    _connect_nodegraph_output,
)

MTLX_INPUTS = {
    "basecolor": "base_color",
    "emission": "emission_color",
    "metalness": "metalness",
    "roughness": "specular_roughness",
    "normal": "normal",
    "opacity": "opacity",
    "displacement": "displacement",
}


class MtlxBuilder(_MtlxLikeBuilder):
    input_map = MTLX_INPUTS
    renderer_name = "mtlx"
    texture_prefix = "mtlx"

    def build(self, collect_path: str) -> UsdShade.NodeGraph:
        stage = self._context.stage
        override = self._context.texture_format_overrides.for_renderer(RENDERER_MTLX)

        nodegraph_path = f"{collect_path}/MtlxNodeGraph"
        nodegraph = UsdShade.NodeGraph.Define(stage, nodegraph_path)

        shader_path = f"{nodegraph_path}/mtlx_mtlxstandard_surface1"
        shader = UsdShade.Shader.Define(stage, shader_path)
        shader.CreateIdAttr("ND_standard_surface_surfaceshader")

        _connect_nodegraph_output(
            nodegraph, "surface", Sdf.ValueTypeNames.Token, shader, "surface"
        )

        self._initialize_standard_surface(shader)
        self._wire_textures(nodegraph, nodegraph_path, shader, override)

        if self._context.is_transmissive:
            self._enable_transmission(shader)

        return nodegraph

    def _initialize_standard_surface(self, shader: UsdShade.Shader) -> None:
        shader.CreateInput("base", Sdf.ValueTypeNames.Float).Set(1)
        shader.CreateInput("base_color", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(0.8, 0.8, 0.8)
        )
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
        shader.CreateInput("opacity", Sdf.ValueTypeNames.Color3f).Set(
            Gf.Vec3f(1, 1, 1)
        )

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
