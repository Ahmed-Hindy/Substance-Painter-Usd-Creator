from pathlib import Path
from typing import Optional
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
PACKAGE_SRC = ROOT / "src" / "axe_usd"
PLUGIN_SRC = ROOT / "packaging" / "axe_usd_plugin"
TEMP_DIR = ROOT / ".temp"

USD_DEPENDENCIES = {
    "39": ("24.5", "py39_usd24_5"),
    "310": ("24.5", "py310_usd24_5"),
    "311": ("25.5.1", "py311_usd25_5_1"),
}
USD_WHEEL_PLATFORM = "win_amd64"

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


def _format_python_version(py_ver: str) -> str:
    if not py_ver.isdigit() or len(py_ver) < 2:
        raise SystemExit(f"Invalid Python version tag: {py_ver}")
    return f"{py_ver[0]}.{py_ver[1:]}"


def _pip_available() -> bool:
    try:
        import pip  # noqa: F401
    except Exception:
        return False
    return True


def _download_usd_wheel_from_pypi(py_ver: str, usd_version: str, wheel_dir: Path) -> Path:
    wheel_tag = f"cp{py_ver}-none-{USD_WHEEL_PLATFORM}.whl"
    index_url = f"https://pypi.org/pypi/usd-core/{usd_version}/json"
    try:
        with urllib.request.urlopen(index_url, timeout=60) as response:
            payload = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Failed to query PyPI for usd-core {usd_version}: {exc}") from exc

    if "urls" in payload:
        files = payload.get("urls", [])
    else:
        releases = payload.get("releases", {})
        files = releases.get(usd_version, [])
    for file_info in files:
        filename = file_info.get("filename", "")
        if filename.endswith(wheel_tag):
            url = file_info.get("url")
            if not url:
                continue
            wheel_path = wheel_dir / filename
            if wheel_path.exists():
                return wheel_path
            tmp_path = wheel_path.with_suffix(".tmp")
            try:
                with urllib.request.urlopen(url, timeout=120) as response, open(tmp_path, "wb") as handle:
                    shutil.copyfileobj(response, handle)
            except urllib.error.URLError as exc:
                raise SystemExit(f"Failed to download {filename}: {exc}") from exc
            tmp_path.replace(wheel_path)
            return wheel_path

    raise SystemExit(
        f"USD wheel not found on PyPI for Python {py_ver} (USD {usd_version})."
    )


def _download_usd_wheel(py_ver: str, usd_version: str, wheel_dir: Path) -> Path:
    wheel_dir.mkdir(parents=True, exist_ok=True)
    wheel_name = f"usd_core-{usd_version}-cp{py_ver}-none-{USD_WHEEL_PLATFORM}.whl"
    wheel_path = wheel_dir / wheel_name
    if wheel_path.exists():
        return wheel_path

    if _pip_available():
        python_version = _format_python_version(py_ver)
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--only-binary=:all:",
            "--no-deps",
            "--platform",
            USD_WHEEL_PLATFORM,
            "--python-version",
            python_version,
            "--implementation",
            "cp",
            "--abi",
            f"cp{py_ver}",
            "--dest",
            str(wheel_dir),
            f"usd-core=={usd_version}",
        ]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as exc:
            print(f"pip download failed; falling back to PyPI fetch: {exc}")

    if wheel_path.exists():
        return wheel_path

    matches = list(wheel_dir.glob(f"usd_core-{usd_version}-cp{py_ver}-none-{USD_WHEEL_PLATFORM}.whl"))
    if matches:
        return matches[0]

    return _download_usd_wheel_from_pypi(py_ver, usd_version, wheel_dir)


def _extract_usd_pxr(wheel_path: Path, dest_dir: Path, temp_root: Path) -> None:
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    extract_dir = temp_root / wheel_path.stem
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(wheel_path, "r") as zf:
        zf.extractall(extract_dir)

    pxr_src = extract_dir / "pxr"
    if not pxr_src.exists():
        raise SystemExit(f"pxr package not found in wheel: {wheel_path}")

    shutil.copytree(pxr_src, dest_dir)

    license_files = list(extract_dir.glob("*.dist-info/LICENSE*"))
    if license_files:
        shutil.copy(license_files[0], dest_dir.parent / "LICENSE.txt")


def _populate_usd_dependencies(plugin_dist: Path) -> None:
    if os.environ.get("AXEUSD_SKIP_USD_DOWNLOAD"):
        print("Skipping USD dependency download (AXEUSD_SKIP_USD_DOWNLOAD=1).")
        return

    deps_root = plugin_dist / "dependencies"
    deps_root.mkdir(parents=True, exist_ok=True)

    wheel_dir = TEMP_DIR / "usd_wheels"
    extract_root = TEMP_DIR / "usd_extract"
    extract_root.mkdir(parents=True, exist_ok=True)

    for py_ver, (usd_version, folder_name) in USD_DEPENDENCIES.items():
        wheel_path = _download_usd_wheel(py_ver, usd_version, wheel_dir)
        dest_dir = deps_root / folder_name / "pxr"
        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        _extract_usd_pxr(wheel_path, dest_dir, extract_root)


def _zip_plugin(plugin_dist: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in plugin_dist.rglob("*"):
            if file_path.is_dir():
                continue
            arcname = file_path.relative_to(plugin_dist.parent)
            zf.write(file_path, arcname)


if DIST_DIR.exists():
    shutil.rmtree(DIST_DIR)

DIST_DIR.mkdir(parents=True, exist_ok=True)

plugin_dist = DIST_DIR / "axe_usd_plugin"
shutil.copytree(
    PLUGIN_SRC,
    plugin_dist,
    ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".ruff_cache", ".pytest_cache"
    ),
)
shutil.copytree(
    PACKAGE_SRC,
    plugin_dist / "axe_usd",
    ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".ruff_cache", ".pytest_cache"
    ),
)

_populate_usd_dependencies(plugin_dist)

version = _read_project_version()
if version:
    version_path = plugin_dist / "axe_usd" / "_version.py"
    version_path.write_text(f'__version__ = "{version}"\n', encoding="utf-8")

zip_path = DIST_DIR / "axe_usd_plugin.zip"
_zip_plugin(plugin_dist, zip_path)

print(f"Built plugin bundle at: {DIST_DIR}")
print(f"Packaged release zip at: {zip_path}")
