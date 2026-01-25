"""ASWF-compliant USD asset file structure."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pxr import Sdf, Usd, UsdGeom

from ..core.filesystem import DefaultFileSystem
from .asset_structure import initialize_component_asset, add_standard_scopes


@dataclass(frozen=True)
class AssetFilePaths:
    """ASWF-compliant USD asset file paths.

    Follows https://github.com/usd-wg/assets/blob/main/docs/asset-structure-guidelines.md

    Structure:
        /AssetName/
            AssetName.usd       # Main entry point (references payload + mtl)
            payload.usd         # References geo.usd
            geo.usd             # Geometry interface (references geometry.usd)
            geometry.usd        # Heavy geometry data (copied from source)
            mtl.usd             # Material library
            /maps/              # Texture maps
    """

    root_dir: Path  # /AssetName/
    asset_file: Path  # /AssetName/AssetName.usd
    payload_file: Path  # /AssetName/payload.usd
    geo_file: Path  # /AssetName/geo.usd (interface)
    geometry_file: Path  # /AssetName/geometry.usd (heavy data)
    mtl_file: Path  # /AssetName/mtl.usd
    maps_dir: Path  # /AssetName/maps/


def create_asset_file_structure(
    output_dir: Path,
    asset_name: str,
) -> AssetFilePaths:
    """Create ASWF-compliant file structure.

    Args:
        output_dir: Parent directory to create asset folder in.
        asset_name: Name of the asset (e.g., "MyProp").

    Returns:
        AssetFilePaths: Paths to all asset files.

    Example:
        >>> paths = create_asset_file_structure(Path("./output"), "Hero")
        >>> # Creates: ./output/Hero/Hero.usd, payload.usd, etc.
    """
    fs = DefaultFileSystem()

    # Create asset root directory
    asset_root = output_dir / asset_name
    fs.ensure_directory(asset_root)

    # Create maps directory for textures
    maps_dir = asset_root / "maps"
    fs.ensure_directory(maps_dir)

    return AssetFilePaths(
        root_dir=asset_root,
        asset_file=asset_root / f"{asset_name}.usd",
        payload_file=asset_root / "payload.usd",
        geo_file=asset_root / "geo.usd",
        geometry_file=asset_root / "geometry.usd",
        mtl_file=asset_root / "mtl.usd",
        maps_dir=maps_dir,
    )


def create_asset_usd_file(
    paths: AssetFilePaths,
    asset_name: str,
) -> Usd.Stage:
    """Create the main Asset.usd file following ASWF structure.

    Creates:
    - /__class__/AssetName (class prim)
    - /AssetName (root Xform, Kind=component, assetInfo, inherits)
    - References payload.usd into /AssetName
    - References mtl.usd into /AssetName/mtl
    - Material bindings (if authored here)

    Args:
        paths: Asset file paths.
        asset_name: Name of the asset.

    Returns:
        Usd.Stage: The created main asset stage.
    """
    # Create main asset file
    stage = Usd.Stage.CreateNew(str(paths.asset_file))

    # Initialize ASWF-compliant component
    root_prim = initialize_component_asset(
        stage, asset_name, asset_identifier=f"./{asset_name}.usd"
    )

    # Add standard scopes
    scopes = add_standard_scopes(stage, root_prim)

    # Reference payload into root (for geo)
    root_prim.GetReferences().AddReference("./payload.usd")

    # Reference material library into mtl scope
    mtl_scope = scopes["mtl"]
    mtl_scope.GetReferences().AddReference("./mtl.usd")

    # Set defaultPrim
    stage.SetDefaultPrim(root_prim)

    stage.Save()
    return stage


def create_payload_usd_file(
    paths: AssetFilePaths,
    asset_name: str,
) -> Usd.Stage:
    """Create payload.usd that references geo.usd.

    Args:
        paths: Asset file paths.
        asset_name: Name of the asset.

    Returns:
        Usd.Stage: The created payload stage.
    """
    stage = Usd.Stage.CreateNew(str(paths.payload_file))

    # Define root and geo scope
    root = stage.DefinePrim(f"/{asset_name}")
    geo_scope = UsdGeom.Scope.Define(stage, f"/{asset_name}/geo")

    # Reference geometry interface file
    geo_scope.GetPrim().GetReferences().AddReference("./geo.usd")

    # Set defaultPrim just in case
    stage.SetDefaultPrim(root)

    stage.Save()
    return stage


def create_geo_usd_file(
    paths: AssetFilePaths,
    asset_name: str,
    has_geometry: bool = True,
) -> Usd.Stage:
    """Create geo.usd geometry interface.

    References the actual geometry data file (geometry.usd).

    Args:
        paths: Asset file paths.
        asset_name: Name of the asset.
        has_geometry: Whether geometry.usd exists/should be referenced.

    Returns:
        Usd.Stage: The created geometry stage.
    """
    stage = Usd.Stage.CreateNew(str(paths.geo_file))

    # Define structure
    root = stage.DefinePrim(f"/{asset_name}")
    geo_scope = UsdGeom.Scope.Define(stage, f"/{asset_name}/geo")

    # Payload reference to the heavy data file
    # Strictly relative path "./geometry.usd"
    if has_geometry:
        geo_scope.GetPrim().GetPayloads().AddPayload("./geometry.usd")

    stage.SetDefaultPrim(root)
    stage.Save()
    return stage


def create_mtl_usd_file(
    paths: AssetFilePaths,
    asset_name: str,
) -> Usd.Stage:
    """Create mtl.usd for material library.

    Args:
        paths: Asset file paths.
        asset_name: Name of the asset.

    Returns:
        Usd.Stage: The created material stage.
    """
    stage = Usd.Stage.CreateNew(str(paths.mtl_file))

    # Define structure
    root = stage.DefinePrim(f"/{asset_name}")
    mtl_scope = UsdGeom.Scope.Define(stage, f"/{asset_name}/mtl")

    # Materials will be authored into this scope by the material processor

    stage.Save()
    return stage
