"""USD fixups for Substance Painter exports."""

from __future__ import annotations

import logging
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom

from ...core.exceptions import USDStageError, ValidationError

logger = logging.getLogger(__name__)

SP_ROOT_PATH = Sdf.Path("/root")
SP_MATERIAL_PATH = SP_ROOT_PATH.AppendChild("material")


def _remove_prim(stage: Usd.Stage, path: Sdf.Path) -> bool:
    path_str = path.pathString
    removed = stage.RemovePrim(path_str)
    return bool(removed)


def _strip_material_bindings(stage: Usd.Stage) -> int:
    stripped = 0
    for prim in stage.Traverse():
        if not prim or not prim.IsValid():
            continue
        for rel in prim.GetRelationships():
            name = rel.GetName()
            if name.startswith("material:binding"):
                if prim.RemoveProperty(name):
                    stripped += 1
    return stripped


def _strip_material_binding_schema(stage: Usd.Stage) -> int:
    """Remove MaterialBindingAPI opinions without authoring delete list ops."""
    layer = stage.GetRootLayer()
    stripped = 0
    for prim in stage.Traverse():
        if not prim or not prim.IsValid():
            continue
        prim_spec = layer.GetPrimAtPath(prim.GetPath())
        if not prim_spec or not prim_spec.HasInfo("apiSchemas"):
            continue
        list_op = prim_spec.GetInfo("apiSchemas")
        if not list_op:
            continue
        def _filter(items: list[str]) -> list[str]:
            return [item for item in items if item != "MaterialBindingAPI"]
        explicit = _filter(list(list_op.explicitItems))
        prepended = _filter(list(list_op.prependedItems))
        appended = _filter(list(list_op.appendedItems))
        ordered = _filter(list(list_op.orderedItems))
        added = _filter(list(list_op.addedItems))
        deleted = _filter(list(list_op.deletedItems))
        if not (explicit or prepended or appended or ordered or added or deleted):
            prim_spec.ClearInfo("apiSchemas")
        else:
            new_list_op = Sdf.TokenListOp()
            new_list_op.explicitItems = explicit
            new_list_op.prependedItems = prepended
            new_list_op.appendedItems = appended
            new_list_op.orderedItems = ordered
            new_list_op.addedItems = added
            new_list_op.deletedItems = deleted
            prim_spec.SetInfo("apiSchemas", new_list_op)
        stripped += 1
    return stripped


def _instance_proxy_prim(
    stage: Usd.Stage,
    proxy_parent: Sdf.Path,
    render_child_path: Sdf.Path,
    child_name: str,
) -> bool:
    """Create an instanceable proxy prim from its render counterpart.

    Args:
        stage: The USD stage being edited.
        proxy_parent: Parent path for proxy prims (e.g. /Asset/geo/proxy).
        render_child_path: Render prim path to reference.
        child_name: Name of the child prim to create under proxy_parent.

    Returns:
        bool: True if the proxy instance was authored.
    """
    proxy_child_path = proxy_parent.AppendChild(child_name)
    _remove_prim(stage, proxy_child_path)
    proxy_prim = stage.OverridePrim(proxy_child_path.pathString)
    proxy_prim.SetInstanceable(True)
    refs = proxy_prim.GetReferences()
    refs.ClearReferences()
    refs.AddInternalReference(render_child_path)
    return True


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
        raise USDStageError("No stage provided for SP mesh fixup.")

    target_path = Sdf.Path(target_root)
    if not (target_path.IsAbsolutePath() and target_path.IsPrimPath()):
        raise ValidationError(
            "Invalid target root path.",
            details={"target_root": target_root},
        )

    layer = stage.GetRootLayer()
    changed = False

    stripped = _strip_material_bindings(stage)
    if stripped:
        logger.debug("Stripped %d material bindings from mesh layer.", stripped)
        changed = True
    schema_stripped = _strip_material_binding_schema(stage)
    if schema_stripped:
        logger.debug(
            "Removed MaterialBindingAPI from %d prims in mesh layer.",
            schema_stripped,
        )
        changed = True

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
    if not root_prim or not root_prim.IsValid():
        raise USDStageError(
            "Expected /root prim is missing from the stage.",
            details={"root_path": SP_ROOT_PATH.pathString},
        )
    children = list(root_prim.GetChildren())
    skip_names = {"material", "render", "proxy"}
    for child in children:
        child_name = child.GetName()
        if child_name in skip_names:
            continue
        child_path = child.GetPath()
        dst_path = render_path.AppendChild(child_name)
        if _remove_prim(stage, dst_path):
            changed = True
        copied = Sdf.CopySpec(layer, child_path, layer, dst_path)
        if not copied:
            logger.warning("CopySpec failed for %s", child_path)
            continue
        changed = True
        if _remove_prim(stage, child_path):
            changed = True
        if _instance_proxy_prim(stage, proxy_path, dst_path, child_name):
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
        raise USDStageError(
            "Failed to open USD layer.",
            details={"layer_path": str(layer_path)},
        )

    changed = fix_sp_mesh_stage(stage, target_root)
    if changed:
        stage.GetRootLayer().Save()
    return changed
