from axe_usd.usd.material_model import (
    TextureFormatOverrides,
    apply_texture_format_override,
    is_transmissive_material,
    normalize_material_dict,
)


def test_normalize_material_dict_aliases_slots():
    material_dict = {
        "Height": {"mat_name": "MatA", "path": "C:/tex/MatA_Height.exr"},
        "Roughness": {"mat_name": "MatA", "path": "C:/tex/MatA_Roughness.exr"},
    }

    normalized = normalize_material_dict(material_dict)

    assert "displacement" in normalized
    assert "roughness" in normalized


def test_apply_texture_format_override_replaces_suffix():
    path = "C:/tex/MatA_BaseColor.exr"

    overridden = apply_texture_format_override(path, "png")

    assert overridden.replace("\\", "/") == "C:/tex/MatA_BaseColor.png"


def test_apply_texture_format_override_appends_when_missing_suffix():
    path = "C:/tex/MatA_BaseColor"

    overridden = apply_texture_format_override(path, ".jpg")

    assert overridden.replace("\\", "/") == "C:/tex/MatA_BaseColor.jpg"


def test_is_transmissive_material_matches_tokens():
    assert is_transmissive_material("Mat_Glass_Clear")
    assert not is_transmissive_material("Mat_Metal_Painted")


def test_texture_format_overrides_normalizes_keys():
    overrides = TextureFormatOverrides.from_mapping({"Usd_Preview": "jpg", "ARNOLD": ".tif"})

    assert overrides.for_renderer("usd_preview") == "jpg"
    assert overrides.for_renderer("arnold") == ".tif"
    assert overrides.for_renderer("mtlx") == "png"


def test_texture_format_overrides_default_to_png():
    overrides = TextureFormatOverrides.from_mapping(None)

    assert overrides.for_renderer("usd_preview") is None
    assert overrides.for_renderer("arnold") == "png"
    assert overrides.for_renderer("mtlx") == "png"
    assert overrides.for_renderer("openpbr") == "png"
