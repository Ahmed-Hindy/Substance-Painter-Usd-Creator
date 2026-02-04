import pytest

pxr = pytest.importorskip("pxr")
from pxr import Gf, Usd, UsdGeom

from axe_usd.dcc.substance_painter import usd_scene_fixup


def test_fixup_authors_mesh_extents_on_render_meshes():
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/root")
    mesh = UsdGeom.Mesh.Define(stage, "/root/MyMesh")
    points = [
        Gf.Vec3f(0, 0, 0),
        Gf.Vec3f(1, 0, 0),
        Gf.Vec3f(1, 2, 0),
        Gf.Vec3f(0, 2, 0),
    ]
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr([4])
    mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])

    usd_scene_fixup.fix_sp_mesh_stage(stage, "/Asset")

    mesh_prim = stage.GetPrimAtPath("/Asset/geo/render/MyMesh")
    assert mesh_prim and mesh_prim.IsValid()
    render_mesh = UsdGeom.Mesh(mesh_prim)
    extent = render_mesh.GetExtentAttr().Get()
    assert extent
    assert len(extent) == 2
    assert extent[0] == Gf.Vec3f(0, 0, 0)
    assert extent[1] == Gf.Vec3f(1, 2, 0)
