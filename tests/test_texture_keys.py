from sp_usd_creator.core.texture_keys import slot_from_path


def test_slot_from_path_ao_matches_token():
    assert slot_from_path("C:/tex/Mat_ao.png") == "occlusion"


def test_slot_from_path_ao_not_substring():
    assert slot_from_path("C:/tex/chaos.png") is None
