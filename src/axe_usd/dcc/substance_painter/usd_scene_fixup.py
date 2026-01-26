"""USD fixups for Substance Painter exports."""

from __future__ import annotations

import logging
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom

logger = logging.getLogger(__name__)

SP_ROOT_PATH = Sdf.Path("/root")
SP_MATERIAL_PATH = SP_ROOT_PATH.AppendChild("material")


def _remove_prim(stage: Usd.Stage, path: Sdf.Path) -> bool:
    path_str = path.pathString
    removed = stage.RemovePrim(path_str)
    return bool(removed)


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

    target_path = Sdf.Path(target_root)
    if not (target_path.IsAbsolutePath() and target_path.IsPrimPath()):
        logger.warning("Invalid target root path: %s", target_root)
        return False

    layer = stage.GetRootLayer()
    changed = False

    if _remove_prim(stage, SP_MATERIAL_PATH):
        changed = True

    UsdGeom.Xform.Define(stage, target_path.pathString)
    changed = True

    geo_path = target_path.AppendChild("geo")
    UsdGeom.Scope.Define(stage, geo_path.pathString)

    proxy_path = geo_path.AppendChild("proxy")
    proxy_scope = UsdGeom.Scope.Define(stage, proxy_path.pathString)
    UsdGeom.Imageable(proxy_scope.GetPrim()).CreatePurposeAttr().Set("proxy")

    render_path = geo_path.AppendChild("render")
    render_scope = UsdGeom.Scope.Define(stage, render_path.pathString)
    render_prim = render_scope.GetPrim()
    UsdGeom.Imageable(render_prim).CreatePurposeAttr().Set("render")
    render_prim.CreateRelationship("proxyPrim").SetTargets([proxy_path])

    root_prim = stage.GetPrimAtPath(SP_ROOT_PATH)
    children = list(root_prim.GetChildren())
    skip_names = {"material", "render", "proxy"}
    for child in children:
        if child.GetName() in skip_names:
            continue
        dst_path = render_path.AppendChild(child.GetName())
        if _remove_prim(stage, dst_path):
            changed = True
        copied = Sdf.CopySpec(layer, child.GetPath(), layer, dst_path)
        if not copied:
            logger.warning("CopySpec failed for %s", child.GetPath())
            continue
        changed = True
        if _remove_prim(stage, child.GetPath()):
            changed = True

    root_prim = stage.GetPrimAtPath(SP_ROOT_PATH)
    if root_prim and root_prim.IsValid() and not list(root_prim.GetChildren()):
        if _remove_prim(stage, SP_ROOT_PATH):
            changed = True

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
