"""Substance Painter plugin for exporting USD assets.

Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

import gc
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Protocol, Sequence, Tuple

from ...version import get_version
from .qt_compat import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
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
    Qt,
)

from ...core.exporter import export_publish
from ...core.exceptions import (
    AxeUSDError,
    ConfigurationError,
    GeometryExportError,
    MaterialExportError,
    USDStageError,
    ValidationError,
)
from ...core.fs_utils import ensure_directory
from ...core.models import ExportSettings
from ...core.publish_paths import build_publish_paths
from ...core.texture_parser import parse_textures
from ...usd.pxr_writer import PxrUsdWriter

from . import presets
from . import usd_scene_fixup
import substance_painter
import substance_painter.event
import substance_painter.export
import substance_painter.ui


# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(
        logging.Formatter("[AxeUSD] %(levelname)s: %(message)s")
    )
    logger.addHandler(stream_handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

PRESET_PATH = Path.home() / ".axe_usd" / "presets.json"
CUSTOM_PRESET_LABEL = "Custom"

DEFAULT_DIALOGUE_DICT = {
    "title": "USD Exporter",
    "enable_usdpreview": True,
    "enable_arnold": False,
    "enable_materialx": True,
    "enable_openpbr": False,
    "enable_save_geometry": True,
}

DEFAULT_PRIMITIVE_PATH = "/Asset"
USD_PREVIEW_JPEG_SIZE_LOG2 = 8  # 256px
USD_PREVIEW_JPEG_SUFFIX = ".jpg"
PREVIEW_TEXTURE_DIRNAME = "previewTextures"
PREVIEW_EXPORT_PRESET = "AxeUSDPreview"

LOG_LEVELS = {
    "Error": logging.ERROR,
    "Warning": logging.WARNING,
    "Info": logging.INFO,
    "Debug": logging.DEBUG,
}

# Hold references to UI widgets
plugin_widgets = []
usd_exported_qdialog = None
callbacks_registered = False


@dataclass
class USDSettings:
    """
    USD export options container.

    Attributes:
        usdpreview (bool): Include UsdPreviewSurface shader.
        arnold (bool): Include Arnold standard_surface shader.
        materialx (bool): Include MaterialX standard_surface shader.
        openpbr (bool): Include MaterialX OpenPBR shader.
        save_geometry (bool): Whether to export mesh geometry.
        texture_format_overrides (Dict[str, str]): Optional per-renderer overrides.
        log_level (str): Logging verbosity.
    """

    usdpreview: bool
    arnold: bool
    materialx: bool
    save_geometry: bool
    openpbr: bool
    texture_format_overrides: Dict[str, str]
    log_level: str


class MeshExporter:
    """
    Exports mesh geometry to USD if requested.
    """

    def __init__(self, settings: ExportSettings):
        """Initialize the mesh exporter.

        Args:
            settings: Export settings for determining output paths.
        """
        # Extract asset name from settings (e.g. primitive_path="/Asset" -> "Asset")
        asset_name = settings.primitive_path.strip("/").split("/")[-1]

        publish_paths = build_publish_paths(
            settings.publish_directory, settings.main_layer_name, asset_name
        )
        self.mesh_path = publish_paths.geometry_path
        self.root_prim_path = DEFAULT_PRIMITIVE_PATH
        self.last_error: str = ""

    def export_mesh(self) -> Optional[Path]:
        """Call Substance Painter's USD mesh exporter.

        Returns:
            Optional[Path]: Path to the exported mesh if successful.
        """
        ensure_directory(self.mesh_path.parent)
        logger.info("Exporting mesh to %s", self.mesh_path)
        logger.debug("Mesh export target suffix: %s", self.mesh_path.suffix)
        export_path = self.mesh_path
        convert_to_usdc = False
        if self.mesh_path.suffix.lower() == ".usdc":
            convert_to_usdc = True
            export_path = self.mesh_path.with_suffix(".usd")
            logger.info(
                "Mesh export target is .usdc; exporting to %s then converting.",
                export_path,
            )

        # Choose an export option to use
        export_option = substance_painter.export.MeshExportOption.BaseMesh
        if not substance_painter.export.scene_is_triangulated():
            export_option = substance_painter.export.MeshExportOption.TriangulatedMesh
        if substance_painter.export.scene_has_tessellation():
            export_option = (
                substance_painter.export.MeshExportOption.TessellationNormalsBaseMesh
            )

        try:
            export_result = substance_painter.export.export_mesh(
                str(export_path), export_option
            )

            # In case of error, display a human readable message:
            if export_result.status != substance_painter.export.ExportStatus.Success:
                raise GeometryExportError(
                    "Mesh export failed.",
                    details={
                        "status": str(export_result.status),
                        "message": str(export_result.message),
                    },
                )
            logger.debug(
                "Mesh export status=%s message=%s",
                export_result.status,
                export_result.message,
            )
            if not export_path.exists():
                raise GeometryExportError(
                    "Mesh export reported success but file is missing.",
                    details={"path": str(export_path)},
                )
            if convert_to_usdc:
                from pxr import Usd

                stage = Usd.Stage.Open(str(export_path))
                if not stage:
                    raise USDStageError(
                        "Failed to open temporary mesh for conversion.",
                        details={"path": str(export_path)},
                    )
                usd_scene_fixup.fix_sp_mesh_stage(stage, self.root_prim_path)
                stage.GetRootLayer().Export(str(self.mesh_path))
                if not self.mesh_path.exists():
                    raise GeometryExportError(
                        "Mesh conversion reported success but file is missing.",
                        details={"path": str(self.mesh_path)},
                    )
                stage = None
                gc.collect()
                if export_path.exists():
                    try:
                        export_path.unlink()
                    except Exception as cleanup_exc:
                        logger.warning(
                            "Failed to remove temporary mesh file %s: %s",
                            export_path,
                            cleanup_exc,
                        )
            return self.mesh_path
        except AxeUSDError as exc:
            self.last_error = exc.message
            if exc.details:
                logger.warning("Mesh export failed: %s (%s)", exc.message, exc.details)
            else:
                logger.warning("Mesh export failed: %s", exc.message)
            return None
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("Mesh export failed: %s", exc)
            return None


def _collect_texture_set_names(
    textures: Mapping[Tuple[str, str], Sequence[str]],
) -> Sequence[str]:
    names: list[str] = []
    for key in textures.keys():
        if isinstance(key, (tuple, list)) and key:
            name = str(key[0])
        else:
            name = str(key)
        if name and name not in names:
            names.append(name)
    return names


def _build_preview_export_config(
    preview_dir: Path, texture_sets: Sequence[str]
) -> Dict[str, object]:
    export_list = [
        {"rootPath": name, "exportPreset": PREVIEW_EXPORT_PRESET}
        for name in texture_sets
    ]
    export_preset = {
        "name": PREVIEW_EXPORT_PRESET,
        "maps": [
            {
                "fileName": "$textureSet_BaseColor",
                "channels": [
                    {
                        "destChannel": "R",
                        "srcChannel": "R",
                        "srcMapType": "documentMap",
                        "srcMapName": "baseColor",
                    },
                    {
                        "destChannel": "G",
                        "srcChannel": "G",
                        "srcMapType": "documentMap",
                        "srcMapName": "baseColor",
                    },
                    {
                        "destChannel": "B",
                        "srcChannel": "B",
                        "srcMapType": "documentMap",
                        "srcMapName": "baseColor",
                    }
                ],
                "parameters": {
                    "fileFormat": USD_PREVIEW_JPEG_SUFFIX.lstrip("."),
                    "bitDepth": "8",
                    "dithering": False,
                    "sizeLog2": USD_PREVIEW_JPEG_SIZE_LOG2,
                    "paddingAlgorithm": "diffusion",
                    "dilationDistance": 16,
                },
            }
        ],
    }
    return {
        "exportPath": str(preview_dir),
        "defaultExportPreset": PREVIEW_EXPORT_PRESET,
        "exportPresets": [export_preset],
        "exportList": export_list,
        "exportShaderParams": False,
    }


def _export_usdpreview_textures(
    textures_dir: Path, texture_sets: Sequence[str]
) -> None:
    if not texture_sets:
        raise ValidationError("UsdPreview export failed: no texture sets found.")

    ensure_directory(textures_dir)
    preview_dir = textures_dir / PREVIEW_TEXTURE_DIRNAME
    ensure_directory(preview_dir)
    export_config = _build_preview_export_config(preview_dir, texture_sets)
    logger.debug("UsdPreview texture sets: %s", texture_sets)
    export_fn = getattr(substance_painter.export, "export_project_textures", None)
    if export_fn is None:
        raise ConfigurationError(
            "UsdPreview export failed: export_project_textures not available."
        )

    logger.debug("UsdPreview export config: %s", export_config)
    try:
        result = export_fn(export_config)
    except Exception as exc:
        raise MaterialExportError(
            "UsdPreview export failed.",
            details={"error": str(exc)},
        ) from exc

    status = getattr(result, "status", None)
    message = getattr(result, "message", "")
    export_status = getattr(substance_painter.export, "ExportStatus", None)
    if export_status and hasattr(export_status, "Success") and status is not None:
        if status != export_status.Success:
            raise MaterialExportError(
                "UsdPreview export failed.",
                details={"status": str(status), "message": str(message)},
            )
    elif result is False:
        raise MaterialExportError(
            "UsdPreview export failed.",
            details={"result": str(result)},
        )


def _is_preview_export_context(context: "ExportContext") -> bool:
    first_path = next((paths[0] for paths in context.textures.values() if paths), None)
    if not first_path:
        return False
    try:
        parts = Path(first_path).parts
    except Exception:
        return False
    return any(
        part.lower() == PREVIEW_TEXTURE_DIRNAME.lower() for part in parts
    )


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
        self._preset_sync_blocked = False

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(6)
        self.setLayout(root_layout)

        menu_bar = QMenuBar()
        menu_bar.setNativeMenuBar(False)
        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction("Help", self._show_help)
        help_menu.addAction("About", self._show_about)
        advanced_menu = menu_bar.addMenu("Advanced")
        log_menu = advanced_menu.addMenu("Logging Verbosity")
        self._log_level_name = "Debug"
        self._log_level_actions = {}
        for level_name in LOG_LEVELS.keys():
            action = log_menu.addAction(level_name)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked, name=level_name: self._set_log_level(name)
            )
            self._log_level_actions[level_name] = action
        for name, action in self._log_level_actions.items():
            action.setChecked(name == self._log_level_name)
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

        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(6)
        preset_label = QLabel("Preset")
        self.preset_combo = QComboBox()
        self.preset_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self.save_preset_btn = QPushButton("Save Preset")
        self.save_preset_btn.clicked.connect(self._save_preset_prompt)
        preset_row.addWidget(preset_label)
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(self.save_preset_btn, 0)
        preset_row_widget = QWidget()
        preset_row_widget.setLayout(preset_row)
        content_layout.addWidget(preset_row_widget)

        engine_box = QGroupBox("Render Engines")
        engine_box.setFlat(True)
        engine_layout = QVBoxLayout()
        engine_layout.setContentsMargins(8, 6, 8, 8)
        engine_layout.setSpacing(4)
        self.usdpreview = QCheckBox("USD Preview")
        self.usdpreview.setChecked(DEFAULT_DIALOGUE_DICT["enable_usdpreview"])
        self.arnold = QCheckBox("Arnold")
        self.arnold.setChecked(DEFAULT_DIALOGUE_DICT["enable_arnold"])
        self.materialx = QCheckBox("MaterialX (Standard Surface)")
        self.materialx.setChecked(DEFAULT_DIALOGUE_DICT["enable_materialx"])
        self.openpbr = QCheckBox("OpenPBR (MaterialX)")
        self.openpbr.setChecked(DEFAULT_DIALOGUE_DICT["enable_openpbr"])
        self.usdpreview.toggled.connect(self._sync_preset_combo)
        self.arnold.toggled.connect(self._sync_preset_combo)
        self.materialx.toggled.connect(self._sync_preset_combo)
        self.openpbr.toggled.connect(self._sync_preset_combo)
        engine_layout.addWidget(self.usdpreview)
        engine_layout.addWidget(self.arnold)
        engine_layout.addWidget(self.materialx)
        engine_layout.addWidget(self.openpbr)
        engine_box.setLayout(engine_layout)
        engine_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        content_layout.addWidget(engine_box)

        options_box = QGroupBox("Export Options")
        options_box.setFlat(True)
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(8, 6, 8, 8)
        options_layout.setSpacing(4)
        self.geom = QCheckBox("Include Geometry in USD")
        self.geom.setToolTip("Exports mesh geometry to USD if supported")
        self.geom.setChecked(DEFAULT_DIALOGUE_DICT["enable_save_geometry"])
        self.geom.toggled.connect(self._sync_preset_combo)
        options_layout.addWidget(self.geom)
        options_box.setLayout(options_layout)
        options_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        content_layout.addWidget(options_box)

        advanced_box = QGroupBox("Advanced")
        advanced_box.setCheckable(True)
        advanced_box.setChecked(False)
        advanced_container = QWidget()
        advanced_layout = QFormLayout()
        advanced_layout.setContentsMargins(8, 6, 8, 8)
        advanced_layout.setSpacing(4)
        advanced_container.setLayout(advanced_layout)

        self.override_usdpreview = QLineEdit()
        self.override_usdpreview.setPlaceholderText("auto")
        self.override_usdpreview.setToolTip(
            "Override USD Preview texture format (e.g., jpg)"
        )
        self.override_usdpreview.textChanged.connect(self._sync_preset_combo)
        advanced_layout.addRow("USD Preview Format", self.override_usdpreview)

        self.override_arnold = QLineEdit()
        self.override_arnold.setPlaceholderText("png")
        self.override_arnold.setToolTip("Override Arnold texture format (e.g., exr)")
        self.override_arnold.textChanged.connect(self._sync_preset_combo)
        advanced_layout.addRow("Arnold Format", self.override_arnold)

        self.override_mtlx = QLineEdit()
        self.override_mtlx.setPlaceholderText("png")
        self.override_mtlx.setToolTip("Override MaterialX texture format (e.g., png)")
        self.override_mtlx.textChanged.connect(self._sync_preset_combo)
        advanced_layout.addRow("MaterialX Format", self.override_mtlx)

        self.override_openpbr = QLineEdit()
        self.override_openpbr.setPlaceholderText("png")
        self.override_openpbr.setToolTip("Override OpenPBR texture format (e.g., png)")
        self.override_openpbr.textChanged.connect(self._sync_preset_combo)
        advanced_layout.addRow("OpenPBR Format", self.override_openpbr)

        advanced_box_layout = QVBoxLayout()
        advanced_box_layout.setContentsMargins(0, 0, 0, 0)
        advanced_box_layout.addWidget(advanced_container)
        advanced_box.setLayout(advanced_box_layout)
        advanced_container.setVisible(False)
        advanced_box.toggled.connect(advanced_container.setVisible)
        content_layout.addWidget(advanced_box)

        self._presets = presets.load_presets(PRESET_PATH, logger)
        self._refresh_preset_combo()
        self._sync_preset_combo()

    def _save_presets(self) -> None:
        try:
            presets.save_presets(PRESET_PATH, self._presets)
        except Exception as exc:
            logger.error("Failed to save presets: %s", exc)
            QMessageBox.warning(
                self,
                "Preset Save Failed",
                f"Could not save presets to:\n{PRESET_PATH}\n\n{exc}",
            )

    def _refresh_preset_combo(self) -> None:
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItem(CUSTOM_PRESET_LABEL)
        for name in presets.BUILTIN_PRESETS.keys():
            self.preset_combo.addItem(name)
        if self._presets:
            self.preset_combo.insertSeparator(self.preset_combo.count())
            for name in sorted(self._presets.keys()):
                self.preset_combo.addItem(name)
        self.preset_combo.blockSignals(False)

    def _sync_preset_combo(self) -> None:
        if self._preset_sync_blocked:
            return
        data = self._collect_preset_data()
        name = presets.match_preset_name(data, self._presets) or CUSTOM_PRESET_LABEL
        self.preset_combo.blockSignals(True)
        index = self.preset_combo.findText(name)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)

    def _on_preset_changed(self, name: str) -> None:
        preset = presets.BUILTIN_PRESETS.get(name)
        if preset is None:
            preset = self._presets.get(name)
        if not preset:
            return
        self._apply_preset_data(preset)

    def _collect_preset_data(self) -> Dict[str, object]:
        return {
            "usdpreview": self.usdpreview.isChecked(),
            "arnold": self.arnold.isChecked(),
            "materialx": self.materialx.isChecked(),
            "openpbr": self.openpbr.isChecked(),
            "save_geometry": self.geom.isChecked(),
            "texture_format_overrides": self._collect_overrides(),
            "log_level": self._log_level_name,
        }

    def _apply_preset_data(self, data: Dict[str, object]) -> None:
        self._preset_sync_blocked = True
        try:
            self.usdpreview.setChecked(bool(data.get("usdpreview", True)))
            self.arnold.setChecked(bool(data.get("arnold", False)))
            self.materialx.setChecked(bool(data.get("materialx", True)))
            self.openpbr.setChecked(bool(data.get("openpbr", False)))
            self.geom.setChecked(bool(data.get("save_geometry", True)))

            overrides = data.get("texture_format_overrides") or {}
            if isinstance(overrides, dict):
                self.override_usdpreview.setText(str(overrides.get("usd_preview", "")))
                self.override_arnold.setText(str(overrides.get("arnold", "")))
                self.override_mtlx.setText(str(overrides.get("mtlx", "")))
                self.override_openpbr.setText(str(overrides.get("openpbr", "")))

            log_level = data.get("log_level")
            if log_level in LOG_LEVELS:
                self._set_log_level(str(log_level))
        finally:
            self._preset_sync_blocked = False

        self._sync_preset_combo()

    def _save_preset_prompt(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        name = name.strip()
        if not ok or not name:
            return
        self._presets[name] = self._collect_preset_data()
        self._save_presets()
        self._refresh_preset_combo()
        self.preset_combo.setCurrentText(name)

    def _set_log_level(self, name: str) -> None:
        if name not in LOG_LEVELS:
            return
        self._log_level_name = name
        for level_name, action in self._log_level_actions.items():
            action.setChecked(level_name == name)
        self._sync_preset_combo()

    def _show_help(self) -> None:
        """Show a short help dialog."""
        message = (
            "Export textures first, then the plugin writes USD next to the export folder."
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

    def get_settings(self) -> USDSettings:
        """
        Read UI state into USDSettings.

        Returns:
            USDSettings: Settings collected from the dialog.
        """
        return USDSettings(
            self.usdpreview.isChecked(),
            self.arnold.isChecked(),
            self.materialx.isChecked(),
            self.geom.isChecked(),
            self.openpbr.isChecked(),
            self._collect_overrides(),
            self._log_level_name,
        )

    def _collect_overrides(self) -> Dict[str, str]:
        overrides: Dict[str, str] = {}
        usd_preview = self.override_usdpreview.text().strip()
        arnold = self.override_arnold.text().strip()
        mtlx = self.override_mtlx.text().strip()
        openpbr = self.override_openpbr.text().strip()
        if usd_preview:
            overrides["usd_preview"] = usd_preview
        if arnold:
            overrides["arnold"] = arnold
        if mtlx:
            overrides["mtlx"] = mtlx
        if openpbr:
            overrides["openpbr"] = openpbr
        return overrides


# Entry-point functions required by Substance Painter
class ExportContext(Protocol):
    """Substance Painter export context interface."""

    textures: Mapping[Tuple[str, str], Sequence[str]]


def start_plugin() -> None:
    """Create the export UI and register callbacks."""
    logger.info("Plugin starting.")
    global usd_exported_qdialog
    usd_exported_qdialog = USDExporterView()
    substance_painter.ui.add_dock_widget(usd_exported_qdialog)
    plugin_widgets.append(usd_exported_qdialog)
    register_callbacks()


def register_callbacks() -> None:
    """Register the post-export callback."""
    logger.info("Registered callbacks.")
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
    logger.info("ExportTexturesEnded emitted.")
    if _is_preview_export_context(context):
        logger.info("Preview texture export detected; skipping USD publish.")
        return
    try:
        if usd_exported_qdialog is None:
            raise ConfigurationError("USD Export UI is not available.")
        if not context.textures:
            raise ValidationError("No textures were exported.")

        first_path = next((paths[0] for paths in context.textures.values() if paths), None)
        if not first_path:
            raise ValidationError("No exported texture files found.")
        export_dir = Path(first_path).parent

        raw = usd_exported_qdialog.get_settings()
        log_level = LOG_LEVELS.get(raw.log_level)
        if log_level is not None:
            logger.setLevel(log_level)
        primitive_path = DEFAULT_PRIMITIVE_PATH
        publish_dir = str(export_dir)
        materials = parse_textures(context.textures)
        if not materials:
            raise ValidationError("No recognized textures were found.")

        texture_overrides = dict(raw.texture_format_overrides or {})
        if raw.usdpreview:
            asset_name = primitive_path.strip("/").split("/")[-1]
            textures_dir = export_dir / asset_name / "textures"
            texture_sets = _collect_texture_set_names(context.textures)
            _export_usdpreview_textures(textures_dir, texture_sets)

        settings = ExportSettings(
            usdpreview=raw.usdpreview,
            arnold=raw.arnold,
            materialx=raw.materialx,
            openpbr=raw.openpbr,
            primitive_path=primitive_path,
            publish_directory=Path(publish_dir),
            save_geometry=raw.save_geometry,
            texture_format_overrides=texture_overrides or None,
        )

        geo_file = None
        if settings.save_geometry:
            mesh_exporter = MeshExporter(settings)
            geo_file = mesh_exporter.export_mesh()
            if geo_file is None:
                raise GeometryExportError(
                    "Mesh export failed.",
                    details={"message": mesh_exporter.last_error},
                )

        export_publish(materials, settings, geo_file, PxrUsdWriter())
    except AxeUSDError as exc:
        logger.error("USD export failed: %s", exc.message)
        if exc.details:
            logger.error("USD export details: %s", exc.details)
        if usd_exported_qdialog is not None:
            detail = f"\n\nDetails: {exc.details}" if exc.details else ""
            QMessageBox.critical(
                usd_exported_qdialog,
                "USD Exporter",
                f"USD export failed:\n{exc.message}{detail}",
            )
        return
    except Exception as exc:
        logger.exception("USD export failed: %s", exc)
        if usd_exported_qdialog is not None:
            QMessageBox.critical(
                usd_exported_qdialog,
                "USD Exporter",
                f"USD export failed:\n{exc}\n\nCheck the logs for more details.",
            )
        return

    QMessageBox.information(
        usd_exported_qdialog,
        "USD Exporter",
        f"USD export complete.\n\nPublish folder:\n{settings.publish_directory}",
    )


def close_plugin() -> None:
    """Remove all widgets that have been added to the UI."""
    logger.info("Closing plugin.")
    global callbacks_registered, usd_exported_qdialog
    if callbacks_registered:
        try:
            substance_painter.event.DISPATCHER.disconnect(
                substance_painter.event.ExportTexturesEnded, on_post_export
            )
        except Exception as e:
            logger.warning(
                "close_plugin() failed to disconnect event handler: %s", e
            )
        callbacks_registered = False
    for widget in plugin_widgets:
        substance_painter.ui.delete_ui_element(widget)
    plugin_widgets.clear()
    usd_exported_qdialog = None
