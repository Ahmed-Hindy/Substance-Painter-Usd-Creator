"""Tests for file system abstraction."""

import json
from pathlib import Path

import pytest

from axe_usd.core.exceptions import FileSystemError, ValidationError
from axe_usd.core.filesystem import DefaultFileSystem


class TestDefaultFileSystem:
    """Tests for DefaultFileSystem implementation."""

    def test_ensure_directory_creates_path(self, tmp_path):
        """ensure_directory creates directories."""
        fs = DefaultFileSystem()
        test_dir = tmp_path / "test" / "nested" / "dir"

        result = fs.ensure_directory(test_dir)

        assert result == test_dir
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_directory_handles_existing(self, tmp_path):
        """ensure_directory handles already existing directories."""
        fs = DefaultFileSystem()
        test_dir = tmp_path / "existing"
        test_dir.mkdir()

        result = fs.ensure_directory(test_dir)

        assert result == test_dir
        assert test_dir.exists()

    def test_ensure_directory_raises_on_invalid_path(self):
        """ensure_directory raises FileSystemError for invalid paths."""
        fs = DefaultFileSystem()
        # Use a path that will fail (e.g., path containing null bytes on Unix-like systems)
        # For cross-platform, we'll use a read-only location instead
        invalid_path = (
            Path("/") / "invalid\x00path"
            if Path("/").exists()
            else Path("C:\\") / "invalid\x00path"
        )

        with pytest.raises(FileSystemError) as exc_info:
            fs.ensure_directory(invalid_path)

        assert "Failed to create directory" in exc_info.value.message

    def test_path_exists_returns_true_for_existing(self, tmp_path):
        """path_exists returns True for existing paths."""
        fs = DefaultFileSystem()
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        assert fs.path_exists(test_file) is True
        assert fs.path_exists(tmp_path) is True

    def test_path_exists_returns_false_for_missing(self, tmp_path):
        """path_exists returns False for missing paths."""
        fs = DefaultFileSystem()
        missing = tmp_path / "does_not_exist.txt"

        assert fs.path_exists(missing) is False

    def test_validate_path_resolves_path(self, tmp_path):
        """validate_path resolves relative paths."""
        fs = DefaultFileSystem()
        test_path = tmp_path / "test.txt"

        resolved = fs.validate_path(test_path)

        assert resolved.is_absolute()

    def test_validate_path_allows_path_within_base(self, tmp_path):
        """validate_path allows paths within base_dir."""
        fs = DefaultFileSystem()
        base = tmp_path
        sub_path = tmp_path / "subdir" / "file.txt"

        resolved = fs.validate_path(sub_path, base_dir=base)

        assert resolved.is_absolute()

    def test_validate_path_rejects_traversal(self, tmp_path):
        """validate_path rejects path traversal attempts."""
        fs = DefaultFileSystem()
        base = tmp_path / "restricted"
        base.mkdir()

        # Try to escape to parent
        escape_path = base / ".." / ".." / "etc" / "passwd"

        with pytest.raises(ValidationError) as exc_info:
            fs.validate_path(escape_path, base_dir=base)

        assert "escapes base directory" in exc_info.value.message

    def test_validate_path_handles_symlinks(self, tmp_path):
        """validate_path resolves symlinks and checks base_dir."""
        fs = DefaultFileSystem()
        base = tmp_path / "base"
        base.mkdir()

        # Create a file outside base
        outside = tmp_path / "outside.txt"
        outside.write_text("data")

        # Create symlink inside base pointing outside
        link = base / "link"
        try:
            link.symlink_to(outside)
        except OSError:
            pytest.skip("Symlinks not supported on this system")

        with pytest.raises(ValidationError) as exc_info:
            fs.validate_path(link, base_dir=base)

        assert "escapes base directory" in exc_info.value.message

    def test_read_json_reads_file(self, tmp_path):
        """read_json reads and parses JSON files."""
        fs = DefaultFileSystem()
        test_file = tmp_path / "test.json"
        data = {"key": "value", "number": 42}
        test_file.write_text(json.dumps(data))

        result = fs.read_json(test_file)

        assert result == data

    def test_read_json_raises_on_missing_file(self, tmp_path):
        """read_json raises FileSystemError for missing files."""
        fs = DefaultFileSystem()
        missing = tmp_path / "missing.json"

        with pytest.raises(FileSystemError) as exc_info:
            fs.read_json(missing)

        assert "Failed to read JSON" in exc_info.value.message
        assert str(missing) in exc_info.value.message

    def test_read_json_raises_on_invalid_json(self, tmp_path):
        """read_json raises FileSystemError for invalid JSON."""
        fs = DefaultFileSystem()
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{")

        with pytest.raises(FileSystemError) as exc_info:
            fs.read_json(bad_file)

        assert "Failed to read JSON" in exc_info.value.message

    def test_write_json_writes_file(self, tmp_path):
        """write_json writes data as JSON."""
        fs = DefaultFileSystem()
        test_file = tmp_path / "output.json"
        data = {"test": "data", "number": 123}

        fs.write_json(test_file, data)

        assert test_file.exists()
        loaded = json.loads(test_file.read_text())
        assert loaded == data

    def test_write_json_creates_parent_dirs(self, tmp_path):
        """write_json creates parent directories automatically."""
        fs = DefaultFileSystem()
        nested_file = tmp_path / "a" / "b" / "c" / "data.json"
        data = {"nested": True}

        fs.write_json(nested_file, data)

        assert nested_file.exists()
        assert nested_file.parent.parent.parent.exists()

    def test_write_json_formats_with_indent(self, tmp_path):
        """write_json formats JSON with indentation."""
        fs = DefaultFileSystem()
        test_file = tmp_path / "pretty.json"
        data = {"key": "value"}

        fs.write_json(test_file, data)

        content = test_file.read_text()
        assert "  " in content  # Has indentation
        assert "\n" in content  # Has newlines

    def test_write_json_raises_on_invalid_data(self, tmp_path):
        """write_json raises FileSystemError for non-serializable data."""
        fs = DefaultFileSystem()
        test_file = tmp_path / "bad.json"

        # Objects are not JSON serializable by default
        class NotSerializable:
            pass

        bad_data = {"obj": NotSerializable()}

        with pytest.raises(FileSystemError) as exc_info:
            fs.write_json(test_file, bad_data)

        assert "Failed to write JSON" in exc_info.value.message
