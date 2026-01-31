"""Substance Painter USD export UI."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from ...version import get_version
from . import presets
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

LOG_LEVELS = {
    "Error": logging.ERROR,
    "Warning": logging.WARNING,
    "Info": logging.INFO,
    "Debug": logging.DEBUG,
}


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


class USDExporterView(QDialog):
    """
    UI widget for USD export settings.
    """

    def __init__(
        self, parent=None, logger: Optional[logging.Logger] = None
    ) -> None:
        """Build the export settings UI.

        Args:
            parent: Optional parent widget.
            logger: Optional logger to use for UI-related messages.
        """
        super().__init__(parent)
        self._logger = logger or logging.getLogger(__name__)
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

        self._presets = presets.load_presets(PRESET_PATH, self._logger)
        self._refresh_preset_combo()
        self._sync_preset_combo()

    def _save_presets(self) -> None:
        try:
            presets.save_presets(PRESET_PATH, self._presets)
        except Exception as exc:
            self._logger.error("Failed to save presets: %s", exc)
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
