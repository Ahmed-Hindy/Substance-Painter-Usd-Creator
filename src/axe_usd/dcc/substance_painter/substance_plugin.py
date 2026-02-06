"""Substance Painter plugin for exporting USD assets.

Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

import gc
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Mapping, Optional, Protocol, Sequence, Tuple

from ...core.exporter import export_publish
from ...core.exceptions import (
    AxeUSDError,
    ConfigurationError,
    GeometryExportError,
    MaterialExportError,
    USDStageError,
    ValidationError,
)
from ...core.fs_utils import ensure_directory
from ...core.models import ExportSettings
from ...core.publish_paths import build_publish_paths
from ...core.texture_parser import parse_textures
from ...usd.pxr_writer import PxrUsdWriter

from . import usd_scene_fixup
from .logging_utils import configure_logging, set_base_log_level
from .qt_compat import QMessageBox
from .ui import LOG_LEVELS, USDExporterView
import substance_painter.application
import substance_painter.event
import substance_painter.export
import substance_painter.textureset
import substance_painter.ui


configure_logging(__name__)
logger = logging.getLogger(__name__)
logger.propagate = True

DEFAULT_PRIMITIVE_PATH = "/Asset"
USD_PREVIEW_JPEG_SIZE_LOG2 = 7  # 128px
USD_PREVIEW_JPEG_SUFFIX = ".jpg"
USD_PREVIEW_RESOLUTION_LOG2 = {
    128: 7,
    256: 8,
    512: 9,
    1024: 10,
}
PREVIEW_TEXTURE_DIRNAME = "previewTextures"
PREVIEW_EXPORT_PRESET = "AxeUSDPreview"
PREVIEW_EXPORT_PRESET_UDIM = "AxeUSDPreviewUDIM"

# Hold references to UI widgets
plugin_widgets = []
usd_exported_qdialog = None
callbacks_registered = False


class MeshExporter:
    """
    Exports mesh geometry to USD if requested.
    """

    def __init__(self, settings: ExportSettings, skip_postprocess: bool = False):
        """Initialize the mesh exporter.

        Args:
            settings: Export settings for determining output paths.
            skip_postprocess: Skip fixup/conversion and leave raw export untouched.
        """
        # Extract asset name from settings (e.g. primitive_path="/Asset" -> "Asset")
        asset_name = settings.primitive_path.strip("/").split("/")[-1]

        publish_paths = build_publish_paths(
            settings.publish_directory, settings.main_layer_name, asset_name
        )
        self.mesh_path = publish_paths.geometry_path
        self.root_prim_path = DEFAULT_PRIMITIVE_PATH
        self.skip_postprocess = skip_postprocess
        self.last_error: str = ""

    def export_mesh(self) -> Optional[Path]:
        """Call Substance Painter's USD mesh exporter.

        Returns:
            Optional[Path]: Path to the exported mesh if successful.
        """
        ensure_directory(self.mesh_path.parent)
        logger.info("Exporting mesh to %s", self.mesh_path)
        logger.debug("Mesh export target suffix: %s", self.mesh_path.suffix)
        export_path = self.mesh_path
        convert_to_usdc = False
        if self.mesh_path.suffix.lower() == ".usdc":
            convert_to_usdc = True
            export_path = self.mesh_path.with_suffix(".usd")
            logger.info(
                "Mesh export target is .usdc; exporting to %s then converting.",
                export_path,
            )

        # Choose an export option to use
        export_option = substance_painter.export.MeshExportOption.BaseMesh
        if not substance_painter.export.scene_is_triangulated():
            export_option = substance_painter.export.MeshExportOption.TriangulatedMesh
        if substance_painter.export.scene_has_tessellation():
            export_option = (
                substance_painter.export.MeshExportOption.TessellationNormalsBaseMesh
            )

        try:
            export_result = substance_painter.export.export_mesh(
                str(export_path), export_option
            )

            # In case of error, display a human readable message:
            if export_result.status != substance_painter.export.ExportStatus.Success:
                raise GeometryExportError(
                    "Mesh export failed.",
                    details={
                        "status": str(export_result.status),
                        "message": str(export_result.message),
                    },
                )
            logger.debug(
                "Mesh export status=%s message=%s",
                export_result.status,
                export_result.message,
            )
            if not export_path.exists():
                raise GeometryExportError(
                    "Mesh export reported success but file is missing.",
                    details={"path": str(export_path)},
                )
            if self.skip_postprocess:
                logger.info("Skipping mesh fixup/conversion for testing.")
                return export_path
            if convert_to_usdc:
                from pxr import Usd

                stage = Usd.Stage.Open(str(export_path))
                if not stage:
                    raise USDStageError(
                        "Failed to open temporary mesh for conversion.",
                        details={"path": str(export_path)},
                    )
                usd_scene_fixup.fix_sp_mesh_stage(stage, self.root_prim_path)
                stage.GetRootLayer().Export(str(self.mesh_path))
                if not self.mesh_path.exists():
                    raise GeometryExportError(
                        "Mesh conversion reported success but file is missing.",
                        details={"path": str(self.mesh_path)},
                    )
                stage = None
                gc.collect()
                if export_path.exists():
                    try:
                        export_path.unlink()
                    except Exception as cleanup_exc:
                        logger.warning(
                            "Failed to remove temporary mesh file %s: %s",
                            export_path,
                            cleanup_exc,
                        )
            return self.mesh_path
        except AxeUSDError as exc:
            self.last_error = exc.message
            if exc.details:
                logger.warning("Mesh export failed: %s (%s)", exc.message, exc.details)
            else:
                logger.warning("Mesh export failed: %s", exc.message)
            return None
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("Mesh export failed: %s", exc)
            return None


def _collect_texture_set_names(
    textures: Mapping[Tuple[str, str], Sequence[str]],
) -> Sequence[str]:
    names: list[str] = []
    for key in textures.keys():
        if isinstance(key, (tuple, list)) and key:
            name = str(key[0])
        else:
            name = str(key)
        if name and name not in names:
            names.append(name)
    return names


def _collect_mesh_name_map(
    texture_set_names: Sequence[str],
) -> Dict[str, list[str]]:
    """Collect mesh name assignments for the exported texture sets."""
    assignments: Dict[str, list[str]] = {}
    try:
        all_texture_sets = substance_painter.textureset.all_texture_sets()
    except Exception as exc:
        logger.warning("Failed to read texture sets for mesh assignments: %s", exc)
        return assignments

    target_names = {str(name) for name in texture_set_names if name}
    for texture_set in all_texture_sets:
        try:
            set_name = str(texture_set.name())
        except Exception as exc:
            logger.warning("Failed to read texture set name: %s", exc)
            continue
        if target_names and set_name not in target_names:
            continue
        try:
            mesh_names = texture_set.all_mesh_names()
        except Exception as exc:
            logger.warning(
                "Failed to read mesh names for texture set %s: %s", set_name, exc
            )
            mesh_names = []
        cleaned: list[str] = []
        for mesh_name in mesh_names or []:
            mesh_str = str(mesh_name)
            if mesh_str and mesh_str not in cleaned:
                cleaned.append(mesh_str)
        if set_name:
            assignments[set_name] = cleaned
            logger.debug(
                "Texture set '%s' assigned to meshes: %s", set_name, cleaned
            )
    return assignments


def _build_preview_export_config(
    preview_dir: Path,
    texture_sets: Sequence[str],
    resolution: int,
    udim_texture_sets: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    udim_set = {name for name in (udim_texture_sets or []) if name}
    export_list = []
    for name in texture_sets:
        preset = (
            PREVIEW_EXPORT_PRESET_UDIM
            if name in udim_set
            else PREVIEW_EXPORT_PRESET
        )
        export_list.append({"rootPath": name, "exportPreset": preset})
    size_log2 = USD_PREVIEW_RESOLUTION_LOG2.get(resolution, USD_PREVIEW_JPEG_SIZE_LOG2)
    export_preset = {
        "name": PREVIEW_EXPORT_PRESET,
        "maps": [
            {
                "fileName": "$textureSet_BaseColor",
                "channels": [
                    {
                        "destChannel": "R",
                        "srcChannel": "R",
                        "srcMapType": "documentMap",
                        "srcMapName": "baseColor",
                    },
                    {
                        "destChannel": "G",
                        "srcChannel": "G",
                        "srcMapType": "documentMap",
                        "srcMapName": "baseColor",
                    },
                    {
                        "destChannel": "B",
                        "srcChannel": "B",
                        "srcMapType": "documentMap",
                        "srcMapName": "baseColor",
                    },
                ],
                "parameters": {
                    "fileFormat": USD_PREVIEW_JPEG_SUFFIX.lstrip("."),
                    "bitDepth": "8",
                    "dithering": False,
                    "sizeLog2": size_log2,
                    "paddingAlgorithm": "diffusion",
                    "dilationDistance": 16,
                },
            }
        ],
    }
    export_presets = [export_preset]
    if udim_set:
        export_presets.append(
            {
                "name": PREVIEW_EXPORT_PRESET_UDIM,
                "maps": [
                    {
                        "fileName": "$textureSet_BaseColor.$udim",
                        "channels": [
                            {
                                "destChannel": "R",
                                "srcChannel": "R",
                                "srcMapType": "documentMap",
                                "srcMapName": "baseColor",
                            },
                            {
                                "destChannel": "G",
                                "srcChannel": "G",
                                "srcMapType": "documentMap",
                                "srcMapName": "baseColor",
                            },
                            {
                                "destChannel": "B",
                                "srcChannel": "B",
                                "srcMapType": "documentMap",
                                "srcMapName": "baseColor",
                            },
                        ],
                        "parameters": {
                            "fileFormat": USD_PREVIEW_JPEG_SUFFIX.lstrip("."),
                            "bitDepth": "8",
                            "dithering": False,
                            "sizeLog2": size_log2,
                            "paddingAlgorithm": "diffusion",
                            "dilationDistance": 16,
                        },
                    }
                ],
            }
        )
    return {
        "exportPath": str(preview_dir),
        "defaultExportPreset": PREVIEW_EXPORT_PRESET,
        "exportPresets": export_presets,
        "exportList": export_list,
        "exportShaderParams": False,
    }


def _export_usdpreview_textures(
    textures_dir: Path,
    texture_sets: Sequence[str],
    resolution: int,
    udim_texture_sets: Optional[Sequence[str]] = None,
) -> None:
    if not texture_sets:
        raise ValidationError("UsdPreview export failed: no texture sets found.")

    ensure_directory(textures_dir)
    preview_dir = textures_dir / PREVIEW_TEXTURE_DIRNAME
    ensure_directory(preview_dir)
    export_config = _build_preview_export_config(
        preview_dir, texture_sets, resolution, udim_texture_sets=udim_texture_sets
    )
    logger.debug("UsdPreview texture sets: %s", texture_sets)
    if udim_texture_sets:
        logger.debug("UsdPreview UDIM texture sets: %s", sorted(udim_texture_sets))
    export_fn = getattr(substance_painter.export, "export_project_textures", None)
    if export_fn is None:
        raise ConfigurationError(
            "UsdPreview export failed: export_project_textures not available."
        )

    logger.debug("UsdPreview export config: %s", export_config)
    try:
        result = export_fn(export_config)
    except Exception as exc:
        raise MaterialExportError(
            "UsdPreview export failed.",
            details={"error": str(exc)},
        ) from exc

    status = getattr(result, "status", None)
    message = getattr(result, "message", "")
    export_status = getattr(substance_painter.export, "ExportStatus", None)
    if export_status and hasattr(export_status, "Success") and status is not None:
        if status != export_status.Success:
            raise MaterialExportError(
                "UsdPreview export failed.",
                details={"status": str(status), "message": str(message)},
            )
    elif result is False:
        raise MaterialExportError(
            "UsdPreview export failed.",
            details={"result": str(result)},
        )


def _move_exported_textures(
    textures: Mapping[Tuple[str, str], Sequence[str]], textures_dir: Path
) -> Mapping[Tuple[str, str], Sequence[str]]:
    ensure_directory(textures_dir)
    updated: dict[Tuple[str, str], list[str]] = {}
    for key, paths in textures.items():
        new_paths: list[str] = []
        for path in paths:
            if not path:
                continue
            src = Path(path)
            if not src.exists():
                raise ValidationError(
                    "Exported texture file missing.",
                    details={"path": str(src)},
                )
            if src.parent == textures_dir:
                new_paths.append(str(src))
                continue
            dest = textures_dir / src.name
            if dest.exists():
                if dest.stat().st_mtime < src.stat().st_mtime:
                    dest.unlink()
                    shutil.move(str(src), str(dest))
                else:
                    src.unlink()
            else:
                shutil.move(str(src), str(dest))
            new_paths.append(str(dest))
        updated[key] = new_paths
    return updated


def _is_preview_export_context(context: "ExportContext") -> bool:
    texture_paths = [
        Path(path) for paths in context.textures.values() for path in paths if path
    ]
    if not texture_paths:
        return False
    preview_token = PREVIEW_TEXTURE_DIRNAME.lower()
    for path in texture_paths:
        try:
            parts = path.parts
        except Exception:
            return False
        if not any(part.lower() == preview_token for part in parts):
            return False
    return True


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


# Entry-point functions required by Substance Painter
class ExportContext(Protocol):
    """Substance Painter export context interface."""

    textures: Mapping[Tuple[str, str], Sequence[str]]


def start_plugin() -> None:
    """Create the export UI and register callbacks."""
    logger.info("Plugin starting.")

    if substance_painter.application.version_info() < (8, 3, 0):
        logger.error(
            "Axe USD Exporter requires Substance Painter 8.3.0 or later. Plugin disabled."
        )
        return

    global usd_exported_qdialog
    usd_exported_qdialog = USDExporterView(logger=logger)
    substance_painter.ui.add_dock_widget(usd_exported_qdialog)
    plugin_widgets.append(usd_exported_qdialog)
    register_callbacks()


def register_callbacks() -> None:
    """Register the post-export callback."""
    logger.info("Registered callbacks.")
    global callbacks_registered
    if callbacks_registered:
        return
    substance_painter.event.DISPATCHER.connect(
        substance_painter.event.ExportTexturesEnded, on_post_export
    )
    callbacks_registered = True


def on_post_export(context: ExportContext) -> None:
    """Handle the texture export completion event.

    Args:
        context: Substance Painter export context.
    """
    logger.info("ExportTexturesEnded emitted.")
    if _is_preview_export_context(context):
        logger.info("Preview texture export detected; skipping USD publish.")
        return
    try:
        if usd_exported_qdialog is None:
            raise ConfigurationError("USD Export UI is not available.")
        if not context.textures:
            raise ValidationError("No textures were exported.")

        empty_sets = [key for key, paths in context.textures.items() if not paths]
        if empty_sets:
            empty_names = _collect_texture_set_names({key: [] for key in empty_sets})
            raise ValidationError(
                "Texture set exported no files.",
                details={"texture_sets": empty_names},
            )

        first_path = next(
            (paths[0] for paths in context.textures.values() if paths), None
        )
        if not first_path:
            raise ValidationError("No exported texture files found.")
        export_dir = Path(first_path).parent

        raw = usd_exported_qdialog.get_settings()
        log_level = LOG_LEVELS.get(raw.log_level)
        if log_level is not None:
            set_base_log_level(log_level)
            logger.setLevel(log_level)
        primitive_path = DEFAULT_PRIMITIVE_PATH
        publish_dir = str(export_dir)

        if _env_flag("AXEUSD_STOP_AFTER_MESH_EXPORT"):
            if not raw.save_geometry:
                raise ValidationError(
                    "Save Geometry must be enabled to stop after mesh export."
                )
            settings = ExportSettings(
                usdpreview=raw.usdpreview,
                arnold=raw.arnold,
                materialx=raw.materialx,
                openpbr=raw.openpbr,
                primitive_path=primitive_path,
                publish_directory=Path(publish_dir),
                save_geometry=True,
                texture_format_overrides=raw.texture_format_overrides or None,
            )
            mesh_exporter = MeshExporter(settings, skip_postprocess=True)
            geo_file = mesh_exporter.export_mesh()
            if geo_file is None:
                raise GeometryExportError(
                    "Mesh export failed.",
                    details={"message": mesh_exporter.last_error},
                )
            if usd_exported_qdialog is not None:
                QMessageBox.information(
                    usd_exported_qdialog,
                    "USD Exporter",
                    f"Mesh export complete.\n\nMesh file:\n{geo_file}",
                )
            return
        asset_name = primitive_path.strip("/").split("/")[-1]
        textures_dir = export_dir / asset_name / "textures"
        textures = _move_exported_textures(context.textures, textures_dir)

        texture_sets = _collect_texture_set_names(textures)
        mesh_name_map = _collect_mesh_name_map(texture_sets)
        materials = parse_textures(textures, mesh_name_map=mesh_name_map)
        if not materials:
            raise ValidationError("No recognized textures were found.")
        udim_texture_sets = tuple(
            sorted({bundle.name for bundle in materials if bundle.udim_slots})
        )

        texture_overrides = dict(raw.texture_format_overrides or {})
        if raw.usdpreview:
            _export_usdpreview_textures(
                textures_dir,
                texture_sets,
                raw.usdpreview_resolution,
                udim_texture_sets=udim_texture_sets,
            )

        settings = ExportSettings(
            usdpreview=raw.usdpreview,
            arnold=raw.arnold,
            materialx=raw.materialx,
            openpbr=raw.openpbr,
            primitive_path=primitive_path,
            publish_directory=Path(publish_dir),
            save_geometry=raw.save_geometry,
            texture_format_overrides=texture_overrides or None,
        )

        geo_file = None
        if settings.save_geometry:
            mesh_exporter = MeshExporter(settings)
            geo_file = mesh_exporter.export_mesh()
            if geo_file is None:
                raise GeometryExportError(
                    "Mesh export failed.",
                    details={"message": mesh_exporter.last_error},
                )

        export_publish(materials, settings, geo_file, PxrUsdWriter())
    except AxeUSDError as exc:
        logger.error("USD export failed: %s", exc.message)
        if exc.details:
            logger.error("USD export details: %s", exc.details)
        if usd_exported_qdialog is not None:
            detail = f"\n\nDetails: {exc.details}" if exc.details else ""
            QMessageBox.critical(
                usd_exported_qdialog,
                "USD Exporter",
                f"USD export failed:\n{exc.message}{detail}",
            )
        return
    except Exception as exc:
        logger.exception("USD export failed: %s", exc)
        if usd_exported_qdialog is not None:
            QMessageBox.critical(
                usd_exported_qdialog,
                "USD Exporter",
                f"USD export failed:\n{exc}\n\nCheck the logs for more details.",
            )
        return

    QMessageBox.information(
        usd_exported_qdialog,
        "USD Exporter",
        f"USD export complete.\n\nPublish folder:\n{settings.publish_directory}",
    )


def close_plugin() -> None:
    """Remove all widgets that have been added to the UI."""
    logger.info("Closing plugin.")
    global callbacks_registered, usd_exported_qdialog
    if callbacks_registered:
        try:
            substance_painter.event.DISPATCHER.disconnect(
                substance_painter.event.ExportTexturesEnded, on_post_export
            )
        except Exception as e:
            logger.warning("close_plugin() failed to disconnect event handler: %s", e)
        callbacks_registered = False
    for widget in plugin_widgets:
        substance_painter.ui.delete_ui_element(widget)
    plugin_widgets.clear()
    usd_exported_qdialog = None
