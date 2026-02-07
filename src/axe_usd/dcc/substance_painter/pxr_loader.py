"""Bootloader for loading version-specific pxr (USD) dependencies.

This module handles dynamic loading of the Pixar USD Python bindings (pxr)
for different Python versions used by Substance Painter.

Substance Painter version history:
- SP 10.0: Python 3.9
- SP 9.x: Python 3.10
- SP 10.1+: Python 3.11

The pxr module must be bundled separately for each Python version due to
binary compatibility requirements.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

# Flag to ensure we only load dependencies once
_dependencies_loaded = False
# Keep DLL directory handles alive for the process lifetime (Windows).
_dll_dir_handles = []


def load_dependencies(plugin_dir: Optional[Path] = None) -> bool:
    """Load version-specific USD dependencies based on Python version.

    Args:
        plugin_dir: Root directory of the plugin. If None, auto-detects from this file's location.

    Returns:
        bool: True if dependencies loaded successfully, False otherwise.
    """
    global _dependencies_loaded

    if _dependencies_loaded:
        logger.debug("USD dependencies already loaded, skipping.")
        return True

    # Auto-detect plugin directory if not provided
    if plugin_dir is None:
        # This file is in axe_usd/dcc/substance_painter/pxr_loader.py
        # parent is substance_painter, parent.parent is dcc, parent.parent.parent is axe_usd, parent.parent.parent.parent is plugin root
        plugin_dir = Path(__file__).resolve().parent.parent.parent.parent

    # Detect Python version
    py_ver = f"{sys.version_info.major}{sys.version_info.minor}"

    # Map Python version to bundled dependency folders
    dep_map = {
        "39": "py39_usd24_5",  # For Substance Painter 10.0 (USD 24.5)
        "310": "py310_usd24_5",  # For Substance Painter 9.x (USD 24.5)
        "311": "py311_usd25_5_1",  # For Substance Painter 10.1+ (USD 25.5.1)
    }

    if py_ver not in dep_map:
        logger.error(
            f"Unsupported Python version: {py_ver} (Python {sys.version_info.major}.{sys.version_info.minor}). "
            f"Supported versions: {', '.join(dep_map.keys())}"
        )
        return False

    dep_folder = dep_map[py_ver]
    dep_path = plugin_dir / "dependencies" / dep_folder

    if not dep_path.exists():
        logger.error(
            f"USD dependencies not found at: {dep_path}\n"
            f"Please ensure the '{dep_folder}' folder exists in the dependencies directory.\n"
            f"See dependencies/README.md for setup instructions."
        )
        return False

    # Add to sys.path if not already present
    dep_path_str = str(dep_path)
    if dep_path_str not in sys.path:
        sys.path.insert(0, dep_path_str)
        logger.info(f"Added USD dependencies to sys.path: {dep_path_str}")

    # Add DLL directories for Windows (Python 3.8+)
    # USD wheels place DLLs under the pxr/ folder, so include both roots.
    if hasattr(os, "add_dll_directory"):
        for dll_dir in (dep_path, dep_path / "pxr"):
            dll_dir_str = str(dll_dir)
            if not dll_dir.exists():
                continue
            try:
                _dll_dir_handles.append(os.add_dll_directory(dll_dir_str))
                logger.debug(f"Added DLL directory: {dll_dir_str}")
            except Exception as e:
                logger.warning(f"Failed to add DLL directory '{dll_dir_str}': {e}")

    _dependencies_loaded = True
    logger.info(f"Successfully loaded USD dependencies for Python {py_ver}")

    return True


def verify_pxr_available() -> bool:
    """Verify that pxr module can be imported.

    Returns:
        bool: True if pxr is importable, False otherwise.
    """
    try:
        import pxr

        logger.debug(f"pxr module verified: {pxr.__file__}")
        return True
    except ImportError as e:
        logger.error(f"Failed to import pxr module: {e}")
        return False
