"""
Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.
"""

import sys
sys.path.append(r'G:\Projects\Dev\Github\SP_usd_creator\scripts')

from importlib import reload
import logging
from dataclasses import dataclass
from pathlib import Path
import substance_painter, substance_painter.ui, substance_painter.event, substance_painter.export
from PySide2.QtWidgets import QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QCheckBox, QHBoxLayout, QSpacerItem, QSizePolicy
from PySide2.QtCore import Qt
from pxr import Usd

import usd_material_processor
reload(usd_material_processor)
from material_classes import MaterialData, TextureInfo

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Hold references to UI widgets
ttplugin_widgets = []



@dataclass
class USDSettings:
    """
    USD export options container.

    Attributes:
        usdpreview (bool): Include UsdPreviewSurface shader.
        arnold (bool): Include Arnold standard_surface shader.
        materialx (bool): Include MaterialX shader.
        primitive_path (str): USD prim path for materials.
        publish_location (str): Path for output USD file.
        save_geometry (bool): Whether to export mesh geometry.
    """
    usdpreview: bool
    arnold: bool
    materialx: bool
    primitive_path: str
    publish_location: str
    save_geometry: bool


class TextureParser:
    """
    Parses Substance Painter texture exports into MaterialData objects.
    """
    def __init__(self, textures_dict, settings):
        self.textures_dict = textures_dict
        self.settings = settings

    def parse(self):
        """
        Build a list of MaterialData from exported textures.

        Returns:
            List of MaterialData
        """
        materials = []
        for (mat_name, _), paths in self.textures_dict.items():
            name = mat_name.replace(' ', '_')
            if not name[0].isalpha(): name = f"_{name}"
            prim_path = f"{self.settings.primitive_path}/{name}"
            tex_info = {}
            for p in paths:
                key = (
                    'albedo' if 'base_color' in p.lower() else
                    'metallic' if 'metallic' in p.lower() else
                    'roughness' if 'roughness' in p.lower() else
                    'normal' if 'normal' in p.lower() else
                    'occlusion'
                )
                tex_info[key] = TextureInfo(file_path=p, traversal_path='')
            md = MaterialData(name, prim_path, None, tex_info, [])
            logger.debug("Parsed MaterialData: %s", md)
            materials.append(md)
        return materials


class USDExporter:
    """
    Writes MaterialData into a USD stage using USDShaderCreator.
    """
    def __init__(self, settings):
        self.settings = settings
        self.stage = Usd.Stage.CreateNew(settings.publish_location)

    def write_materials(self, materials):
        """
        Create USD materials for each MaterialData and save the stage.

        Args:
            materials (List[MaterialData])
        """
        for md in materials:
            usd_material_processor.USDShaderCreator(
                self.stage, md,
                parent_prim=self.settings.primitive_path,
                create_usd_preview=self.settings.usdpreview,
                create_arnold=self.settings.arnold,
                create_mtlx=self.settings.materialx
            ).create()
        # Ensure directory exists before saving
        Path(self.settings.publish_location).parent.mkdir(parents=True, exist_ok=True)
        self.stage.GetRootLayer().Save()
        logger.info("Saved USD file to %s", self.settings.publish_location)


class MeshExporter:
    """
    Exports mesh geometry to USD if requested.
    """
    def __init__(self, settings):
        self.mesh_path = Path(settings.publish_location).with_name('mesh.usd')

    def export_mesh(self):
        """
        Call Substance Painter's USD mesh exporter.
        """
        logger.info("Exporting mesh to %s", self.mesh_path)
        try:
            substance_painter.export.export_mesh(
                str(self.mesh_path),
                substance_painter.export.MeshExportOption.BaseMesh
            )
        except Exception as e:
            logger.error("Mesh export failed: %s", e)


class USDExporterView(QDialog):
    """
    UI widget for USD export settings.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("USD Exporter")
        self.setLayout(QVBoxLayout())
        grid = QGridLayout(); grid.setAlignment(Qt.AlignTop)
        self.layout().addWidget(QLabel("Render engines:"))
        self.usdpreview = QCheckBox("USD Preview"); self.usdpreview.setChecked(True)
        self.arnold = QCheckBox("Arnold"); self.arnold.setChecked(True)
        self.materialx = QCheckBox("MaterialX [WIP]")
        grid.addWidget(self.usdpreview,0,1); grid.addWidget(self.arnold,1,1); grid.addWidget(self.materialx,2,1)
        self.layout().addLayout(grid)
        h1 = QHBoxLayout(); h1.addWidget(QLabel("Publish Location"));
        self.pub = QLineEdit("<export_folder>/materials.usda"); self.pub.setMinimumWidth(300)
        h1.addWidget(self.pub); h1.addItem(QSpacerItem(0,0,QSizePolicy.Expanding,QSizePolicy.Fixed))
        self.layout().addLayout(h1)
        h2 = QHBoxLayout(); h2.addWidget(QLabel("Primitive Path"));
        self.prim = QLineEdit("/RootNode/Materials"); self.prim.setMinimumWidth(300)
        h2.addWidget(self.prim); h2.addItem(QSpacerItem(0,0,QSizePolicy.Expanding,QSizePolicy.Fixed))
        self.layout().addLayout(h2)
        self.geom = QCheckBox("Save Geometry in USD File")
        self.layout().addWidget(self.geom)


    def get_settings(self):
        """
        Read UI state into USDSettings.

        Returns:
            USDSettings
        """
        return USDSettings(
            self.usdpreview.isChecked(),
            self.arnold.isChecked(),
            self.materialx.isChecked(),
            self.prim.text(),
            self.pub.text(),
            self.geom.isChecked()
        )







# Instantiate UI once
usd_exported_qdialog = USDExporterView()



def start_plugin():
    print("Plugin Starting...")
    substance_painter.ui.add_dock_widget(usd_exported_qdialog)
    plugin_widgets.append(usd_exported_qdialog)
    register_callbacks()


def register_callbacks():
    """Register the post-export callback"""
    print("Registered callbacks")
    substance_painter.event.DISPATCHER.connect(substance_painter.event.ExportTexturesEnded, on_post_export)


def on_post_export(context):
    """Function to be called after textures are exported"""
    print("ExportTexturesEnded emitted!!!")
    raw = usd_exported_qdialog.get_settings()
    # Resolve the <export_folder> token from first texture path
    first_tex = next(iter(context.textures.values()))[0]
    export_dir = Path(first_tex).parent
    publish = raw.publish_location.replace("<export_folder>", str(export_dir))
    settings = USDSettings(raw.usdpreview, raw.arnold, raw.materialx, raw.primitive_path, publish, raw.save_geometry)
    materials = TextureParser(context.textures, settings).parse()
    exporter = USDExporter(settings)
    exporter.write_materials(materials)
    if settings.save_geometry:
        MeshExporter(settings).export_mesh()


def close_plugin():
    """Remove all widgets that have been added to the UI"""
    print("Closing plugin")
    for widget in plugin_widgets:
        substance_painter.ui.delete_ui_element(widget)
    plugin_widgets.clear()
