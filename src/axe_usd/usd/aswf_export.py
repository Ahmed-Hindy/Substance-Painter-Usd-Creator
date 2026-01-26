from typing import Mapping, Optional

from .types import MaterialTextureList


def create_aswf_asset_publish(
    material_dict_list: MaterialTextureList,
    geo_file: Optional[str] = None,
    asset_name: str = "Asset",
    output_directory: Optional[str] = None,
    create_usd_preview: bool = True,
    create_arnold: bool = False,
    create_mtlx: bool = True,
    create_openpbr: bool = False,
    texture_format_overrides: Optional[Mapping[str, str]] = None,
) -> None:
    """Backward-compatible wrapper for the component-builder export."""
    from .material_processor import create_shaded_asset_publish

    create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=geo_file,
        parent_path=f"/{asset_name}",
        layer_save_path=output_directory,
        main_layer_name="main.usda",
        create_usd_preview=create_usd_preview,
        create_arnold=create_arnold,
        create_mtlx=create_mtlx,
        create_openpbr=create_openpbr,
        texture_format_overrides=texture_format_overrides,
    )
