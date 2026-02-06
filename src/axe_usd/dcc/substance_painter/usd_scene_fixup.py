"""USD fixups for Substance Painter exports."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from pxr import Gf, Sdf, Usd, UsdGeom

from ...core.exceptions import USDStageError, ValidationError

logger = logging.getLogger(__name__)


def _detect_source_root(stage: Usd.Stage) -> Usd.Prim:
    pseudo_root = stage.GetPseudoRoot()
    if not pseudo_root:
        raise USDStageError("Stage is missing a pseudo-root.")

    children = [child for child in pseudo_root.GetChildren() if child.IsValid()]
    if not children:
        raise USDStageError("No root prims found in stage.")

    if len(children) == 1:
        return children[0]

    details = {"root_paths": [str(child.GetPath()) for child in children]}
    raise USDStageError("Ambiguous root prims; cannot auto-detect.", details=details)


def _compute_mesh_extent(mesh: UsdGeom.Mesh) -> Optional[List[Gf.Vec3f]]:
    points_attr = mesh.GetPointsAttr()
    if not points_attr:
        return None
    points = points_attr.Get()
    if not points:
        return None

    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    min_z = min(point[2] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    max_z = max(point[2] for point in points)
    return [Gf.Vec3f(min_x, min_y, min_z), Gf.Vec3f(max_x, max_y, max_z)]


def _author_mesh_extents(stage: Usd.Stage, render_root: Sdf.Path) -> int:
    render_prim = stage.GetPrimAtPath(render_root)
    if not render_prim or not render_prim.IsValid():
        logger.warning("Render root prim missing: %s", render_root.pathString)
        return 0

    authored = 0
    for prim in Usd.PrimRange(render_prim):
        if prim == render_prim:
            continue
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        extent = _compute_mesh_extent(mesh)
        if not extent:
            logger.debug("Skipping extent for mesh with no points: %s", prim.GetPath())
            continue
        extent_attr = mesh.GetExtentAttr()
        if not extent_attr:
            extent_attr = mesh.CreateExtentAttr()
        extent_attr.Set(extent)
        authored += 1

    if authored:
        logger.debug("Authored extents on %d mesh prims.", authored)
    return authored


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

    - Removes material scope under the detected root prim.
    - Moves all prims under the detected root prim to the target root prim.

    Args:
        stage: The opened USD stage to modify.
        target_root: Target root prim path (e.g. "/Asset").

    Returns:
        bool: True if changes were applied.
    """
    if not stage:
        raise USDStageError("No stage provided for SP mesh fixup.")

    pseudo_root = stage.GetPseudoRoot()
    if pseudo_root:
        root_children = [str(child.GetPath()) for child in pseudo_root.GetChildren()]
        logger.debug("Initial stage root prims: %s", root_children)

    source_root = _detect_source_root(stage)
    source_root_path = source_root.GetPath()
    logger.debug("Detected source root prim: %s", source_root_path)

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

    material_path = source_root_path.AppendChild("material")
    if _remove_prim(stage, material_path):
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

    children = list(source_root.GetChildren())
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

    _author_mesh_extents(stage, render_path)

    if source_root.IsValid() and not list(source_root.GetChildren()):
        if _remove_prim(stage, source_root_path):
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
