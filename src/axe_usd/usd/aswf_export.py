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
    """Create ASWF-compliant USD asset with proper file structure.

    Follows https://github.com/usd-wg/assets/blob/main/docs/asset-structure-guidelines.md

    Creates file structure:
        /AssetName/
            AssetName.usd       # Main entry (references payload + mtl)
            payload.usd         # References geo.usd
            geo.usd             # Geometry layer
            mtl.usd             # Material library
            /maps/              # Texture directory

    Creates prim structure:
        /__class__/AssetName    # Class prim for inheritance
        /AssetName              # Root Xform (Kind=component, assetInfo)
            /geo                # Geometry scope
            /mtl                # Material scope

    Args:
        material_dict_list: Material texture dictionaries to publish.
        geo_file: Optional geometry USD file to reference.
        asset_name: Name of the asset (default: "Asset").
        output_directory: Output directory (creates /AssetName/ inside).
        create_usd_preview: Whether to create UsdPreviewSurface materials.
        create_arnold: Whether to create Arnold materials.
        create_mtlx: Whether to create MaterialX materials.
        create_openpbr: Whether to create MaterialX OpenPBR materials.
        texture_format_overrides: Optional per-renderer texture format overrides.
    """
    from pathlib import Path
    from .asset_files import (
        create_asset_file_structure,
        create_asset_usd_file,
        create_payload_usd_file,
        create_geo_usd_file,
        create_mtl_usd_file,
    )

    if not output_directory:
        output_directory = f"{tempfile.gettempdir()}/temp_usd_export"
        os.makedirs(output_directory, exist_ok=True)

    output_dir = Path(output_directory)

    # Create ASWF file structure
    paths = create_asset_file_structure(output_dir, asset_name)

    # Create geo.usd if geometry file provided
    if geo_file:
        create_geo_usd_file(paths, asset_name, Path(geo_file) if geo_file else None)
    else:
        # Create empty geo.usd
        create_geo_usd_file(paths, asset_name, None)

    # Create payload.usd (references geo.usd)
    create_payload_usd_file(paths, asset_name)

    # Create mtl.usd with materials
    mtl_stage = Usd.Stage.Open(str(paths.mtl_file))
    if not mtl_stage:
        mtl_stage = create_mtl_usd_file(paths, asset_name)

    # Author materials into mtl.usd
    material_primitive_path = f"/{asset_name}/mtl"

    for material_dict in material_dict_list:
        material_name = next(
            (info["mat_name"] for info in material_dict.values()),
            "UnknownMaterialName",
        )
        USDShaderCreate(
            stage=mtl_stage,
            material_name=material_name,
            material_dict=material_dict,
            parent_primpath=material_primitive_path,
            create_usd_preview=create_usd_preview,
            create_arnold=create_arnold,
            create_mtlx=create_mtlx,
            create_openpbr=create_openpbr,
            texture_format_overrides=texture_format_overrides,
        )

    mtl_stage.Save()

    # Create Asset.usd (main entry point, references payload + mtl)
    create_asset_usd_file(paths, asset_name)

    logger.info(
        "Finished creating ASWF-compliant USD asset: '%s/%s/%s.usd'.",
        output_directory,
        asset_name,
        asset_name,
    )
    logger.info(
        "Asset structure: %s.usd, payload.usd, geo.usd, mtl.usd, /maps/", asset_name
    )
    logger.info("Success")
