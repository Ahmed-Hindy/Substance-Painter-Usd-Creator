"""Tests for component-builder file structure."""

import pytest

pxr = pytest.importorskip("pxr")

Usd = pxr.Usd
Kind = pxr.Kind

from axe_usd.usd.asset_files import (  # noqa: E402
    MTL_LIBRARY_ROOT,
    MTL_VARIANT_DEFAULT,
    MTL_VARIANT_SET,
    create_asset_file_structure,
    create_asset_usd_file,
    create_payload_usd_file,
    create_geo_usd_file,
    create_mtl_usd_file,
)


class TestCreateAssetFileStructure:
    """Tests for component-builder file structure creation."""

    def test_creates_asset_directory(self, tmp_path):
        """Creates /AssetName/ directory."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        assert paths.root_dir.exists()
        assert paths.root_dir.name == "TestAsset"

    def test_creates_textures_directory(self, tmp_path):
        """Creates /AssetName/textures/ directory for textures."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        assert paths.textures_dir.exists()
        assert paths.textures_dir.name == "textures"

    def test_path_structure(self, tmp_path):
        """Paths follow component-builder naming convention."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        assert paths.asset_file.name == "TestAsset.usd"
        assert paths.payload_file.name == "payload.usdc"
        assert paths.geo_file.name == "geo.usdc"
        assert paths.mtl_file.name == "mtl.usdc"


class TestCreateAssetUsdFile:
    """Tests for Asset.usd creation."""

    def test_creates_asset_file(self, tmp_path):
        """Creates Asset.usd file."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        stage = create_asset_usd_file(paths, "TestAsset")

        assert paths.asset_file.exists()
        assert stage is not None

    def test_references_payload(self, tmp_path):
        """Asset.usd payloads payload.usdc."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_asset_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.asset_file))
        root = stage.GetPrimAtPath("/TestAsset")

        assert root.HasAuthoredPayloads()

    def test_has_component_kind(self, tmp_path):
        """Root prim has Kind=component."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_asset_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.asset_file))
        root = stage.GetPrimAtPath("/TestAsset")

        model_api = pxr.Usd.ModelAPI(root)
        assert model_api.GetKind() == Kind.Tokens.component

class TestCreatePayloadUsdFile:
    """Tests for payload.usdc creation."""

    def test_creates_payload_file(self, tmp_path):
        """Creates payload.usdc file."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        stage = create_payload_usd_file(paths, "TestAsset")

        assert paths.payload_file.exists()
        assert stage is not None

    def test_references_geo_and_mtl(self, tmp_path):
        """payload.usdc references geo.usdc and mtl.usdc."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_payload_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.payload_file))
        root = stage.GetPrimAtPath("/TestAsset")

        assert root.IsValid()
        refs = root.GetMetadata("references")
        assert refs is not None
        ref_paths = [str(ref.assetPath) for ref in refs.GetAddedOrExplicitItems()]
        assert "./mtl.usdc" in ref_paths
        assert "./geo.usdc" in ref_paths


class TestCreateGeoUsdFile:
    """Tests for geo.usd creation."""

    def test_creates_geo_file(self, tmp_path):
        """Creates geo.usdc file."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        stage = create_geo_usd_file(paths, "TestAsset")

        assert paths.geo_file.exists()
        assert stage is not None

    def test_has_geo_scaffold(self, tmp_path):
        """geo.usdc has /AssetName/geo scaffold."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_geo_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.geo_file))
        geo_scope = stage.GetPrimAtPath("/TestAsset/geo")
        proxy_scope = stage.GetPrimAtPath("/TestAsset/geo/proxy")
        render_scope = stage.GetPrimAtPath("/TestAsset/geo/render")

        assert geo_scope.IsValid()
        assert proxy_scope.IsValid()
        assert render_scope.IsValid()


class TestCreateMtlUsdFile:
    """Tests for mtl.usd creation."""

    def test_creates_mtl_file(self, tmp_path):
        """Creates mtl.usdc file."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        stage = create_mtl_usd_file(paths, "TestAsset")

        assert paths.mtl_file.exists()
        assert stage is not None

    def test_has_mtl_scaffold(self, tmp_path):
        """mtl.usdc has library and variant scaffolding."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_mtl_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.mtl_file))
        root = stage.GetPrimAtPath("/TestAsset")
        library = stage.GetPrimAtPath(f"/{MTL_LIBRARY_ROOT}")
        mtl_scope = stage.GetPrimAtPath(f"/{MTL_LIBRARY_ROOT}/mtl")

        assert root.IsValid()
        assert library.IsValid()
        assert mtl_scope.IsValid()
        variant_set = root.GetVariantSets().GetVariantSet(MTL_VARIANT_SET)
        assert variant_set.IsValid()
        assert MTL_VARIANT_DEFAULT in variant_set.GetVariantNames()


class TestComponentFileStructureIntegration:
    """Integration tests for complete component-builder file structure."""

    def test_complete_structure_can_be_opened(self, tmp_path):
        """Complete structure loads correctly."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        # Create all files
        create_geo_usd_file(paths, "TestAsset")
        create_payload_usd_file(paths, "TestAsset")
        create_mtl_usd_file(paths, "TestAsset")
        create_asset_usd_file(paths, "TestAsset")

        # Open main asset file
        stage = Usd.Stage.Open(str(paths.asset_file))

        assert stage is not None
        assert stage.GetDefaultPrim().GetPath() == pxr.Sdf.Path("/TestAsset")

    def test_composition_resolves_correctly(self, tmp_path):
        """Composed stage has prims from referenced files."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        # Create all files
        create_geo_usd_file(paths, "TestAsset")
        create_payload_usd_file(paths, "TestAsset")
        create_mtl_usd_file(paths, "TestAsset")
        create_asset_usd_file(paths, "TestAsset")

        # Open and verify composition
        stage = Usd.Stage.Open(str(paths.asset_file))

        # Should have scopes from all composed layers
        assert stage.GetPrimAtPath("/TestAsset").IsValid()
        assert stage.GetPrimAtPath("/TestAsset/geo").IsValid()
        assert stage.GetPrimAtPath("/TestAsset/mtl").IsValid()
