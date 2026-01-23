from pathlib import Path

from .models import PublishPaths


_USD_EXTENSIONS = {".usd", ".usda", ".usdc"}


def build_publish_paths(publish_directory: Path, main_layer_name: str) -> PublishPaths:
    """Build publish paths for an export directory.

    Args:
        publish_directory: Target directory or main layer file path.
        main_layer_name: File name for the main layer.

    Returns:
        PublishPaths: Container of resolved publish paths.
    """
    root_dir = Path(publish_directory)
    if root_dir.suffix.lower() in _USD_EXTENSIONS:
        root_dir = root_dir.parent

    layers_dir = root_dir / "layers"

    return PublishPaths(
        root_dir=root_dir,
        layers_dir=layers_dir,
        main_layer_path=root_dir / main_layer_name,
        layer_mats_path=layers_dir / "layer_mats.usda",
        layer_assign_path=layers_dir / "layer_assign.usda",
    )
