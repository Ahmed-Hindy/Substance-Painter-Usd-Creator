# Developer Guide


## Repo Layout
- `src/axe_usd/`
  - `core/`: pure logic (paths, parsing, export orchestration)
  - `usd/`: USD authoring backend (pxr adapter + shader authoring)
  - `dcc/`: Substance Painter integration (UI, event wiring)
- `tools/`: build and install scripts
- `packaging/`: plugin wrapper template
- `tests/`: unit tests for core logic

## Plugins Folder Layout
The Substance Painter plugins folder should contain:
- `axe_usd_plugin/` (entry point package)
  - `__init__.py` (entry point)
  - `axe_usd/` (core package)

## Entry Points
- `src/axe_usd/dcc/substance_plugin.py`: actual plugin logic (UI + export).
- `packaging/axe_usd_plugin/__init__.py`: thin wrapper used for shipping.

## Build and Install
- Build bundle:
  - `python tools/build_plugin.py`
  - Output: `dist/axe_usd_plugin/`
- Install to Substance Painter (Windows):
  - `powershell -File tools/install_plugin.ps1`

## CI/CD (GitHub Releases)
- Workflow: `.github/workflows/build-and-release.yml`
- On every push to `main`, the workflow builds and uploads a zip artifact.
- On tags matching `v*`, it publishes a GitHub Release with `axe_usd_plugin.zip`.
- To cut a release:
  1. Update `VERSION`
  2. Tag: `git tag vX.Y.Z`
  3. Push tag: `git push origin vX.Y.Z`

## Testing
- Create venv and install deps:
  - `uv venv`
  - `uv sync`
- Run tests:
  - `uv run pytest`
- Lint:
  - `uv run ruff check .`

## Export Flow (High Level)
1. Substance Painter triggers `on_post_export`.
2. DCC adapter reads UI settings.
3. Core parser normalizes texture slots.
4. Core exporter builds publish paths and delegates to USD writer.
5. USD writer creates layers and shader networks.

## Substance Painter Texture Context
`on_post_export` receives a `context` object with a `textures` mapping shaped like:
- `Dict[Tuple[str, str], List[str]]`
  - Key tuple: `(material_name, texture_set)` (the exporter uses the first item).
  - Value list: absolute texture file paths.

Example:
```python
context.textures = {
    ("02_Body", ""): [
        "F:/Projects/export/Asset_02_Body_BaseColor.png",
        "F:/Projects/export/Asset_02_Body_Roughness.png",
    ]
}
```

The parser ignores unknown texture tokens and skips empty bundles.

## Extending Renderers
- Update `src/axe_usd/usd/material_processor.py` to add new shader networks.
- Update `src/axe_usd/core/texture_keys.py` if new texture slot tokens are required.
- Keep `core` independent of USD or Substance Painter imports.

## Packaging Notes
- Only ship:
- `axe_usd_plugin/`
  - `axe_usd/`
  - `VERSION` (optional)
- Do not ship:
  - `.venv`, `tests/`, `Examples/`, `dist/`, `__pycache__/`

## Troubleshooting
- If the plugin fails to import `pxr`, verify `usd-core` is available in the Substance Painter Python environment.
- If materials are missing, confirm texture filenames include expected tokens (see `docs/USER_GUIDE.md`).
