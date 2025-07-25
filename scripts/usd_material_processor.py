"""
Copyright Ahmed Hindy. Please mention the author if you found any part of this code useful.

"""
from importlib import reload
import json
from pprint import pprint
from pxr import Usd, UsdShade, UsdGeom, Sdf


import material_classes
from material_classes import MaterialData



class USD_Shader_Create:
    """
    Creates a collect usd material on stage with Arnold and/or UsdPreview materials. Assigns material to prims
    """
    def __init__(self, stage, material_data: MaterialData, parent_prim='/scene/material_py/', create_usd_preview=True,
                 create_arnold=True, create_mtlx=False):
        self.stage = stage
        self.material_data = material_data
        self.parent_prim = parent_prim
        self.prims_assigned_to_the_mat = material_data.prims_assigned_to_material
        self.create_usd_preview = create_usd_preview
        self.create_arnold = create_arnold
        self.create_mtlx = create_mtlx
        self.newly_created_usd_mat = None

        self.create_usd_material()

        print(f"\n{self.stage=}\n{self.material_data=}\n{self.prims_assigned_to_the_mat=}\n{self.create_usd_preview=}\n"
              f"{self.create_mtlx=}\n{self.create_arnold=}\n{self.newly_created_usd_mat=}\n"
              f"{material_data.material_name=}\n{material_data.material_path=}\n{material_data.usd_material=}\n"
              f"{material_data.textures=}\n{material_data.prims_assigned_to_material=}\n")

    def _create_usd_preview_material(self, parent_path):
        material_path = f'{parent_path}/UsdPreviewMaterial'
        material = UsdShade.Material.Define(self.stage, material_path)

        nodegraph_path = f'{material_path}/UsdPreviewNodeGraph'
        nodegraph = self.stage.DefinePrim(nodegraph_path, 'NodeGraph')

        shader_path = f'{nodegraph_path}/UsdPreviewSurface'
        shader = UsdShade.Shader.Define(self.stage, shader_path)
        shader.CreateIdAttr("UsdPreviewSurface")

        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

        # Create textures for USD Preview Shader
        texture_types_to_inputs = {
            'albedo': 'diffuseColor',
            'metallness': 'metallic',
            'roughness': 'roughness',
            'normal': 'normal',
            # 'occlusion': 'occlusion'  # we dont need occlusion for now.
        }

        for tex_type, tex_info in self.material_data.textures.items():
            if tex_type not in texture_types_to_inputs:
                continue

            input_name = texture_types_to_inputs[tex_type]
            texture_prim_path = f'{nodegraph_path}/{tex_type}Texture'
            texture_prim = UsdShade.Shader.Define(self.stage, texture_prim_path)
            texture_prim.CreateIdAttr("UsdUVTexture")
            file_input = texture_prim.CreateInput("file", Sdf.ValueTypeNames.Asset)
            file_input.Set(tex_info.file_path)

            wrapS = texture_prim.CreateInput("wrapS", Sdf.ValueTypeNames.Token)
            wrapT = texture_prim.CreateInput("wrapT", Sdf.ValueTypeNames.Token)
            wrapS.Set('repeat')
            wrapT.Set('repeat')

            # Create Primvar Reader for ST coordinates
            st_reader_path = f'{nodegraph_path}/TexCoordReader' ### TODO: remove it from the for loop.
            st_reader = UsdShade.Shader.Define(self.stage, st_reader_path)
            st_reader.CreateIdAttr("UsdPrimvarReader_float2")
            st_input = st_reader.CreateInput("varname", Sdf.ValueTypeNames.Token)
            st_input.Set("st")
            texture_prim.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_reader.ConnectableAPI(), "result")

            if tex_type in ['opacity', 'metallic', 'roughness']:
                shader.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(texture_prim.ConnectableAPI(),
                                                                                          "r")
            else:
                shader.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(texture_prim.ConnectableAPI(),
                                                                                          "rgb")

        return material

    def _arnold_create_material(self, parent_path):
        shader_path = f'{parent_path}/standard_surface1'
        shader = UsdShade.Shader.Define(self.stage, shader_path)
        shader.CreateIdAttr("arnold:standard_surface")
        material_prim = shader.GetPrim().GetParent()
        material_usdshade = UsdShade.Material.Define(self.stage, material_prim.GetPath())
        material_usdshade.CreateOutput("arnold:surface", Sdf.ValueTypeNames.Token).ConnectToSource(shader.ConnectableAPI(), "surface")

        self._arnold_initialize_shader(shader)
        self._arnold_fill_texture_file_paths(material_prim, shader)
        return material_usdshade

    def _arnold_initialize_shader(self, shader_usdshade):
        shader_usdshade.CreateInput('base', Sdf.ValueTypeNames.Float).Set(1.0)
        shader_usdshade.CreateInput('base_color', Sdf.ValueTypeNames.Float3).Set((0.8, 0.8, 0.8))
        shader_usdshade.CreateInput('metalness', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('specular', Sdf.ValueTypeNames.Float).Set(1.0)
        shader_usdshade.CreateInput('specular_color', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('specular_roughness', Sdf.ValueTypeNames.Float).Set(0.2)
        shader_usdshade.CreateInput('specular_IOR', Sdf.ValueTypeNames.Float).Set(1.5)
        shader_usdshade.CreateInput('specular_anisotropy', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('specular_rotation', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('coat', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('coat_color', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('coat_roughness', Sdf.ValueTypeNames.Float).Set(0.1)
        shader_usdshade.CreateInput('coat_IOR', Sdf.ValueTypeNames.Float).Set(1.5)
        shader_usdshade.CreateInput('coat_normal', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('coat_affect_color', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('coat_affect_roughness', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('transmission', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('transmission_color', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('transmission_depth', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('transmission_scatter', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('transmission_scatter_anisotropy', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('transmission_dispersion', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('transmission_extra_roughness', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('subsurface', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('subsurface_color', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('subsurface_radius', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('subsurface_scale', Sdf.ValueTypeNames.Float).Set(1.0)
        shader_usdshade.CreateInput('subsurface_anisotropy', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('emission', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('emission_color', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('opacity', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('thin_walled', Sdf.ValueTypeNames.Bool).Set(False)
        shader_usdshade.CreateInput('sheen', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('sheen_color', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('sheen_roughness', Sdf.ValueTypeNames.Float).Set(0.3)
        shader_usdshade.CreateInput('indirect_diffuse', Sdf.ValueTypeNames.Float).Set(1.0)
        shader_usdshade.CreateInput('indirect_specular', Sdf.ValueTypeNames.Float).Set(1.0)
        shader_usdshade.CreateInput('internal_reflections', Sdf.ValueTypeNames.Bool).Set(True)
        shader_usdshade.CreateInput('caustics', Sdf.ValueTypeNames.Bool).Set(False)
        shader_usdshade.CreateInput('exit_to_background', Sdf.ValueTypeNames.Bool).Set(False)
        shader_usdshade.CreateInput('aov_id1', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('aov_id2', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('aov_id3', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('aov_id4', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('aov_id5', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('aov_id6', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('aov_id7', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('aov_id8', Sdf.ValueTypeNames.Float3).Set((0.0, 0.0, 0.0))
        shader_usdshade.CreateInput('transmit_aovs', Sdf.ValueTypeNames.Bool).Set(False)

    def _arnold_fill_texture_file_paths(self, material_prim, shader):
        """
        Fills the texture file paths for the given shader using the material_data.
        """
        texture_types_to_inputs = {
            'albedo': 'base_color',
            'metallness': 'metalness',
            'roughness': 'specular_roughness',
            'normal': 'normal',
            'opacity': 'opacity'
        }
        print(f"{self.material_data=}\n\n")
        for tex_type, tex_info in self.material_data.textures.items():
            if tex_type not in texture_types_to_inputs:
                continue
            input_name = texture_types_to_inputs[tex_type]
            texture_prim_path = f'{material_prim.GetPath()}/{tex_type}Texture'
            texture_prim = UsdShade.Shader.Define(self.stage, texture_prim_path)
            texture_prim.CreateIdAttr("arnold:image")
            file_input = texture_prim.CreateInput("filename", Sdf.ValueTypeNames.Asset)
            file_input.Set(tex_info.file_path)
            shader.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(texture_prim.ConnectableAPI(),
                                                                                      "rgba")
            # EXPERIMENTAL
            if tex_type == 'opacity':
                shader.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(texture_prim.ConnectableAPI(),
                                                                                          "r")


###  mtlx ###
    def _mtlx_create_material(self, parent_path):
        shader_path = f'{parent_path}/mtlxstandard_surface'
        shader_usdshade = UsdShade.Shader.Define(self.stage, shader_path)
        shader_usdshade.CreateIdAttr("ND_standard_surface_surfaceshader")
        material_prim = shader_usdshade.GetPrim().GetParent()
        material_usdshade = UsdShade.Material.Define(self.stage, material_prim.GetPath())
        material_usdshade.CreateOutput("mtlx:surface", Sdf.ValueTypeNames.Token).ConnectToSource(shader_usdshade.ConnectableAPI(), "surface")

        self._mtlx_initialize_shader(shader_usdshade)
        self._mtlx_fill_texture_file_paths(material_prim, shader_usdshade)
        return material_usdshade

    def _mtlx_initialize_shader(self, shader_usdshade):
        shader_usdshade.CreateInput('base', Sdf.ValueTypeNames.Float).Set(1.0)
        shader_usdshade.CreateInput('base_color', Sdf.ValueTypeNames.Float3).Set((0.8, 0.8, 0.8))
        shader_usdshade.CreateInput('coat', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('coat_roughness', Sdf.ValueTypeNames.Float).Set(0.1)
        shader_usdshade.CreateInput('emission', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('emission_color', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('metalness', Sdf.ValueTypeNames.Float).Set(0.0)
        shader_usdshade.CreateInput('specular', Sdf.ValueTypeNames.Float).Set(1.0)
        shader_usdshade.CreateInput('specular_color', Sdf.ValueTypeNames.Float3).Set((1.0, 1.0, 1.0))
        shader_usdshade.CreateInput('specular_IOR', Sdf.ValueTypeNames.Float).Set(1.5)
        shader_usdshade.CreateInput('specular_roughness', Sdf.ValueTypeNames.Float).Set(0.2)
        shader_usdshade.CreateInput('transmission', Sdf.ValueTypeNames.Float).Set(0.0)


    def _mtlx_fill_texture_file_paths(self, material_prim, shader_usdshade):
        """
        Fills the texture file paths for the given shader using the material_data.
        """
        texture_types_to_inputs = {
            'albedo': 'base_color',
            'metallness': 'metalness',
            'roughness': 'specular_roughness',
            'normal': 'normal',
            # 'opacity': 'opacity'  # no opacity?
        }
        print(f"{self.material_data=}\n\n")
        for tex_type, tex_info in self.material_data.textures.items():
            if tex_type not in texture_types_to_inputs:
                continue
            input_name = texture_types_to_inputs[tex_type]
            texture_prim_path = f'{material_prim.GetPath()}/{tex_type}_texture'
            texture_prim = UsdShade.Shader.Define(self.stage, texture_prim_path)
            if tex_type == 'albedo':
                texture_prim.CreateIdAttr("ND_image_color3")
            else:
                texture_prim.CreateIdAttr("ND_image_float")

            file_input = texture_prim.CreateInput("file", Sdf.ValueTypeNames.Asset)
            file_input.Set(tex_info.file_path)
            shader_usdshade.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(
                texture_prim.ConnectableAPI(), "rgba")
            # EXPERIMENTAL
            if tex_type == 'opacity':
                shader_usdshade.CreateInput(input_name, Sdf.ValueTypeNames.Float3).ConnectToSource(
                    texture_prim.ConnectableAPI(), "r")


    def _create_collect_prim(self, create_usd_preview=True, create_arnold=True, create_mtlx=False) -> UsdShade.Material:
        """
        creates a collect material prim on stage
        :return: UsdShade.Material of the collect prim
        """
        collect_prim_path = f'{self.parent_prim}/{self.material_data.material_name}_collect'
        print(f"DEBUG: {collect_prim_path=}")
        if not self.parent_prim:
            UsdGeom.Scope.Define(self.stage, self.parent_prim)

        collect_usd_material = UsdShade.Material.Define(self.stage, collect_prim_path)
        collect_usd_material.CreateInput("inputnum", Sdf.ValueTypeNames.Int).Set(2)

        if create_usd_preview:
            # Create the USD Preview Shader under the collect material
            usd_preview_material = self._create_usd_preview_material(collect_prim_path)
            usd_preview_shader = usd_preview_material.GetSurfaceOutput().GetConnectedSource()[0]
            collect_usd_material.CreateOutput("surface", Sdf.ValueTypeNames.Token).ConnectToSource(usd_preview_shader, "surface")

        if create_arnold:
            # Create the Arnold Shader under the collect material
            arnold_material = self._arnold_create_material(collect_prim_path)
            arnold_shader = arnold_material.GetOutput("arnold:surface").GetConnectedSource()[0]
            collect_usd_material.CreateOutput("arnold:surface", Sdf.ValueTypeNames.Token).ConnectToSource(arnold_shader, "surface")

        if create_mtlx:
            # Create the mtlx Shader under the collect material
            mtlx_material = self._mtlx_create_material(collect_prim_path)
            mtlx_shader = mtlx_material.GetOutput("mtlx:surface").GetConnectedSource()[0]
            collect_usd_material.CreateOutput("mtlx:surface", Sdf.ValueTypeNames.Token).ConnectToSource(mtlx_shader, "surface")

        return collect_usd_material


    def _assign_material_to_primitives(self, new_material: UsdShade.Material) -> None:
        """
        Reassigns a new USD material to a list of primitives.
        :param new_material: UsdShade.Material primitive to assign to the primitives
        """
        if not new_material or not isinstance(new_material, UsdShade.Material):
            raise ValueError(f"New material is not a <UsdShade.Material> object, instead it's a {type(new_material)}.")

        for prim in self.prims_assigned_to_the_mat:
            UsdShade.MaterialBindingAPI(prim).Bind(new_material)


    def create_usd_material(self):
        """
        Main function to run. will create a collect material with Arnold and usdPreview shaders in stage.
        """
        self.newly_created_usd_mat = self._create_collect_prim(create_usd_preview=self.create_usd_preview,
                                                               create_arnold=self.create_arnold, create_mtlx=self.create_mtlx)
        # print(f"{self.newly_created_usd_mat=}")
        self._assign_material_to_primitives(self.newly_created_usd_mat)
