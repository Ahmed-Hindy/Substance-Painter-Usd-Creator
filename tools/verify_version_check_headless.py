"""Headless verification script for the Substance Painter version gate."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _build_substance_painter_stub() -> SimpleNamespace:
    application = SimpleNamespace(version=(11, 0, 0))
    application.version_info = lambda: application.version

    ui = SimpleNamespace(add_dock_widget=MagicMock())
    event = MagicMock()
    export = MagicMock()

    mock_sp = SimpleNamespace(
        application=application,
        ui=ui,
        event=event,
        export=export,
    )
    sys.modules["substance_painter"] = mock_sp
    sys.modules["substance_painter.application"] = application
    sys.modules["substance_painter.ui"] = ui
    sys.modules["substance_painter.event"] = event
    sys.modules["substance_painter.export"] = export
    return mock_sp


def main() -> int:
    mock_sp = _build_substance_painter_stub()
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))

    from axe_usd.dcc.substance_painter import substance_plugin

    print("Testing Version Check...")

    print("  Testing unsupported version (8.0.0)...")
    mock_sp.application.version = (8, 0, 0)
    mock_sp.ui.add_dock_widget.reset_mock()
    substance_plugin.start_plugin()
    if mock_sp.ui.add_dock_widget.called:
        print("FAIL: Plugin started on unsupported version!")
        return 1
    print("PASS: Plugin prevented startup on unsupported version.")

    print("  Testing supported version (9.0.0)...")
    mock_sp.application.version = (9, 0, 0)
    mock_sp.ui.add_dock_widget.reset_mock()
    original_ui_class = substance_plugin.USDExporterView
    substance_plugin.USDExporterView = MagicMock()
    try:
        substance_plugin.start_plugin()
    finally:
        substance_plugin.USDExporterView = original_ui_class

    if not mock_sp.ui.add_dock_widget.called:
        print("FAIL: Plugin did not start on supported version!")
        return 1

    print("PASS: Plugin started on supported version.")
    print("All version checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
