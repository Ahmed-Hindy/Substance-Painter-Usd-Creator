"""USD material processing utilities.

Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

import logging
import os
import tempfile
from typing import Iterable, Mapping, Optional

from pxr import Sdf, Tf, Usd, UsdGeom, UsdShade

from ..core.exceptions import MaterialAssignmentError

from . import utils as usd_utils
from .material_builders import (
    ArnoldBuilder,
    MaterialBuildContext,
    MtlxBuilder,
    OpenPbrBuilder,
    UsdPreviewBuilder,
)
from .material_model import (
    TextureFormatOverrides,
    is_transmissive_material,
    normalize_material_dict,
)
from .types import MaterialTextureDict, MaterialTextureList

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
        parent_primpath: str = "/Asset/material",
        create_usd_preview: bool = False,
        create_arnold: bool = False,
        create_mtlx: bool = False,
        create_openpbr: bool = False,
        texture_format_overrides: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Initialize the shader creator and build the materials.

        Args:
            stage: USD stage to author into.
            material_name: Name of the material to create.
            material_dict: Mapping of texture slots to file paths.
            parent_primpath: Parent prim path to place materials under.
            create_usd_preview: Whether to create UsdPreviewSurface materials.
            create_arnold: Whether to create Arnold materials.
            create_mtlx: Whether to create MaterialX materials.
            create_openpbr: Whether to create MaterialX OpenPBR materials.
            texture_format_overrides: Optional per-renderer texture format overrides (usd_preview, arnold, mtlx, openpbr).
        """
        self.stage = stage
        self.material_dict = normalize_material_dict(material_dict, logger=logger)
        self.material_name = material_name
        self.parent_primpath = parent_primpath
        self.create_usd_preview = create_usd_preview
        self.create_arnold = create_arnold
        self.create_mtlx = create_mtlx
        self.create_openpbr = create_openpbr
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
        collect_usd_material.GetPrim().SetMetadata("displayName", self.material_name)
        return collect_usd_material

    def _build_context(self) -> MaterialBuildContext:
        return MaterialBuildContext(
            stage=self.stage,
            material_dict=self.material_dict,
            is_transmissive=self.is_transmissive,
            texture_format_overrides=self.texture_format_overrides,
            logger=logger,
        )

    def run(self) -> None:
        """Create the collect material and requested shader networks."""
        collect_usd_material = self._create_collect_material()
        collect_path = str(collect_usd_material.GetPath())
        context = self._build_context()

        if self.create_usd_preview:
            usd_preview_shader = UsdPreviewBuilder(context).build(collect_path)
            collect_usd_material.CreateSurfaceOutput().ConnectToSource(
                usd_preview_shader.ConnectableAPI(), "surface"
            )

        if self.create_arnold:
            arnold_shader = ArnoldBuilder(context).build(collect_path)
            collect_usd_material.CreateOutput(
                "arnold:surface", Sdf.ValueTypeNames.Token
            ).ConnectToSource(arnold_shader.ConnectableAPI(), "surface")

        if self.create_openpbr and self.create_mtlx:
            logger.warning(
                "OpenPBR enabled; skipping MaterialX standard surface output."
            )
            self.create_mtlx = False

        if self.create_mtlx:
            mtlx_shader = MtlxBuilder(context).build(collect_path)
            collect_usd_material.CreateOutput(
                "mtlx:surface", Sdf.ValueTypeNames.Token
            ).ConnectToSource(mtlx_shader.ConnectableAPI(), "surface")

        if self.create_openpbr:
            openpbr_shader = OpenPbrBuilder(context).build(collect_path)
            collect_usd_material.CreateOutput(
                "mtlx:surface", Sdf.ValueTypeNames.Token
            ).ConnectToSource(openpbr_shader.ConnectableAPI(), "surface")


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
            logger.warning(
                "No UsdShade.Material found under prim: '%s'.", mats_parent_path
            )
            return

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
                logger.warning("No meshes found with name: %s", mat_name)
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
    texture_format_overrides: Optional[Mapping[str, str]] = None,
) -> None:
    """Create ASWF-compliant USD asset with materials and optional geometry.

    Follows https://github.com/usd-wg/assets/blob/main/docs/asset-structure-guidelines.md

    Creates structure:
    - /<AssetName>: Root Xform with Kind=component, assetInfo, class inheritance
    - /<AssetName>/geo: Geometry scope (if geo_file provided)
    - /<AssetName>/mtl: Material scope
    - /__class__/<AssetName>: Class prim for inheritance

    Args:
        material_dict_list: Material texture dictionaries to publish.
        stage: Optional existing USD stage to author into.
        geo_file: Optional geometry USD file to payload.
        parent_path: Root prim path for the published asset (e.g., "/Asset").
        layer_save_path: Directory to save the USD layers.
        main_layer_name: File name for the main layer.
        create_usd_preview: Whether to create UsdPreviewSurface materials.
        create_arnold: Whether to create Arnold materials.
        create_mtlx: Whether to create MaterialX materials.
        create_openpbr: Whether to create MaterialX OpenPBR materials.
        texture_format_overrides: Optional per-renderer texture format overrides (usd_preview, arnold, mtlx, openpbr).
    """
    from .asset_structure import (
        initialize_component_asset,
        add_standard_scopes,
        add_payload,
    )

    if not layer_save_path:
        layer_save_path = f"{tempfile.gettempdir()}/temp_usd_export"
        os.makedirs(layer_save_path, exist_ok=True)
    layer_save_path = str(layer_save_path)
    os.makedirs(f"{layer_save_path}/layers", exist_ok=True)

    # Extract asset name from parent_path (e.g., "/Asset" -> "Asset")
    asset_name = parent_path.strip("/").split("/")[-1]

    # Create stage with ASWF-compliant structure
    if not stage:
        stage = Usd.Stage.CreateNew(f"{layer_save_path}/{main_layer_name}")

    # Initialize ASWF-compliant component asset (Kind, assetInfo, class inheritance)
    root_prim = initialize_component_asset(
        stage, asset_name, asset_identifier=f"./{main_layer_name}"
    )

    # Add standard geo/mtl scopes
    scopes = add_standard_scopes(stage, root_prim)
    geo_scope = scopes["geo"]
    mtl_scope = scopes["mtl"]

    # Create sublayers for materials and assignments
    layer_root = stage.GetRootLayer()

    layer_mats_path_abs = f"{layer_save_path}/layers/layer_mats.usda"
    layer_mats_rel_paths = os.path.relpath(layer_mats_path_abs, layer_save_path)
    layer_mats = Sdf.Layer.CreateNew(layer_mats_path_abs)
    layer_root.subLayerPaths.append(layer_mats_rel_paths)

    layer_assign_path_abs = f"{layer_save_path}/layers/layer_assign.usda"
    layer_assign_rel_paths = os.path.relpath(layer_assign_path_abs, layer_save_path)
    layer_assign = Sdf.Layer.CreateNew(layer_assign_path_abs)
    layer_root.subLayerPaths.append(layer_assign_rel_paths)

    # Add geometry payload if provided
    if geo_file:
        stage.SetEditTarget(layer_root)
        try:
            mesh_rel_path = os.path.relpath(geo_file, layer_save_path)
        except ValueError:
            mesh_rel_path = os.path.abspath(geo_file)

        # Use the geo scope's prim for payload reference
        geo_scope.GetPayloads().AddPayload(mesh_rel_path, f"{parent_path}/mesh/")

    # Create materials in mtl scope
    stage.SetEditTarget(layer_mats)
    material_primitive_path = mtl_scope.GetPath().pathString  # Use the /Asset/mtl path

    for material_dict in material_dict_list:
        material_name = next(
            (info["mat_name"] for info in material_dict.values()),
            "UnknownMaterialName",
        )
        USDShaderCreate(
            stage=stage,
            material_name=material_name,
            material_dict=material_dict,
            parent_primpath=material_primitive_path,
            create_usd_preview=create_usd_preview,
            create_arnold=create_arnold,
            create_mtlx=create_mtlx,
            create_openpbr=create_openpbr,
            texture_format_overrides=texture_format_overrides,
        )

    # Assign materials to geometry if present
    if geo_file:
        stage.SetEditTarget(layer_assign)
        USDShaderAssign(stage).run(
            mats_parent_path=material_primitive_path,
            mesh_parent_path=geo_scope.GetPath().pathString,  # Assign to /Asset/geo
        )

    # Save all layers
    layer_mats.Save()
    layer_assign.Save()
    layer_root.Save()

    logger.info(
        "Finished creating ASWF-compliant USD asset: '%s/%s' (Kind: component, assetInfo set).",
        layer_save_path,
        main_layer_name,
    )
    logger.info("Success")
