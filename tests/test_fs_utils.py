from sp_usd_creator.core.fs_utils import ensure_directory


def test_ensure_directory_creates_path(tmp_path):
    target = tmp_path / "nested" / "layers"
    assert not target.exists()

    result = ensure_directory(target)

    assert result == target
    assert target.exists()
    assert target.is_dir()
