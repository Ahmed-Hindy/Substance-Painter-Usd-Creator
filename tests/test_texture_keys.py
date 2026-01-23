from axe_usd.core.texture_keys import slot_from_path


def test_slot_from_path_ao_matches_token():
    """Ensure AO tokens normalize to occlusion."""
    assert slot_from_path("C:/tex/Mat_ao.png") == "occlusion"


def test_slot_from_path_ao_not_substring():
    """Ensure substring collisions do not match slots."""
    assert slot_from_path("C:/tex/chaos.png") is None
