"""USD material processing utilities.

Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from pxr import Sdf, Tf, Usd, UsdGeom, UsdShade, Vt

from ..core.exceptions import GeometryExportError, MaterialAssignmentError

from . import utils as usd_utils
from .material_builders import (
    ARNOLD_DISPLACEMENT_BUMP,
    ArnoldBuilder,
    MaterialBuildContext,
    MtlxBuilder,
    OpenPbrBuilder,
    UsdPreviewBuilder,
)
from .material_model import (
    TextureFormatOverrides,
    is_transmissive_material,
    normalize_asset_path,
    normalize_material_dict,
)
from .types import MaterialTextureDict, MaterialTextureList
from .asset_files import (
    MTL_LIBRARY_ROOT,
    MTL_VARIANT_DEFAULT,
    MTL_VARIANT_SET,
)

# Configure module-level logger
logger = logging.getLogger(__name__)


class USDShaderCreate:
    """Create USD material prims and shader networks.

    Attributes:
        stage: USD stage to author into.
        material_name: Name of the material to create.
        material_dict: Mapping of texture slots to file paths.
        parent_primpath: Parent prim path to place materials under.
        create_usd_preview: Whether to create UsdPreviewSurface materials.
        create_arnold: Whether to create Arnold materials.
        create_mtlx: Whether to create MaterialX materials.
        create_openpbr: Whether to create MaterialX OpenPBR materials.
        texture_format_overrides: Optional per-renderer texture format overrides (usd_preview, arnold, mtlx, openpbr).
        is_transmissive: Whether the material is treated as transmissive.
    """

    def __init__(
        self,
        stage: Usd.Stage,
        material_name: str,
        material_dict: MaterialTextureDict,
        mesh_names: Optional[Sequence[str]] = None,
        parent_primpath: str = "/Asset/material",
        create_usd_preview: bool = False,
        create_arnold: bool = False,
        create_mtlx: bool = False,
        create_openpbr: bool = False,
        arnold_displacement_mode: str = ARNOLD_DISPLACEMENT_BUMP,
        texture_format_overrides: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Initialize the shader creator and build the materials.

        Args:
            stage: USD stage to author into.
            material_name: Name of the material to create.
            material_dict: Mapping of texture slots to file paths.
            mesh_names: Optional mesh names assigned to this material.
            parent_primpath: Parent prim path to place materials under.
            create_usd_preview: Whether to create UsdPreviewSurface materials.
            create_arnold: Whether to create Arnold materials.
            create_mtlx: Whether to create MaterialX materials.
            create_openpbr: Whether to create MaterialX OpenPBR materials.
            arnold_displacement_mode: Whether to use bump or true displacement for
                                      Arnold height maps.
            texture_format_overrides: Optional per-renderer texture format overrides (usd_preview, arnold, mtlx, openpbr).
        """
        self.stage = stage
        self.material_dict = normalize_material_dict(material_dict, logger=logger)
        self.material_name = material_name
        self.mesh_names = tuple(mesh_names) if mesh_names else ()
        self.parent_primpath = parent_primpath
        self.create_usd_preview = create_usd_preview
        self.create_arnold = create_arnold
        self.create_mtlx = create_mtlx
        self.create_openpbr = create_openpbr
        self.arnold_displacement_mode = arnold_displacement_mode
        self.texture_format_overrides = TextureFormatOverrides.from_mapping(
            texture_format_overrides
        )

        self.is_transmissive = is_transmissive_material(self.material_name)
        if self.is_transmissive:
            logger.debug("Detected transmissive material: '%s'.", self.material_name)

        self.run()

    def _create_collect_material(self) -> UsdShade.Material:
        UsdGeom.Scope.Define(self.stage, self.parent_primpath)
        prim_name = self.material_name or "Material"
        if not Sdf.Path.IsValidIdentifier(prim_name):
            prim_name = f"_{prim_name}"
            sanitized = Tf.MakeValidIdentifier(prim_name)
            logger.debug(
                "Material name '%s' is not a valid USD identifier; using '%s'.",
                prim_name,
                sanitized,
            )
            prim_name = sanitized
        collect_prim_path = f"{self.parent_primpath}/{prim_name}"
        collect_usd_material = UsdShade.Material.Define(self.stage, collect_prim_path)
        collect_usd_material.CreateInput("inputnum", Sdf.ValueTypeNames.Int).Set(2)
        collect_usd_material.GetPrim().SetCustomDataByKey(
            "source_material_name", self.material_name
        )
        if self.mesh_names:
            collect_usd_material.GetPrim().SetCustomDataByKey(
                "source_mesh_names", Vt.StringArray(list(self.mesh_names))
            )
        collect_usd_material.GetPrim().SetMetadata("displayName", self.material_name)
        return collect_usd_material

    def _build_context(self) -> MaterialBuildContext:
        return MaterialBuildContext(
            stage=self.stage,
            material_dict=self.material_dict,
            is_transmissive=self.is_transmissive,
            texture_format_overrides=self.texture_format_overrides,
            logger=logger,
            arnold_displacement_mode=self.arnold_displacement_mode,
        )

    def run(self) -> None:
        """Create the collect material and requested shader networks."""
        collect_usd_material = self._create_collect_material()
        collect_path = str(collect_usd_material.GetPath())
        context = self._build_context()

        if self.create_usd_preview:
            UsdPreviewBuilder(context).build(collect_path)

        if self.create_arnold:
            arnold_nodegraph = ArnoldBuilder(context).build(collect_path)
            collect_usd_material.CreateOutput(
                "arnold:surface", Sdf.ValueTypeNames.Token
            ).ConnectToSource(arnold_nodegraph.ConnectableAPI(), "surface")
            displacement_output = arnold_nodegraph.GetOutput("displacement")
            if displacement_output and displacement_output.GetAttr().IsValid():
                collect_usd_material.CreateOutput(
                    "arnold:displacement", displacement_output.GetTypeName()
                ).ConnectToSource(arnold_nodegraph.ConnectableAPI(), "displacement")

        if self.create_openpbr and self.create_mtlx:
            logger.warning(
                "OpenPBR enabled; skipping MaterialX standard surface output."
            )
            self.create_mtlx = False

        if self.create_mtlx:
            mtlx_nodegraph = MtlxBuilder(context).build(collect_path)
            collect_usd_material.CreateOutput(
                "mtlx:surface", Sdf.ValueTypeNames.Token
            ).ConnectToSource(mtlx_nodegraph.ConnectableAPI(), "surface")
            collect_usd_material.CreateOutput(
                "kma:surface", Sdf.ValueTypeNames.Token
            ).ConnectToSource(mtlx_nodegraph.ConnectableAPI(), "surface")
            displacement_output = mtlx_nodegraph.GetOutput("displacement")
            if displacement_output and displacement_output.GetAttr().IsValid():
                collect_usd_material.CreateOutput(
                    "mtlx:displacement", displacement_output.GetTypeName()
                ).ConnectToSource(mtlx_nodegraph.ConnectableAPI(), "displacement")

        if self.create_openpbr:
            openpbr_nodegraph = OpenPbrBuilder(context).build(collect_path)
            collect_usd_material.CreateOutput(
                "mtlx:surface", Sdf.ValueTypeNames.Token
            ).ConnectToSource(openpbr_nodegraph.ConnectableAPI(), "surface")
            collect_usd_material.CreateOutput(
                "kma:surface", Sdf.ValueTypeNames.Token
            ).ConnectToSource(openpbr_nodegraph.ConnectableAPI(), "surface")
            displacement_output = openpbr_nodegraph.GetOutput("displacement")
            if displacement_output and displacement_output.GetAttr().IsValid():
                collect_usd_material.CreateOutput(
                    "mtlx:displacement", displacement_output.GetTypeName()
                ).ConnectToSource(openpbr_nodegraph.ConnectableAPI(), "displacement")


class USDShaderAssign:
    """Assign USD materials to matching mesh prims."""

    def __init__(self, stage: Usd.Stage, naming_convention=None) -> None:
        """Initialize the material assigner.

        Args:
            stage: USD stage to update.
            naming_convention: Optional naming convention for cleaning material names.
                             If None, uses the default convention.
        """
        from .naming import NamingConvention

        self.stage = stage
        self.naming_convention = naming_convention or NamingConvention()

    def assign_material_to_primitives(
        self,
        material_prim: Usd.Prim,
        prims_to_assign_to: Iterable[Usd.Prim],
    ) -> None:
        """Assign a USD material to a list of primitives.

        Args:
            material_prim: Material prim to bind.
            prims_to_assign_to: Prims that should receive the material.

        Raises:
            MaterialAssignmentError: If the provided material is not a UsdShade.Material.
        """
        if (
            not material_prim
            or not material_prim.IsValid()
            or not material_prim.IsA(UsdShade.Material)
        ):
            raise MaterialAssignmentError(
                "Invalid material type for assignment",
                details={
                    "material_type": type(material_prim).__name__,
                    "is_valid": material_prim.IsValid() if material_prim else False,
                },
            )

        material = UsdShade.Material(material_prim)

        for prim in prims_to_assign_to:
            UsdShade.MaterialBindingAPI(prim).Bind(material)

    def run(self, mats_parent_path: str, mesh_parent_path: str) -> None:
        """Bind materials to meshes with matching names.

        Args:
            mats_parent_path: Parent prim path containing materials.
            mesh_parent_path: Parent prim path containing meshes.
        """
        mats_parent_prim = self.stage.GetPrimAtPath(mats_parent_path)

        # 1. get list of Materials under a parent prim:
        check, found_mats = usd_utils.collect_prims_of_type(
            mats_parent_prim, prim_type=UsdShade.Material, recursive=False
        )
        if not check:
            raise MaterialAssignmentError(
                "No UsdShade.Material found under prim.",
                details={"mats_parent_path": mats_parent_path},
            )

        for mat_prim in found_mats:
            # 2. cleaning material name:
            source_name = mat_prim.GetCustomDataByKey("source_material_name")
            if source_name:
                mat_name = str(source_name)
            else:
                # Use naming convention to clean material name
                mat_name = self.naming_convention.clean_material_name(
                    mat_prim.GetName()
                )

            mesh_parent_prim = self.stage.GetPrimAtPath(mesh_parent_path)

            # 3. collect all meshes that have the mat name as part of its name:
            check, asset_prims = usd_utils.collect_prims_of_type(
                mesh_parent_prim,
                prim_type=UsdGeom.Mesh,
                contains_str=mat_name,
                recursive=True,
            )
            if not asset_prims:
                logger.warning("No meshes found with name like: %s", mat_name)
                continue

            asset_names = [x.GetName() for x in asset_prims]
            logger.debug("mat_name: %s, asset_names: %s", mat_name, asset_names[0])

            # 4. assign the material to the list of mesh prims:
            self.assign_material_to_primitives(mat_prim, asset_prims)


class USDMeshConfigure:
    """Configure mesh primvars and metadata.

    Notes:
        TODO: Add transmission support to MTLX.
        TODO: Add Karma render settings for caustics and double sided.
        TODO: Set subdiv schema to "__none__".
    """

    def __init__(self, stage: Usd.Stage) -> None:
        """Initialize the mesh configurator.

        Args:
            stage: USD stage to update.
        """
        self.stage = stage

    def add_karma_primvars(self, prim: Usd.Prim) -> None:
        """Add Karma-specific primvars to a prim.

        Args:
            prim: Prim to update.
        """
        karma_primvars = {
            "primvars:karma:object:causticsenable": (True, Sdf.ValueTypeNames.Bool),
            # "karma:customShading": (0.5, Sdf.ValueTypeNames.Float),
            # "karma:shadowBias": (0.05, Sdf.ValueTypeNames.Float)
        }

        for attrName, (value, typeName) in karma_primvars.items():
            # Check if the attribute already exists; if not, create it.
            attr = prim.GetAttribute(attrName)
            if not attr:
                attr = prim.CreateAttribute(attrName, typeName)

            # Set the attribute value.
            attr.Set(value)
            logger.debug("Set attribute %s to %s (Type: %s)", attrName, value, typeName)


_UDIM_TOKEN = "<UDIM>"


def _relative_asset_path(dest_path: Path, maps_dir: Path) -> str:
    try:
        rel_path = dest_path.relative_to(maps_dir.parent)
        return f"./{rel_path.as_posix()}"
    except ValueError:
        logger.warning("Could not compute relative path for %s", dest_path)
        return dest_path.as_posix()


def _move_texture_file(source_path: Path, dest_dir: Path) -> Path:
    dest_path = dest_dir / source_path.name
    if dest_path.exists():
        if dest_path.stat().st_mtime < source_path.stat().st_mtime:
            dest_path.unlink()
            shutil.move(str(source_path), str(dest_path))
        elif source_path.resolve() != dest_path.resolve():
            source_path.unlink()
    else:
        shutil.move(str(source_path), str(dest_path))
    return dest_path


def _relocate_textures(
    material_dict_list: MaterialTextureList,
    maps_dir: Path,
) -> MaterialTextureList:
    """Copy textures to the maps directory and update paths.

    Args:
        material_dict_list: List of material dictionaries with source paths.
        maps_dir: Destination directory for textures.

    Returns:
        MaterialTextureList: Updated list with relative paths to copied textures.
    """
    updated_list = []

    for mat_dict in material_dict_list:
        new_mat_dict = {}
        for slot, info in mat_dict.items():
            source_path = Path(info["path"])
            new_info = info.copy()

            if not source_path.is_absolute():
                new_info["path"] = normalize_asset_path(info["path"])
                new_mat_dict[slot] = new_info
                continue

            if _UDIM_TOKEN in source_path.name:
                dest_path = maps_dir / source_path.name
                if source_path.is_absolute() and (
                    source_path.parent.resolve() != maps_dir.resolve()
                ):
                    logger.warning(
                        "UDIM textures are expected in %s; got %s",
                        maps_dir,
                        source_path.parent,
                    )
                new_info["path"] = _relative_asset_path(dest_path, maps_dir)
                new_mat_dict[slot] = new_info
                continue

            if not source_path.exists():
                logger.warning("Texture not found: %s", source_path)
                new_mat_dict[slot] = info
                continue

            dest_path = maps_dir / source_path.name
            if source_path.is_absolute() and (
                source_path.parent.resolve() == maps_dir.resolve()
            ):
                new_info["path"] = _relative_asset_path(dest_path, maps_dir)
                new_mat_dict[slot] = new_info
                continue

            try:
                moved_path = _move_texture_file(source_path, maps_dir)
                logger.debug("Moved texture: %s -> %s", source_path, moved_path)
                new_info["path"] = _relative_asset_path(moved_path, maps_dir)
            except Exception as exc:
                logger.error("Failed to move texture %s: %s", source_path, exc)
                new_info["path"] = _relative_asset_path(dest_path, maps_dir)

            new_mat_dict[slot] = new_info

        updated_list.append(new_mat_dict)

    return updated_list


def _mesh_names_from_material_dict(
    material_dict: MaterialTextureDict,
) -> tuple[str, ...]:
    for info in material_dict.values():
        mesh_names = info.get("mesh_names")
        if not mesh_names:
            continue
        cleaned: list[str] = []
        for mesh_name in mesh_names:
            mesh_str = str(mesh_name)
            if mesh_str and mesh_str not in cleaned:
                cleaned.append(mesh_str)
        return tuple(cleaned)
    return ()


def _mesh_names_from_material_prim(material_prim: Usd.Prim) -> list[str]:
    data = material_prim.GetCustomDataByKey("source_mesh_names")
    if not data:
        return []
    if isinstance(data, (str, bytes)):
        raw_names = [data]
    else:
        try:
            raw_names = list(data)
        except TypeError:
            raw_names = [data]
    cleaned: list[str] = []
    for mesh_name in raw_names:
        mesh_str = str(mesh_name)
        if mesh_str and mesh_str not in cleaned:
            cleaned.append(mesh_str)
    return cleaned


def _collect_binding_candidates(stage: Usd.Stage, root_path: str) -> list[Usd.Prim]:
    root_prim = stage.GetPrimAtPath(root_path)
    if not root_prim or not root_prim.IsValid():
        return []
    xforms: list[Usd.Prim] = []
    meshes: list[Usd.Prim] = []
    for prim in Usd.PrimRange(root_prim):
        if prim == root_prim:
            continue
        if prim.IsA(UsdGeom.Xform):
            xforms.append(prim)
        elif prim.IsA(UsdGeom.Mesh):
            meshes.append(prim)
    return xforms or meshes


def _index_prims_by_name(prims: Iterable[Usd.Prim]) -> dict[str, list[Usd.Prim]]:
    index: dict[str, list[Usd.Prim]] = {}
    for prim in prims:
        name = prim.GetName()
        if not name:
            continue
        index.setdefault(name, []).append(prim)
    return index


def _binding_target_for_prim(prim: Usd.Prim) -> str:
    if prim.IsA(UsdGeom.Xform):
        return str(prim.GetPath())
    parent = prim.GetParent()
    if parent and parent.IsValid() and parent.IsA(UsdGeom.Xform):
        return str(parent.GetPath())
    return str(prim.GetPath())


def _proxy_binding_target(stage: Usd.Stage, render_target: str) -> Optional[str]:
    if "/geo/render/" not in render_target:
        return None
    proxy_path = render_target.replace("/geo/render/", "/geo/proxy/", 1)
    proxy_prim = stage.GetPrimAtPath(proxy_path)
    if proxy_prim and proxy_prim.IsValid():
        return _binding_target_for_prim(proxy_prim)
    proxy_parent_path = proxy_path.rsplit("/", 1)[0]
    proxy_parent = stage.GetPrimAtPath(proxy_parent_path)
    if proxy_parent and proxy_parent.IsValid():
        return _binding_target_for_prim(proxy_parent)
    return None


def _collect_targets_for_mesh_names(
    stage: Usd.Stage,
    render_root: str,
    mesh_names: Iterable[str],
    name_index: dict[str, list[Usd.Prim]],
) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for mesh_name in mesh_names:
        if not mesh_name:
            continue
        direct_path = f"{render_root}/{mesh_name}"
        direct_prim = stage.GetPrimAtPath(direct_path)
        if direct_prim and direct_prim.IsValid():
            target = _binding_target_for_prim(direct_prim)
            if target not in seen:
                seen.add(target)
                targets.append(target)
        for prim in name_index.get(mesh_name, []):
            target = _binding_target_for_prim(prim)
            if target not in seen:
                seen.add(target)
                targets.append(target)
    return targets


def _collect_mesh_paths(stage: Usd.Stage, root_path: str) -> list[str]:
    mesh_paths: list[str] = []
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            path = str(prim.GetPath())
            if root_path and not path.startswith(root_path):
                continue
            mesh_paths.append(path)
    return mesh_paths


def _binding_target_for_mesh_path(mesh_path: str) -> str:
    if "/geo/proxy/" in mesh_path:
        return mesh_path.rsplit("/", 1)[0]
    return mesh_path


def _collect_material_prims(stage: Usd.Stage, parent_path: str) -> list[Usd.Prim]:
    parent = stage.GetPrimAtPath(parent_path)
    if not parent or not parent.IsValid():
        return []
    check, found = usd_utils.collect_prims_of_type(
        parent, prim_type=UsdShade.Material, recursive=True
    )
    if not check:
        return []
    return found


def _bind_materials_in_variant(
    asset_file: Path, mtl_file: Path, asset_name: str
) -> None:
    asset_stage = Usd.Stage.Open(str(asset_file))
    if not asset_stage:
        logger.warning("Failed to open asset stage for binding: %s", asset_file)
        return

    mtl_stage = Usd.Stage.Open(str(mtl_file))
    if not mtl_stage:
        logger.warning("Failed to open material stage for binding: %s", mtl_file)
        return

    root_path = f"/{asset_name}"
    root_prim = mtl_stage.GetPrimAtPath(root_path)
    if not root_prim or not root_prim.IsValid():
        logger.warning("Missing root prim for material binding: %s", root_path)
        return

    variant_set = root_prim.GetVariantSets().GetVariantSet(MTL_VARIANT_SET)
    if not variant_set or not variant_set.IsValid():
        variant_set = root_prim.GetVariantSets().AddVariantSet(MTL_VARIANT_SET)
    if MTL_VARIANT_DEFAULT not in variant_set.GetVariantNames():
        variant_set.AddVariant(MTL_VARIANT_DEFAULT)
    variant_set.SetVariantSelection(MTL_VARIANT_DEFAULT)

    material_prims = _collect_material_prims(mtl_stage, f"/{MTL_LIBRARY_ROOT}/mtl")
    if not material_prims:
        logger.warning("No materials found to bind in %s", mtl_file)
        return

    render_root = f"/{asset_name}/geo/render"
    binding_candidates = _collect_binding_candidates(asset_stage, render_root)
    name_index = _index_prims_by_name(binding_candidates)
    proxy_root = f"/{asset_name}/geo/proxy"
    logger.debug("Material binding render root: %s", render_root)
    logger.debug("Material binding proxy root: %s", proxy_root)
    logger.debug("Render binding candidates: %d", len(binding_candidates))
    if binding_candidates:
        logger.debug(
            "Sample binding candidates: %s",
            [str(prim.GetPath()) for prim in binding_candidates[:3]],
        )

    with variant_set.GetVariantEditContext():
        from .naming import NamingConvention

        if not binding_candidates:
            logger.warning(
                "No meshes found for material binding under %s.", render_root
            )
            return

        naming = NamingConvention()
        for material_prim in material_prims:
            source_name = material_prim.GetCustomDataByKey("source_material_name")
            raw_name = str(source_name) if source_name else material_prim.GetName()
            cleaned = naming.clean_material_name(raw_name)
            mesh_names = _mesh_names_from_material_prim(material_prim)

            render_targets: list[str] = []
            if mesh_names:
                render_targets = _collect_targets_for_mesh_names(
                    asset_stage, render_root, mesh_names, name_index
                )
                if not render_targets:
                    logger.warning(
                        "No prims found for mesh assignments %s (material %s).",
                        mesh_names,
                        cleaned,
                    )

            if not render_targets:
                render_targets = [
                    _binding_target_for_prim(prim)
                    for prim in binding_candidates
                    if cleaned in prim.GetName()
                ]

            if not render_targets:
                logger.warning("No meshes found with name like: %s", cleaned)
                continue

            bind_targets: list[str] = []
            seen: set[str] = set()
            for render_target in render_targets:
                if render_target not in seen:
                    seen.add(render_target)
                    bind_targets.append(render_target)
                proxy_target = _proxy_binding_target(asset_stage, render_target)
                if proxy_target and proxy_target not in seen:
                    seen.add(proxy_target)
                    bind_targets.append(proxy_target)

            material = UsdShade.Material.Get(
                mtl_stage, f"/{asset_name}/mtl/{material_prim.GetName()}"
            )
            if not material or not material.GetPrim().IsValid():
                logger.warning(
                    "Material not found for binding: %s", material_prim.GetName()
                )
                continue

            for bind_path in bind_targets:
                mesh_prim = mtl_stage.OverridePrim(bind_path)
                UsdShade.MaterialBindingAPI.Apply(mesh_prim)
                UsdShade.MaterialBindingAPI(mesh_prim).Bind(material)
                logger.debug(
                    "Bound %s -> %s",
                    bind_path,
                    material.GetPrim().GetPath(),
                )

    mtl_stage.Save()


def create_shaded_asset_publish(
    material_dict_list: MaterialTextureList,
    stage: Optional[Usd.Stage] = None,
    geo_file: Optional[str] = None,
    parent_path: str = "/Asset",
    layer_save_path: Optional[str] = None,
    main_layer_name: str = "main.usda",
    create_usd_preview: bool = True,
    create_arnold: bool = False,
    create_mtlx: bool = True,
    create_openpbr: bool = False,
    arnold_displacement_mode: str = ARNOLD_DISPLACEMENT_BUMP,
    texture_format_overrides: Optional[Mapping[str, str]] = None,
) -> None:
    """Create a component-builder USD asset with materials and optional geometry.

    Creates structure:
    - Files: AssetName.usd, payload.usdc, geo.usdc, mtl.usdc, /textures/
    - Prims: /__class__/Asset, /Asset (Kind=component)

    Args:
        material_dict_list: Material texture dictionaries to publish.
        stage: Ignored (legacy argument, kept for signature compatibility).
        geo_file: Optional geometry USD file to reference (source).
        parent_path: Root prim path for the published asset (e.g., "/Asset").
        layer_save_path: Output directory.
        main_layer_name: Ignored (uses AssetName.usd).
        create_usd_preview: Whether to create UsdPreviewSurface materials.
        create_arnold: Whether to create Arnold materials.
        create_mtlx: Whether to create MaterialX materials.
        create_openpbr: Whether to create MaterialX OpenPBR materials.
        arnold_displacement_mode: Whether to use bump or true displacement for
                                  Arnold height maps.
        texture_format_overrides: Optional per-renderer texture format overrides.
    """
    from .asset_files import (
        create_asset_file_structure,
        create_asset_usd_file,
        create_payload_usd_file,
        create_geo_usd_file,
        create_mtl_usd_file,
    )

    if not layer_save_path:
        layer_save_path = f"{tempfile.gettempdir()}/temp_usd_export"
        os.makedirs(layer_save_path, exist_ok=True)
    layer_save_path = str(layer_save_path)

    # Extract asset name from parent_path (e.g., "/Asset" -> "Asset")
    asset_name = parent_path.strip("/").split("/")[-1]

    # Component-builder file structure
    output_dir = Path(layer_save_path)
    paths = create_asset_file_structure(output_dir, asset_name)

    # 1. Handle geometry file
    has_geometry = False
    if geo_file:
        geo_path = Path(geo_file)
        if not geo_path.exists():
            raise GeometryExportError(
                "Geometry file not found.",
                details={"path": str(geo_path)},
            )
        expected_path = paths.geo_file.resolve()
        actual_path = geo_path.resolve()
        if actual_path != expected_path:
            raise GeometryExportError(
                "Geometry file is not at the expected path.",
                details={"expected": str(expected_path), "actual": str(actual_path)},
            )
        has_geometry = True
        logger.info("Using geometry file: %s", geo_path)

    # 2. Create geo.usdc scaffold (does not overwrite existing files)
    create_geo_usd_file(paths, asset_name)

    # 3. Create mtl.usdc and author materials
    mtl_stage = create_mtl_usd_file(paths, asset_name)
    material_primitive_path = f"/{MTL_LIBRARY_ROOT}/mtl"
    material_dict_list = _relocate_textures(material_dict_list, paths.textures_dir)

    for material_dict in material_dict_list:
        material_name = next(
            (info["mat_name"] for info in material_dict.values()),
            "UnknownMaterialName",
        )
        mesh_names = _mesh_names_from_material_dict(material_dict)
        USDShaderCreate(
            stage=mtl_stage,
            material_name=material_name,
            material_dict=material_dict,
            mesh_names=mesh_names or None,
            parent_primpath=material_primitive_path,
            create_usd_preview=create_usd_preview,
            create_arnold=create_arnold,
            create_mtlx=create_mtlx,
            create_openpbr=create_openpbr,
            arnold_displacement_mode=arnold_displacement_mode,
            texture_format_overrides=texture_format_overrides,
        )
    mtl_stage.Save()

    # 4. Create payload.usdc (references mtl.usdc and geo.usdc)
    create_payload_usd_file(paths, asset_name)

    # 5. Create Asset.usd (main entry point)
    create_asset_usd_file(paths, asset_name)

    # 6. Bind materials inside mtl.usdc variant if geometry is available
    if has_geometry:
        logger.info("Binding materials to geometry via mtl variant...")
        _bind_materials_in_variant(paths.asset_file, paths.mtl_file, asset_name)

    logger.info(
        "Created component USD asset: '%s/%s/%s.usd'",
        layer_save_path,
        asset_name,
        asset_name,
    )
    logger.info(
        "Structure: %s.usd, payload.usdc, geo.usdc, mtl.usdc, /textures/",
        asset_name,
    )
    logger.info("Success")
