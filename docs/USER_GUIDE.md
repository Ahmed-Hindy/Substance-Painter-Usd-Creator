# User Guide

## Overview
This plugin exports materials and optional geometry from Adobe Substance Painter to USD. It supports multiple render engines (USD Preview Surface, Arnold, MaterialX) and writes a layered USD publish under a chosen output directory.

## Installation (End Users)
1. Download the latest release zip from GitHub Releases (`axe_usd_plugin.zip`).
2. Unzip the archive to your Substance Painter plugins folder:
   - Windows: `C:\Users\<USERNAME>\Documents\Adobe\Adobe Substance 3D Painter\python\plugins`
   - macOS: `~/Library/Application Support/Adobe/Adobe Substance 3D Painter/python/plugins`
   - Linux: `~/.local/share/Adobe/Adobe Substance 3D Painter/python/plugins`
   This places `axe_usd_plugin/` directly in the plugins folder.
3. Restart Substance Painter.

If you previously installed `AxeFX_usd_plugin.py`, `sp_usd_creator/`, `axe_usd/`, or an older `axe_usd_plugin.py`, delete them before copying the new build to avoid duplicate plugins.

## Installation (Developers)
1. Build the plugin bundle:
   - `python tools/build_plugin.py`
2. Copy `dist/axe_usd_plugin/` to your Substance Painter plugins folder.
3. Optional dev install on Windows:
   - `powershell -File tools/install_plugin.ps1`

## Usage
1. Open Substance Painter.
2. Menu: `Plugins` -> `USD Exporter`.
3. Configure:
   - Render Engines: USD Preview, Arnold, MaterialX.
   - Publish Directory: target folder for USD outputs.
   - Primitive Path: root prim for materials (e.g., `/RootNode/Materials`).
   - Save Geometry: exports mesh as `layers/mesh.usd` if enabled.
4. Export textures normally in Substance Painter. After export finishes, the plugin writes USD files.

## Output Layout
When you publish to a directory like `C:\Projects\Exports\my_asset`, the plugin writes:
- `main.usda` (default main layer)
- `layers/layer_mats.usda` (materials layer)
- `layers/layer_assign.usda` (material bindings)
- `layers/mesh.usd` (optional geometry)

## Texture Naming Conventions
The plugin looks for tokens in exported texture file names:
- `base_color`, `basecolor`, `albedo`, `diffuse` -> base color
- `metallic`, `metalness` -> metalness
- `roughness` -> roughness
- `normal` -> normal
- `opacity`, `alpha` -> opacity
- `occlusion`, `ao` -> occlusion
- `height`, `displacement` -> displacement

Tokens are matched as standalone words (non-alphanumeric boundaries), so unrelated substrings like `road` do not match `ao`. Unknown texture files are ignored, and materials are still authored when only a subset of maps is available.

## Notes
- USD Preview uses `metallic`, Arnold/MaterialX use `metalness`. The plugin normalizes this for you.
- The publish directory can include `<export_folder>` to substitute the active texture export folder.
- Advanced: per-renderer texture format overrides are available via the API (see `docs/DEVELOPER_GUIDE.md`).

## Troubleshooting
- Plugin not showing up:
  - Ensure `axe_usd_plugin/` is directly inside the Substance Painter plugins directory.
  - Restart Substance Painter.
- No USD files written:
  - Make sure texture export succeeded and produced files.
  - Confirm publish directory is valid and writable.
- Missing metalness or displacement:
  - Check texture filenames include `metallic`/`metalness` or `height`/`displacement` tokens.
- USD import errors:
  - Verify `usd-core` is available in your Python environment if testing outside Substance Painter.
