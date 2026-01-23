from pathlib import Path
from typing import Iterable, Optional, Protocol

from .models import ExportSettings, MaterialBundle, PublishPaths
from .publish_paths import build_publish_paths


class ExportWriter(Protocol):
    def export(
        self,
        materials: Iterable[MaterialBundle],
        settings: ExportSettings,
        geo_file: Optional[Path],
        paths: PublishPaths,
    ) -> None:
        ...


def export_publish(
    materials: Iterable[MaterialBundle],
    settings: ExportSettings,
    geo_file: Optional[Path],
    writer: ExportWriter,
) -> PublishPaths:
    paths = build_publish_paths(settings.publish_directory, settings.main_layer_name)
    writer.export(materials, settings, geo_file, paths)
    return paths
