from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class ExportSettings:
    """Configuration for a USD export run.

    Attributes:
        usdpreview: Whether to emit UsdPreviewSurface materials.
        arnold: Whether to emit Arnold materials.
        materialx: Whether to emit MaterialX materials.
        primitive_path: Root prim path for published assets.
        publish_directory: Output directory for USD layers.
        save_geometry: Whether to export mesh geometry.
        main_layer_name: Name of the main layer file.
        texture_format_overrides: Optional per-renderer texture format overrides.
    """

    usdpreview: bool
    arnold: bool
    materialx: bool
    primitive_path: str
    publish_directory: Path
    save_geometry: bool
    main_layer_name: str = "main.usda"
    texture_format_overrides: Optional[Dict[str, str]] = None


@dataclass(frozen=True)
class MaterialBundle:
    """Material name with resolved texture slot paths.

    Attributes:
        name: Material identifier.
        textures: Mapping of slot name to texture path.
    """

    name: str
    textures: Dict[str, str]


@dataclass(frozen=True)
class PublishPaths:
    """Resolved file system paths for USD publishing.

    Attributes:
        root_dir: Root publish directory.
        layers_dir: Directory for layer files.
        main_layer_path: Full path to the main layer.
        layer_mats_path: Path to the material layer.
        layer_assign_path: Path to the assignment layer.
    """

    root_dir: Path
    layers_dir: Path
    main_layer_path: Path
    layer_mats_path: Path
    layer_assign_path: Path
