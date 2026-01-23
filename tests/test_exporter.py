from pathlib import Path

from sp_usd_creator.core.exporter import export_publish
from sp_usd_creator.core.models import ExportSettings, MaterialBundle


class FakeWriter:
    def __init__(self):
        self.called = False
        self.materials = None
        self.settings = None
        self.geo_file = None
        self.paths = None

    def export(self, materials, settings, geo_file, paths):
        self.called = True
        self.materials = list(materials)
        self.settings = settings
        self.geo_file = geo_file
        self.paths = paths


def test_export_publish_calls_writer():
    settings = ExportSettings(
        usdpreview=True,
        arnold=False,
        materialx=False,
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
