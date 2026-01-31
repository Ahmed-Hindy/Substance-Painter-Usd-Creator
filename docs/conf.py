from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import sys

DOCS_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOCS_DIR.parent
SRC_DIR = REPO_ROOT / "src"

sys.path.insert(0, str(SRC_DIR))


def _read_version() -> str:
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return "unknown"
    try:
        content = pyproject.read_text(encoding="utf-8")
    except Exception:
        return "unknown"

    in_project = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project or not stripped.startswith("version"):
            continue
        match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
        if match:
            return match.group(1)
    return "unknown"


project = "SP USD Creator"
author = "SP USD Creator contributors"
release = _read_version()
copyright = f"{datetime.now().year}, {author}"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_enable_extensions = ["colon_fence"]

autosummary_generate = False

autodoc_typehints = "description"
autodoc_mock_imports = [
    "pxr",
    "substance_painter",
    "PySide2",
    "PySide6",
]

# HTML theme configuration
html_theme = "furo"
html_title = "SP USD Creator"

html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#2b7a78",
        "color-brand-content": "#17252a",
    },
    "dark_css_variables": {
        "color-brand-primary": "#3aafa9",
        "color-brand-content": "#def2f1",
    },
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
}

html_static_path = ["_static"]
html_css_files = []

# Additional options
html_show_sourcelink = True
html_copy_source = True
