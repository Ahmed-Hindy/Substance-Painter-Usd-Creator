from pathlib import Path

from axe_usd.core.publish_paths import build_publish_paths


def test_build_publish_paths_from_directory():
    """Verify path building when given a directory."""
    paths = build_publish_paths(Path("publish"), "main.usda")
    assert paths.root_dir == Path("publish")
    assert paths.root_dir == Path("publish")
    assert paths.geometry_path == Path("publish/geometry.usd")


def test_build_publish_paths_from_file():
    """Verify path building when given a main layer file path."""
    paths = build_publish_paths(Path("publish/main.usda"), "main.usda")
    assert paths.root_dir == Path("publish")
