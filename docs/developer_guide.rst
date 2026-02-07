Developer Guide
===============

Repo Layout
-----------

- ``src/axe_usd/``

  - ``core/``: pure logic (paths, parsing, export orchestration)
  - ``usd/``: USD authoring backend (pxr adapter + shader authoring)
  - ``dcc/``: Substance Painter integration (UI, event wiring)

- ``tools/``: build and install scripts
- ``packaging/``: plugin wrapper template
- ``tests/``: unit tests for core logic

Plugins Folder Layout
---------------------

The Substance Painter plugins folder should contain:

- ``axe_usd_plugin/`` (entry point package)

  - ``__init__.py`` (entry point)
  - ``axe_usd/`` (core package)

Entry Points
------------

- ``src/axe_usd/dcc/substance_painter/substance_plugin.py``: actual plugin logic (UI + export).
- ``packaging/axe_usd_plugin/__init__.py``: thin wrapper used for shipping.

Build and Install
-----------------

**Build bundle:**

.. code-block:: bash

   python tools/build_plugin.py

Output: ``dist/axe_usd_plugin/``

**Install to Substance Painter (Windows):**

.. code-block:: powershell

   powershell -File tools/install_plugin.ps1

**Dev update (skip dependencies):**

.. code-block:: powershell

   powershell -File tools/install_plugin.ps1 -SkipDependencies

Use the dev update when SP is running so locked USD ``.pyd`` files are not
overwritten. Run the full install with SP closed to refresh dependencies.
Disable/enable the plugin to reload the updated Python code.

CI/CD (GitHub Releases)
-----------------------

- Workflow: ``.github/workflows/build-and-release.yml``
- On every push to ``main``, the workflow builds and uploads a zip artifact.
- On tags matching ``v*``, it publishes a GitHub Release with ``axe_usd_plugin.zip``.

**To cut a release:**

1. Update ``pyproject.toml`` version
2. Tag: ``git tag vX.Y.Z``
3. Push tag: ``git push origin vX.Y.Z``

Testing
-------

**Create venv and install deps:**

.. code-block:: bash

   uv venv
   uv sync

**Run tests:**

.. code-block:: bash

   uv run pytest

**Lint:**

.. code-block:: bash

   uv run ruff check .

UI Preview (No Substance Painter Required)
-------------------------------------------

**Install dev deps:**

.. code-block:: bash

   uv sync

**Run the standalone UI preview:**

.. code-block:: bash

   uv run sp-usd-preview-ui
   # Or:
   python tools/preview_ui.py

Export Flow (High Level)
-------------------------

1. Substance Painter triggers ``on_post_export``.
2. DCC adapter reads UI settings.
3. Core parser normalizes texture slots.
4. Core exporter builds publish paths and delegates to USD writer.
5. USD writer creates layers and shader networks.

Texture Format Overrides
-------------------------

You can override texture formats per renderer by passing ``texture_format_overrides`` in
``ExportSettings``. Keys are ``usd_preview``, ``arnold``, ``mtlx``, and ``openpbr``, and values can
be file extensions with or without a leading dot. Overrides replace existing suffixes and
are appended when the texture path has no suffix. When no override is provided, non-USDPreview
renderers default to ``png``.

**Example:**

.. code-block:: python

   settings = ExportSettings(
       usdpreview=True,
       arnold=True,
       materialx=True,
       openpbr=False,
       primitive_path="/Asset",
       publish_directory=Path("publish"),
       save_geometry=False,
       texture_format_overrides={
           "usd_preview": "jpg",
           "arnold": ".exr",
           "mtlx": "png",
           "openpbr": "png",
       },
   )

MaterialX Notes
---------------

- Metalness and roughness textures are wired as float inputs end-to-end.

Substance Painter Texture Context
----------------------------------

``on_post_export`` receives a ``context`` object with a ``textures`` mapping shaped like:

- ``Dict[Tuple[str, str], List[str]]``

  - Key tuple: ``(material_name, texture_set)`` (the exporter uses the first item).
  - Value list: absolute texture file paths.

**Example:**

.. code-block:: python

   context.textures = {
       ("02_Body", ""): [
           "F:/Projects/export/Asset_02_Body_BaseColor.png",
           "F:/Projects/export/Asset_02_Body_Roughness.png",
       ]
   }

The parser ignores unknown texture tokens and skips empty bundles.

Mesh Assignments
----------------

The ``context.textures`` payload does not include mesh assignment data. To
preserve per-texture-set mesh bindings, the plugin queries
``substance_painter.textureset.all_texture_sets()`` and records the
``all_mesh_names()`` results on each exported material. These mesh names are
used during material binding to target the corresponding Xform prims under
``/Asset/geo/render`` (and proxy equivalents), ensuring assignments stay stable
even when mesh prim names include suffixes.

Extending Renderers
-------------------

- Add a shader network builder in ``src/axe_usd/usd/material_builders.py``.
- Wire the builder into ``src/axe_usd/usd/material_processor.py``.
- Update ``src/axe_usd/core/texture_keys.py`` if new texture slot tokens are required.
- Keep ``core`` independent of USD or DCC imports.

Packaging Notes
---------------

**Only ship:**

- ``axe_usd_plugin/``

  - ``axe_usd/``

**Do not ship:**


Extending Renderers
-------------------

- Add a shader network builder in ``src/axe_usd/usd/material_builders.py``.
- Wire the builder into ``src/axe_usd/usd/material_processor.py``.
- Update ``src/axe_usd/core/texture_keys.py`` if new texture slot tokens are required.
- Keep ``core`` independent of USD or Substance Painter imports.

Packaging Notes
---------------

**Only ship:**

- ``axe_usd_plugin/``

  - ``axe_usd/``

**Do not ship:**

- ``.venv``, ``tests/``, ``Examples/``, ``dist/``, ``__pycache__/``

Troubleshooting
---------------

- If the plugin fails to import ``pxr``, verify ``usd-core`` is available in the Substance Painter Python environment.
- If materials are missing, confirm texture filenames include expected tokens (see :doc:`user_guide`).

Standalone / Other DCC Usage
----------------------------

The ``axe_usd.core`` and ``axe_usd.usd`` packages are designed to be DCC-agnostic. You can use them in any Python environment (Blender, Houdini, Maya, or standalone scripts) to generate USD assets.

**Example: Standalone Python Script**

.. code-block:: python

   from pathlib import Path
   from axe_usd.usd.material_processor import create_shaded_asset_publish

   # 1. Define your texture inputs (MaterialTextureDict)
   # Structure: List[Dict[slot_name, {mat_name, path, mesh_names?}]]
   material_data = [
       {
           "basecolor": {"mat_name": "MyMat", "path": "C:/textures/MyMat_BaseColor.png"},
           "roughness": {"mat_name": "MyMat", "path": "C:/textures/MyMat_Roughness.png"},
           "normal":    {"mat_name": "MyMat", "path": "C:/textures/MyMat_Normal.png"},
           # Optional: Assign this material to specific mesh components
           "basecolor": {
               "mat_name": "MyMat",
               "path": "C:/textures/MyMat_BaseColor.png",
               "mesh_names": ["Mesh_Head", "Mesh_Body"]  
           }
       }
   ]

   # 2. Call the exporter
   create_shaded_asset_publish(
       material_dict_list=material_data,
       geo_file="C:/geometry/my_asset.usd",  # Optional: source geometry
       parent_path="/Asset",                 # Root prim path
       layer_save_path="C:/output/MyAsset",  # Output directory
       create_usd_preview=True,
       create_mtlx=True,
       create_arnold=True,
   )

This script will generate a full ASWF-compliant USD asset in ``C:/output/MyAsset``.

Adding Support for a New DCC
----------------------------

To integrate ``axe_usd`` into a new DCC (e.g., Blender, Houdini), you need to write a simple **Adapter**.

**Steps:**

1.  **Create a DCC package**:
    Create ``src/axe_usd/dcc/<dcc_name>/`` (e.g., ``blender/``).

2.  **Implement the Collector**:
    Write a function that:
    
    - Iterates over the DCC's material selection.
    - Extracts texture file paths for each slot (Base Color, Roughness, etc.).
    - Formats them into the ``MaterialTextureDict`` structure shown above.

3.  **Call the Exporter**:
    Pass the collected data to ``create_shaded_asset_publish``.

**Architecture Tip:**
Keep your DCC-specific code (UI, selection logic) inside ``src/axe_usd/dcc/`` and import ``src/axe_usd/usd`` to do the heavy lifting. This ensures your integration remains clean and maintainable.
