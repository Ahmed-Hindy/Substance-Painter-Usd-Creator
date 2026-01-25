"""File system abstraction for testability and validation."""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Protocol


class FileSystem(Protocol):
    """Protocol for file system operations.

    This protocol defines the interface for file system operations,
    allowing for easy mocking in tests and centralized validation.
    """

    def ensure_directory(self, path: Path) -> Path:
        """Create directory if it doesn't exist.

        Args:
            path: Directory path to create.

        Returns:
            Path: The created/existing directory path.

        Raises:
            FileSystemError: If directory creation fails.
        """
        ...

    def validate_path(self, path: Path, base_dir: Optional[Path] = None) -> Path:
        """Validate and resolve a path.

        Args:
            path: Path to validate.
            base_dir: Optional base directory to check against (for path traversal).

        Returns:
            Path: Resolved path.

        Raises:
            ValidationError: If path is invalid or escapes base_dir.
        """
        ...

    def path_exists(self, path: Path) -> bool:
        """Check if path exists.

        Args:
            path: Path to check.

        Returns:
            bool: True if path exists.
        """
        ...

    def read_json(self, path: Path) -> Dict[str, Any]:
        """Read JSON file.

        Args:
            path: Path to JSON file.

        Returns:
            Dict: Parsed JSON content.

        Raises:
            FileSystemError: If read or parse fails.
        """
        ...

    def write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON file.

        Args:
            path: Path to write to.
            data: Data to write as JSON.

        Raises:
            FileSystemError: If write fails.
        """
        ...


class DefaultFileSystem:
    """Default file system implementation with validation."""

    def ensure_directory(self, path: Path) -> Path:
        """Create directory if it doesn't exist."""
        from .exceptions import FileSystemError

        try:
            path.mkdir(parents=True, exist_ok=True)
            return path
        except (OSError, ValueError) as exc:
            raise FileSystemError(
                f"Failed to create directory: {path}",
                details={"path": str(path), "error": str(exc)},
            ) from exc

    def validate_path(self, path: Path, base_dir: Optional[Path] = None) -> Path:
        """Validate and resolve a path."""
        from .exceptions import ValidationError

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
        from .exceptions import FileSystemError

        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise FileSystemError(
                f"Failed to read JSON from {path}",
                details={
                    "path": str(path),
                    "error": str(exc),
                    "type": type(exc).__name__,
                },
            ) from exc

    def write_json(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON file."""
        from .exceptions import FileSystemError

        try:
            # Ensure parent directory exists
            self.ensure_directory(path.parent)

            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except (OSError, TypeError) as exc:
            raise FileSystemError(
                f"Failed to write JSON to {path}",
                details={
                    "path": str(path),
                    "error": str(exc),
                    "type": type(exc).__name__,
                },
            ) from exc
