"""Tests for custom exception hierarchy."""

import pytest

from axe_usd.core.exceptions import (
    AxeUSDError,
    ConfigurationError,
    FileSystemError,
    GeometryExportError,
    MaterialAssignmentError,
    MaterialExportError,
    TextureParsingError,
    USDStageError,
    ValidationError,
)


def test_base_exception_with_message():
    """Base exception stores message."""
    exc = AxeUSDError("Test error")
    assert exc.message == "Test error"
    assert exc.details == {}
    assert str(exc) == "Test error"


def test_base_exception_with_details():
    """Base exception stores details."""
    exc = AxeUSDError("Test error", details={"key": "value", "code": 123})
    assert exc.message == "Test error"
    assert exc.details == {"key": "value", "code": 123}


def test_exception_inheritance():
    """All custom exceptions inherit from AxeUSDError."""
    exceptions = [
        TextureParsingError,
        MaterialExportError,
        GeometryExportError,
        USDStageError,
        ValidationError,
        FileSystemError,
        ConfigurationError,
        MaterialAssignmentError,
    ]

    for exc_class in exceptions:
        exc = exc_class("Test message")
        assert isinstance(exc, AxeUSDError)
        assert isinstance(exc, Exception)


def test_validation_error_with_details():
    """ValidationError can store validation details."""
    exc = ValidationError(
        "Invalid path", details={"path": "/invalid//path", "reason": "double slashes"}
    )
    assert exc.message == "Invalid path"
    assert exc.details["path"] == "/invalid//path"
    assert exc.details["reason"] == "double slashes"


def test_material_export_error():
    """MaterialExportError works as expected."""
    exc = MaterialExportError(
        "Failed to create material", details={"material_name": "TestMat"}
    )
    assert "Failed to create material" in str(exc)
    assert exc.details["material_name"] == "TestMat"


def test_exception_can_be_caught_by_base_class():
    """Specific exceptions can be caught by base class."""
    try:
        raise ValidationError("Test")
    except AxeUSDError as exc:
        assert exc.message == "Test"


def test_exception_can_be_caught_specifically():
    """Specific exceptions can be caught by their type."""
    with pytest.raises(ValidationError) as exc_info:
        raise ValidationError("Invalid input")

    assert exc_info.value.message == "Invalid input"
