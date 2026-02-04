"""Component-builder USD asset file structure."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pxr import Kind, Sdf, Usd, UsdGeom

from ..core.filesystem import DefaultFileSystem
from .asset_structure import initialize_component_asset

DEFAULT_UP_AXIS = "Y"
DEFAULT_METERS_PER_UNIT = 1
DEFAULT_FRAMES_PER_SECOND = 24
DEFAULT_TIME_CODES_PER_SECOND = 24

MTL_LIBRARY_ROOT = "ASSET_mtl_default"
MTL_VARIANT_SET = "mtl"
MTL_VARIANT_DEFAULT = "default"


@dataclass(frozen=True)
class AssetFilePaths:
    """Component-builder USD asset file paths.

    Structure:
        /AssetName/
            AssetName.usd       # Main entry point (payloads payload.usdc)
            payload.usdc        # References mtl.usdc and geo.usdc
            geo.usdc            # Geometry layer
            mtl.usdc            # Material layer
            /textures/          # Texture maps (handled by DCC plugin)
    """

    root_dir: Path  # /AssetName/
    asset_file: Path  # /AssetName/AssetName.usd
    payload_file: Path  # /AssetName/payload.usdc
    geo_file: Path  # /AssetName/geo.usdc
    mtl_file: Path  # /AssetName/mtl.usdc
    textures_dir: Path  # /AssetName/textures/


def create_asset_file_structure(
    output_dir: Path,
    asset_name: str,
) -> AssetFilePaths:
    """Create component-builder file structure.

    Args:
        output_dir: Parent directory to create asset folder in.
        asset_name: Name of the asset (e.g., "MyProp").

    Returns:
        AssetFilePaths: Paths to all asset files.

    Example:
        >>> paths = create_asset_file_structure(Path("./output"), "Hero")
        >>> # Creates: ./output/Hero/Hero.usd, payload.usdc, etc.
    """
    fs = DefaultFileSystem()

    # Create asset root directory
    asset_root = output_dir / asset_name
    fs.ensure_directory(asset_root)

    # Create textures directory for maps (handled elsewhere)
    textures_dir = asset_root / "textures"
    fs.ensure_directory(textures_dir)

    return AssetFilePaths(
        root_dir=asset_root,
        asset_file=asset_root / f"{asset_name}.usd",
        payload_file=asset_root / "payload.usdc",
        geo_file=asset_root / "geo.usdc",
        mtl_file=asset_root / "mtl.usdc",
        textures_dir=textures_dir,
    )


def create_asset_usd_file(
    paths: AssetFilePaths,
    asset_name: str,
) -> Usd.Stage:
    """Create the main Asset.usd file.

    Creates:
    - /__class__/AssetName (class prim)
    - /AssetName (root Xform, Kind=component, assetInfo, inherits)
    - Payloads payload.usdc into /AssetName

    Args:
        paths: Asset file paths.
        asset_name: Name of the asset.

    Returns:
        Usd.Stage: The created main asset stage.
    """
    # Create main asset file
    stage = Usd.Stage.CreateNew(str(paths.asset_file))
    _apply_stage_metadata(stage)

    # Initialize component root
    root_prim = initialize_component_asset(
        stage, asset_name, asset_identifier=f"./{asset_name}.usd"
    )

    # Payload component composition
    root_prim.GetPayloads().AddPayload("./payload.usdc")

    # Set defaultPrim
    stage.SetDefaultPrim(root_prim)

    stage.Save()
    return stage


def create_payload_usd_file(
    paths: AssetFilePaths,
    asset_name: str,
) -> Usd.Stage:
    """Create payload.usdc that references mtl.usdc and geo.usdc.

    Args:
        paths: Asset file paths.
        asset_name: Name of the asset.

    Returns:
        Usd.Stage: The created payload stage.
    """
    stage = Usd.Stage.CreateNew(str(paths.payload_file))
    _apply_stage_metadata(stage)

    # Define root prim
    root = stage.DefinePrim(f"/{asset_name}")
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)

    # Reference material and geometry layers (order matters)
    root.GetReferences().AddReference("./mtl.usdc")
    root.GetReferences().AddReference("./geo.usdc")

    # Set defaultPrim just in case
    stage.SetDefaultPrim(root)

    stage.Save()
    return stage


def create_geo_usd_file(
    paths: AssetFilePaths,
    asset_name: str,
) -> Usd.Stage:
    """Create geo.usdc geometry layer scaffold.

    Args:
        paths: Asset file paths.
        asset_name: Name of the asset.
    Returns:
        Usd.Stage: The created geometry stage.
    """
    if paths.geo_file.exists():
        stage = Usd.Stage.Open(str(paths.geo_file))
    else:
        stage = Usd.Stage.CreateNew(str(paths.geo_file))

    _apply_stage_metadata(stage)

    root_path = Sdf.Path(f"/{asset_name}")
    root_prim = stage.GetPrimAtPath(root_path)
    if not root_prim.IsValid():
        root_prim = UsdGeom.Xform.Define(stage, root_path).GetPrim()

    geo_scope = _ensure_scope(stage, f"/{asset_name}/geo")
    if geo_scope:
        UsdGeom.ModelAPI.Apply(geo_scope.GetPrim())

        proxy_scope = _ensure_scope(stage, f"/{asset_name}/geo/proxy")
        if proxy_scope:
            UsdGeom.Imageable(proxy_scope.GetPrim()).CreatePurposeAttr().Set("proxy")

        render_scope = _ensure_scope(stage, f"/{asset_name}/geo/render")
        if render_scope:
            UsdGeom.Imageable(render_scope.GetPrim()).CreatePurposeAttr().Set("render")
            render_scope.GetPrim().CreateRelationship("proxyPrim").SetTargets(
                [Sdf.Path(f"/{asset_name}/geo/proxy")]
            )

    stage.SetDefaultPrim(root_prim)
    stage.Save()
    return stage


def create_mtl_usd_file(
    paths: AssetFilePaths,
    asset_name: str,
) -> Usd.Stage:
    """Create mtl.usdc for the material layer.

    Args:
        paths: Asset file paths.
        asset_name: Name of the asset.

    Returns:
        Usd.Stage: The created material stage.
    """
    stage = Usd.Stage.CreateNew(str(paths.mtl_file))
    _apply_stage_metadata(stage)

    root_prim = UsdGeom.Xform.Define(stage, f"/{asset_name}").GetPrim()
    root_prim.GetReferences().AddInternalReference(f"/{MTL_LIBRARY_ROOT}")
    _ensure_variant_set(root_prim, MTL_VARIANT_SET, MTL_VARIANT_DEFAULT)

    UsdGeom.Scope.Define(stage, f"/{MTL_LIBRARY_ROOT}")
    UsdGeom.Scope.Define(stage, f"/{MTL_LIBRARY_ROOT}/mtl")

    stage.SetDefaultPrim(root_prim)
    stage.Save()
    return stage


def _apply_stage_metadata(stage: Usd.Stage) -> None:
    stage.SetMetadata("upAxis", DEFAULT_UP_AXIS)
    stage.SetMetadata("metersPerUnit", DEFAULT_METERS_PER_UNIT)
    stage.SetMetadata("framesPerSecond", DEFAULT_FRAMES_PER_SECOND)
    stage.SetMetadata("timeCodesPerSecond", DEFAULT_TIME_CODES_PER_SECOND)


def _ensure_scope(stage: Usd.Stage, path: str) -> Optional[UsdGeom.Scope]:
    prim = stage.GetPrimAtPath(path)
    if prim and prim.IsValid():
        if prim.IsA(UsdGeom.Scope):
            return UsdGeom.Scope(prim)
        return None
    return UsdGeom.Scope.Define(stage, path)


def _ensure_variant_set(
    prim: Usd.Prim, set_name: str, variant_name: str
) -> Usd.VariantSet:
    variant_sets = prim.GetVariantSets()
    variant_set = variant_sets.AddVariantSet(set_name)
    if variant_name not in variant_set.GetVariantNames():
        variant_set.AddVariant(variant_name)
    variant_set.SetVariantSelection(variant_name)
    return variant_set
