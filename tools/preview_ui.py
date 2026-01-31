from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType


def _install_sp_stub() -> None:
    if "substance_painter" in sys.modules:
        return
    sp_module = ModuleType("substance_painter")
    app_module = ModuleType("substance_painter.application")

    def version_info() -> tuple[int, int, int]:
        return (10, 1, 0)

    app_module.version_info = version_info
    sp_module.application = app_module
    sys.modules["substance_painter"] = sp_module
    sys.modules["substance_painter.application"] = app_module


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))
    _install_sp_stub()

    from axe_usd.dcc.substance_painter.qt_compat import QApplication
    from axe_usd.dcc.substance_painter.ui import USDExporterView

    app = QApplication(sys.argv)
    view = USDExporterView()
    view.show()
    if hasattr(app, "exec"):
        return int(app.exec())
    return int(app.exec_())


if __name__ == "__main__":
    raise SystemExit(main())
