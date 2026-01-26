"""USD asset structure utilities."""

from pathlib import Path
from typing import Optional

from pxr import Kind, Sdf, Usd, UsdGeom


def initialize_component_asset(
    stage: Usd.Stage,
    asset_name: str,
    asset_identifier: Optional[str] = None,
) -> Usd.Prim:
    """Initialize a Component asset structure.

    Creates the following structure:
    - /__class__/<asset_name>: Class prim for inheritance
    - /<asset_name>: Root Xform with Kind=component, assetInfo, inheritance
    - Sets stage defaultPrim metadata

    Args:
        stage: USD stage to initialize.
        asset_name: Name of the asset (e.g., "hero_prop").
        asset_identifier: Optional asset identifier (defaults to "./<asset_name>.usd").

    Returns:
        Usd.Prim: The root asset prim.

    Example:
        >>> stage = Usd.Stage.CreateInMemory()
        >>> root = initialize_component_asset(stage, "MyAsset")
        >>> print(root.GetPath())
        /MyAsset
    """
    # 1. Set defaultPrim metadata
    root_path = Sdf.Path(f"/{asset_name}")
    stage.SetDefaultPrim(stage.DefinePrim(root_path))

    # 2. Create class prim for inheritance
    class_scope = stage.CreateClassPrim("/__class__")
    class_prim = stage.CreateClassPrim(f"/__class__/{asset_name}")

    # 3. Define root as Xform (must be transformable)
    root_xform = UsdGeom.Xform.Define(stage, root_path)
    root_prim = root_xform.GetPrim()
    UsdGeom.ModelAPI.Apply(root_prim)

    # 4. Set Kind to component (leaf assets)
    model_api = Usd.ModelAPI(root_prim)
    model_api.SetKind(Kind.Tokens.component)

    # 5. Set assetInfo metadata
    if asset_identifier is None:
        asset_identifier = f"./{asset_name}.usd"

    root_prim.SetAssetInfoByKey("name", asset_name)
    root_prim.SetAssetInfoByKey("identifier", Sdf.AssetPath(asset_identifier))

    # 6. Add inheritance from class prim
    root_prim.GetInherits().AddInherit(class_prim.GetPath())

    return root_prim


def add_standard_scopes(
    stage: Usd.Stage,
    asset_root: Usd.Prim,
) -> dict[str, Usd.Prim]:
    """Add standard geometry and material scopes to an asset.

    Creates:
    - /<asset>/geo: Geometry scope
    - /<asset>/mtl: Material scope

    Args:
        stage: USD stage.
        asset_root: Root prim of the asset.

    Returns:
        dict: Dictionary with keys 'geo' and 'mtl' mapping to scope prims.

    Example:
        >>> scopes = add_standard_scopes(stage, root_prim)
        >>> print(scopes['geo'].GetPath())
        /MyAsset/geo
    """
    asset_path = asset_root.GetPath()

    # Create geometry scope
    geo_scope = UsdGeom.Scope.Define(stage, asset_path.AppendChild("geo"))

    # Create material scope
    mtl_scope = UsdGeom.Scope.Define(stage, asset_path.AppendChild("mtl"))

    return {
        "geo": geo_scope.GetPrim(),
        "mtl": mtl_scope.GetPrim(),
    }


def add_payload(
    asset_root: Usd.Prim,
    payload_path: str = "./payload.usdc",
) -> None:
    """Add a payload reference to the asset root.

    Args:
        asset_root: Root prim of the asset.
        payload_path: Relative path to the payload file.

    Example:
        >>> add_payload(root_prim, "./payload.usdc")
    """
    asset_root.GetPayloads().AddPayload(payload_path)


def set_asset_version(
    asset_root: Usd.Prim,
    version: str,
) -> None:
    """Set the version in assetInfo metadata.

    Args:
        asset_root: Root prim of the asset.
        version: Version string (e.g., "1.0", "v023").
    """
    asset_root.SetAssetInfoByKey("version", version)


def get_asset_info(asset_root: Usd.Prim) -> dict:
    """Retrieve assetInfo metadata from a prim.

    Args:
        asset_root: Root prim of the asset.

    Returns:
        dict: Dictionary of assetInfo values.
    """
    info = {}

    # Get standard assetInfo keys
    for key in ["name", "identifier", "version"]:
        value = asset_root.GetAssetInfoByKey(key)
        if value:
            info[key] = value

    return info


def create_subcomponent(
    stage: Usd.Stage,
    parent_path: Sdf.Path,
    subcomponent_name: str,
) -> Usd.Prim:
    """Create a subcomponent prim under a component.

    Args:
        stage: USD stage.
        parent_path: Path to the parent component.
        subcomponent_name: Name of the subcomponent.

    Returns:
        Usd.Prim: The subcomponent prim with Kind=subcomponent.
    """
    subcomp_path = parent_path.AppendChild(subcomponent_name)
    subcomp_xform = UsdGeom.Xform.Define(stage, subcomp_path)
    subcomp_prim = subcomp_xform.GetPrim()

    # Set subcomponent kind
    model_api = Usd.ModelAPI(subcomp_prim)
    model_api.SetKind(Kind.Tokens.subcomponent)

    return subcomp_prim
