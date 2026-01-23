from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
PACKAGE_SRC = ROOT / "src" / "axe_usd"
PLUGIN_SRC = ROOT / "packaging" / "axe_usd_plugin"

if not PACKAGE_SRC.exists():
    raise SystemExit(f"Package not found: {PACKAGE_SRC}")
if not PLUGIN_SRC.exists():
    raise SystemExit(f"Plugin template not found: {PLUGIN_SRC}")

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

print(f"Built plugin bundle at: {DIST_DIR}")
