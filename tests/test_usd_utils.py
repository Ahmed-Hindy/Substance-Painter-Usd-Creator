import pytest

from pxr import Usd, UsdShade

from axe_usd.usd.utils import collect_prims_of_type


def test_collect_prims_of_type_finds_materials():
    """Ensure collect_prims_of_type finds material prims."""
    stage = Usd.Stage.CreateInMemory()
    UsdShade.Material.Define(stage, "/Root/material/MatA")

    root = stage.GetPrimAtPath("/Root")
    ok, found = collect_prims_of_type(root, UsdShade.Material, recursive=True)

    assert ok is True
    assert len(found) == 1
    assert found[0].GetPath().pathString == "/Root/material/MatA"
