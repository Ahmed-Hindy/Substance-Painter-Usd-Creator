"""Shared helpers for USD material builders."""

from dataclasses import dataclass
import logging
from typing import Dict, Iterable, Optional, Tuple

from pxr import Sdf, Usd, UsdShade

from ..material_model import TextureFormatOverrides, apply_texture_format_override
from ..types import MaterialTextureDict

RENDERER_ARNOLD = "arnold"
RENDERER_MTLX = "mtlx"
RENDERER_OPENPBR = "openpbr"

ARNOLD_DISPLACEMENT_BUMP = "bump"
ARNOLD_DISPLACEMENT_DISPLACEMENT = "displacement"

MTLX_LIKE_IMAGE_SIGNATURE = {
    "basecolor": "color3",
    "emission": "color3",
    "normal": "vector3",
    "metalness": "float",
    "opacity": "color3",
    "roughness": "float",
    "displacement": "float",
}


@dataclass(frozen=True)
class MaterialBuildContext:
    stage: Usd.Stage
    material_dict: MaterialTextureDict
    is_transmissive: bool
    texture_format_overrides: TextureFormatOverrides
    logger: logging.Logger
    arnold_displacement_mode: str = ARNOLD_DISPLACEMENT_BUMP


def _iter_textures(
    context: MaterialBuildContext,
    input_map: Dict[str, str],
    renderer_name: str,
) -> Iterable[Tuple[str, str, str]]:
    for slot, info in context.material_dict.items():
        input_name = input_map.get(slot)
        if not input_name:
            context.logger.warning(
                "Texture slot '%s' not supported for %s.", slot, renderer_name
            )
            continue
        path = info.get("path")
        if not path:
            context.logger.warning("Texture slot '%s' missing path; skipping.", slot)
            continue
        yield slot, input_name, path


def _connect_nodegraph_output(
    nodegraph: UsdShade.NodeGraph,
    output_name: str,
    output_type: Sdf.ValueTypeNames,
    source: UsdShade.Shader,
    source_output: str,
) -> UsdShade.Output:
    output = nodegraph.CreateOutput(output_name, output_type)
    output.ConnectToSource(source.ConnectableAPI(), source_output)
    return output


class _MtlxLikeBuilder:
    input_map: Dict[str, str] = {}
    renderer_name = ""
    texture_prefix = ""
    image_signatures = MTLX_LIKE_IMAGE_SIGNATURE
    emission_intensity_input = "emission"

    def __init__(self, context: MaterialBuildContext) -> None:
        self._context = context

    def _initialize_image_shader(
        self, image_path: str, signature: str = "color3"
    ) -> UsdShade.Shader:
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

    def _initialize_range_shader(
        self, range_path: str, signature: str = "color3"
    ) -> UsdShade.Shader:
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

    def _connect_color_correct(
        self,
        collect_path: str,
        slot: str,
        texture_shader: UsdShade.Shader,
        std_surf_shader: UsdShade.Shader,
        input_name: str,
    ) -> None:
        color_correct_path = f"{collect_path}/{self.texture_prefix}_{slot}ColorCorrect"
        color_correct_shader = self._initialize_color_correct_shader(
            color_correct_path
        )
        color_correct_shader.CreateInput(
            "in", Sdf.ValueTypeNames.Color3f
        ).ConnectToSource(
            texture_shader.ConnectableAPI(),
            "out",
        )
        std_surf_shader.CreateInput(
            input_name, Sdf.ValueTypeNames.Color3f
        ).ConnectToSource(
            color_correct_shader.ConnectableAPI(),
            "out",
        )

    def _connect_range(
        self,
        collect_path: str,
        slot: str,
        texture_shader: UsdShade.Shader,
        std_surf_shader: UsdShade.Shader,
        input_name: str,
    ) -> None:
        range_path = f"{collect_path}/{self.texture_prefix}_{slot}Range"
        range_shader = self._initialize_range_shader(range_path, signature="float")
        range_shader.CreateInput(
            "in", Sdf.ValueTypeNames.Float
        ).ConnectToSource(
            texture_shader.ConnectableAPI(),
            "out",
        )
        std_surf_shader.CreateInput(
            input_name, Sdf.ValueTypeNames.Float
        ).ConnectToSource(
            range_shader.ConnectableAPI(),
            "out",
        )

    def _connect_normal(
        self,
        collect_path: str,
        texture_shader: UsdShade.Shader,
        std_surf_shader: UsdShade.Shader,
        input_name: str,
    ) -> None:
        normal_map_path = f"{collect_path}/{self.texture_prefix}_NormalMap"
        normal_map_shader = self._initialize_normal_map_shader(normal_map_path)
        normal_map_shader.CreateInput(
            "in", Sdf.ValueTypeNames.Float3
        ).ConnectToSource(
            texture_shader.ConnectableAPI(),
            "out",
        )
        std_surf_shader.CreateInput(
            input_name, Sdf.ValueTypeNames.Float3
        ).ConnectToSource(
            normal_map_shader.ConnectableAPI(),
            "out",
        )

    def _connect_displacement(
        self,
        _nodegraph: UsdShade.NodeGraph,
        std_surf_shader: UsdShade.Shader,
        input_name: str,
        texture_shader: UsdShade.Shader,
    ) -> None:
        std_surf_shader.CreateInput(
            input_name, Sdf.ValueTypeNames.Float
        ).ConnectToSource(
            texture_shader.ConnectableAPI(),
            "out",
        )

    def _wire_textures(
        self,
        nodegraph: UsdShade.NodeGraph,
        collect_path: str,
        std_surf_shader: UsdShade.Shader,
        override: Optional[str],
    ) -> None:
        for slot, input_name, path in _iter_textures(
            self._context, self.input_map, self.renderer_name
        ):
            tex_filepath = apply_texture_format_override(path, override)
            texture_prim_path = f"{collect_path}/{self.texture_prefix}_{slot}Texture"
            texture_shader = self._initialize_image_shader(
                texture_prim_path,
                signature=self.image_signatures[slot],
            )
            texture_shader.GetInput("file").Set(tex_filepath)

            if slot == "basecolor":
                self._connect_color_correct(
                    collect_path, slot, texture_shader, std_surf_shader, input_name
                )
            elif slot == "emission":
                std_surf_shader.CreateInput(
                    input_name, Sdf.ValueTypeNames.Color3f
                ).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
                emission_input = std_surf_shader.GetInput(self.emission_intensity_input)
                if emission_input:
                    emission_input.Set(1)
            elif slot in {"metalness", "roughness"}:
                if slot == "metalness" and self._context.is_transmissive:
                    continue
                self._connect_range(
                    collect_path, slot, texture_shader, std_surf_shader, input_name
                )
            elif slot == "opacity":
                opacity_type = (
                    Sdf.ValueTypeNames.Float
                    if self.image_signatures[slot] == "float"
                    else Sdf.ValueTypeNames.Color3f
                )
                std_surf_shader.CreateInput(
                    input_name, opacity_type
                ).ConnectToSource(
                    texture_shader.ConnectableAPI(),
                    "out",
                )
            elif slot == "normal":
                self._connect_normal(
                    collect_path, texture_shader, std_surf_shader, input_name
                )
            elif slot == "displacement":
                self._connect_displacement(
                    nodegraph, std_surf_shader, input_name, texture_shader
                )
