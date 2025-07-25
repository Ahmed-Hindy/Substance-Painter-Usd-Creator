import sys
import os
from importlib import reload
from typing import Dict, Tuple, List


sys.path.append(r'G:\Projects\Dev\Github\SP_usd_creator\scripts')

import material_classes
import usd_material_processor
reload(material_classes)
reload(usd_material_processor)
from material_classes import MaterialData
from usd_material_processor import USD_Shader_Create

print(f'reloading done!')


from pxr import Usd
import substance_painter
import substance_painter.ui
import substance_painter.event
import substance_painter.project
import substance_painter.export
import substance_painter.resource
from PySide2.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QGridLayout, QLabel, QLineEdit, QSpacerItem, QSizePolicy
from PySide2.QtCore import Qt



"""
TODO 1. Add UDIM support. [DONE]
     2. add substance_painter.export.export_mesh()
     3. I have to work on material assignments so it automatically works when it overlays in houdini.

"""



plugin_widgets = []


def start_plugin():
    print("Plugin Starting...")

    global usd_exported_qdialog
    usd_exported_qdialog = USDExporterView()
    substance_painter.ui.add_dock_widget(usd_exported_qdialog)
    plugin_widgets.append(usd_exported_qdialog)
    register_callbacks()


def register_callbacks():
    """Register the post-export callback"""
    print("Registered callbacks")
    substance_painter.event.DISPATCHER.connect(substance_painter.event.ExportTexturesEnded, on_post_export)


def on_post_export(context):
    """Function to be called after textures are exported event"""
    print("ExportTexturesEnded emitted!!!")
    exported_textures: Dict[Tuple[str, str], List[str]]
    exported_textures = context.textures
    CreateUSD(usd_exported_qdialog, exported_textures).run()
    CreateUSD(usd_exported_qdialog, exported_textures).export_mesh_as_usd()


def close_plugin():
    """Remove all widgets that have been added to the UI"""
    print("Closing plugin")
    for widget in plugin_widgets:
        substance_painter.ui.delete_ui_element(widget)
    plugin_widgets.clear()


class CreateUSD:
    def __init__(self, usd_exported_qdialog, textures_dict=None):

        self.usd_exported_qdialog = usd_exported_qdialog
        self.textures_dict = textures_dict
        self.textures_publish_dir = self.extract_textures_publish_location(self.textures_dict)

        self.selected_options_dict = self.usd_exported_qdialog.get_selected_options()
        self.checkbox_create_usdpreview = self.selected_options_dict['usdpreview']
        self.checkbox_create_arnold = self.selected_options_dict['arnold']
        self.checkbox_create_materialx = self.selected_options_dict['materialx']
        self.material_primitive_path = self.selected_options_dict['primitive_path']
        self.save_geometry = self.selected_options_dict['save_geometry']
        self.usd_publish_location_with_token = self.selected_options_dict['publish_location']  # has <export_folder> token
        self.usd_publish_location = self.usd_publish_location_with_token.replace('<export_folder>', self.textures_publish_dir)
        self.project = substance_painter.project
        self.substance_painter_version = substance_painter.application.version_info()
        self.export_settings = None
        self.stage = None

    @staticmethod
    def extract_material_names(textures_dict) -> List[str]:
        """
        Extract material names from textures_dict
        :param textures_dict: dictionary we get from SP, format: Dict[Tuple[str, str], List[str]]
        :return: list of str of material names. e.g. ['Base mat', 'Body mat', 'Guns mat', 'Neck mat', 'Top mat']
        """
        return [material_name for (material_name, _), _ in textures_dict.items()]

    @staticmethod
    def extract_textures_for_material(textures_dict, material_name) -> List[str]:
        """
        Extract list of textures for a given material name
        :param textures_dict: dictionary we get from SP, format: Dict[Tuple[str, str], List[str]]
        :param material_name: str name of a material in scene, e.g.'Body mat'
        :return: list of strs for texture maps fll paths, e.g.
        ['F:/Body mat_Base_color_1001.png', 'F:/Body mat_Height_1001.png']
        """
        for (mat_name, stack_name), texture_list in textures_dict.items():
            if mat_name == material_name:
                return texture_list
        return []

    @staticmethod
    def extract_textures_publish_location(textures_dict) -> str:
        """
        Extract textures publish folder from textures_dict
        :return: string folder path for the first material encountered in the for loop
        """
        for (_, _), texture_list in textures_dict.items():
            textures_publish_dir = os.path.dirname(texture_list[0])
            textures_parent_directory = os.path.dirname(textures_publish_dir)
            return textures_parent_directory

    def convert_keys_to_strings(self, textures_dict: Dict[Tuple[str, str], List[str]]):
        """[tmp] for json dumping only!, Converts tuple keys to strings"""
        if isinstance(textures_dict, dict):
            return {str(k): self.convert_keys_to_strings(v) for k, v in textures_dict.items()}
        elif isinstance(textures_dict, list):
            return [self.convert_keys_to_strings(i) for i in textures_dict]
        else:
            return textures_dict

    @staticmethod
    def replace_udim_in_texture_path(tex_path):
        import re
        """
        Replace UDIM number in the texture path with <udim>.
        :param tex_path: str, texture file path
        :return: str, modified texture file path
        """
        # Regular expression to match UDIM numbers (1001, 1002, ..., 1099)
        udim_pattern = re.compile(r'10\d{2}')

        # Replace UDIM number with <udim>
        new_tex_path = udim_pattern.sub('<udim>', tex_path)

        return new_tex_path

    def create_materialdata(self) -> List[MaterialData]:
        """
        Create a MaterialData object from exported texture data.
        takes in self.textures_dict: Dict[Tuple[str, str], List[str]]
        :return: list of MaterialData object for all materials.
        """
        materialdata_list = []
        for (material_name, stack_name), texture_paths_list in self.textures_dict.items():
            material_name = material_name.replace(' ', '_')
            stack_name = stack_name.replace(' ', '_')

            if not material_name or not material_name[0].isalpha():
                # prefix with underscore if it doesn't start with a letter
                material_name = f"_{material_name}"

            material_path = f"{self.material_primitive_path}/{material_name}"
            print(f"\n  ///{material_name=}, {material_path=}")

            normalized_dict = {}
            for tex_path in texture_paths_list:
                tex_path = self.replace_udim_in_texture_path(tex_path)
                if "basecolor" in tex_path.lower():
                    normalized_dict["albedo"] = tex_path
                elif "base_color" in tex_path.lower():
                    normalized_dict["albedo"] = tex_path
                elif "metalness" in tex_path.lower():
                    normalized_dict["metallic"] = tex_path
                elif "metallic" in tex_path.lower():
                    normalized_dict["metallic"] = tex_path
                elif "roughness" in tex_path.lower():
                    normalized_dict["roughness"] = tex_path
                elif "normal" in tex_path.lower():
                    normalized_dict["normal"] = tex_path
                elif "ao" in tex_path.lower():
                    normalized_dict["occlusion"] = tex_path
                elif "height" in tex_path.lower():
                    normalized_dict["displacement"] = tex_path

            material_data = MaterialData(
                material_name=material_name, material_path=material_path, usd_material=None,
                textures={key: material_classes.TextureInfo(file_path=value, traversal_path='', connected_input='') for key, value in
                          normalized_dict.items()}
            )
            materialdata_list.append(material_data)
            print(f"Created MaterialData: {material_data}")
        return materialdata_list

    def write_material_to_usd(self, material_data) -> None:
        """Write MaterialData to a USD stage using USD_Shader_Create"""
        USD_Shader_Create(self.stage, material_data, parent_prim=self.material_primitive_path,
                          create_usd_preview=self.checkbox_create_usdpreview, create_arnold=self.checkbox_create_arnold,
                          create_mtlx=self.checkbox_create_materialx)

        print(f"Material USD file has been exported to {self.usd_publish_location}")

    def export_mesh_as_usd(self):
        """
        exports mesh to usd
        """
        print(f"{self.save_geometry=}")
        print(f"SP version: {self.substance_painter_version[0]}.{self.substance_painter_version[1]}")
        if not self.save_geometry:
            return
        if self.substance_painter_version[0] < 8 and self.substance_painter_version[1] < 3:
            print(f"Exporting Mesh as USD failed as this version of substance painter doesn't support usd yet.\n"
                  f"Please upgrade to v8.3 or higher")
            return

        substance_painter.export.export_mesh(f'{self.textures_publish_dir}/mesh.usd',
                                             substance_painter.export.MeshExportOption.BaseMesh)
        print(f"exported mesh to {f'{self.textures_publish_dir}/mesh.usd'}")

    def run(self):
        """ main run function """
        print("exporting usd....")
        self.stage = Usd.Stage.CreateNew(self.usd_publish_location)
        materialdata_list = self.create_materialdata()
        for materialdata in materialdata_list:
            self.write_material_to_usd(materialdata)
            self.stage.GetRootLayer().Save()


class USDExporterView(QDialog):
    def __init__(self, parent=None):
        super(USDExporterView, self).__init__(parent)

        self.setWindowTitle("USD Exporter")
        self.outer_layout = QVBoxLayout()
        self.setLayout(self.outer_layout)

        # Material options
        self.select_engines_label = QLabel("usd material will be created with the following render engines:")
        self.material_options_layout = QGridLayout()
        self.material_options_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.material_options_layout.setContentsMargins(10, 10, 10, 0)

        self.usdpreview_checkbox = QCheckBox("USD Preview")
        self.arnold_checkbox = QCheckBox("Arnold")
        self.materialx_checkbox = QCheckBox("MaterialX [WIP]")
        self.usdpreview_checkbox.setChecked(True)
        self.arnold_checkbox.setChecked(True)

        self.label_renderers = QLabel("Renderers             ")
        self.material_options_layout.addWidget(self.label_renderers, 0, 0)
        self.material_options_layout.addWidget(self.usdpreview_checkbox, 0, 1)
        self.material_options_layout.addWidget(self.arnold_checkbox, 1, 1)
        self.material_options_layout.addWidget(self.materialx_checkbox, 2, 1)

        # Material Publish Location
        self.publish_location_vbox = QHBoxLayout()
        self.publish_location_vbox.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.publish_location_label = QLabel("Publish Location ")
        self.publish_location_lineedit = QLineEdit("<export_folder>/materials.usda")
        self.publish_location_lineedit.setMaxLength(128)
        self.publish_location_lineedit.setMinimumWidth(300)
        self.publish_location_lineedit.setMaximumWidth(600)
        self.publish_location_lineedit.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.publish_location_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.publish_location_vbox.addWidget(self.publish_location_label)
        self.publish_location_vbox.addWidget(self.publish_location_lineedit)
        self.publish_location_vbox.addItem(self.publish_location_spacer)


        # USD Stage prim path
        self.stage_prim_path_vbox = QHBoxLayout()
        self.stage_prim_path_vbox.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.stage_prim_path_label = QLabel("Primitive Path")
        self.stage_prim_path_lineedit = QLineEdit("/RootNode/Materials")
        self.stage_prim_path_lineedit.setMaxLength(128)
        self.stage_prim_path_lineedit.setMinimumWidth(300)
        self.stage_prim_path_lineedit.setMaximumWidth(600)
        self.stage_prim_path_lineedit.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.stage_prim_path_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.stage_prim_path_vbox.addWidget(self.stage_prim_path_label)
        self.stage_prim_path_vbox.addWidget(self.stage_prim_path_lineedit)
        self.stage_prim_path_vbox.addItem(self.stage_prim_path_spacer)

        # Save geometry option
        self.save_geometry_checkbox = QCheckBox("Save Geometry in USD File")

        # add everything to the main layout
        self.outer_layout.addWidget(self.select_engines_label)
        self.outer_layout.addLayout(self.material_options_layout)
        self.outer_layout.addLayout(self.publish_location_vbox)
        self.outer_layout.addLayout(self.stage_prim_path_vbox)
        self.outer_layout.addWidget(self.save_geometry_checkbox)


    def get_selected_options(self):
        print(f"\n //{self.save_geometry_checkbox.isChecked()=}")
        return {
            "usdpreview": self.usdpreview_checkbox.isChecked(),
            "arnold": self.arnold_checkbox.isChecked(),
            "materialx": self.materialx_checkbox.isChecked(),
            "publish_location": self.publish_location_lineedit.text(),
            "primitive_path": self.stage_prim_path_lineedit.text(),
            "save_geometry": self.save_geometry_checkbox.isChecked()
        }

