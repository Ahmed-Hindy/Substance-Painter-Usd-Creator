import pytest

pxr = pytest.importorskip("pxr")

from axe_usd.usd import material_processor


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
        parent_path="/ASSET",
        layer_save_path=str(tmp_path),
        main_layer_name="main.usda",
        create_usd_preview=True,
        create_arnold=False,
        create_mtlx=False,
    )

    assert (tmp_path / "main.usda").exists()
    assert (tmp_path / "layers" / "layer_mats.usda").exists()
    assert (tmp_path / "layers" / "layer_assign.usda").exists()
