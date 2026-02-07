# Substance Painter USD Export Plugin

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![VFX Platform CY2024](https://img.shields.io/badge/VFX_Platform-CY2024-2b7a78.svg)](https://vfxplatform.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Documentation](https://img.shields.io/badge/docs-sphinx-blue)](docs/user_guide.rst)

This plugin allows you to export materials and geometry from Adobe Substance Painter to USD (`.usd`) files, with support for multiple render engines.
Targets Substance Painter 8.3.0+ and the VFX Platform CY2024 spec.

**[Full Documentation](docs/user_guide.rst)**


## Features
- Export Substance Painter materials as USD with shader networks for:
    - Windows: `C:\Users\<USERNAME>\Documents\Adobe\Adobe Substance 3D Painter\python\plugins`
    - macOS: `~/Library/Application Support/Adobe/Adobe Substance 3D Painter/python/plugins`
    - Linux: `~/.local/share/Adobe/Adobe Substance 3D Painter/python/plugins`
   This will place `axe_usd_plugin/` directly in the plugins folder.
3. Restart Substance Painter.

**Note**: Release artifacts bundle the USD dependencies. For local builds, the
`tools/build_plugin.py` script downloads the required USD wheels automatically.


## Developer Installation

### Manual

1. Build the plugin bundle:
   - `python tools/build_plugin.py`
2. Copy `dist/axe_usd_plugin/` into your Substance Painter plugins directory.

### AutoBuild [Currently Windows Only]

- `powershell -File tools/install_plugin.ps1`
- this will build and copy `dist/axe_usd_plugin/` into your Substance Painter plugins directory in a single step.
- `powershell -File tools/install_plugin.ps1 -SkipDependencies` for quick code-only updates while SP is running.
  - Requires a full install with SP closed to populate `dependencies/` first.
  - Disable/enable the plugin to reload the updated Python code.


## Documentation

- [User Guide](docs/user_guide.rst)
- [Developer Guide](docs/DEVELOPER_GUIDE.md)


## Usage

1. Start Substance Painter.
2. Menu bar -> `Plugins` -> `USD Exporter` to open the plugin UI.
   - If the plugin is not visible, ensure it is installed in the correct directory.
3. Configure the export settings:
   - **Render Engines**: USD Preview, OpenPBR, MaterialX Standard Surface, Arnold.
   - **Export Options**: Enable **Include Mesh in USD** if you want geometry exported.
   - **USD Preview Options**: Optional texture format override and preview texture resolution, defaults to 128x128 resolution and jpeg format.
4. Export textures normally in Substance Painter. Script will automatically run after the export finishes.
5. Output is written to `<export_dir>/Asset/`.
6. The plugin moves all exported textures into `<export_dir>/Asset/textures/`.
7. Open `<export_dir>/Asset/Asset.usd` in any USD viewer.

| | |
|:---:|:---:|
| <img src="Examples/images/Screenshot_3.png" width="300"><br>Substance Plugin UI | <img src="Examples/images/Screenshot_4.png" width="300"><br>Houdini OpenGL |
| <img src="Examples/images/Screenshot_5.png" width="300"><br>Houdini Karma XPU | <img src="Examples/images/Screenshot_6.png" width="300"><br>Blender 5.0 |

<p align="center">
    <em>The screenshots above show the Plugin UI in Substance Painter, and the exported USD assets validated in multiple renderers: Houdini (OpenGL & Karma XPU) and Blender 5.0.</em>
</p>

### Example USD File:
Example File provided: [Asset/Asset.usd](Examples/Asset/Asset.usd)
