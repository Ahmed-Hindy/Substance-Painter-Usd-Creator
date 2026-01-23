# Developer Guide


## Repo Layout
- `sp_usd_creator/`
  - `core/`: pure logic (paths, parsing, export orchestration)
  - `usd/`: USD authoring backend (pxr adapter + shader authoring)
  - `dcc/`: Substance Painter integration (UI, event wiring)
- `tools/`: build and install scripts
- `packaging/`: plugin wrapper template
- `tests/`: unit tests for core logic

## Plugins Folder Layout
The Substance Painter plugins folder should contain:
- `AxeFX_usd_plugin.py` (entry point)
- `sp_usd_creator/` (package)

## Entry Points
- `sp_usd_creator/dcc/substance_plugin.py`: actual plugin logic (UI + export).
- `packaging/AxeFX_usd_plugin.py`: thin wrapper used for shipping.
- `sp_plugin.py`: repo-level thin wrapper for convenience.

## Build and Install
- Build bundle:
  - `python tools/build_plugin.py`
  - Output: `dist/AxeFX_usd_plugin.py` and `dist/sp_usd_creator/`
- Install to Substance Painter (Windows):
  - `powershell -File tools/install_plugin.ps1`

## CI/CD (GitHub Releases)
- Workflow: `.github/workflows/build-and-release.yml`
- On every push to `main`, the workflow builds and uploads a zip artifact.
- On tags matching `v*`, it publishes a GitHub Release with `AxeFX_usd_plugin.zip`.
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

## Extending Renderers
- Update `sp_usd_creator/usd/material_processor.py` to add new shader networks.
- Update `sp_usd_creator/core/texture_keys.py` if new texture slot tokens are required.
- Keep `core` independent of USD or Substance Painter imports.

## Packaging Notes
- Only ship:
  - `AxeFX_usd_plugin.py`
  - `sp_usd_creator/`
  - `VERSION` (optional)
- Do not ship:
  - `.venv`, `tests/`, `Examples/`, `dist/`, `__pycache__/`

## Troubleshooting
- If the plugin fails to import `pxr`, verify `usd-core` is available in the Substance Painter Python environment.
- If materials are missing, confirm texture filenames include expected tokens (see `docs/USER_GUIDE.md`).
