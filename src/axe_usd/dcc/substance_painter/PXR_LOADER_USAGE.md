# pxr_loader Usage Guide

## Overview

`pxr_loader.py` is a bootloader module that dynamically loads version-specific USD (Pixar Universal Scene Description) Python bindings based on the detected Python version. It's designed specifically for Substance Painter, which uses different Python versions across releases.

**Location**: `src/axe_usd/dcc/substance_painter/pxr_loader.py`

---

## How It Works in Substance Painter

### Automatic Loading

When the plugin is loaded by Substance Painter, the bootloader runs automatically:

1. **Plugin Entry Point** (`dist/axe_usd_plugin/__init__.py`):
   ```python
   from pathlib import Path
   
   PLUGIN_DIR = Path(__file__).resolve().parent
   
   # Load USD dependencies before any pxr imports
   from .axe_usd.dcc.substance_painter.pxr_loader import load_dependencies
   load_dependencies(PLUGIN_DIR)
   
   # Now safe to import modules that use pxr
   from .axe_usd.dcc.substance_painter.substance_plugin import start_plugin, close_plugin
   ```

2. **Bootloader Execution**:
   - Detects Python version (3.9, 3.10, or 3.11)
   - Maps to appropriate dependency folder:
     - Python 3.9 → `dependencies/py39_usd24_5/` (USD 24.5)
     - Python 3.10 → `dependencies/py310_usd24_5/` (USD 24.5)
     - Python 3.11 → `dependencies/py311_usd25_5_1/` (USD 25.5.1)
   - Adds dependency path to `sys.path`
   - Registers DLL directory for Windows
   - Sets global flag to prevent duplicate loading

3. **Result**: All subsequent `from pxr import ...` statements work seamlessly

### Supported Substance Painter Versions

| SP Version | Python Version | Dependency Folder |
|------------|----------------|-------------------|
| 9.x | 3.10 | `py310_usd24_5/` |
| 10.0 | 3.9 | `py39_usd24_5/` |
| 10.1+ | 3.11 | `py311_usd25_5_1/` |

---

## Testing Without Substance Painter

### Method 1: Using the Provided Test Script

A test script is provided in the repository root:

```bash
cd G:\Projects\Dev\Github\SP_usd_creator
python test_pxr_loader.py
```

**What it tests**:
- ✓ Module import from new location
- ✓ Path detection with explicit plugin_dir
- ✓ Dependencies directory structure
- ✓ Python version detection

**Expected output**:
```
============================================================
Testing pxr_loader from new location
============================================================
[Test 1] Importing pxr_loader from new location...
✓ Import successful
[Test 2] Testing load_dependencies with explicit plugin_dir...
Load result: True/False (depends on Python version)
...
```

**Note**: If you're running Python 3.8 or other unsupported versions, the load will fail with "Unsupported Python version" - this is expected behavior.

---

### Method 2: Manual Testing with Python 3.9, 3.10, or 3.11

If you have Python 3.10 or 3.11 installed:

```python
import sys
from pathlib import Path

# Add plugin to path
plugin_dir = Path("G:/Projects/Dev/Github/SP_usd_creator/dist/axe_usd_plugin")
sys.path.insert(0, str(plugin_dir))

# Import and test
from axe_usd.dcc.substance_painter.pxr_loader import load_dependencies, verify_pxr_available

# Load dependencies
result = load_dependencies(plugin_dir)
print(f"Load result: {result}")

# Verify pxr is importable
if result:
    pxr_available = verify_pxr_available()
    print(f"pxr available: {pxr_available}")
    
    if pxr_available:
        # Test actual pxr imports
        from pxr import Usd, UsdGeom, UsdShade
        print("✓ Successfully imported pxr modules!")
```

**Expected output** (Python 3.9, 3.10, or 3.11):
```
Load result: True
pxr available: True
✓ Successfully imported pxr modules!
```

---

### Method 3: Testing in Substance Painter Console

1. Open Substance Painter
2. Open the Python console: `Python` → `Console`
3. Run:

```python
import sys
print(f"Python version: {sys.version}")

# Check if pxr is available
try:
    from pxr import Usd
    print("✓ pxr module loaded successfully!")
    print(f"USD version: {Usd.GetVersion()}")
except ImportError as e:
    print(f"✗ Failed to import pxr: {e}")
```

**Expected output**:
```
Python version: 3.11.x (or 3.10.x / 3.9.x)
✓ pxr module loaded successfully!
USD version: (25, 5, 1) for Python 3.11, (24, 5, 0) for Python 3.9/3.10
```

---

## Troubleshooting

### "Unsupported Python version" Error

**Cause**: Your Python version is not 3.9, 3.10, or 3.11.

**Solution**: 
- For testing: Use Python 3.10 or 3.11
- For Substance Painter: Ensure you're using SP 9.x+ (which uses Python 3.10 or 3.11)

---

### "USD dependencies not found" Error

**Cause**: The dependencies folder is missing or incorrectly structured.

**Solution**:
1. Verify folder structure:
   ```
   dist/axe_usd_plugin/
   ├── dependencies/
   │   ├── py39_usd24_5/
   │   │   └── pxr/
   │   ├── py310_usd24_5/
   │   │   └── pxr/
   │   └── py311_usd25_5_1/
   │       └── pxr/
   ```

2. Check that `pxr/` folders contain USD modules:
   - Gf, Kind, Sdf, Tf, Usd, UsdGeom, UsdShade

3. If missing, re-download the plugin or rebuild using `python tools/build_plugin.py`

---

### "Failed to import pxr module" Error

**Cause**: USD dependencies loaded but pxr import still fails.

**Possible reasons**:
1. **Missing DLLs**: Install Visual C++ Redistributable 2019+
   - Download: https://aka.ms/vs/17/release/vc_redist.x64.exe

2. **Corrupted installation**: Re-download/rebuild the plugin

3. **Path issues**: Verify `sys.path` contains the dependency folder:
   ```python
   import sys
   print([p for p in sys.path if 'dependencies' in p])
   ```

---

## API Reference

### `load_dependencies(plugin_dir: Optional[Path] = None) -> bool`

Load version-specific USD dependencies based on Python version.

**Parameters**:
- `plugin_dir` (Optional[Path]): Root directory of the plugin. If None, auto-detects from file location.

**Returns**:
- `bool`: True if dependencies loaded successfully, False otherwise.

**Example**:
```python
from pathlib import Path
from axe_usd.dcc.substance_painter.pxr_loader import load_dependencies

plugin_dir = Path("/path/to/axe_usd_plugin")
success = load_dependencies(plugin_dir)
```

---

### `verify_pxr_available() -> bool`

Verify that pxr module can be imported.

**Returns**:
- `bool`: True if pxr is importable, False otherwise.

**Example**:
```python
from axe_usd.dcc.substance_painter.pxr_loader import verify_pxr_available

if verify_pxr_available():
    from pxr import Usd, UsdGeom
    # Use USD modules
```

---

## Development Notes

### Path Detection Logic

The bootloader auto-detects the plugin root directory:

```python
# File location: axe_usd/dcc/substance_painter/pxr_loader.py
# Path traversal:
#   parent         → substance_painter/
#   parent.parent  → dcc/
#   parent.parent.parent → axe_usd/
#   parent.parent.parent.parent → plugin root (axe_usd_plugin/)

plugin_dir = Path(__file__).resolve().parent.parent.parent.parent
```

### Dependency Folder Structure

```
plugin_root/
└── dependencies/
    ├── py39_usd24_5/         # Python 3.9
    │   └── pxr/
    │       ├── Gf/
    │       ├── Kind/
    │       ├── Sdf/
    │       ├── Tf/
    │       ├── Usd/
    │       ├── UsdGeom/
    │       ├── UsdShade/
    │       ├── __init__.py
    │       └── *.dll
    ├── py310_usd24_5/          # Python 3.10
    │   └── pxr/
    │       ├── Gf/
    │       ├── Kind/
    │       ├── Sdf/
    │       ├── Tf/
    │       ├── Usd/
    │       ├── UsdGeom/
    │       ├── UsdShade/
    │       ├── __init__.py
    │       └── *.dll
    └── py311_usd25_5_1/      # Python 3.11
        └── pxr/
            ├── (same structure)
```

### Adding Support for New Python Versions

To add support for a new Python version (e.g., 3.12):

1. Download the appropriate `usd-core` wheel from PyPI
2. Extract to `dependencies/py312_usdXX/`
3. Update `dep_map` in `pxr_loader.py`:
   ```python
   dep_map = {
       "39": "py39_usd24_5",
       "310": "py310_usd24_5",
       "311": "py311_usd25_5_1",
       "312": "py312_usdXX",  # Add new mapping
   }
   ```

---

## Related Files

- **Plugin Entry Point**: `dist/axe_usd_plugin/__init__.py`
- **Test Script**: `test_pxr_loader.py`
- **Dependencies README**: `dist/axe_usd_plugin/dependencies/README.md`
- **Main README**: `README.md`
