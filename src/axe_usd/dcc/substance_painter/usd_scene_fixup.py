"""USD fixups for Substance Painter exports."""

from __future__ import annotations

import logging
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom

logger = logging.getLogger(__name__)

SP_ROOT_PATH = Sdf.Path("/root")
SP_MATERIAL_PATH = SP_ROOT_PATH.AppendChild("material")

_ENV_LOGGED = False


def _debug_print(message: str, *args: object) -> None:
    formatted = message % args if args else message
    print(f"[AxeUSD] DEBUG: {formatted}")


def _log_usd_env_once() -> None:
    global _ENV_LOGGED
    if _ENV_LOGGED:
        return
    _ENV_LOGGED = True
    _debug_print("Usd module: %s", getattr(Usd, "__file__", "unknown"))
    _debug_print("Sdf module: %s", getattr(Sdf, "__file__", "unknown"))
    if hasattr(Usd, "GetVersionString"):
        _debug_print("Usd version string: %s", Usd.GetVersionString())
    if hasattr(Usd, "GetVersion"):
        _debug_print("Usd version: %s", Usd.GetVersion())
    _debug_print("Sdf has DeleteSpec: %s", hasattr(Sdf, "DeleteSpec"))
    _debug_print("Sdf has CopySpec: %s", hasattr(Sdf, "CopySpec"))


def _remove_prim(stage: Usd.Stage, path: Sdf.Path) -> None:
    path_str = path.pathString
    removed = stage.RemovePrim(path_str)
    still_valid = stage.GetPrimAtPath(path).IsValid()
    _debug_print(
        "Removed prim via stage.RemovePrim: %s (result=%s, still_valid=%s)",
        path_str,
        removed,
        still_valid,
    )


def fix_sp_mesh_stage(stage: Usd.Stage, target_root: str) -> bool:
    """Normalize a Substance Painter mesh stage for component layout.

    - Removes /root/material (and its children).
    - Moves all prims under /root to the target root prim.

    Args:
        stage: The opened USD stage to modify.
        target_root: Target root prim path (e.g. "/Asset").

    Returns:
        bool: True if changes were applied.
    """
    if not stage:
        logger.warning("No stage provided for SP mesh fixup.")
        return False

    _log_usd_env_once()

    target_path = Sdf.Path(target_root)
    if not (target_path.IsAbsolutePath() and target_path.IsPrimPath()):
        logger.warning("Invalid target root path: %s", target_root)
        return False

    root_prim = stage.GetPrimAtPath(SP_ROOT_PATH)
    if not root_prim or not root_prim.IsValid():
        logger.debug("No /root prim found; skipping SP mesh fixup.")
        return False

    layer = stage.GetRootLayer()
    _debug_print("Fixup layer: %s", layer.identifier)
    changed = False

    if stage.GetPrimAtPath(SP_MATERIAL_PATH).IsValid():
        _debug_print("Deleting prim: %s", SP_MATERIAL_PATH.pathString)
        _remove_prim(stage, SP_MATERIAL_PATH)
        changed = True
        _debug_print("Removed prim: %s", SP_MATERIAL_PATH.pathString)

    if not stage.GetPrimAtPath(target_path).IsValid():
        stage.DefinePrim(target_path.pathString)
        changed = True
        logger.debug("Created target root prim: %s", target_path.pathString)

    geo_path = target_path.AppendChild("geo")
    if not stage.GetPrimAtPath(geo_path).IsValid():
        UsdGeom.Scope.Define(stage, geo_path.pathString)
        changed = True
        _debug_print("Created geo scope: %s", geo_path.pathString)

    render_path = geo_path.AppendChild("render")
    if not stage.GetPrimAtPath(render_path).IsValid():
        UsdGeom.Scope.Define(stage, render_path.pathString)
        changed = True
        _debug_print("Created render scope: %s", render_path.pathString)

    children = list(root_prim.GetChildren())
    for child in children:
        if child.GetName() == "material":
            continue
        if child.GetName() in {"render", "proxy"}:
            continue
        dst_path = render_path.AppendChild(child.GetName())
        if stage.GetPrimAtPath(dst_path).IsValid():
            logger.warning("Target prim already exists: %s", dst_path.pathString)
            continue
        _debug_print("Copying prim %s -> %s", child.GetPath(), dst_path)
        Sdf.CopySpec(layer, child.GetPath(), layer, dst_path)
        _debug_print("Deleting prim: %s", child.GetPath())
        _remove_prim(stage, child.GetPath())
        changed = True
        _debug_print("Moved prim %s -> %s", child.GetPath(), dst_path)

    root_prim = stage.GetPrimAtPath(SP_ROOT_PATH)
    if root_prim and root_prim.IsValid() and not list(root_prim.GetChildren()):
        _debug_print("Deleting prim: %s", SP_ROOT_PATH.pathString)
        _remove_prim(stage, SP_ROOT_PATH)
        changed = True
        _debug_print("Removed empty prim: %s", SP_ROOT_PATH.pathString)

    return changed


def fix_sp_mesh_layer(layer_path: Path, target_root: str) -> bool:
    """Open and fix a Substance Painter mesh layer on disk.

    Args:
        layer_path: Path to the USD layer to modify in place.
        target_root: Target root prim path (e.g. "/Asset").

    Returns:
        bool: True if changes were applied and saved.
    """
    stage = Usd.Stage.Open(str(layer_path))
    if not stage:
        logger.warning("Failed to open USD layer: %s", layer_path)
        return False

    changed = fix_sp_mesh_stage(stage, target_root)
    if changed:
        stage.GetRootLayer().Save()
    return changed
