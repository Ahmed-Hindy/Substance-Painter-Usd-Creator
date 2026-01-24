import pytest

pxr = pytest.importorskip("pxr")

from axe_usd.usd import material_processor


def _asset_path_value(input_attr):
    value = input_attr.Get()
    path = value.path if hasattr(value, "path") else value
    if path is None:
        return None
    return str(path).replace("\\", "/")


def test_create_shaded_asset_publish_creates_layers(tmp_path):
    """Ensure USD publish creates the expected layer files."""
    material_dict_list = [
        {
            "basecolor": {
                "mat_name": "MatA",
                "path": "C:/tex/MatA_BaseColor.png",
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
        create_usd_preview=True,
        create_arnold=False,
        create_mtlx=False,
    )

    assert (tmp_path / "main.usda").exists()
    assert (tmp_path / "layers" / "layer_mats.usda").exists()
    assert (tmp_path / "layers" / "layer_assign.usda").exists()


def test_usd_preview_texture_override_applies(tmp_path):
    """Ensure usd preview textures honor per-renderer format overrides."""
    material_dict_list = [
        {
            "basecolor": {
                "mat_name": "MatA",
                "path": "C:/tex/MatA_BaseColor.exr",
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
        create_usd_preview=True,
        create_arnold=False,
        create_mtlx=False,
        texture_format_overrides={"usd_preview": "jpg"},
    )

    stage = pxr.Usd.Stage.Open(str(tmp_path / "main.usda"))
    texture_prim = stage.GetPrimAtPath(
        "/Asset/material/MatA/UsdPreviewMaterial/UsdPreviewNodeGraph/basecolorTexture"
    )
    texture_shader = pxr.UsdShade.Shader(texture_prim)
    assert _asset_path_value(texture_shader.GetInput("file")) == "C:/tex/MatA_BaseColor.jpg"


def test_renderer_specific_format_overrides(tmp_path):
    """Ensure per-renderer overrides apply to each network."""
    material_dict_list = [
        {
            "basecolor": {
                "mat_name": "MatA",
                "path": "C:/tex/MatA_BaseColor.exr",
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
        create_usd_preview=True,
        create_arnold=True,
        create_mtlx=True,
        texture_format_overrides={
            "usd_preview": "jpg",
            "arnold": "tif",
            "mtlx": "png",
        },
    )

    stage = pxr.Usd.Stage.Open(str(tmp_path / "main.usda"))

    usd_preview_prim = stage.GetPrimAtPath(
        "/Asset/material/MatA/UsdPreviewMaterial/UsdPreviewNodeGraph/basecolorTexture"
    )
    usd_preview_shader = pxr.UsdShade.Shader(usd_preview_prim)
    assert _asset_path_value(usd_preview_shader.GetInput("file")) == "C:/tex/MatA_BaseColor.jpg"

    arnold_prim = stage.GetPrimAtPath("/Asset/material/MatA/arnold_basecolorTexture")
    arnold_shader = pxr.UsdShade.Shader(arnold_prim)
    assert _asset_path_value(arnold_shader.GetInput("filename")) == "C:/tex/MatA_BaseColor.tif"

    mtlx_prim = stage.GetPrimAtPath("/Asset/material/MatA/mtlx_basecolorTexture")
    mtlx_shader = pxr.UsdShade.Shader(mtlx_prim)
    assert _asset_path_value(mtlx_shader.GetInput("file")) == "C:/tex/MatA_BaseColor.png"


def test_mtlx_metalness_is_float(tmp_path):
    """Ensure MaterialX metalness remains float through the network."""
    material_dict_list = [
        {
            "metalness": {
                "mat_name": "MatA",
                "path": "C:/tex/MatA_Metalness.exr",
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

    stage = pxr.Usd.Stage.Open(str(tmp_path / "main.usda"))
    image_prim = stage.GetPrimAtPath("/Asset/material/MatA/mtlx_metalnessTexture")
    image_shader = pxr.UsdShade.Shader(image_prim)
    assert image_shader.GetIdAttr().Get() == "ND_image_float"

    range_prim = stage.GetPrimAtPath("/Asset/material/MatA/mtlx_metalnessRange")
    range_shader = pxr.UsdShade.Shader(range_prim)
    assert range_shader.GetIdAttr().Get() == "ND_range_float"
    assert range_shader.GetInput("in").GetTypeName() == pxr.Sdf.ValueTypeNames.Float

    std_prim = stage.GetPrimAtPath("/Asset/material/MatA/mtlx_mtlxstandard_surface1")
    std_shader = pxr.UsdShade.Shader(std_prim)
    assert std_shader.GetInput("metalness").GetTypeName() == pxr.Sdf.ValueTypeNames.Float


def test_assign_material_raises_for_non_material():
    stage = pxr.Usd.Stage.CreateInMemory()
    prim = stage.DefinePrim("/NotMaterial", "Xform")
    assigner = material_processor.USDShaderAssign(stage)

    with pytest.raises(ValueError):
        assigner.assign_material_to_primitives(prim, [])


def test_assign_material_binds_mesh():
    stage = pxr.Usd.Stage.CreateInMemory()
    material_processor.USDShaderCreate(
        stage=stage,
        material_name="MatA",
        material_dict={
            "basecolor": {"mat_name": "MatA", "path": "C:/tex/MatA_BaseColor.png"}
        },
        parent_primpath="/Asset/material",
        create_usd_preview=True,
        create_arnold=False,
        create_mtlx=False,
    )
    mesh = pxr.UsdGeom.Mesh.Define(stage, "/Asset/mesh/Mesh_MatA")

    material_processor.USDShaderAssign(stage).run(
        mats_parent_path="/Asset/material",
        mesh_parent_path="/Asset",
    )

    binding = pxr.UsdShade.MaterialBindingAPI(mesh).GetDirectBinding().GetMaterial()
    assert binding
