from pathlib import Path

from axe_usd.core.models import ExportSettings, MaterialBundle
from axe_usd.core.publish_paths import build_publish_paths
from axe_usd.usd.pxr_writer import PxrUsdWriter


def test_pxr_writer_exports_layers(tmp_path):
    """Ensure PxrUsdWriter writes the expected layer files."""
    materials = [
        MaterialBundle(name="MatA", textures={"basecolor": "C:/tex/MatA_BaseColor.png"})
    ]
    settings = ExportSettings(
        usdpreview=True,
        arnold=False,
        materialx=False,
        openpbr=False,
        primitive_path="/Asset",
        publish_directory=Path(tmp_path),
        save_geometry=False,
    )
    paths = build_publish_paths(settings.publish_directory, settings.main_layer_name)

    PxrUsdWriter().export(materials, settings, None, paths)

    # Convert paths to component structure checks
    asset_dir = tmp_path / "Asset"
    assert (asset_dir / "Asset.usd").exists()
    assert (asset_dir / "mtl.usdc").exists()
    assert (asset_dir / "payload.usdc").exists()
