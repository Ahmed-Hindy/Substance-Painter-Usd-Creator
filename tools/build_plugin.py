from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
PACKAGE_SRC = ROOT / "src" / "axe_usd"
WRAPPER_SRC = ROOT / "packaging" / "axe_usd_plugin.py"
VERSION_SRC = ROOT / "VERSION"

if not PACKAGE_SRC.exists():
    raise SystemExit(f"Package not found: {PACKAGE_SRC}")
if not WRAPPER_SRC.exists():
    raise SystemExit(f"Wrapper not found: {WRAPPER_SRC}")

if DIST_DIR.exists():
    shutil.rmtree(DIST_DIR)

DIST_DIR.mkdir(parents=True, exist_ok=True)

shutil.copy2(WRAPPER_SRC, DIST_DIR / "axe_usd_plugin.py")
shutil.copytree(
    PACKAGE_SRC,
    DIST_DIR / "axe_usd",
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".ruff_cache", ".pytest_cache"),
)

if VERSION_SRC.exists():
    shutil.copy2(VERSION_SRC, DIST_DIR / "VERSION")

print(f"Built plugin bundle at: {DIST_DIR}")
