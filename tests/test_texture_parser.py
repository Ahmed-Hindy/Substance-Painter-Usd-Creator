from axe_usd.core.texture_parser import parse_textures


def test_parse_textures_canonicalizes_slots():
    """Ensure texture slots are normalized from export names."""
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


def test_parse_textures_sample_context_payload():
    """Ensure sample payloads produce expected slot sets."""
    textures = {
        ("02_Body", ""): [
            "F:/Users/Ahmed Hindy/Documents/Adobe/Adobe Substance 3D Painter/export/"
            "MeetMat_2019_Cameras_03_CleanedMaterialNames_02_Body_BaseColor.png",
            "F:/Users/Ahmed Hindy/Documents/Adobe/Adobe Substance 3D Painter/export/"
            "MeetMat_2019_Cameras_03_CleanedMaterialNames_02_Body_Metalness.png",
            "F:/Users/Ahmed Hindy/Documents/Adobe/Adobe Substance 3D Painter/export/"
            "MeetMat_2019_Cameras_03_CleanedMaterialNames_02_Body_Roughness.png",
            "F:/Users/Ahmed Hindy/Documents/Adobe/Adobe Substance 3D Painter/export/"
            "MeetMat_2019_Cameras_03_CleanedMaterialNames_02_Body_Normal.png",
            "F:/Users/Ahmed Hindy/Documents/Adobe/Adobe Substance 3D Painter/export/"
            "MeetMat_2019_Cameras_03_CleanedMaterialNames_02_Body_Height.png",
        ],
    }

    bundles = parse_textures(textures)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.name == "02_Body"
    assert set(bundle.textures.keys()) == {
        "basecolor",
        "metalness",
        "roughness",
        "normal",
        "displacement",
    }


def test_parse_textures_missing_maps():
    """Ensure missing maps still produce a bundle with found slots."""
    textures = {
        ("Mat_Minimal", ""): [
            "C:/tex/Mat_Minimal_BaseColor.png",
            "C:/tex/Mat_Minimal_Roughness.png",
        ],
    }

    bundles = parse_textures(textures)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.name == "Mat_Minimal"
    assert set(bundle.textures.keys()) == {"basecolor", "roughness"}


def test_parse_textures_ignores_unknown_textures():
    """Ensure unrecognized textures are ignored."""
    textures = {
        ("Mat_Unknowns", ""): [
            "C:/tex/Mat_Unknowns_BaseColor.png",
            "C:/tex/Mat_Unknowns_Roughness.png",
            "C:/tex/Mat_Unknowns_CustomFoo.png",
            "C:/tex/Mat_Unknowns_Depth.exr",
        ],
    }

    bundles = parse_textures(textures)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.name == "Mat_Unknowns"
    assert set(bundle.textures.keys()) == {"basecolor", "roughness"}
