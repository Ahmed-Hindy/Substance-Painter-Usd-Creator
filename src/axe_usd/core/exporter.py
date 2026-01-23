from pathlib import Path
from typing import Iterable, Optional, Protocol

from .models import ExportSettings, MaterialBundle, PublishPaths
from .publish_paths import build_publish_paths


class ExportWriter(Protocol):
    """Protocol for exporters that write USD publish outputs."""

    def export(
        self,
        materials: Iterable[MaterialBundle],
        settings: ExportSettings,
        geo_file: Optional[Path],
        paths: PublishPaths,
    ) -> None:
        """Export USD layers for the given materials.

        Args:
            materials: Material bundles to export.
            settings: Export settings that drive output content.
            geo_file: Optional geometry USD file to reference.
            paths: Precomputed publish paths to write to.
        """
        ...


def export_publish(
    materials: Iterable[MaterialBundle],
    settings: ExportSettings,
    geo_file: Optional[Path],
    writer: ExportWriter,
) -> PublishPaths:
    """Build publish paths and delegate export to the writer.

    Args:
        materials: Material bundles to export.
        settings: Export settings including output location.
        geo_file: Optional geometry USD file to reference.
        writer: Export writer implementation.

    Returns:
        PublishPaths: The resolved publish paths used for export.
    """
    paths = build_publish_paths(settings.publish_directory, settings.main_layer_name)
    writer.export(materials, settings, geo_file, paths)
    return paths
