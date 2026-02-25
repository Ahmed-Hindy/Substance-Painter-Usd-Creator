from pathlib import Path
import sys
import types

import pytest

from axe_usd.core.exceptions import ValidationError


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


@pytest.mark.parametrize(
    ("resolution", "expected_log2"),
    [
        (128, 7),
        (256, 8),
        (512, 9),
        (1024, 10),
        (2048, 11),
        (4096, 12),
    ],
)
def test_build_preview_export_config_supports_all_ui_resolutions(
    resolution: int, expected_log2: int
) -> None:
    _install_qt_stub()
    _install_sp_stub()
    from axe_usd.dcc.substance_painter import substance_plugin

    config = substance_plugin._build_preview_export_config(
        preview_dir=Path("C:/tmp/preview"),
        texture_sets=("Body",),
        resolution=resolution,
    )

    parameters = config["exportPresets"][0]["maps"][0]["parameters"]
    assert parameters["sizeLog2"] == expected_log2


def test_build_preview_export_config_rejects_unsupported_resolution() -> None:
    _install_qt_stub()
    _install_sp_stub()
    from axe_usd.dcc.substance_painter import substance_plugin

    with pytest.raises(ValidationError) as exc_info:
        substance_plugin._build_preview_export_config(
            preview_dir=Path("C:/tmp/preview"),
            texture_sets=("Body",),
            resolution=300,
        )

    assert exc_info.value.details["resolution"] == 300
    assert exc_info.value.details["supported_resolutions"] == [
        128,
        256,
        512,
        1024,
        2048,
        4096,
    ]
