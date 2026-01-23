from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass(frozen=True)
class ExportSettings:
    usdpreview: bool
    arnold: bool
    materialx: bool
    primitive_path: str
    publish_directory: Path
    save_geometry: bool
    main_layer_name: str = "main.usda"


@dataclass(frozen=True)
class MaterialBundle:
    name: str
    textures: Dict[str, str]


@dataclass(frozen=True)
class PublishPaths:
    root_dir: Path
    layers_dir: Path
    main_layer_path: Path
    layer_mats_path: Path
    layer_assign_path: Path
