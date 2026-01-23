from pathlib import Path
from typing import Optional
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
PACKAGE_SRC = ROOT / "src" / "axe_usd"
PLUGIN_SRC = ROOT / "packaging" / "axe_usd_plugin"

if not PACKAGE_SRC.exists():
    raise SystemExit(f"Package not found: {PACKAGE_SRC}")
if not PLUGIN_SRC.exists():
    raise SystemExit(f"Plugin template not found: {PLUGIN_SRC}")


def _read_project_version() -> Optional[str]:
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        content = pyproject.read_text(encoding="utf-8")
    except Exception:
        return None

    in_project = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project or not stripped.startswith("version"):
            continue
        match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
        if match:
            return match.group(1)
    return None


if DIST_DIR.exists():
    shutil.rmtree(DIST_DIR)

DIST_DIR.mkdir(parents=True, exist_ok=True)

plugin_dist = DIST_DIR / "axe_usd_plugin"
shutil.copytree(
    PLUGIN_SRC,
    plugin_dist,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".ruff_cache", ".pytest_cache"),
)
shutil.copytree(
    PACKAGE_SRC,
    plugin_dist / "axe_usd",
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".ruff_cache", ".pytest_cache"),
)

version = _read_project_version()
if version:
    version_path = plugin_dist / "axe_usd" / "_version.py"
    version_path.write_text(f'__version__ = "{version}"\n', encoding="utf-8")

print(f"Built plugin bundle at: {DIST_DIR}")
