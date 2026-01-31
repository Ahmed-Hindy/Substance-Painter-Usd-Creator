![Screenshot_1.png](Examples/images/Screenshot_1.png)

# Substance Painter USD Export Plugin
This plugin allows you to export materials and geometry from Adobe Substance Painter to USD (`.usda`) files, supporting multiple render engines (USD Preview, Arnold, MaterialX).


## Features
- Export Substance Painter materials as USD with shader networks for:
  - USD Preview Surface
  - Arnold Standard Surface (optional)
  - MaterialX Standard Surface (legacy)
  - MaterialX OpenPBR
- Export mesh geometry to USD
- Customizable export location and primitive path
- Simple UI for export settings


## User Installation

1. Download the packaged release zip (`axe_usd_plugin.zip`) from GitHub Releases.
2. Unzip it into your Substance Painter plugins folder:
    - Windows: `C:\Users\<USERNAME>\Documents\Adobe\Adobe Substance 3D Painter\python\plugins`
    - macOS: `~/Library/Application Support/Adobe/Adobe Substance 3D Painter/python/plugins`
    - Linux: `~/.local/share/Adobe/Adobe Substance 3D Painter/python/plugins`
   This will place `axe_usd_plugin/` directly in the plugins folder.
3. Restart Substance Painter.


## Developer Installation

### Manual

1. Build the plugin bundle:
   - `python tools/build_plugin.py`
2. Copy `dist/axe_usd_plugin/` into your Substance Painter plugins directory.

### AutoBuild [Currently Windows Only]

- `powershell -File tools/install_plugin.ps1`
- this will build and copy `dist/axe_usd_plugin/` into your Substance Painter plugins directory in a single step.


## Documentation

- User guide: `docs/USER_GUIDE.md`
- Developer guide: `docs/DEVELOPER_GUIDE.md`


## Usage

1. Start Substance Painter.
2. Menu bar -> `Plugins` -> `USD Exporter` to open the plugin UI.
   - If the plugin is not visible, ensure it is installed in the correct directory.
3. Configure the export settings:
   - **Render Engines**: USD Preview, OpenPBR, MaterialX Standard Surface, Arnold (optional).
   - **Export Options**: Enable **Include Mesh in USD** if you want geometry exported.
   - **USD Preview Options**: Optional texture format override and preview texture resolution.
4. Export textures normally in Substance Painter. Script will automatically run after the export finishes.
5. Output is written to `<export_dir>/<AssetName>/`.
6. The plugin moves all exported textures into `<export_dir>/<AssetName>/textures/`.
7. Open `<AssetName>/<AssetName>.usd` in any USD viewer.

![Screenshot_2.png](Examples/images/Screenshot_2.png)

&nbsp;


## Examples
### Exporting Materials and Geometry

1. Open the plugin UI and configure the following settings:
   - **Render Engines**: Enable `USD Preview` and `OpenPBR`.
   - **Publish Directory**: Set to `<export_folder>`.
   - **Primitive Path**: Set to `/RootNode`.
   - **Save Geometry**: Check this option to export mesh geometry.

2. Export textures in Substance Painter. The plugin will:
   - Generate a USD file with materials and shader networks.
   - Optionally export a `mesh.usd` file containing the geometry.


<br>

### Example USD File:
Example File provided: [main.usda](Examples/main.usda)



### Example ASCII USD Material 
The following is an example from a generated material layer (`mtl.usdc` exported to `.usda`) showing a material named `_01_Head` with both `UsdPreviewSurface` and MaterialX Standard Surface networks:

```usd
#usda 1.0
(
    defaultPrim = "SPsample_v002"
    doc = """Generated from Composed Stage of root layer c:\\Users\\Ahmed Hindy\\AppData\\Local\\Temp\\axe_usd_test_aif40bu7\\SPsample_v002\\mtl.usdc
"""
    framesPerSecond = 24
    metersPerUnit = 1
    timeCodesPerSecond = 24
    upAxis = "Y"
)

def Xform "SPsample_v002"
{
    def Scope "mtl"
    {
        def Material "_01_Head" (
            customData = {
                string source_material_name = "01_Head"
            }
            displayName = "01_Head"
        )
        {
            int inputs:inputnum = 2
            token outputs:mtlx:surface.connect = </SPsample_v002/mtl/_01_Head/mtlx_mtlxstandard_surface1.outputs:surface>
            token outputs:surface.connect = </SPsample_v002/mtl/_01_Head/UsdPreviewNodeGraph.outputs:surface>

            def NodeGraph "UsdPreviewNodeGraph"
            {
                token outputs:surface.connect = </SPsample_v002/mtl/_01_Head/UsdPreviewNodeGraph/UsdPreviewSurface.outputs:surface>

                def Shader "UsdPreviewSurface"
                {
                    uniform token info:id = "UsdPreviewSurface"
                    float3 inputs:diffuseColor.connect = </SPsample_v002/mtl/_01_Head/UsdPreviewNodeGraph/basecolorTexture.outputs:rgb>
                    token outputs:surface
                }

                def Shader "TexCoordReader"
                {
                    uniform token info:id = "UsdPrimvarReader_float2"
                    token inputs:varname = "st"
                    float2 outputs:result
                }

                def Shader "basecolorTexture"
                {
                    uniform token info:id = "UsdUVTexture"
                    asset inputs:file = @c:/Users/Ahmed Hindy/AppData/Local/Temp/axe_usd_test_aif40bu7/SPsample_v002/textures/previewTextures/01_Head_BaseColor.jpg@
                    float2 inputs:st.connect = </SPsample_v002/mtl/_01_Head/UsdPreviewNodeGraph/TexCoordReader.outputs:result>
                    token inputs:wrapS = "repeat"
                    token inputs:wrapT = "repeat"
                    float3 outputs:rgb
                }
            }

            def Shader "mtlx_mtlxstandard_surface1"
            {
                uniform token info:id = "ND_standard_surface_surfaceshader"
                float inputs:base = 1
                color3f inputs:base_color = (0.8, 0.8, 0.8)
                color3f inputs:base_color.connect = </SPsample_v002/mtl/_01_Head/mtlx_basecolorColorCorrect.outputs:out>
                float inputs:coat = 0
                float inputs:coat_roughness = 0.1
                float inputs:emission = 0
                float3 inputs:emission_color = (1, 1, 1)
                float inputs:metalness = 0
                float inputs:metalness.connect = </SPsample_v002/mtl/_01_Head/mtlx_metalnessRange.outputs:out>
                float3 inputs:normal.connect = </SPsample_v002/mtl/_01_Head/mtlx_NormalMap.outputs:out>
                color3f inputs:opacity = (1, 1, 1)
                float inputs:specular = 1
                float3 inputs:specular_color = (1, 1, 1)
                float inputs:specular_IOR = 1.5
                float inputs:specular_roughness = 0.2
                float inputs:specular_roughness.connect = </SPsample_v002/mtl/_01_Head/mtlx_roughnessRange.outputs:out>
                int inputs:thin_walled = 0
                float inputs:transmission = 0
                token outputs:surface
            }

            def Shader "mtlx_basecolorTexture"
            {
                uniform token info:id = "ND_image_color3"
                asset inputs:file = @c:/Users/Ahmed Hindy/AppData/Local/Temp/axe_usd_test_aif40bu7/SPsample_v002/textures/MeetMat_2019_Cameras_03_CleanedMaterialNames_01_Head_BaseColor.png@
                color3f outputs:out
            }

            def Shader "mtlx_basecolorColorCorrect"
            {
                uniform token info:id = "ND_colorcorrect_color3"
                color3f inputs:in.connect = </SPsample_v002/mtl/_01_Head/mtlx_basecolorTexture.outputs:out>
                color3f outputs:out
            }

            def Shader "mtlx_displacementTexture"
            {
                uniform token info:id = "ND_image_float"
                asset inputs:file = @c:/Users/Ahmed Hindy/AppData/Local/Temp/axe_usd_test_aif40bu7/SPsample_v002/textures/MeetMat_2019_Cameras_03_CleanedMaterialNames_01_Head_Height.png@
            }

            def Shader "mtlx_metalnessTexture"
            {
                uniform token info:id = "ND_image_float"
                asset inputs:file = @c:/Users/Ahmed Hindy/AppData/Local/Temp/axe_usd_test_aif40bu7/SPsample_v002/textures/MeetMat_2019_Cameras_03_CleanedMaterialNames_01_Head_Metalness.png@
                float outputs:out
            }

            def Shader "mtlx_metalnessRange"
            {
                uniform token info:id = "ND_range_float"
                float inputs:in.connect = </SPsample_v002/mtl/_01_Head/mtlx_metalnessTexture.outputs:out>
                float outputs:out
            }

            def Shader "mtlx_normalTexture"
            {
                uniform token info:id = "ND_image_vector3"
                asset inputs:file = @c:/Users/Ahmed Hindy/AppData/Local/Temp/axe_usd_test_aif40bu7/SPsample_v002/textures/MeetMat_2019_Cameras_03_CleanedMaterialNames_01_Head_Normal.png@
                float3 outputs:out
            }

            def Shader "mtlx_NormalMap"
            {
                uniform token info:id = "ND_normalmap"
                float3 inputs:in.connect = </SPsample_v002/mtl/_01_Head/mtlx_normalTexture.outputs:out>
                float3 outputs:out
            }

            def Shader "mtlx_roughnessTexture"
            {
                uniform token info:id = "ND_image_float"
                asset inputs:file = @c:/Users/Ahmed Hindy/AppData/Local/Temp/axe_usd_test_aif40bu7/SPsample_v002/textures/MeetMat_2019_Cameras_03_CleanedMaterialNames_01_Head_Roughness.png@
                float outputs:out
            }

            def Shader "mtlx_roughnessRange"
            {
                uniform token info:id = "ND_range_float"
                float inputs:in.connect = </SPsample_v002/mtl/_01_Head/mtlx_roughnessTexture.outputs:out>
                float outputs:out
            }
        }
    }
}
```
