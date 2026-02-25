import sys
import types


def _install_qt_stub() -> None:
    if "axe_usd.dcc.substance_painter.qt_compat" in sys.modules:
        return

    qt_stub = types.ModuleType("axe_usd.dcc.substance_painter.qt_compat")

    def _stub_class(name: str):
        return type(name, (), {})

    qt_stub.Qt = types.SimpleNamespace(AlignTop=0, AlignLeft=0, AlignVCenter=0)
    for name in (
        "QCheckBox",
        "QComboBox",
        "QDialog",
        "QFormLayout",
        "QFrame",
        "QGroupBox",
        "QHBoxLayout",
        "QLabel",
        "QMessageBox",
        "QMenuBar",
        "QPushButton",
        "QScrollArea",
        "QVBoxLayout",
        "QWidget",
        "QDesktopServices",
        "QIcon",
        "QUrl",
    ):
        setattr(qt_stub, name, _stub_class(name))

    sys.modules["axe_usd.dcc.substance_painter.qt_compat"] = qt_stub


def _install_sp_stub() -> None:
    if "substance_painter" in sys.modules:
        return

    sp_stub = types.ModuleType("substance_painter")
    sp_stub.application = types.ModuleType("substance_painter.application")
    sp_stub.event = types.ModuleType("substance_painter.event")
    sp_stub.export = types.ModuleType("substance_painter.export")
    sp_stub.textureset = types.ModuleType("substance_painter.textureset")
    sp_stub.ui = types.ModuleType("substance_painter.ui")

    sys.modules["substance_painter"] = sp_stub
    sys.modules["substance_painter.application"] = sp_stub.application
    sys.modules["substance_painter.event"] = sp_stub.event
    sys.modules["substance_painter.export"] = sp_stub.export
    sys.modules["substance_painter.textureset"] = sp_stub.textureset
    sys.modules["substance_painter.ui"] = sp_stub.ui


class _FakeCheck:
    def __init__(self, value: bool) -> None:
        self._value = value

    def isChecked(self) -> bool:
        return self._value


class _FakeCombo:
    def __init__(self, data: object, text: str) -> None:
        self._data = data
        self._text = text

    def currentData(self):
        return self._data

    def currentText(self) -> str:
        return self._text


def test_arnold_displacement_toggle_maps_to_export_settings():
    _install_qt_stub()
    _install_sp_stub()

    from axe_usd.dcc.substance_painter import substance_plugin, ui

    fake_view = types.SimpleNamespace(
        override_usdpreview=_FakeCombo(".jpg", ".jpg"),
        usdpreview=_FakeCheck(True),
        arnold=_FakeCheck(True),
        arnold_displacement=_FakeCheck(True),
        materialx=_FakeCheck(True),
        geom=_FakeCheck(True),
        openpbr=_FakeCheck(False),
        usdpreview_resolution=_FakeCombo(None, "128"),
        _log_level_name="Debug",
    )

    settings = ui.USDExporterView.get_settings(fake_view)
    assert settings.arnold_displacement_mode == "displacement"

    export_settings = substance_plugin._build_export_settings(
        settings,
        primitive_path="/Asset",
        publish_dir="C:/tmp",
        save_geometry=True,
        texture_overrides=settings.texture_format_overrides,
    )
    assert export_settings.arnold_displacement_mode == "displacement"
