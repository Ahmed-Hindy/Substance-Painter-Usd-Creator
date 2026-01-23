from sp_usd_creator.core.texture_parser import parse_textures


def test_parse_textures_skips_empty_bundle():
    textures = {
        ("Mat_Empty", "set"): [
            "C:/tex/Mat_Empty_Custom.png",
        ]
    }

    bundles = parse_textures(textures)
    assert bundles == []
