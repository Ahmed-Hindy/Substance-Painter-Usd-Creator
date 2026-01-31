User Guide
==========

Overview
--------

This plugin exports materials and optional geometry from Adobe Substance Painter to USD. It supports multiple render engines (USD Preview Surface, Arnold, MaterialX) and writes a layered USD publish under a chosen output directory.

Installation (End Users)
-------------------------

1. Download the packaged release zip (``axe_usd_plugin.zip``) from GitHub Releases.
2. Unzip it into your Substance Painter plugins folder:

   - ``<DOCUMENTS>/Adobe/Adobe Substance 3D Painter/python/plugins/``
   
   This should create ``axe_usd_plugin/`` directly inside the plugins folder.

3. Restart Substance Painter.

.. important::
   If you previously installed ``AxeFX_usd_plugin.py``, ``sp_usd_creator/``, ``axe_usd/``, or an older ``axe_usd_plugin.py``, delete them before copying the new build to avoid duplicate plugins.


Usage
-----

1. Open Substance Painter.
2. Menu: ``Plugins`` → ``USD Exporter``.
3. Configure:

   - **Render Engines**: USD Preview, OpenPBR, MaterialX standard surface, Arnold optional.
   - **Publish Folder**: the plugin writes USD next to your texture export folder (no UI field).
   - **Primitive Path**: currently fixed to ``/Asset`` (used for the component asset name and prims).
   - **Save Geometry**: exports mesh into ``<AssetName>/geo.usdc`` if enabled.

4. Export textures normally in Substance Painter. After export finishes, the plugin writes USD files.

Output Layout
-------------

When you export textures to a directory like ``C:\Projects\Exports\my_asset``, the plugin writes
into ``<export_dir>/<AssetName>/`` (AssetName comes from the primitive path, default ``Asset``):

- ``<AssetName>/<AssetName>.usd`` (main entry point)
- ``<AssetName>/payload.usdc`` (references geometry + materials)
- ``<AssetName>/geo.usdc`` (geometry layer when enabled)
- ``<AssetName>/mtl.usdc`` (materials layer)
- ``<AssetName>/textures/`` (all exported textures, moved from the export folder)
- ``<AssetName>/textures/previewTextures/`` (USD Preview textures when enabled)

Texture Naming Conventions
---------------------------

The plugin looks for tokens in exported texture file names:

- ``base_color``, ``basecolor``, ``albedo``, ``diffuse`` → base color
- ``metallic``, ``metalness`` → metalness
- ``roughness`` → roughness
- ``normal`` → normal
- ``opacity``, ``alpha`` → opacity
- ``occlusion``, ``ao`` → occlusion
- ``height``, ``displacement`` → displacement

Tokens are matched as standalone words (non-alphanumeric boundaries), so unrelated substrings like ``road`` do not match ``ao``. Unknown texture files are ignored, and materials are still authored when only a subset of maps is available.

Notes
-----

- USD Preview uses ``metallic``, Arnold/MaterialX use ``metalness``. The plugin normalizes this for you.
- The publish folder is derived from the texture export directory (USD is written alongside it).
- By default, non-USDPreview renderers use ``png`` texture overrides unless customized via the API.
- Advanced: per-renderer texture format overrides (``usd_preview``, ``arnold``, ``mtlx``, ``openpbr``) are available via the API (see :doc:`developer_guide`).

Troubleshooting
---------------

**Plugin not showing up:**

- Ensure ``axe_usd_plugin/`` is directly inside the Substance Painter plugins directory.
- Restart Substance Painter.

**No USD files written:**

- Make sure texture export succeeded and produced files.
- Confirm publish directory is valid and writable.

**Missing metalness or displacement:**

- Check texture filenames include ``metallic``/``metalness`` or ``height``/``displacement`` tokens.

**USD import errors:**

- Verify ``usd-core`` is available in your Python environment if testing outside Substance Painter.
