from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class ExportSettings:
    """Configuration for a USD export run.

    Attributes:
        usdpreview: Whether to emit UsdPreviewSurface materials.
        arnold: Whether to emit Arnold materials.
        materialx: Whether to emit MaterialX standard surface materials.
        openpbr: Whether to emit MaterialX OpenPBR materials.
        primitive_path: Root prim path for published assets.
        publish_directory: Output directory for USD layers.
        save_geometry: Whether to export mesh geometry.
        main_layer_name: Name of the main layer file.
        texture_format_overrides: Optional per-renderer texture format overrides.
        arnold_displacement_mode: Whether to use bump or true displacement for
                                  Arnold height maps.
    """

    usdpreview: bool
    arnold: bool
    materialx: bool
    openpbr: bool
    primitive_path: str
    publish_directory: Path
    save_geometry: bool
    main_layer_name: str = "main.usda"
    texture_format_overrides: Optional[Dict[str, str]] = None
    arnold_displacement_mode: str = "bump"


@dataclass(frozen=True)
class MaterialBundle:
    """Material name with resolved texture slot paths.

    Attributes:
        name: Material identifier.
        textures: Mapping of slot name to texture path.
        mesh_names: Optional mesh names assigned to this material/texture set.
        udim_slots: Optional texture slots that use UDIM token paths.
    """

    name: str
    textures: Dict[str, str]
    mesh_names: Tuple[str, ...] = ()
    udim_slots: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PublishPaths:
    """Resolved file system paths for USD publishing.

    Attributes:
        root_dir: Root publish directory.
        geometry_path: Path to the geometry layer file (geo.usdc).
    """

    root_dir: Path
    geometry_path: Path
