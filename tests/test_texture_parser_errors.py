"""Tests for texture parsing with error handling."""

import pytest

from axe_usd.core.exceptions import TextureParsingError
from axe_usd.core.texture_parser import parse_textures


def test_parse_textures_with_none_raises_error():
    """parse_textures raises TextureParsingError when given None."""
    with pytest.raises(TextureParsingError) as exc_info:
        parse_textures(None)

    assert "cannot be None" in exc_info.value.message


def test_parse_textures_with_invalid_type_raises_error():
    """parse_textures raises TextureParsingError for non-mapping types."""
    with pytest.raises(TextureParsingError) as exc_info:
        parse_textures("invalid")  # String instead of mapping

    assert "Invalid texture dictionary type" in exc_info.value.message
    assert exc_info.value.details["type"] == "str"


def test_parse_textures_with_list_raises_error():
    """parse_textures raises TextureParsingError when given a list."""
    with pytest.raises(TextureParsingError) as exc_info:
        parse_textures([("key", ["path"])])  # List instead of mapping

    assert "Invalid texture dictionary type" in exc_info.value.message
    assert exc_info.value.details["type"] == "list"
