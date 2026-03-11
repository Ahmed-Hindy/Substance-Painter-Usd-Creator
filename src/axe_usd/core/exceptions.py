"""Custom exceptions for USD export operations."""

from typing import Any, Mapping, Optional


class AxeUSDError(Exception):
    """Base exception for all axe_usd errors.

    Attributes:
        message: Human-readable error message.
        details: Optional dictionary of additional error context.
    """

    def __init__(
        self, message: str, details: Optional[Mapping[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self._details = dict(details) if details else {}

    @property
    def message(self) -> str:
        """Return the human-readable error message."""
        if self.args:
            return str(self.args[0])
        return ""

    @property
    def details(self) -> Mapping[str, Any]:
        """Return an immutable view of error details."""
        return self._details

    def __str__(self) -> str:
        message = self.message
        if not self._details:
            return message
        return f"{message} (details={self._details!r})"


class TextureParsingError(AxeUSDError):
    """Raised when texture slot parsing fails."""


class MaterialExportError(AxeUSDError):
    """Raised when material export operations fail."""


class GeometryExportError(AxeUSDError):
    """Raised when geometry export fails."""


class USDStageError(AxeUSDError):
    """Raised when USD stage operations fail."""


class ValidationError(AxeUSDError):
    """Raised when input validation fails."""


class FileSystemError(AxeUSDError):
    """Raised when file system operations fail."""


class ConfigurationError(AxeUSDError):
    """Raised when configuration is invalid."""


class MaterialAssignmentError(AxeUSDError):
    """Raised when material assignment to meshes fails."""
