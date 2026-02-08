import shutil
from pathlib import Path

import pytest
from pxr import Sdf, Usd, UsdGeom, UsdShade

from axe_usd.usd import material_processor

SP_SAMPLE_USD = Path(
    r"C:\Users\Ahmed Hindy\AppData\Local\Temp\axe_usd_test_aif40bu7\SPsample_v002\SPsample_v002.usd"
)


@pytest.fixture
def sp_sample_sources() -> dict[str, Path]:
    textures_dir = SP_SAMPLE_USD.parent / "textures"
    if not textures_dir.exists():
        pytest.skip(f"Missing SP sample textures: {textures_dir}")

    def _pick(pattern: str) -> Path:
        matches = sorted(textures_dir.glob(pattern))
        if not matches:
            raise AssertionError(
                f"Missing texture match for {pattern} in {textures_dir}"
            )
        return matches[0]

    return {
        "basecolor": _pick("*_BaseColor.png"),
        "metalness": _pick("*_Metalness.png"),
        "normal": _pick("*_Normal.png"),
        "roughness": _pick("*_Roughness.png"),
        "displacement": _pick("*_Height.png"),
    }


@pytest.fixture
def sp_texture_factory(sp_sample_sources, tmp_path):
    name_map = {
        "basecolor": "MatA_BaseColor",
        "metalness": "MatA_Metalness",
        "normal": "MatA_Normal",
        "roughness": "MatA_Roughness",
        "displacement": "MatA_Height",
    }

    def _make(ext_overrides=None) -> dict[str, Path]:
        ext_overrides = ext_overrides or {}
        dest_dir = tmp_path / "source_textures"
        dest_dir.mkdir(parents=True, exist_ok=True)
        copied: dict[str, Path] = {}
        for slot, src in sp_sample_sources.items():
            ext = ext_overrides.get(slot, src.suffix)
            if not ext.startswith("."):
                ext = f".{ext}"
            dest = dest_dir / f"{name_map[slot]}{ext}"
            shutil.copy2(src, dest)
            copied[slot] = dest
        return copied

    return _make


def _material_dict_from_paths(
    paths: dict[str, Path],
) -> list[dict[str, dict[str, str]]]:
    material_dict: dict[str, dict[str, str]] = {}
    for slot, path in paths.items():
        material_dict[slot] = {"mat_name": "MatA", "path": str(path)}
    return [material_dict]


def _asset_path_value(input_attr):
    value = input_attr.Get()
    path = value.path if hasattr(value, "path") else value
    if path is None:
        return None
    normalized = str(path).replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def test_create_shaded_asset_publish_creates_layers(tmp_path, sp_texture_factory):
    """Ensure USD publish creates the expected component layer files."""
    textures = sp_texture_factory()
    material_dict_list = _material_dict_from_paths({"basecolor": textures["basecolor"]})

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=True,
        create_arnold=False,
        create_mtlx=False,
    )

    # Convert tmp_path to consistent string for tests
    asset_dir = tmp_path / "Asset"
    assert (asset_dir / "Asset.usd").exists()
    assert (asset_dir / "mtl.usdc").exists()
    assert (asset_dir / "payload.usdc").exists()
    assert (asset_dir / "geo.usdc").exists()


def test_usd_preview_texture_override_applies(tmp_path, sp_texture_factory):
    """Ensure usd preview textures honor per-renderer format overrides."""
    textures = sp_texture_factory({"basecolor": ".exr"})
    material_dict_list = _material_dict_from_paths({"basecolor": textures["basecolor"]})

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=True,
        create_arnold=False,
        create_mtlx=False,
        texture_format_overrides={"usd_preview": "jpg"},
    )

    # Open mtl.usdc to check material definitions
    stage = Usd.Stage.Open(str(tmp_path / "Asset/mtl.usdc"))
    texture_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/UsdPreviewNodeGraph/basecolorTexture"
    )
    texture_shader = UsdShade.Shader(texture_prim)
    assert (
        _asset_path_value(texture_shader.GetInput("file"))
        == "textures/previewTextures/MatA_BaseColor.jpg"
    )


def test_renderer_specific_format_overrides(tmp_path, sp_texture_factory):
    """Ensure per-renderer overrides apply to each network."""
    textures = sp_texture_factory({"basecolor": ".exr"})
    material_dict_list = _material_dict_from_paths({"basecolor": textures["basecolor"]})

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=True,
        create_arnold=True,
        create_mtlx=True,
        texture_format_overrides={
            "usd_preview": "jpg",
            "arnold": "tif",
            "mtlx": "png",
        },
    )

    # Open mtl.usdc to check materials
    stage = Usd.Stage.Open(str(tmp_path / "Asset/mtl.usdc"))

    usd_preview_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/UsdPreviewNodeGraph/basecolorTexture"
    )
    usd_preview_shader = UsdShade.Shader(usd_preview_prim)
    assert (
        _asset_path_value(usd_preview_shader.GetInput("file"))
        == "textures/previewTextures/MatA_BaseColor.jpg"
    )

    arnold_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/ArnoldNodeGraph/arnold_basecolorTexture"
    )
    arnold_shader = UsdShade.Shader(arnold_prim)
    assert (
        _asset_path_value(arnold_shader.GetInput("filename"))
        == "textures/MatA_BaseColor.tif"
    )

    mtlx_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/MtlxNodeGraph/mtlx_basecolorTexture"
    )
    mtlx_shader = UsdShade.Shader(mtlx_prim)
    assert (
        _asset_path_value(mtlx_shader.GetInput("file")) == "textures/MatA_BaseColor.png"
    )


def test_emission_and_opacity_wired_for_non_preview_renderers(tmp_path):
    """Emission and opacity textures should wire for non-preview renderers."""
    src_dir = tmp_path / "source_textures"
    src_dir.mkdir(parents=True, exist_ok=True)
    base_path = src_dir / "MatA_BaseColor.png"
    emission_path = src_dir / "MatA_Emissive.png"
    opacity_path = src_dir / "MatA_Opacity.png"
    base_path.write_bytes(b"base")
    emission_path.write_bytes(b"emission")
    opacity_path.write_bytes(b"opacity")

    material_dict_list = [
        {
            "basecolor": {"mat_name": "MatA", "path": str(base_path)},
            "emission": {"mat_name": "MatA", "path": str(emission_path)},
            "opacity": {"mat_name": "MatA", "path": str(opacity_path)},
        }
    ]

    standard_dir = tmp_path / "standard_publish"
    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(standard_dir),
        main_layer_name="main.usda",
        create_usd_preview=True,
        create_arnold=True,
        create_mtlx=True,
        create_openpbr=False,
    )

    stage = Usd.Stage.Open(str(standard_dir / "Asset/mtl.usdc"))

    for slot in ("emission", "opacity"):
        assert not stage.GetPrimAtPath(
            f"/Asset/mtl/MatA/UsdPreviewNodeGraph/{slot}Texture"
        ).IsValid()

    arnold_shader = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/ArnoldNodeGraph/arnold_standard_surface1")
    )
    assert arnold_shader.GetInput("emission").Get() == 1
    arnold_opacity_input = arnold_shader.GetInput("opacity")
    assert arnold_opacity_input and arnold_opacity_input.HasConnectedSource()

    arnold_emission_tex = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/ArnoldNodeGraph/arnold_emissionTexture")
    )
    assert (
        _asset_path_value(arnold_emission_tex.GetInput("filename"))
        == "textures/MatA_Emissive.png"
    )
    arnold_opacity_tex = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/ArnoldNodeGraph/arnold_opacityTexture")
    )
    assert (
        _asset_path_value(arnold_opacity_tex.GetInput("filename"))
        == "textures/MatA_Opacity.png"
    )

    mtlx_shader = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/MtlxNodeGraph/mtlx_mtlxstandard_surface1")
    )
    assert mtlx_shader.GetInput("emission").Get() == 1
    mtlx_opacity_input = mtlx_shader.GetInput("opacity")
    assert mtlx_opacity_input and mtlx_opacity_input.HasConnectedSource()

    mtlx_emission_tex = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/MtlxNodeGraph/mtlx_emissionTexture")
    )
    assert (
        _asset_path_value(mtlx_emission_tex.GetInput("file"))
        == "textures/MatA_Emissive.png"
    )
    mtlx_opacity_tex = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/MtlxNodeGraph/mtlx_opacityTexture")
    )
    assert (
        _asset_path_value(mtlx_opacity_tex.GetInput("file"))
        == "textures/MatA_Opacity.png"
    )

    openpbr_src_dir = tmp_path / "openpbr_textures"
    openpbr_src_dir.mkdir(parents=True, exist_ok=True)
    openpbr_base = openpbr_src_dir / "MatA_BaseColor.png"
    openpbr_emission = openpbr_src_dir / "MatA_Emissive.png"
    openpbr_opacity = openpbr_src_dir / "MatA_Opacity.png"
    openpbr_base.write_bytes(b"base")
    openpbr_emission.write_bytes(b"emission")
    openpbr_opacity.write_bytes(b"opacity")

    openpbr_materials = [
        {
            "basecolor": {"mat_name": "MatA", "path": str(openpbr_base)},
            "emission": {"mat_name": "MatA", "path": str(openpbr_emission)},
            "opacity": {"mat_name": "MatA", "path": str(openpbr_opacity)},
        }
    ]

    openpbr_dir = tmp_path / "openpbr_publish"
    material_processor.create_shaded_asset_publish(
        material_dict_list=openpbr_materials,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(openpbr_dir),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=False,
        create_openpbr=True,
    )

    stage = Usd.Stage.Open(str(openpbr_dir / "Asset/mtl.usdc"))
    openpbr_shader = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/OpenPbrNodeGraph/openpbr_surface1")
    )
    assert openpbr_shader.GetInput("emission_luminance").Get() == 1
    openpbr_nodegraph = UsdShade.NodeGraph(
        stage.GetPrimAtPath("/Asset/mtl/MatA/OpenPbrNodeGraph")
    )
    openpbr_surface_output = openpbr_nodegraph.GetOutput("surface")
    assert openpbr_surface_output and openpbr_surface_output.HasConnectedSource()
    openpbr_surface_source = openpbr_surface_output.GetConnectedSource()
    assert openpbr_surface_source
    assert openpbr_surface_source[1] == "out"

    openpbr_material = UsdShade.Material(stage.GetPrimAtPath("/Asset/mtl/MatA"))
    openpbr_material_output = openpbr_material.GetOutput("mtlx:surface")
    assert openpbr_material_output and openpbr_material_output.HasConnectedSource()
    openpbr_material_source = openpbr_material_output.GetConnectedSource()
    assert openpbr_material_source
    assert openpbr_material_source[1] == "surface"
    assert (
        openpbr_material_source[0].GetPrim().GetPath()
        == openpbr_nodegraph.GetPrim().GetPath()
    )
    openpbr_opacity_input = openpbr_shader.GetInput("geometry_opacity")
    assert openpbr_opacity_input and openpbr_opacity_input.HasConnectedSource()
    openpbr_emission_tex = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/OpenPbrNodeGraph/openpbr_emissionTexture")
    )
    assert (
        _asset_path_value(openpbr_emission_tex.GetInput("file"))
        == "textures/MatA_Emissive.png"
    )
    openpbr_opacity_tex = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/OpenPbrNodeGraph/openpbr_opacityTexture")
    )
    assert (
        _asset_path_value(openpbr_opacity_tex.GetInput("file"))
        == "textures/MatA_Opacity.png"
    )


def test_mtlx_displacement_output_authored_with_multiple_textures(tmp_path):
    """MaterialX displacement output should be authored when multiple textures exist."""
    src_dir = tmp_path / "source_textures"
    src_dir.mkdir(parents=True, exist_ok=True)
    base_path = src_dir / "MatA_BaseColor.png"
    roughness_path = src_dir / "MatA_Roughness.png"
    normal_path = src_dir / "MatA_Normal.png"
    displacement_path = src_dir / "MatA_Height.png"
    base_path.write_bytes(b"base")
    roughness_path.write_bytes(b"roughness")
    normal_path.write_bytes(b"normal")
    displacement_path.write_bytes(b"height")

    material_dict_list = [
        {
            "basecolor": {"mat_name": "MatA", "path": str(base_path)},
            "roughness": {"mat_name": "MatA", "path": str(roughness_path)},
            "normal": {"mat_name": "MatA", "path": str(normal_path)},
            "displacement": {"mat_name": "MatA", "path": str(displacement_path)},
        }
    ]

    publish_dir = tmp_path / "mtlx_publish"
    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(publish_dir),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=True,
        create_openpbr=False,
    )

    stage = Usd.Stage.Open(str(publish_dir / "Asset/mtl.usdc"))
    mtlx_nodegraph = UsdShade.NodeGraph(
        stage.GetPrimAtPath("/Asset/mtl/MatA/MtlxNodeGraph")
    )
    mtlx_displacement_output = mtlx_nodegraph.GetOutput("displacement")
    assert mtlx_displacement_output and mtlx_displacement_output.HasConnectedSource()
    mtlx_displacement_source = mtlx_displacement_output.GetConnectedSource()
    assert mtlx_displacement_source
    assert mtlx_displacement_source[1] == "out"

    mtlx_material = UsdShade.Material(stage.GetPrimAtPath("/Asset/mtl/MatA"))
    mtlx_material_output = mtlx_material.GetOutput("mtlx:displacement")
    assert mtlx_material_output and mtlx_material_output.HasConnectedSource()
    mtlx_material_source = mtlx_material_output.GetConnectedSource()
    assert mtlx_material_source
    assert mtlx_material_source[1] == "displacement"
    assert (
        mtlx_material_source[0].GetPrim().GetPath()
        == mtlx_nodegraph.GetPrim().GetPath()
    )

    mtlx_displacement_tex = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/MtlxNodeGraph/mtlx_displacementTexture")
    )
    assert (
        _asset_path_value(mtlx_displacement_tex.GetInput("file"))
        == "textures/MatA_Height.png"
    )


def test_openpbr_displacement_output_authored(tmp_path):
    """OpenPBR displacement output should be authored through the NodeGraph."""
    src_dir = tmp_path / "source_textures"
    src_dir.mkdir(parents=True, exist_ok=True)
    base_path = src_dir / "MatA_BaseColor.png"
    displacement_path = src_dir / "MatA_Height.png"
    base_path.write_bytes(b"base")
    displacement_path.write_bytes(b"height")

    material_dict_list = [
        {
            "basecolor": {"mat_name": "MatA", "path": str(base_path)},
            "displacement": {"mat_name": "MatA", "path": str(displacement_path)},
        }
    ]

    publish_dir = tmp_path / "openpbr_publish"
    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(publish_dir),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=False,
        create_openpbr=True,
    )

    stage = Usd.Stage.Open(str(publish_dir / "Asset/mtl.usdc"))
    openpbr_nodegraph = UsdShade.NodeGraph(
        stage.GetPrimAtPath("/Asset/mtl/MatA/OpenPbrNodeGraph")
    )
    openpbr_displacement_output = openpbr_nodegraph.GetOutput("displacement")
    assert (
        openpbr_displacement_output and openpbr_displacement_output.HasConnectedSource()
    )
    openpbr_displacement_source = openpbr_displacement_output.GetConnectedSource()
    assert openpbr_displacement_source
    assert openpbr_displacement_source[1] == "out"

    openpbr_material = UsdShade.Material(stage.GetPrimAtPath("/Asset/mtl/MatA"))
    openpbr_material_output = openpbr_material.GetOutput("mtlx:displacement")
    assert openpbr_material_output and openpbr_material_output.HasConnectedSource()
    openpbr_material_source = openpbr_material_output.GetConnectedSource()
    assert openpbr_material_source
    assert openpbr_material_source[1] == "displacement"
    assert (
        openpbr_material_source[0].GetPrim().GetPath()
        == openpbr_nodegraph.GetPrim().GetPath()
    )

    openpbr_displacement_tex = UsdShade.Shader(
        stage.GetPrimAtPath(
            "/Asset/mtl/MatA/OpenPbrNodeGraph/openpbr_displacementTexture"
        )
    )
    assert (
        _asset_path_value(openpbr_displacement_tex.GetInput("file"))
        == "textures/MatA_Height.png"
    )


def test_arnold_displacement_mode_authors_displacement_output(tmp_path):
    """Arnold displacement mode should publish a displacement output."""
    src_dir = tmp_path / "source_textures"
    src_dir.mkdir(parents=True, exist_ok=True)
    base_path = src_dir / "MatA_BaseColor.png"
    displacement_path = src_dir / "MatA_Height.png"
    base_path.write_bytes(b"base")
    displacement_path.write_bytes(b"height")

    material_dict_list = [
        {
            "basecolor": {"mat_name": "MatA", "path": str(base_path)},
            "displacement": {"mat_name": "MatA", "path": str(displacement_path)},
        }
    ]

    publish_dir = tmp_path / "arnold_publish"
    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(publish_dir),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=True,
        create_mtlx=False,
        create_openpbr=False,
        arnold_displacement_mode="displacement",
    )

    stage = Usd.Stage.Open(str(publish_dir / "Asset/mtl.usdc"))
    arnold_nodegraph = UsdShade.NodeGraph(
        stage.GetPrimAtPath("/Asset/mtl/MatA/ArnoldNodeGraph")
    )
    displacement_output = arnold_nodegraph.GetOutput("displacement")
    assert displacement_output and displacement_output.HasConnectedSource()
    displacement_source = displacement_output.GetConnectedSource()
    assert displacement_source
    assert displacement_source[1] == "out"

    arnold_material = UsdShade.Material(stage.GetPrimAtPath("/Asset/mtl/MatA"))
    arnold_material_output = arnold_material.GetOutput("arnold:displacement")
    assert arnold_material_output and arnold_material_output.HasConnectedSource()
    arnold_material_source = arnold_material_output.GetConnectedSource()
    assert arnold_material_source
    assert arnold_material_source[1] == "displacement"
    assert (
        arnold_material_source[0].GetPrim().GetPath()
        == arnold_nodegraph.GetPrim().GetPath()
    )

    displacement_shader = UsdShade.Shader(
        stage.GetPrimAtPath("/Asset/mtl/MatA/ArnoldNodeGraph/arnold_Displacement")
    )
    displacement_input = displacement_shader.GetInput("height")
    assert displacement_input and displacement_input.HasConnectedSource()

    displacement_tex = UsdShade.Shader(
        stage.GetPrimAtPath(
            "/Asset/mtl/MatA/ArnoldNodeGraph/arnold_displacementTexture"
        )
    )
    assert (
        _asset_path_value(displacement_tex.GetInput("filename"))
        == "textures/MatA_Height.png"
    )
    assert not stage.GetPrimAtPath(
        "/Asset/mtl/MatA/ArnoldNodeGraph/arnold_Bump2d"
    ).IsValid()


def test_udim_paths_remain_relative(tmp_path):
    """UDIM token paths should be authored as relative assets."""
    asset_textures = tmp_path / "Asset" / "textures"
    asset_textures.mkdir(parents=True, exist_ok=True)
    for tile in ("1001", "1002"):
        (asset_textures / f"MatA_BaseColor.{tile}.exr").write_bytes(b"texture")

    material_dict_list = [
        {
            "basecolor": {
                "mat_name": "MatA",
                "path": str(asset_textures / "MatA_BaseColor.<UDIM>.exr"),
            }
        }
    ]

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=True,
        texture_format_overrides={"mtlx": "exr"},
    )

    stage = Usd.Stage.Open(str(tmp_path / "Asset/mtl.usdc"))
    texture_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/MtlxNodeGraph/mtlx_basecolorTexture"
    )
    texture_shader = UsdShade.Shader(texture_prim)
    assert (
        _asset_path_value(texture_shader.GetInput("file"))
        == "textures/MatA_BaseColor.<UDIM>.exr"
    )
    assert (tmp_path / "Asset/textures/MatA_BaseColor.1001.exr").exists()


def test_relative_texture_paths_are_normalized(tmp_path):
    """Relative texture paths should be normalized without filesystem moves."""
    material_dict_list = [
        {
            "basecolor": {
                "mat_name": "MatA",
                "path": "textures/MatA_BaseColor.png",
            }
        }
    ]

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=True,
    )

    stage = Usd.Stage.Open(str(tmp_path / "Asset/mtl.usdc"))
    texture_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/MtlxNodeGraph/mtlx_basecolorTexture"
    )
    texture_shader = UsdShade.Shader(texture_prim)
    assert (
        _asset_path_value(texture_shader.GetInput("file"))
        == "textures/MatA_BaseColor.png"
    )


def test_mtlx_metalness_is_float(tmp_path, sp_texture_factory):
    """Ensure MaterialX metalness remains float through the network."""
    textures = sp_texture_factory({"metalness": ".exr"})
    material_dict_list = _material_dict_from_paths({"metalness": textures["metalness"]})

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=True,
    )

    stage = Usd.Stage.Open(str(tmp_path / "Asset/mtl.usdc"))
    image_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/MtlxNodeGraph/mtlx_metalnessTexture"
    )
    image_shader = UsdShade.Shader(image_prim)
    assert image_shader.GetIdAttr().Get() == "ND_image_float"

    range_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/MtlxNodeGraph/mtlx_metalnessRange"
    )
    range_shader = UsdShade.Shader(range_prim)
    assert range_shader.GetIdAttr().Get() == "ND_range_float"
    assert range_shader.GetInput("in").GetTypeName() == Sdf.ValueTypeNames.Float

    std_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/MtlxNodeGraph/mtlx_mtlxstandard_surface1"
    )
    std_shader = UsdShade.Shader(std_prim)
    assert std_shader.GetInput("metalness").GetTypeName() == Sdf.ValueTypeNames.Float


def test_openpbr_surface_id(tmp_path, sp_texture_factory):
    """Ensure OpenPBR surface shader is authored with the correct ID."""
    textures = sp_texture_factory({"basecolor": ".exr"})
    material_dict_list = _material_dict_from_paths({"basecolor": textures["basecolor"]})

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=False,
        create_openpbr=True,
    )

    stage = Usd.Stage.Open(str(tmp_path / "Asset/mtl.usdc"))
    shader_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/OpenPbrNodeGraph/openpbr_surface1"
    )
    shader = UsdShade.Shader(shader_prim)
    assert shader.GetIdAttr().Get() == "ND_open_pbr_surface_surfaceshader"


def test_openpbr_input_names(tmp_path, sp_texture_factory):
    """Ensure OpenPBR uses base_metalness and geometry_normal inputs."""
    textures = sp_texture_factory({"metalness": ".exr", "normal": ".exr"})
    material_dict_list = _material_dict_from_paths(
        {"metalness": textures["metalness"], "normal": textures["normal"]}
    )

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=None,
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=False,
        create_openpbr=True,
    )

    stage = Usd.Stage.Open(str(tmp_path / "Asset/mtl.usdc"))
    shader_prim = stage.GetPrimAtPath(
        "/Asset/mtl/MatA/OpenPbrNodeGraph/openpbr_surface1"
    )
    shader = UsdShade.Shader(shader_prim)
    assert shader.GetInput("base_metalness") is not None
    assert shader.GetInput("geometry_normal") is not None


def test_assign_material_raises_for_non_material():
    """assign_material_to_primitives raises MaterialAssignmentError for non-materials."""
    from axe_usd.core.exceptions import MaterialAssignmentError

    stage = Usd.Stage.CreateInMemory()
    prim = stage.DefinePrim("/NotMaterial", "Xform")
    assigner = material_processor.USDShaderAssign(stage)

    with pytest.raises(MaterialAssignmentError):
        assigner.assign_material_to_primitives(prim, [])


def test_assign_material_binds_mesh():
    stage = Usd.Stage.CreateInMemory()
    material_processor.USDShaderCreate(
        stage=stage,
        material_name="MatA",
        material_dict={
            "basecolor": {"mat_name": "MatA", "path": "./textures/MatA_BaseColor.png"}
        },
        parent_primpath="/Asset/material",
        create_usd_preview=True,
        create_arnold=False,
        create_mtlx=False,
    )
    mesh = UsdGeom.Mesh.Define(stage, "/Asset/mesh/Mesh_MatA")

    material_processor.USDShaderAssign(stage).run(
        mats_parent_path="/Asset/material",
        mesh_parent_path="/Asset",
    )

    binding = UsdShade.MaterialBindingAPI(mesh).GetDirectBinding().GetMaterial()
    assert binding


def test_bind_materials_in_variant_uses_mesh_names_for_xforms(tmp_path):
    from axe_usd.usd.asset_files import create_asset_file_structure, create_geo_usd_file

    paths = create_asset_file_structure(tmp_path, "Asset")
    geo_stage = create_geo_usd_file(paths, "Asset")

    render_xform = UsdGeom.Xform.Define(
        geo_stage, "/Asset/geo/render/locust_antenna_001_geo"
    )
    UsdGeom.Mesh.Define(
        geo_stage,
        "/Asset/geo/render/locust_antenna_001_geo/locust_antenna_001_geo",
    )
    proxy_xform = UsdGeom.Xform.Define(
        geo_stage, "/Asset/geo/proxy/locust_antenna_001_geo"
    )
    UsdGeom.Mesh.Define(
        geo_stage,
        "/Asset/geo/proxy/locust_antenna_001_geo/locust_antenna_001_geo",
    )
    geo_stage.Save()

    tex_dir = tmp_path / "input_textures"
    tex_dir.mkdir(parents=True, exist_ok=True)
    tex_path = tex_dir / "antenna_BaseColor.png"
    tex_path.write_bytes(b"texture")

    material_dict_list = [
        {
            "basecolor": {
                "mat_name": "antenna",
                "path": str(tex_path),
                "mesh_names": ["locust_antenna_001_geo"],
            }
        }
    ]

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=str(paths.geo_file),
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=False,
    )

    stage = Usd.Stage.Open(str(paths.mtl_file))
    root = stage.GetPrimAtPath("/Asset")
    variant = root.GetVariantSets().GetVariantSet("mtl")
    variant.SetVariantSelection("default")

    for path in (
        "/Asset/geo/render/locust_antenna_001_geo",
        "/Asset/geo/proxy/locust_antenna_001_geo",
    ):
        prim = stage.GetPrimAtPath(path)
        assert prim.IsValid()
        binding = UsdShade.MaterialBindingAPI(prim).GetDirectBinding().GetMaterial()
        assert binding
        assert str(binding.GetPrim().GetPath()) == "/Asset/mtl/antenna"


def test_bind_materials_in_variant_normalizes_mesh_names_for_xforms(tmp_path):
    from axe_usd.usd.asset_files import create_asset_file_structure, create_geo_usd_file

    paths = create_asset_file_structure(tmp_path, "Asset")
    geo_stage = create_geo_usd_file(paths, "Asset")

    render_xform = UsdGeom.Xform.Define(
        geo_stage, "/Asset/geo/render/locust_grasshopper_v17_copy1"
    )
    UsdGeom.Mesh.Define(
        geo_stage,
        "/Asset/geo/render/locust_grasshopper_v17_copy1/locust_grasshopper_v17_copy1_1",
    )
    proxy_xform = UsdGeom.Xform.Define(
        geo_stage, "/Asset/geo/proxy/locust_grasshopper_v17_copy1"
    )
    UsdGeom.Mesh.Define(
        geo_stage,
        "/Asset/geo/proxy/locust_grasshopper_v17_copy1/locust_grasshopper_v17_copy1_1",
    )
    geo_stage.Save()

    tex_dir = tmp_path / "input_textures"
    tex_dir.mkdir(parents=True, exist_ok=True)
    tex_path = tex_dir / "body_BaseColor.png"
    tex_path.write_bytes(b"texture")

    material_dict_list = [
        {
            "basecolor": {
                "mat_name": "body",
                "path": str(tex_path),
                "mesh_names": ["locust grasshopper_v17_copy1"],
            }
        }
    ]

    material_processor.create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=str(paths.geo_file),
        parent_path="/Asset",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=False,
        create_arnold=False,
        create_mtlx=False,
    )

    stage = Usd.Stage.Open(str(paths.mtl_file))
    root = stage.GetPrimAtPath("/Asset")
    variant = root.GetVariantSets().GetVariantSet("mtl")
    variant.SetVariantSelection("default")

    for path in (
        "/Asset/geo/render/locust_grasshopper_v17_copy1",
        "/Asset/geo/proxy/locust_grasshopper_v17_copy1",
    ):
        prim = stage.GetPrimAtPath(path)
        assert prim.IsValid()
        binding = UsdShade.MaterialBindingAPI(prim).GetDirectBinding().GetMaterial()
        assert binding
        assert str(binding.GetPrim().GetPath()) == "/Asset/mtl/body"
