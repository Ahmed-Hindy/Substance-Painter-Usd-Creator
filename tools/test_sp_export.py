"""Quick USD test harness for SP exports.

Takes a Substance Painter geo.usd/usdc export, runs the mesh fixup, and writes
a component-style USD asset into a temp output directory.
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import tempfile
from pathlib import Path

import OpenImageIO as oiio
from pxr import Usd, UsdGeom


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axe_usd.core.texture_parser import parse_textures  # noqa: E402
from axe_usd.core.texture_keys import slot_from_path  # noqa: E402
from axe_usd.dcc.substance_painter import usd_scene_fixup  # noqa: E402
from axe_usd.usd.asset_files import create_asset_file_structure  # noqa: E402
from axe_usd.usd.material_builders import (  # noqa: E402
    PREVIEW_TEXTURE_DIRNAME,
    PREVIEW_TEXTURE_SUFFIX,
)
from axe_usd.usd.material_processor import create_shaded_asset_publish  # noqa: E402


logger = logging.getLogger("axe_usd_test")
logging.basicConfig(level=logging.INFO, format="[AxeUSDTest] %(message)s")
DEFAULT_PREVIEW_TEXTURE_SIZE = 64


def _copy_textures(src_dir: Path, dest_dir: Path) -> list[Path]:
    copied: list[Path] = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    for path in src_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".usd", ".usdc", ".usda"}:
            continue
        if "previewTextures" in path.parts:
            continue
        dest = dest_dir / path.name
        if dest.exists():
            continue
        shutil.copy2(path, dest)
        copied.append(dest)
    return copied


def _build_material_dict_list(
    textures: list[Path], material_name: str
) -> list[dict[str, dict[str, str]]]:
    material_dict: dict[str, dict[str, str]] = {}
    for path in textures:
        slot = slot_from_path(path.name)
        if not slot:
            continue
        material_dict[slot] = {"mat_name": material_name, "path": str(path)}
    return [material_dict] if material_dict else []


def _collect_mesh_tokens(stage: Usd.Stage) -> list[str]:
    tokens: list[str] = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        name = prim.GetName()
        if name and name not in tokens:
            tokens.append(name)
        lower = name.lower()
        if lower.startswith("mesh_"):
            suffix = name.split("_", 1)[1]
            if suffix and suffix not in tokens:
                tokens.append(suffix)
    return tokens


def _match_token(text: str, token: str) -> bool:
    pattern = rf"(^|[^a-z0-9]){re.escape(token.lower())}([^a-z0-9]|$)"
    return re.search(pattern, text) is not None


def _fallback_material_name(filename: str, slot: str | None) -> str:
    stem = Path(filename).stem
    parts = stem.split("_")
    if parts and slot and slot in parts[-1].lower():
        parts = parts[:-1]
    if len(parts) >= 2:
        return "_".join(parts[-2:])
    return "_".join(parts) if parts else stem


def _group_textures_by_material(
    textures: list[Path], mesh_tokens: list[str]
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for path in textures:
        stem = path.stem.lower()
        matches = [token for token in mesh_tokens if _match_token(stem, token)]
        if matches:
            material_name = max(matches, key=len)
        else:
            material_name = _fallback_material_name(
                path.name, slot_from_path(path.name)
            )
        grouped.setdefault(material_name, []).append(str(path))
    return grouped


def _build_material_dict_list_from_textures(
    textures: list[Path],
    mesh_tokens: list[str],
    material_name: str,
) -> list[dict[str, dict[str, str]]]:
    if material_name:
        return _build_material_dict_list(textures, material_name)
    grouped = _group_textures_by_material(textures, mesh_tokens)
    bundles = parse_textures(grouped)
    material_dict_list: list[dict[str, dict[str, str]]] = []
    for bundle in bundles:
        mat_dict: dict[str, dict[str, str]] = {}
        for slot, path in bundle.textures.items():
            mat_dict[slot] = {"mat_name": bundle.name, "path": path}
        if mat_dict:
            material_dict_list.append(mat_dict)
    return material_dict_list


def _write_preview_texture(
    basecolor_path: Path,
    textures_dir: Path,
    material_name: str,
    preview_size: int,
) -> Path:
    preview_dir = textures_dir / PREVIEW_TEXTURE_DIRNAME
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_name = f"{material_name}_BaseColor{PREVIEW_TEXTURE_SUFFIX}"
    preview_path = preview_dir / preview_name

    if preview_path.exists():
        return preview_path

    image_buf = oiio.ImageBuf(str(basecolor_path))
    if not image_buf.read():
        raise SystemExit(f"Failed to read texture: {basecolor_path}")

    spec = image_buf.spec()
    roi = oiio.ROI(0, preview_size, 0, preview_size, 0, 1, 0, spec.nchannels)
    resized = oiio.ImageBuf()
    if not oiio.ImageBufAlgo.resize(resized, image_buf, roi=roi):
        raise SystemExit(f"Failed to resize texture: {basecolor_path}")
    if not resized.write(str(preview_path)):
        raise SystemExit(f"Failed to write preview texture: {preview_path}")
    return preview_path


def _generate_preview_textures(
    material_dict_list: list[dict[str, dict[str, str]]],
    textures_dir: Path,
    preview_size: int,
) -> list[Path]:
    previews: list[Path] = []
    for material_dict in material_dict_list:
        base_info = material_dict.get("basecolor")
        if not base_info:
            logger.warning("No basecolor entry found; skipping preview texture export.")
            continue
        base_path = base_info.get("path")
        if not base_path:
            continue
        mat_name = base_info.get("mat_name", "")
        previews.append(
            _write_preview_texture(
                Path(base_path),
                textures_dir,
                mat_name,
                preview_size,
            )
        )
    return previews


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SP USD fixup and export tests.")
    parser.add_argument("--geo", required=True, help="Path to SP geo.usd/usdc")
    parser.add_argument(
        "--out",
        default="",
        help="Output directory for test results (defaults to temp dir).",
    )
    parser.add_argument(
        "--asset-name",
        default="Asset",
        help="Asset name to use in output structure.",
    )
    parser.add_argument(
        "--root-prim",
        default="",
        help="Target root prim path (defaults to /<asset-name>).",
    )
    parser.add_argument(
        "--textures",
        default="",
        help="Optional directory of textures to build materials from.",
    )
    parser.add_argument(
        "--material-name",
        default="",
        help="Material name to use when building materials (defaults to asset name).",
    )
    parser.add_argument("--usdpreview", action="store_true", default=True)
    parser.add_argument("--no-usdpreview", dest="usdpreview", action="store_false")
    parser.add_argument("--mtlx", action="store_true", default=True)
    parser.add_argument("--no-mtlx", dest="mtlx", action="store_false")
    parser.add_argument("--openpbr", action="store_true", default=False)
    parser.add_argument("--arnold", action="store_true", default=False)
    parser.add_argument(
        "--preview-size",
        type=int,
        default=DEFAULT_PREVIEW_TEXTURE_SIZE,
        help="Preview texture size in pixels (default: 64).",
    )

    args = parser.parse_args()

    geo_path = Path(args.geo)
    if not geo_path.exists():
        raise SystemExit(f"Geo file not found: {geo_path}")

    out_root = (
        Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="axe_usd_test_"))
    )
    asset_name = args.asset_name
    target_root = args.root_prim or f"/{asset_name}"
    material_name = args.material_name

    paths = create_asset_file_structure(out_root, asset_name)
    logger.info("Output directory: %s", paths.root_dir)

    stage = Usd.Stage.Open(str(geo_path))
    if not stage:
        raise SystemExit(f"Failed to open geo stage: {geo_path}")
    usd_scene_fixup.fix_sp_mesh_stage(stage, target_root)
    stage.GetRootLayer().Export(str(paths.geo_file))
    mesh_tokens = _collect_mesh_tokens(stage)
    if not mesh_tokens:
        logger.warning("No mesh tokens found for material grouping.")

    material_dict_list: list[dict[str, dict[str, str]]] = []
    if args.textures:
        textures_dir = Path(args.textures)
        copied = _copy_textures(textures_dir, paths.textures_dir)
        material_dict_list = _build_material_dict_list_from_textures(
            copied,
            mesh_tokens,
            material_name,
        )
        logger.info("Collected %d textures for materials.", len(copied))
        if args.usdpreview and material_dict_list:
            previews = _generate_preview_textures(
                material_dict_list,
                paths.textures_dir,
                args.preview_size,
            )
            logger.info("Generated %d preview textures.", len(previews))

    create_shaded_asset_publish(
        material_dict_list=material_dict_list,
        stage=None,
        geo_file=str(paths.geo_file),
        parent_path=target_root,
        layer_save_path=str(out_root),
        create_usd_preview=args.usdpreview,
        create_arnold=args.arnold,
        create_mtlx=args.mtlx,
        create_openpbr=args.openpbr,
    )

    logger.info("Wrote test asset to: %s", paths.root_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
