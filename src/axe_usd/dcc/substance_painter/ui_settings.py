"""Helpers for Substance Painter UI settings."""

ARNOLD_DISPLACEMENT_BUMP = "bump"
ARNOLD_DISPLACEMENT_DISPLACEMENT = "displacement"


def resolve_arnold_displacement_mode(
    arnold_enabled: bool, displacement_enabled: bool
) -> str:
    if arnold_enabled and displacement_enabled:
        return ARNOLD_DISPLACEMENT_DISPLACEMENT
    return ARNOLD_DISPLACEMENT_BUMP
