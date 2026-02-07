"""UsdPreviewSurface shader network builder."""

from pathlib import Path

from pxr import Sdf, UsdShade

from .base import MaterialBuildContext, _connect_nodegraph_output

PREVIEW_TEXTURE_DIRNAME = "previewTextures"
PREVIEW_TEXTURE_SUFFIX = ".jpg"


def _preview_texture_path(path: str, mat_name: str) -> str:
    source_path = Path(path)
    if "<UDIM>" in path:
        preview_name = f"{mat_name}_BaseColor.<UDIM>{PREVIEW_TEXTURE_SUFFIX}"
    else:
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
        _connect_nodegraph_output(
            nodegraph, "surface", Sdf.ValueTypeNames.Token, shader, "surface"
        )
        material.CreateSurfaceOutput().ConnectToSource(
            nodegraph.ConnectableAPI(), "surface"
        )

        st_reader_path = f"{nodegraph_path}/TexCoordReader"
        st_reader = UsdShade.Shader.Define(stage, st_reader_path)
        st_reader.CreateIdAttr("UsdPrimvarReader_float2")
        st_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

        def _define_texture(texture_name: str, file_path: str) -> UsdShade.Shader:
            texture_prim_path = f"{nodegraph_path}/{texture_name}"
            texture_prim = UsdShade.Shader.Define(stage, texture_prim_path)
            texture_prim.CreateIdAttr("UsdUVTexture")
            texture_prim.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(file_path)
            texture_prim.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
            texture_prim.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")
            texture_prim.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                st_reader.ConnectableAPI(), "result"
            )
            return texture_prim

        base_info = self._context.material_dict.get("basecolor")
        if base_info:
            path = base_info.get("path")
            if path:
                mat_name = base_info.get("mat_name", "")
                tex_filepath = _preview_texture_path(path, mat_name)
                texture_prim = _define_texture("basecolorTexture", tex_filepath)
                shader.CreateInput(
                    "diffuseColor", Sdf.ValueTypeNames.Float3
                ).ConnectToSource(
                    texture_prim.ConnectableAPI(),
                    "rgb",
                )

        return shader
