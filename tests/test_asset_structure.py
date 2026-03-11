"""Tests for USD asset structure utilities."""

from pxr import Kind, Sdf, Usd, UsdGeom

from axe_usd.usd.asset_structure import initialize_component_asset


class TestInitializeComponentAsset:
    """Tests for initialize_component_asset function."""

    def test_creates_root_xform(self):
        """Root prim is created as UsdGeom.Xform."""
        stage = Usd.Stage.CreateInMemory()
        root = initialize_component_asset(stage, "TestAsset")

        assert root.IsValid()
        assert root.IsA(UsdGeom.Xform)
        assert root.GetPath() == Sdf.Path("/TestAsset")

    def test_sets_component_kind(self):
        """Root prim has Kind=component."""
        stage = Usd.Stage.CreateInMemory()
        root = initialize_component_asset(stage, "TestAsset")

        model_api = Usd.ModelAPI(root)
        assert model_api.GetKind() == Kind.Tokens.component

    def test_sets_default_prim(self):
        """Stage defaultPrim is set to the root."""
        stage = Usd.Stage.CreateInMemory()
        root = initialize_component_asset(stage, "TestAsset")

        assert stage.GetDefaultPrim() == root

    def test_creates_class_prim(self):
        """Creates /__class__/<asset_name> for inheritance."""
        stage = Usd.Stage.CreateInMemory()
        initialize_component_asset(stage, "TestAsset")

        class_prim = stage.GetPrimAtPath("/__class__/TestAsset")
        assert class_prim.IsValid()
        assert class_prim.IsAbstract()  # Class prims are abstract

    def test_adds_inheritance(self):
        """Root prim inherits from class prim."""
        stage = Usd.Stage.CreateInMemory()
        root = initialize_component_asset(stage, "TestAsset")

        inherits = root.GetInherits()
        inherited_paths = list(inherits.GetAllDirectInherits())

        assert len(inherited_paths) > 0
        assert Sdf.Path("/__class__/TestAsset") in inherited_paths

    def test_sets_asset_info_name(self):
        """assetInfo contains the asset name."""
        stage = Usd.Stage.CreateInMemory()
        root = initialize_component_asset(stage, "TestAsset")

        name = root.GetAssetInfoByKey("name")
        assert name == "TestAsset"

    def test_sets_asset_info_identifier_default(self):
        """assetInfo identifier defaults to ./<asset_name>.usd."""
        stage = Usd.Stage.CreateInMemory()
        root = initialize_component_asset(stage, "TestAsset")

        identifier = root.GetAssetInfoByKey("identifier")
        assert str(identifier.path) == "./TestAsset.usd"

    def test_sets_asset_info_identifier_custom(self):
        """assetInfo identifier can be customized."""
        stage = Usd.Stage.CreateInMemory()
        root = initialize_component_asset(
            stage, "TestAsset", asset_identifier="/custom/path/asset.usd"
        )

        identifier = root.GetAssetInfoByKey("identifier")
        assert str(identifier.path) == "/custom/path/asset.usd"
