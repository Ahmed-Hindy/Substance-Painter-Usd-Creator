from pathlib import Path

from axe_usd.core.exporter import export_publish
from axe_usd.core.models import ExportSettings, MaterialBundle


class FakeWriter:
    """Test double for the export writer protocol."""

    def __init__(self):
        """Initialize the fake writer state."""
        self.called = False
        self.materials = None
        self.settings = None
        self.geo_file = None
        self.paths = None

    def export(self, materials, settings, geo_file, paths):
        """Capture export arguments for assertions.

        Args:
            materials: Material bundles passed to the writer.
            settings: Export settings used for the call.
            geo_file: Optional geometry file path.
            paths: Publish paths used for export.
        """
        self.called = True
        self.materials = list(materials)
        self.settings = settings
        self.geo_file = geo_file
        self.paths = paths


def test_export_publish_calls_writer():
    """Ensure export_publish delegates to the writer and returns paths."""
    settings = ExportSettings(
        usdpreview=True,
        arnold=False,
        materialx=False,
        openpbr=False,
        primitive_path="/root",
        publish_directory=Path("publish"),
        save_geometry=False,
    )
    materials = [MaterialBundle(name="Mat", textures={"basecolor": "albedo.png"})]

    writer = FakeWriter()
    paths = export_publish(materials, settings, None, writer)

    assert writer.called is True
    assert writer.paths == paths
    assert paths.root_dir == Path("publish")
    assert writer.materials[0].name == "Mat"
