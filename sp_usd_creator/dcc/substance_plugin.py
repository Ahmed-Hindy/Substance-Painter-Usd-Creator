"""
Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""
import logging
from dataclasses import dataclass
from pathlib import Path

from PySide2.QtGui import QIcon
from PySide2.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QMessageBox,
)

from ..core.exporter import export_publish
from ..core.fs_utils import ensure_directory
from ..core.models import ExportSettings
from ..core.publish_paths import build_publish_paths
from ..core.texture_parser import parse_textures
from ..usd.pxr_writer import PxrUsdWriter

import substance_painter
import substance_painter.event
import substance_painter.export
import substance_painter.ui


# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DEFAULT_DIALOGUE_DICT = {
    "title": "USD Exporter",
    "publish_location": "<export_folder>",
    "primitive_path": "/root",
    "enable_usdpreview": True,
    "enable_arnold": True,
    "enable_materialx": True,
    "enable_save_geometry": True,
}

# Hold references to UI widgets
plugin_widgets = []


@dataclass
class USDSettings:
    """
    USD export options container.

    Attributes:
        usdpreview (bool): Include UsdPreviewSurface shader.
        arnold (bool): Include Arnold standard_surface shader.
        materialx (bool): Include MaterialX shader.
        primitive_path (str): USD prim path for material_dict_list.
        publish_directory (str): Directory for output USD layers.
        save_geometry (bool): Whether to export mesh geometry.
    """

    usdpreview: bool
    arnold: bool
    materialx: bool
    primitive_path: str
    publish_directory: str
    save_geometry: bool


class MeshExporter:
    """
    Exports mesh geometry to USD if requested.
    """

    def __init__(self, settings: ExportSettings):
        publish_paths = build_publish_paths(settings.publish_directory, settings.main_layer_name)
        self.mesh_path = publish_paths.layers_dir / "mesh.usd"

    def export_mesh(self):
        """
        Call Substance Painter's USD mesh exporter.
        """
        ensure_directory(self.mesh_path.parent)
        logger.info("Exporting mesh to %s", self.mesh_path)

        # Choose an export option to use
        export_option = substance_painter.export.MeshExportOption.BaseMesh
        if not substance_painter.export.scene_is_triangulated():
            export_option = substance_painter.export.MeshExportOption.TriangulatedMesh
        if substance_painter.export.scene_has_tessellation():
            export_option = substance_painter.export.MeshExportOption.TessellationNormalsBaseMesh

        try:
            export_result = substance_painter.export.export_mesh(str(self.mesh_path), export_option)

            # In case of error, display a human readable message:
            if export_result.status != substance_painter.export.ExportStatus.Success:
                print(export_result.message)
                return None
            return self.mesh_path
        except Exception as exc:
            logger.error("Mesh export failed: %s", exc)
            return None


class USDExporterView(QDialog):
    """
    UI widget for USD export settings.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("USD Exporter")
        self.setWindowIcon(QIcon())
        self.setMinimumSize(500, 200)
        self.setLayout(QVBoxLayout())

        engine_box = QGroupBox("Render Engines")
        engine_layout = QVBoxLayout()
        self.usdpreview = QCheckBox("USD Preview")
        self.usdpreview.setChecked(DEFAULT_DIALOGUE_DICT["enable_usdpreview"])
        self.arnold = QCheckBox("Arnold")
        self.arnold.setChecked(DEFAULT_DIALOGUE_DICT["enable_arnold"])
        self.materialx = QCheckBox("MaterialX")
        self.materialx.setChecked(DEFAULT_DIALOGUE_DICT["enable_materialx"])
        engine_layout.addWidget(self.usdpreview)
        engine_layout.addWidget(self.arnold)
        engine_layout.addWidget(self.materialx)
        engine_box.setLayout(engine_layout)
        self.layout().addWidget(engine_box)

        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Publish Directory"))
        self.pub = QLineEdit()
        self.pub.setMinimumWidth(300)
        self.pub.setPlaceholderText(DEFAULT_DIALOGUE_DICT["publish_location"])
        self.pub.setToolTip("Use <export_folder> token to insert texture folder path")
        h1.addWidget(self.pub)
        h1.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.layout().addLayout(h1)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Primitive Path"))
        self.prim = QLineEdit()
        self.prim.setMinimumWidth(300)
        self.prim.setPlaceholderText(DEFAULT_DIALOGUE_DICT["primitive_path"])
        self.prim.setToolTip("USD prim path where material_dict_list will be created")
        self.prim.editingFinished.connect(self._validate_prim_path)
        h2.addWidget(self.prim)
        h2.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Fixed))
        self.layout().addLayout(h2)

        self.geom = QCheckBox("Save Geometry in USD File")
        self.geom.setToolTip("Exports mesh geometry to USD if supported")
        self.geom.setChecked(DEFAULT_DIALOGUE_DICT["enable_save_geometry"])
        self.layout().addWidget(self.geom)

    def _validate_prim_path(self):
        text = self.prim.text()
        if not text.startswith("/"):
            QMessageBox.warning(self, "Invalid Path", "Primitive path must start with '/'")
            self.prim.setStyleSheet("border:1px solid red")
        else:
            self.prim.setStyleSheet("")

    def get_settings(self) -> USDSettings:
        """
        Read UI state into USDSettings.

        Returns:
            USDSettings
        """
        # Use default publish location if user leaves the field blank
        publish_dir = self.pub.text().strip() or DEFAULT_DIALOGUE_DICT["publish_location"]
        primitive_path = self.prim.text().strip() or DEFAULT_DIALOGUE_DICT["primitive_path"]

        return USDSettings(
            self.usdpreview.isChecked(),
            self.arnold.isChecked(),
            self.materialx.isChecked(),
            primitive_path,
            publish_dir,
            self.geom.isChecked(),
        )


# Entry-point functions required by Substance Painter

def start_plugin():
    print("Plugin Starting...")
    global usd_exported_qdialog
    usd_exported_qdialog = USDExporterView()
    substance_painter.ui.add_dock_widget(usd_exported_qdialog)
    plugin_widgets.append(usd_exported_qdialog)
    register_callbacks()


def register_callbacks():
    """Register the post-export callback"""
    print("Registered callbacks")
    substance_painter.event.DISPATCHER.connect(
        substance_painter.event.ExportTexturesEnded, on_post_export
    )


def on_post_export(context):
    """Function to be called after textures are exported"""
    print("ExportTexturesEnded emitted!!!")
    if not context.textures:
        logger.warning("No textures exported; skipping USD publish.")
        return

    first_tex = next(iter(context.textures.values()))[0]
    export_dir = Path(first_tex).parent

    raw = usd_exported_qdialog.get_settings()
    publish_dir = raw.publish_directory.replace("<export_folder>", str(export_dir))
    settings = ExportSettings(
        usdpreview=raw.usdpreview,
        arnold=raw.arnold,
        materialx=raw.materialx,
        primitive_path=raw.primitive_path,
        publish_directory=Path(publish_dir),
        save_geometry=raw.save_geometry,
    )
    materials = parse_textures(context.textures)

    geo_file = None
    if settings.save_geometry:
        geo_file = MeshExporter(settings).export_mesh()
    export_publish(materials, settings, geo_file, PxrUsdWriter())


def close_plugin():
    """Remove all widgets that have been added to the UI"""
    print("Closing plugin")
    for widget in plugin_widgets:
        substance_painter.ui.delete_ui_element(widget)
    plugin_widgets.clear()
