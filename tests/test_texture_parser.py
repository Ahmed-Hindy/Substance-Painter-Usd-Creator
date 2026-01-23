from sp_usd_creator.core.texture_parser import parse_textures


def test_parse_textures_canonicalizes_slots():
    textures = {
        ("Mat_A", "set"): [
            "C:/tex/Mat_A_Base_Color.png",
            "C:/tex/Mat_A_Metallic.png",
            "C:/tex/Mat_A_Roughness.png",
            "C:/tex/Mat_A_Height.png",
        ]
    }

    bundles = parse_textures(textures)
    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.name == "Mat_A"
    assert bundle.textures["basecolor"].endswith("Base_Color.png")
    assert bundle.textures["metalness"].endswith("Metallic.png")
    assert bundle.textures["roughness"].endswith("Roughness.png")
    assert bundle.textures["displacement"].endswith("Height.png")
