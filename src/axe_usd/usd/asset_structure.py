"""USD asset structure utilities."""

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
    stage.CreateClassPrim("/__class__")
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
