"""Custom exceptions for USD export operations."""

from typing import Any, Dict, Optional


class AxeUSDError(Exception):
    """Base exception for all axe_usd errors.

    Attributes:
        message: Human-readable error message.
        details: Optional dictionary of additional error context.
    """

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message.
            details: Optional dictionary of additional error context.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class TextureParsingError(AxeUSDError):
    """Raised when texture slot parsing fails."""

    pass


class MaterialExportError(AxeUSDError):
    """Raised when material export operations fail."""

    pass


class GeometryExportError(AxeUSDError):
    """Raised when geometry export fails."""

    pass


class USDStageError(AxeUSDError):
    """Raised when USD stage operations fail."""

    pass


class ValidationError(AxeUSDError):
    """Raised when input validation fails."""

    pass


class FileSystemError(AxeUSDError):
    """Raised when file system operations fail."""

    pass


class ConfigurationError(AxeUSDError):
    """Raised when configuration is invalid."""

    pass


class MaterialAssignmentError(AxeUSDError):
    """Raised when material assignment to meshes fails."""

    pass
