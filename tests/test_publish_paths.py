from pathlib import Path

from sp_usd_creator.core.publish_paths import build_publish_paths


def test_build_publish_paths_from_directory():
    paths = build_publish_paths(Path("publish"), "main.usda")
    assert paths.root_dir == Path("publish")
    assert paths.layers_dir == Path("publish") / "layers"
    assert paths.main_layer_path == Path("publish") / "main.usda"


def test_build_publish_paths_from_file():
    paths = build_publish_paths(Path("publish/main.usda"), "main.usda")
    assert paths.root_dir == Path("publish")
