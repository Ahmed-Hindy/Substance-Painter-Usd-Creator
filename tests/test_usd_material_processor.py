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
