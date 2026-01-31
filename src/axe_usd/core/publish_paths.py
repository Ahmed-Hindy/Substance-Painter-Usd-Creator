from pathlib import Path

from .models import PublishPaths


_USD_EXTENSIONS = {".usd", ".usda", ".usdc"}


def build_publish_paths(
    publish_directory: Path, main_layer_name: str, asset_name: str = ""
) -> PublishPaths:
    """Build publish paths for an export directory.

    Args:
        publish_directory: Target directory or main layer file path.
        main_layer_name: File name for the main layer.
        asset_name: Optional asset name to subfolder geometry.

    Returns:
        PublishPaths: Container of resolved publish paths.
    """
    root_dir = Path(publish_directory)
    if root_dir.suffix.lower() in _USD_EXTENSIONS:
        root_dir = root_dir.parent

    # geo.usdc should be inside the asset directory if asset_name provided
    # Component layout: <Root>/<AssetName>/geo.usdc
    # If no asset_name, fallback to root
    if asset_name:
        geometry_path = root_dir / asset_name / "geo.usdc"
    else:
        geometry_path = root_dir / "geo.usdc"

    return PublishPaths(
        root_dir=root_dir,
        geometry_path=geometry_path,
    )
