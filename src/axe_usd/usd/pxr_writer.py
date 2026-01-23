from pathlib import Path
from typing import Iterable, Optional

from ..core.models import ExportSettings, MaterialBundle, PublishPaths
from . import material_processor
from .types import MaterialTextureDict, MaterialTextureList


class PxrUsdWriter:
    """Write USD layers using the Pixar USD Python API."""

    def export(
        self,
        materials: Iterable[MaterialBundle],
        settings: ExportSettings,
        geo_file: Optional[Path],
        paths: PublishPaths,
    ) -> None:
        """Export materials and optional geometry to USD layers.

        Args:
            materials: Material bundles to export.
            settings: Export settings to honor.
            geo_file: Optional geometry USD file to payload.
            paths: Publish path container.
        """
        material_dict_list: MaterialTextureList = [
            _bundle_to_dict(bundle) for bundle in materials
        ]
        material_processor.create_shaded_asset_publish(
            material_dict_list=material_dict_list,
            stage=None,
            geo_file=str(geo_file) if geo_file else None,
            parent_path=settings.primitive_path,
            layer_save_path=str(paths.root_dir),
            main_layer_name=settings.main_layer_name,
            create_usd_preview=settings.usdpreview,
            create_arnold=settings.arnold,
            create_mtlx=settings.materialx,
        )


def _bundle_to_dict(bundle: MaterialBundle) -> MaterialTextureDict:
    """Convert a material bundle into the expected texture dict format.

    Args:
        bundle: Material bundle to convert.

    Returns:
        MaterialTextureDict: Mapping of slots to texture info dictionaries.
    """
    return {
        slot: {"mat_name": bundle.name, "path": texture_path}
        for slot, texture_path in bundle.textures.items()
    }
