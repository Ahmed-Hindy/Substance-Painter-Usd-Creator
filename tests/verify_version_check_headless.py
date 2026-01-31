import sys
import os
from unittest.mock import MagicMock

# Mock modules
mock_sp = MagicMock()
mock_sp.application = MagicMock()
mock_sp.ui = MagicMock()
mock_sp.event = MagicMock()
mock_sp.export = MagicMock()

sys.modules["substance_painter"] = mock_sp
sys.modules["substance_painter.application"] = mock_sp.application
sys.modules["substance_painter.ui"] = mock_sp.ui
sys.modules["substance_painter.event"] = mock_sp.event
sys.modules["substance_painter.export"] = mock_sp.export

# Set default version to > 10.1.0 so qt_compat loads PySide6 (which we have)
mock_sp.application.version_info.return_value = (11, 0, 0)

# Ensure src is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "..", "src")
sys.path.insert(0, src_path)

# Import after mocking
from axe_usd.dcc.substance_painter import substance_plugin


def test_version_check():
    print("Testing Version Check...")

    # Test case 1: Unsupported version (8.0.0)
    print("  Testing unsupported version (8.0.0)...")
    mock_sp.application.version_info.return_value = (8, 0, 0)
    mock_sp.ui.add_dock_widget.reset_mock()

    substance_plugin.start_plugin()

    if mock_sp.ui.add_dock_widget.called:
        print("FAIL: Plugin started on unsupported version!")
        sys.exit(1)
    else:
        print("PASS: Plugin prevented startup on unsupported version.")

    # Test case 2: Supported version (9.0.0)
    print("  Testing supported version (9.0.0)...")
    mock_sp.application.version_info.return_value = (9, 0, 0)
    mock_sp.ui.add_dock_widget.reset_mock()
    # Mock USDExporterView to avoid instantiation issues during this test if needed,
    # but since we mocked imports, it might try to instanciate real class which imports qt_compat.
    # The real class imports qt_compat which we mocked partially?
    # Actually, substance_plugin imports UI.
    # Let's mock the UI class itself to be safe and avoid Qt dependency here.
    original_ui_class = substance_plugin.USDExporterView
    substance_plugin.USDExporterView = MagicMock()

    substance_plugin.start_plugin()

    if not mock_sp.ui.add_dock_widget.called:
        print("FAIL: Plugin did not start on supported version!")
        sys.exit(1)
    else:
        print("PASS: Plugin started on supported version.")

    print("All version checks passed.")


if __name__ == "__main__":
    test_version_check()
