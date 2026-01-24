import pytest

pxr = pytest.importorskip("pxr")

from pathlib import Path

from axe_usd.core.models import ExportSettings, MaterialBundle
from axe_usd.core.publish_paths import build_publish_paths
from axe_usd.usd.pxr_writer import PxrUsdWriter


def test_pxr_writer_exports_layers(tmp_path):
    """Ensure PxrUsdWriter writes the expected layer files."""
    materials = [MaterialBundle(name="MatA", textures={"basecolor": "C:/tex/MatA_BaseColor.png"})]
    settings = ExportSettings(
        usdpreview=True,
        arnold=False,
        materialx=False,
        primitive_path="/Asset",
        publish_directory=Path(tmp_path),
        save_geometry=False,
    )
    paths = build_publish_paths(settings.publish_directory, settings.main_layer_name)

    PxrUsdWriter().export(materials, settings, None, paths)

    assert paths.main_layer_path.exists()
    assert paths.layer_mats_path.exists()
    assert paths.layer_assign_path.exists()
