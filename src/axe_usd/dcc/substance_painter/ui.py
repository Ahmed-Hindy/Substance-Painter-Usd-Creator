"""Substance Painter USD export UI."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from ...version import get_version
from .qt_compat import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QMenuBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QDesktopServices,
    QIcon,
    QUrl,
    Qt,
)

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
        usdpreview_resolution (int): Size of USD Preview textures (pixels).
        texture_format_overrides (Dict[str, str]): Optional per-renderer overrides.
        log_level (str): Logging verbosity.
    """

    usdpreview: bool
    arnold: bool
    materialx: bool
    save_geometry: bool
    openpbr: bool
    usdpreview_resolution: int
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
        self.setMinimumSize(320, 240)
        self._plugin_version = get_version()

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(6)
        self.setLayout(root_layout)

        menu_bar = QMenuBar()
        menu_bar.setNativeMenuBar(False)
        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction("Help", self._show_help)
        help_menu.addAction("User Guide", self._open_docs)
        help_menu.addAction("About", self._show_about)
        advanced_menu = menu_bar.addMenu("Advanced")
        log_menu = advanced_menu.addMenu("Log Level")
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
        content_layout.setSpacing(10)
        content_layout.setAlignment(Qt.AlignTop)
        content.setLayout(content_layout)
        scroll_area.setWidget(content)

        engine_box = QGroupBox("Render Engines")
        engine_box.setFlat(True)
        engine_box.setStyleSheet(
            "QCheckBox:checked { font-weight: 600; color: #2b4a5f; }"
        )
        engine_layout = QVBoxLayout()
        engine_layout.setContentsMargins(8, 4, 8, 6)
        engine_layout.setSpacing(4)
        self.usdpreview = QCheckBox("USD Preview")
        self.usdpreview.setChecked(DEFAULT_DIALOGUE_DICT["enable_usdpreview"])
        self.arnold = QCheckBox("Arnold")
        self.arnold.setChecked(DEFAULT_DIALOGUE_DICT["enable_arnold"])
        self.materialx = QCheckBox("MaterialX (Standard Surface)")
        self.materialx.setChecked(DEFAULT_DIALOGUE_DICT["enable_materialx"])
        self.openpbr = QCheckBox("OpenPBR (MaterialX)")
        self.openpbr.setChecked(DEFAULT_DIALOGUE_DICT["enable_openpbr"])
        engine_layout.addWidget(self.usdpreview)
        engine_layout.addWidget(self.materialx)
        engine_layout.addWidget(self.openpbr)
        engine_layout.addWidget(self.arnold)
        engine_help = QLabel("You can enable multiple engines at once.")
        engine_help.setWordWrap(True)
        engine_help.setStyleSheet("color: #666;")
        engine_layout.addWidget(engine_help)
        engine_box.setLayout(engine_layout)
        engine_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        content_layout.addWidget(engine_box)

        options_box = QGroupBox("Export Options")
        options_box.setFlat(True)
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(8, 4, 8, 6)
        options_layout.setSpacing(4)
        self.geom = QCheckBox("Include Mesh in USD")
        self.geom.setToolTip("Exports mesh geometry to USD if supported")
        self.geom.setChecked(DEFAULT_DIALOGUE_DICT["enable_save_geometry"])
        options_layout.addWidget(self.geom)

        usdpreview_header = QLabel("USD Preview Options")
        usdpreview_header.setStyleSheet("color: #555; font-weight: 600;")
        options_layout.addSpacing(4)
        options_layout.addWidget(usdpreview_header)

        usdpreview_form = QFormLayout()
        usdpreview_form.setContentsMargins(0, 0, 0, 0)
        usdpreview_form.setSpacing(4)
        usdpreview_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.override_usdpreview = QComboBox()
        self.override_usdpreview.addItems(["auto", "jpeg", "png"])
        self.override_usdpreview.setToolTip(
            "Override USD Preview texture format (e.g., jpg)"
        )
        usdpreview_form.addRow("USD Preview Override", self.override_usdpreview)

        self.usdpreview_resolution = QComboBox()
        self.usdpreview_resolution.addItems(["128", "256", "512", "1024"])
        self.usdpreview_resolution.setCurrentText("128")
        self.usdpreview_resolution.setToolTip(
            "Resolution for USD Preview textures (max 1024)"
        )
        usdpreview_form.addRow(
            "USD Preview Resolution", self.usdpreview_resolution
        )
        options_layout.addLayout(usdpreview_form)

        self.preview_hint = QLabel(
            "Preview textures will be exported to previewTextures/"
        )
        self.preview_hint.setWordWrap(True)
        self.preview_hint.setStyleSheet("color: #666;")
        options_layout.addWidget(self.preview_hint)

        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        self.reset_export_btn = QPushButton("Reset to Defaults")
        self.reset_export_btn.setToolTip("Reset export options to defaults")
        self.reset_export_btn.clicked.connect(self._reset_export_options)
        reset_row.addWidget(self.reset_export_btn, 0)
        options_layout.addLayout(reset_row)

        options_box.setLayout(options_layout)
        options_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        content_layout.addWidget(options_box)

        self.override_usdpreview.setEnabled(self.usdpreview.isChecked())
        self.usdpreview_resolution.setEnabled(self.usdpreview.isChecked())
        self.preview_hint.setVisible(self.usdpreview.isChecked())
        self.usdpreview.toggled.connect(self.override_usdpreview.setEnabled)
        self.usdpreview.toggled.connect(self.usdpreview_resolution.setEnabled)
        self.usdpreview.toggled.connect(self.preview_hint.setVisible)

    def _set_log_level(self, name: str) -> None:
        if name not in LOG_LEVELS:
            return
        self._log_level_name = name
        for level_name, action in self._log_level_actions.items():
            action.setChecked(level_name == name)

    def _reset_export_options(self) -> None:
        self.geom.setChecked(DEFAULT_DIALOGUE_DICT["enable_save_geometry"])
        self.override_usdpreview.setCurrentText("auto")
        self.usdpreview_resolution.setCurrentText("128")

    def _show_help(self) -> None:
        """Show a short help dialog."""
        message = (
            "Export textures first, then the plugin writes USD next to the export folder."
        )
        QMessageBox.information(self, "Axe USD Exporter Help", message)

    def _open_docs(self) -> None:
        """Open the local user guide if available."""
        repo_root = Path(__file__).resolve().parents[4]
        docs_path = repo_root / "docs" / "USER_GUIDE.md"
        if not docs_path.exists():
            docs_path = repo_root / "docs" / "index.md"
        if docs_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs_path)))
        else:
            QMessageBox.information(
                self,
                "Docs Not Found",
                "Local documentation was not found in this install.",
            )

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
            int(self.usdpreview_resolution.currentText()),
            self._collect_overrides(),
            self._log_level_name,
        )

    def _collect_overrides(self) -> Dict[str, str]:
        overrides: Dict[str, str] = {}
        usd_preview = self.override_usdpreview.currentText().strip().lower()
        if usd_preview and usd_preview != "auto":
            overrides["usd_preview"] = usd_preview
        return overrides
