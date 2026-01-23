"""Substance Painter plugin for exporting USD assets.

Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Protocol, Sequence, Tuple

from ...version import get_version
from .qt_compat import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMenuBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QIcon,
    QPalette,
    Qt,
)

from ...core.exporter import export_publish
from ...core.fs_utils import ensure_directory
from ...core.models import ExportSettings
from ...core.publish_paths import build_publish_paths
from ...core.texture_parser import parse_textures
from ...usd.pxr_writer import PxrUsdWriter

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
usd_exported_qdialog = None
callbacks_registered = False


def _is_widget_valid(widget) -> bool:
    """Return True when the Qt widget reference is still valid.

    Args:
        widget: Qt widget instance or None.

    Returns:
        bool: True if the widget is valid or unavailable to validate.
    """
    if widget is None:
        return False
    try:
        from shiboken2 import isValid
    except Exception:
        return True
    return isValid(widget)


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
        """Initialize the mesh exporter.

        Args:
            settings: Export settings for determining output paths.
        """
        publish_paths = build_publish_paths(settings.publish_directory, settings.main_layer_name)
        self.mesh_path = publish_paths.layers_dir / "mesh.usd"

    def export_mesh(self) -> Optional[Path]:
        """Call Substance Painter's USD mesh exporter.

        Returns:
            Optional[Path]: Path to the exported mesh if successful.
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
        """Build the export settings UI.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("USD Exporter")
        self.setWindowIcon(QIcon())
        self.setMinimumSize(520, 240)
        self._plugin_version = get_version()

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(6)
        self.setLayout(root_layout)

        menu_bar = QMenuBar()
        menu_bar.setNativeMenuBar(False)
        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction("Help", self._show_help)
        help_menu.addAction("About", self._show_about)
        root_layout.setMenuBar(menu_bar)

        title = QLabel("Axe USD Exporter")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        root_layout.addWidget(title)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        root_layout.addWidget(scroll_area, 1)

        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        content_layout.setAlignment(Qt.AlignTop)
        content.setLayout(content_layout)
        scroll_area.setWidget(content)

        engine_box = QGroupBox("Render Engines")
        engine_box.setFlat(True)
        engine_layout = QVBoxLayout()
        engine_layout.setContentsMargins(8, 6, 8, 8)
        engine_layout.setSpacing(4)
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
        engine_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        content_layout.addWidget(engine_box)

        paths_box = QGroupBox("Paths")
        paths_box.setFlat(True)
        paths_layout = QFormLayout()
        paths_layout.setContentsMargins(8, 6, 8, 8)
        paths_layout.setSpacing(4)
        paths_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        paths_layout.setFormAlignment(Qt.AlignTop)
        paths_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.pub = QLineEdit()
        self.pub.setMinimumWidth(320)
        self.pub.setPlaceholderText(DEFAULT_DIALOGUE_DICT["publish_location"])
        self.pub.setToolTip("Use <export_folder> token to insert texture folder path")
        self.pub.setClearButtonEnabled(True)
        pub_row = QHBoxLayout()
        pub_row.setContentsMargins(0, 0, 0, 0)
        pub_row.setSpacing(6)
        pub_row.addWidget(self.pub, 1)
        self.pub_browse = QPushButton("Browse...")
        self.pub_browse.setToolTip("Select a publish directory on disk")
        self.pub_browse.clicked.connect(self._browse_publish_directory)
        self.pub_browse.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        pub_row.addWidget(self.pub_browse, 0)
        pub_row_widget = QWidget()
        pub_row_widget.setLayout(pub_row)
        paths_layout.addRow("Publish Directory", pub_row_widget)

        pub_hint = self._make_hint_label("Tip: <export_folder> uses the texture export folder.")
        paths_layout.addRow("", pub_hint)

        self.prim = QLineEdit()
        self.prim.setMinimumWidth(320)
        self.prim.setPlaceholderText(DEFAULT_DIALOGUE_DICT["primitive_path"])
        self.prim.setToolTip("USD prim path where material_dict_list will be created")
        self.prim.setClearButtonEnabled(True)
        self.prim.editingFinished.connect(self._validate_prim_path)
        paths_layout.addRow("Primitive Path", self.prim)

        prim_hint = self._make_hint_label("Example: /root or /root/materials")
        paths_layout.addRow("", prim_hint)

        paths_box.setLayout(paths_layout)
        paths_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        content_layout.addWidget(paths_box)

        options_box = QGroupBox("Export Options")
        options_box.setFlat(True)
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(8, 6, 8, 8)
        options_layout.setSpacing(4)
        self.geom = QCheckBox("Include Geometry in USD")
        self.geom.setToolTip("Exports mesh geometry to USD if supported")
        self.geom.setChecked(DEFAULT_DIALOGUE_DICT["enable_save_geometry"])
        options_layout.addWidget(self.geom)
        options_box.setLayout(options_layout)
        options_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        content_layout.addWidget(options_box)

    def _validate_prim_path(self):
        """Validate the primitive path input field."""
        text = self.prim.text()
        if not text.startswith("/"):
            QMessageBox.warning(self, "Invalid Path", "Primitive path must start with '/'")
            self.prim.setStyleSheet("border:1px solid red")
        else:
            self.prim.setStyleSheet("")

    def _make_hint_label(self, text: str) -> QLabel:
        """Create a hint label styled for the dialog.

        Args:
            text: Hint text to display.

        Returns:
            QLabel: Configured hint label widget.
        """
        hint = QLabel(text)
        hint.setWordWrap(True)
        hint_font = hint.font()
        hint_font.setPointSize(max(8, hint_font.pointSize() - 1))
        hint.setFont(hint_font)
        pal = hint.palette()
        placeholder_role = getattr(QPalette, "PlaceholderText", None)
        if placeholder_role is not None:
            hint_color = pal.color(placeholder_role)
        else:
            hint_color = pal.color(QPalette.Disabled, QPalette.WindowText)
        if hint_color.isValid():
            pal.setColor(QPalette.WindowText, hint_color)
        hint.setPalette(pal)
        hint.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        return hint

    def _show_help(self) -> None:
        """Show a short help dialog."""
        message = (
            "Export textures first, then the plugin writes USD next to the export folder.\n\n"
            "Use <export_folder> to auto-insert the current texture export path."
        )
        QMessageBox.information(self, "Axe USD Exporter Help", message)

    def _show_about(self) -> None:
        """Show an about dialog with version details."""
        message = (
            f"Axe USD Exporter\n"
            f"Version {self._plugin_version}\n\n"
            "Exports Substance Painter textures to USD with supported render engines."
        )
        QMessageBox.information(self, "About Axe USD Exporter", message)

    def _browse_publish_directory(self) -> None:
        """Open a directory picker for the publish path."""
        current = self.pub.text().strip()
        if not current or current == DEFAULT_DIALOGUE_DICT["publish_location"]:
            current = str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Publish Directory",
            current,
        )
        if selected:
            self.pub.setText(selected)

    def get_settings(self) -> USDSettings:
        """
        Read UI state into USDSettings.

        Returns:
            USDSettings: Settings collected from the dialog.
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
class ExportContext(Protocol):
    """Substance Painter export context interface."""

    textures: Mapping[Tuple[str, str], Sequence[str]]


def start_plugin() -> None:
    """Create the export UI and register callbacks."""
    print("Plugin Starting...")
    global usd_exported_qdialog
    usd_exported_qdialog = USDExporterView()
    substance_painter.ui.add_dock_widget(usd_exported_qdialog)
    plugin_widgets.append(usd_exported_qdialog)
    register_callbacks()


def register_callbacks() -> None:
    """Register the post-export callback."""
    print("Registered callbacks")
    global callbacks_registered
    if callbacks_registered:
        return
    substance_painter.event.DISPATCHER.connect(
        substance_painter.event.ExportTexturesEnded, on_post_export
    )
    callbacks_registered = True


def on_post_export(context: ExportContext) -> None:
    """Handle the texture export completion event.

    Args:
        context: Substance Painter export context.
    """
    print("ExportTexturesEnded emitted!!!")
    if not _is_widget_valid(usd_exported_qdialog):
        logger.warning("USD Export UI is not available; skipping export.")
        return
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


def close_plugin() -> None:
    """Remove all widgets that have been added to the UI."""
    print("Closing plugin")
    global callbacks_registered, usd_exported_qdialog
    if callbacks_registered:
        try:
            substance_painter.event.DISPATCHER.disconnect(
                substance_painter.event.ExportTexturesEnded, on_post_export
            )
        except Exception as e:
            print(f"WARNING: close_plugin() Failed to disconnect event handler: {e}")
            pass
        callbacks_registered = False
    for widget in plugin_widgets:
        substance_painter.ui.delete_ui_element(widget)
    plugin_widgets.clear()
    usd_exported_qdialog = None
