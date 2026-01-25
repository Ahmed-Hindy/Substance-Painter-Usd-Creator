"""Tests for ASWF-compliant file structure."""

import pytest
from pathlib import Path

pxr = pytest.importorskip("pxr")

from pxr import Usd, Kind

from axe_usd.usd.asset_files import (
    create_asset_file_structure,
    create_asset_usd_file,
    create_payload_usd_file,
    create_geo_usd_file,
    create_mtl_usd_file,
)


class TestCreateAssetFileStructure:
    """Tests for ASWF file structure creation."""

    def test_creates_asset_directory(self, tmp_path):
        """Creates /AssetName/ directory."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        assert paths.root_dir.exists()
        assert paths.root_dir.name == "TestAsset"

    def test_creates_maps_directory(self, tmp_path):
        """Creates /AssetName/maps/ directory for textures."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        assert paths.maps_dir.exists()
        assert paths.maps_dir.name == "maps"

    def test_path_structure(self, tmp_path):
        """Paths follow ASWF naming convention."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        assert paths.asset_file.name == "TestAsset.usd"
        assert paths.payload_file.name == "payload.usd"
        assert paths.geo_file.name == "geo.usd"
        assert paths.mtl_file.name == "mtl.usd"


class TestCreateAssetUsdFile:
    """Tests for Asset.usd creation."""

    def test_creates_asset_file(self, tmp_path):
        """Creates Asset.usd file."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        stage = create_asset_usd_file(paths, "TestAsset")

        assert paths.asset_file.exists()
        assert stage is not None

    def test_references_payload(self, tmp_path):
        """Asset.usd references payload.usd."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_asset_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.asset_file))
        root = stage.GetPrimAtPath("/TestAsset")

        # Check for payload/reference composition arcs
        assert root.HasAuthoredReferences() or root.HasAuthoredPayloads()

    def test_has_component_kind(self, tmp_path):
        """Root prim has Kind=component."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_asset_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.asset_file))
        root = stage.GetPrimAtPath("/TestAsset")

        model_api = pxr.Usd.ModelAPI(root)
        assert model_api.GetKind() == Kind.Tokens.component

    def test_has_geo_and_mtl_scopes(self, tmp_path):
        """Asset has /geo and /mtl scopes."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_asset_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.asset_file))

        geo = stage.GetPrimAtPath("/TestAsset/geo")
        mtl = stage.GetPrimAtPath("/TestAsset/mtl")

        assert geo.IsValid()
        assert mtl.IsValid()


class TestCreatePayloadUsdFile:
    """Tests for payload.usd creation."""

    def test_creates_payload_file(self, tmp_path):
        """Creates payload.usd file."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        stage = create_payload_usd_file(paths, "TestAsset")

        assert paths.payload_file.exists()
        assert stage is not None

    def test_references_geo_file(self, tmp_path):
        """payload.usd references geo.usd."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_payload_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.payload_file))
        geo_scope = stage.GetPrimAtPath("/TestAsset/geo")

        assert geo_scope.IsValid()
        assert geo_scope.HasAuthoredReferences()


class TestCreateGeoUsdFile:
    """Tests for geo.usd creation."""

    def test_creates_geo_file(self, tmp_path):
        """Creates geo.usd file."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        stage = create_geo_usd_file(paths, "TestAsset", None)

        assert paths.geo_file.exists()
        assert stage is not None

    def test_has_geo_scope(self, tmp_path):
        """geo.usd has /AssetName/geo scope."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_geo_usd_file(paths, "TestAsset", None)

        stage = Usd.Stage.Open(str(paths.geo_file))
        geo_scope = stage.GetPrimAtPath("/TestAsset/geo")

        assert geo_scope.IsValid()


class TestCreateMtlUsdFile:
    """Tests for mtl.usd creation."""

    def test_creates_mtl_file(self, tmp_path):
        """Creates mtl.usd file."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        stage = create_mtl_usd_file(paths, "TestAsset")

        assert paths.mtl_file.exists()
        assert stage is not None

    def test_has_mtl_scope(self, tmp_path):
        """mtl.usd has /AssetName/mtl scope."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")
        create_mtl_usd_file(paths, "TestAsset")

        stage = Usd.Stage.Open(str(paths.mtl_file))
        mtl_scope = stage.GetPrimAtPath("/TestAsset/mtl")

        assert mtl_scope.IsValid()


class TestASWFFileStructureIntegration:
    """Integration tests for complete ASWF file structure."""

    def test_complete_structure_can_be_opened(self, tmp_path):
        """Complete ASWF structure loads correctly."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        # Create all files
        create_geo_usd_file(paths, "TestAsset", None)
        create_payload_usd_file(paths, "TestAsset")
        create_mtl_usd_file(paths, "TestAsset")
        create_asset_usd_file(paths, "TestAsset")

        # Open main asset file
        stage = Usd.Stage.Open(str(paths.asset_file))

        assert stage is not None
        assert stage.GetDefaultPrim().GetPath() == pxr.Sdf.Path("/TestAsset")

    def test_composition_resolves_correctly(self, tmp_path):
        """Composed stage has all prims from referenced files."""
        paths = create_asset_file_structure(tmp_path, "TestAsset")

        # Create all files
        create_geo_usd_file(paths, "TestAsset", None)
        create_payload_usd_file(paths, "TestAsset")
        create_mtl_usd_file(paths, "TestAsset")
        create_asset_usd_file(paths, "TestAsset")

        # Open and verify composition
        stage = Usd.Stage.Open(str(paths.asset_file))

        # Should have scopes from all composed layers
        assert stage.GetPrimAtPath("/TestAsset").IsValid()
        assert stage.GetPrimAtPath("/TestAsset/geo").IsValid()
        assert stage.GetPrimAtPath("/TestAsset/mtl").IsValid()
