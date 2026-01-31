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

    def __init__(self, parent=None, logger: Optional[logging.Logger] = None) -> None:
        """Build the export settings UI.

        Args:
            parent: Optional parent widget.
            logger: Optional logger to use for UI-related messages.
        """
        super().__init__(parent)
        self._logger = logger or logging.getLogger(__name__)
        self._plugin_version = get_version()
        self._log_level_actions = {}
        self._log_level_name = "Debug"

        self._setup_window()
        self._build_ui()

    def _setup_window(self):
        self.setWindowTitle("USD Exporter")
        self.setWindowIcon(QIcon())
        self.setMinimumSize(360, 480)

    def _build_ui(self):
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(15, 15, 15, 15)
        root_layout.setSpacing(10)
        self.setLayout(root_layout)

        self._build_menu(root_layout)
        self._build_header(root_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        root_layout.addWidget(scroll_area, 1)

        content = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(10, 5, 15, 5)
        self.content_layout.setSpacing(15)
        self.content_layout.setAlignment(Qt.AlignTop)
        content.setLayout(self.content_layout)
        scroll_area.setWidget(content)

        self._build_engine_group()
        self._build_options_group()
        self._build_footer()

    def _build_menu(self, root_layout: QVBoxLayout):
        menu_bar = QMenuBar()
        menu_bar.setNativeMenuBar(False)

        # Help Menu
        help_menu = menu_bar.addMenu("Help")
        help_menu.addAction("Help", self._show_help)
        help_menu.addAction("User Guide", self._open_docs)
        help_menu.addAction("About", self._show_about)

        # Advanced Menu
        advanced_menu = menu_bar.addMenu("Advanced")
        log_menu = advanced_menu.addMenu("Log Level")

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

    def _build_header(self, root_layout: QVBoxLayout):
        header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 10)

        title = QLabel("Axe USD Exporter")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)

        header_layout.addWidget(title)
        header_layout.addStretch()

        version_label = QLabel(f"v{self._plugin_version}")
        header_layout.addWidget(version_label)

        header.setLayout(header_layout)
        root_layout.addWidget(header)

    def _build_engine_group(self):
        engine_box = QGroupBox("Render Engines")
        engine_layout = QVBoxLayout()
        engine_layout.setContentsMargins(15, 20, 15, 15)
        engine_layout.setSpacing(8)

        self.usdpreview = QCheckBox("USD Preview Surface")
        self.usdpreview.setChecked(DEFAULT_DIALOGUE_DICT["enable_usdpreview"])
        self.usdpreview.setToolTip("Standard USD lighting model")

        self.materialx = QCheckBox("MaterialX (Standard Surface)")
        self.materialx.setChecked(DEFAULT_DIALOGUE_DICT["enable_materialx"])

        self.openpbr = QCheckBox("OpenPBR (MaterialX)")
        self.openpbr.setChecked(DEFAULT_DIALOGUE_DICT["enable_openpbr"])

        self.arnold = QCheckBox("Arnold Standard Surface")
        self.arnold.setChecked(DEFAULT_DIALOGUE_DICT["enable_arnold"])

        engine_layout.addWidget(self.usdpreview)
        engine_layout.addWidget(self.materialx)
        engine_layout.addWidget(self.openpbr)
        engine_layout.addWidget(self.arnold)

        help_label = QLabel("Select target renderers for material export.")
        help_label.setWordWrap(True)
        engine_layout.addWidget(help_label)

        engine_box.setLayout(engine_layout)
        self.content_layout.addWidget(engine_box)

    def _build_options_group(self):
        options_box = QGroupBox("Export Options")
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(15, 20, 15, 15)
        options_layout.setSpacing(12)

        # Geometry
        self.geom = QCheckBox("Include Mesh Geometry")
        self.geom.setToolTip("Export the mesh along with materials")
        self.geom.setChecked(DEFAULT_DIALOGUE_DICT["enable_save_geometry"])
        options_layout.addWidget(self.geom)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        options_layout.addWidget(line)

        # USD Preview Options
        preview_grid = QFormLayout()
        preview_grid.setContentsMargins(0, 5, 0, 5)
        preview_grid.setSpacing(8)
        preview_grid.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.override_usdpreview = QComboBox()
        self.override_usdpreview.addItems(["Auto (Match Source)", "JPEG", "PNG"])
        self.override_usdpreview.setItemData(0, "auto")
        self.override_usdpreview.setItemData(1, "jpeg")
        self.override_usdpreview.setItemData(2, "png")
        self.override_usdpreview.setToolTip(
            "Force a specific format for preview textures"
        )

        self.usdpreview_resolution = QComboBox()
        valid_res = ["128", "256", "512", "1024", "2048", "4096"]
        self.usdpreview_resolution.addItems(valid_res)
        self.usdpreview_resolution.setCurrentText("128")
        self.usdpreview_resolution.setToolTip(
            "Max resolution for baked preview textures"
        )

        preview_grid.addRow("Texture Format:", self.override_usdpreview)
        preview_grid.addRow("Max Resolution:", self.usdpreview_resolution)
        options_layout.addLayout(preview_grid)

        self.preview_hint = QLabel("Baked textures are saved to /previewTextures")
        self.preview_hint.setWordWrap(True)
        options_layout.addWidget(self.preview_hint)

        options_box.setLayout(options_layout)
        self.content_layout.addWidget(options_box)

        # Connect signals
        self.usdpreview.toggled.connect(self.override_usdpreview.setEnabled)
        self.usdpreview.toggled.connect(self.usdpreview_resolution.setEnabled)
        self.usdpreview.toggled.connect(self.preview_hint.setVisible)

        # Initial state
        state = self.usdpreview.isChecked()
        self.override_usdpreview.setEnabled(state)
        self.usdpreview_resolution.setEnabled(state)
        self.preview_hint.setVisible(state)

    def _build_footer(self):
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 10, 0, 0)

        self.reset_export_btn = QPushButton("Reset Defaults")
        self.reset_export_btn.setToolTip("Reset all settings to default values")
        self.reset_export_btn.clicked.connect(self._reset_export_options)
        self.reset_export_btn.setFixedWidth(120)

        footer_layout.addStretch()
        footer_layout.addWidget(self.reset_export_btn)

        self.layout().addLayout(footer_layout)

    def _set_log_level(self, name: str) -> None:
        if name not in LOG_LEVELS:
            return
        self._log_level_name = name
        for level_name, action in self._log_level_actions.items():
            action.setChecked(level_name == name)

    def _reset_export_options(self) -> None:
        self.geom.setChecked(DEFAULT_DIALOGUE_DICT["enable_save_geometry"])
        self.usdpreview.setChecked(DEFAULT_DIALOGUE_DICT["enable_usdpreview"])
        self.arnold.setChecked(DEFAULT_DIALOGUE_DICT["enable_arnold"])
        self.materialx.setChecked(DEFAULT_DIALOGUE_DICT["enable_materialx"])
        self.openpbr.setChecked(DEFAULT_DIALOGUE_DICT["enable_openpbr"])

        self.override_usdpreview.setCurrentIndex(0)  # auto
        self.usdpreview_resolution.setCurrentText("128")

    def _show_help(self) -> None:
        """Show a short help dialog."""
        message = (
            "<h3>Usage Guide</h3>"
            "<p>1. Configure export settings in this window.</p>"
            "<p>2. Run the Substance Painter export process.</p>"
            "<p>3. The plugin will automatically generate USD files in the export directory.</p>"
        )
        QMessageBox.information(self, "Axe USD Exporter Help", message)

    def _open_docs(self) -> None:
        """Open the local user guide if available."""
        repo_root = Path(__file__).resolve().parents[4]
        docs_path = repo_root / "docs" / "user_guide.rst"
        if not docs_path.exists():
            docs_path = repo_root / "docs" / "index.rst"
        if docs_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs_path)))
        else:
            QMessageBox.warning(
                self,
                "Docs Not Found",
                "Local documentation was not found in this install.",
            )

    def _show_about(self) -> None:
        """Show an about dialog with version details."""
        message = (
            f"<h3>Axe USD Exporter</h3>"
            f"<p>Version: <b>{self._plugin_version}</b></p>"
            "<p>Exports Substance Painter textures to USD with support for:</p>"
            "<ul>"
            "<li>UsdPreviewSurface</li>"
            "<li>Arnold Standard Surface</li>"
            "<li>MaterialX</li>"
            "</ul>"
        )
        QMessageBox.information(self, "About Axe USD Exporter", message)

    def get_settings(self) -> USDSettings:
        """
        Read UI state into USDSettings.

        Returns:
            USDSettings: Settings collected from the dialog.
        """
        # Handle the combobox data for override format
        format_override = self.override_usdpreview.currentData()
        overrides = {}
        if format_override and format_override != "auto":
            overrides["usd_preview"] = format_override

        return USDSettings(
            self.usdpreview.isChecked(),
            self.arnold.isChecked(),
            self.materialx.isChecked(),
            self.geom.isChecked(),
            self.openpbr.isChecked(),
            int(self.usdpreview_resolution.currentText()),
            overrides,
            self._log_level_name,
        )
