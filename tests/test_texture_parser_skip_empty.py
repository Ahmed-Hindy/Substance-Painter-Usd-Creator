from axe_usd.core.texture_parser import parse_textures


def test_parse_textures_skips_empty_bundle():
    """Ensure empty bundles are skipped."""
    textures = {
        ("Mat_Empty", "set"): [
            "C:/tex/Mat_Empty_Custom.png",
        ]
    }

    bundles = parse_textures(textures)
    assert bundles == []
