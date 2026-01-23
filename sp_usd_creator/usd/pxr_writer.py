from pathlib import Path
from typing import Iterable, Optional

from ..core.models import ExportSettings, MaterialBundle, PublishPaths
from . import material_processor


class PxrUsdWriter:
    def export(
        self,
        materials: Iterable[MaterialBundle],
        settings: ExportSettings,
        geo_file: Optional[Path],
        paths: PublishPaths,
    ) -> None:
        material_dict_list = [_bundle_to_dict(bundle) for bundle in materials]
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


def _bundle_to_dict(bundle: MaterialBundle):
    return {
        slot: {"mat_name": bundle.name, "path": texture_path}
        for slot, texture_path in bundle.textures.items()
    }
