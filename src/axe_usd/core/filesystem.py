"""File system abstraction for testability and validation."""

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from .exceptions import FileSystemError, ValidationError


class FileSystem(Protocol):
    """Protocol for file system operations.

    This protocol defines the interface for file system operations,
    allowing for easy mocking in tests and centralized validation.
    """

    def ensure_directory(self, path: Path) -> Path:
        """Create directory if it doesn't exist."""
        ...

    def validate_path(self, path: Path, base_dir: Optional[Path] = None) -> Path:
        """Validate and resolve a path."""
        ...

    def path_exists(self, path: Path) -> bool:
        """Check if path exists."""
        ...

    def read_json(self, path: Path) -> Dict[str, Any]:
        """Read JSON file."""
        ...

    def write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON file."""
        ...


class DefaultFileSystem:
    """Default file system implementation with validation."""

    @staticmethod
    @contextmanager
    def _fs_error(msg, **details):
        """Wrap file system exceptions into FileSystemError."""
        try:
            yield
        except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
            raise FileSystemError(
                msg,
                details={**details, "error": str(exc), "type": type(exc).__name__},
            ) from exc

    def ensure_directory(self, path: Path) -> Path:
        """Create directory if it doesn't exist."""
        with self._fs_error(f"Failed to create directory: {path}", path=str(path)):
            path.mkdir(parents=True, exist_ok=True)
            return path

    def validate_path(self, path: Path, base_dir: Optional[Path] = None) -> Path:
        """Validate and resolve a path."""
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError) as exc:
            raise ValidationError(
                f"Cannot resolve path: {path}",
                details={"path": str(path), "error": str(exc)},
            ) from exc

        # Check for path traversal if base_dir provided
        if base_dir:
            try:
                base_resolved = base_dir.resolve()
                resolved.relative_to(base_resolved)
            except ValueError as exc:
                raise ValidationError(
                    f"Path escapes base directory: {path}",
                    details={
                        "path": str(path),
                        "base_dir": str(base_dir),
                        "resolved": str(resolved),
                        "base_resolved": str(base_resolved),
                    },
                ) from exc

        return resolved

    def path_exists(self, path: Path) -> bool:
        """Check if path exists."""
        return path.exists()

    def read_json(self, path: Path) -> Dict[str, Any]:
        """Read JSON file."""
        with self._fs_error(f"Failed to read JSON from {path}", path=str(path)):
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)

    def write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON file."""
        with self._fs_error(f"Failed to write JSON to {path}", path=str(path)):
            # Ensure parent directory exists
            self.ensure_directory(path.parent)

            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
