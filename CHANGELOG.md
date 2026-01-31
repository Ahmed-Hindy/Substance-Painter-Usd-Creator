## [1.5.0]

### Documentation

- **Sphinx Theme**: Applied modern Furo theme with custom color scheme and dark mode support.
- **reStructuredText**: Converted all documentation from Markdown to reStructuredText for enhanced Sphinx features.
- **Enhanced Docs**: Added proper directives, cross-references, and semantic markup throughout documentation.
- **Copy Buttons**: Added sphinx-copybutton extension for easy code copying.

### README

- **Image Layout**: Improved screenshot layout with 2x2 grid and descriptive captions.
- **Content Updates**: Streamlined feature descriptions and usage instructions.
- **Examples**: Updated example file references and simplified documentation structure.

### Bug Fixes

- **Version Check**: Plugin now disables on unsupported Substance Painter versions.
- **User Guide**: Removed technical implementation details from user-facing documentation.
- **Documentation Link**: Added link to full documentation in README.

### UI Improvements

- **Modular Layout**: Refactored UI into modular components for better maintainability.
- **Style Cleanup**: Removed inline styles in favor of proper Qt styling.
- **UI Options**: Updated Substance Painter UI options and preview tooling.

## [1.4.0]

### UI / Plugin Structure

- Split the Substance Painter exporter UI into its own module.
- Simplified UI wiring/presets while preserving behavior and logging.

### USD Export / ASWF Structure

- Implemented an ASWF-compliant asset structure across the export pipeline (component layout, payload/geo/mtl layers, consistent paths).

### Materials & Textures

- Improved material graph generation and texture relocation into the asset’s textures/ directory.

### Tests

- Replaced pytest.importorskip("pxr") patterns with direct pxr imports to avoid silent skips.
- Updated USD tests to use local SP sample textures via fixtures, so material graph assertions are based on real inputs.
- Stabilized expected prim paths to match current authored graphs.

### docs

- Added Sphinx documentation scaffolding and a GitHub Pages workflow.

## [1.3.0]

- Adopt `src/` layout and rename the plugin package.
- Harden export flow and guard UI lifecycle.
- Switch to folder-only plugin layout and add PySide2/6 compatibility.
- Add docstrings and cleanup release packaging.

## [1.2.0]

- Package the plugin and add CI for releases.

## [1.1.0]

- Update default widget settings.
- Fix material assignments for exported meshes.
- Refresh examples.

## [1.0.0]

- Initial release.
