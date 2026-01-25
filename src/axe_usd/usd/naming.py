"""Configurable naming conventions for USD materials and meshes."""

from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass(frozen=True)
class NamingConvention:
    """Material and mesh naming conventions.

    This class defines how material names should be cleaned by removing
    DCC-specific prefixes and suffixes before matching with mesh names.

    Attributes:
        strip_prefixes: List of prefixes to remove from material names.
        strip_suffixes: List of suffixes to remove from material names.

    Examples:
        >>> convention = NamingConvention()
        >>> convention.clean_material_name("mat_Body_ShaderSG")
        'Body'

        >>> custom = NamingConvention(
        ...     strip_prefixes=["custom_"],
        ...     strip_suffixes=["_MAT"]
        ... )
        >>> custom.clean_material_name("custom_Body_MAT")
        'Body'
    """

    strip_prefixes: Sequence[str] = field(
        default_factory=lambda: [
            "mat_",  # Generic material prefix
            "material_",  # Longer material prefix
            "M_",  # Unreal Engine convention
        ]
    )

    strip_suffixes: Sequence[str] = field(
        default_factory=lambda: [
            "_ShaderSG",  # Maya shading group suffix
            "_collect",  # Internal plugin convention
            "_MAT",  # Houdini material suffix
            "_mtl",  # Generic material suffix
            "_SG",  # Short shading group suffix
        ]
    )

    def clean_material_name(self, raw_name: str) -> str:
        """Clean a material name by removing configured prefixes/suffixes.

        Suffixes are removed first (since they're at the end), then prefixes.
        This order matters when both prefix and suffix are present.

        Args:
            raw_name: Raw material name from USD prim.

        Returns:
            str: Cleaned material name.

        Examples:
            >>> convention = NamingConvention()
            >>> convention.clean_material_name("Body")
            'Body'
            >>> convention.clean_material_name("mat_Body")
            'Body'
            >>> convention.clean_material_name("Body_ShaderSG")
            'Body'
            >>> convention.clean_material_name("mat_Body_collect")
            'Body'
        """
        name = raw_name

        # Remove suffixes first (order matters for edge cases)
        for suffix in self.strip_suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)]

        # Remove prefixes
        for prefix in self.strip_prefixes:
            if name.startswith(prefix):
                name = name[len(prefix) :]

        return name


def clean_material_name(
    raw_name: str, convention: Optional[NamingConvention] = None
) -> str:
    """Clean a material name using the provided or default convention.

    This is a convenience function that uses DEFAULT_NAMING if no
    convention is provided.

    Args:
        raw_name: Raw material name from USD prim.
        convention: Optional naming convention (uses DEFAULT_NAMING if None).

    Returns:
        str: Cleaned material name.

    Examples:
        >>> clean_material_name("mat_Body_ShaderSG")
        'Body'
        >>> custom = NamingConvention(strip_prefixes=["my_"])
        >>> clean_material_name("my_Body", custom)
        'Body'
    """
    conv = convention or NamingConvention()
    return conv.clean_material_name(raw_name)
