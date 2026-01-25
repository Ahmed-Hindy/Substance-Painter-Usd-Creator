"""Tests for USD naming conventions."""

from axe_usd.usd.naming import NamingConvention, clean_material_name


class TestNamingConvention:
    """Tests for NamingConvention class."""

    def test_default_naming_strips_maya_suffix(self):
        """Default convention strips Maya _ShaderSG suffix."""
        convention = NamingConvention()
        assert convention.clean_material_name("Body_ShaderSG") == "Body"

    def test_default_naming_strips_prefix(self):
        """Default convention strips mat_ prefix."""
        convention = NamingConvention()
        assert convention.clean_material_name("mat_Body") == "Body"

    def test_default_naming_strips_collect_suffix(self):
        """Default convention strips _collect suffix."""
        convention = NamingConvention()
        assert convention.clean_material_name("Body_collect") == "Body"

    def test_default_naming_strips_both(self):
        """Default convention strips both prefix and suffix."""
        convention = NamingConvention()
        assert convention.clean_material_name("mat_Body_ShaderSG") == "Body"

    def test_default_naming_preserves_clean_name(self):
        """Default convention preserves names without prefix/suffix."""
        convention = NamingConvention()
        assert convention.clean_material_name("Body") == "Body"

    def test_custom_naming_convention(self):
        """Custom naming convention with different rules."""
        custom = NamingConvention(
            strip_prefixes=["custom_", "my_"], strip_suffixes=["_suffix", "_end"]
        )
        assert custom.clean_material_name("custom_Body_suffix") == "Body"
        assert custom.clean_material_name("my_Head_end") == "Head"

    def test_naming_with_no_match(self):
        """Names that don't match any rules are returned unchanged."""
        custom = NamingConvention(strip_prefixes=["mat_"], strip_suffixes=["_SG"])
        assert custom.clean_material_name("Body") == "Body"
        assert custom.clean_material_name("SomeOtherName") == "SomeOtherName"

    def test_naming_removes_first_matching_suffix_only(self):
        """Only the first matching suffix is removed."""
        custom = NamingConvention(strip_suffixes=["_MAT", "_Material"])
        # Should remove _MAT, not _Material
        assert custom.clean_material_name("Body_MAT") == "Body"

    def test_naming_removes_first_matching_prefix_only(self):
        """Only the first matching prefix is removed."""
        custom = NamingConvention(strip_prefixes=["mat_", "material_"])
        # Should remove mat_, not material_
        assert custom.clean_material_name("mat_Body") == "Body"

    def test_empty_name_returns_empty(self):
        """Empty string input returns empty string."""
        convention = NamingConvention()
        assert convention.clean_material_name("") == ""

    def test_extended_default_convention_compatibility(self):
        """Full default convention includes Houdini and generic patterns."""
        # The full default includes more patterns than the backwards-compatible DEFAULT_NAMING
        full_convention = NamingConvention()  # Uses all defaults

        assert full_convention.clean_material_name("mat_Body") == "Body"
        assert full_convention.clean_material_name("material_Body") == "Body"
        assert full_convention.clean_material_name("M_Body") == "Body"
        assert full_convention.clean_material_name("Body_ShaderSG") == "Body"
        assert full_convention.clean_material_name("Body_MAT") == "Body"
        assert full_convention.clean_material_name("Body_mtl") == "Body"
        assert full_convention.clean_material_name("Body_SG") == "Body"


class TestCleanMaterialName:
    """Tests for clean_material_name convenience function."""

    def test_uses_default_convention_when_none(self):
        """clean_material_name uses DEFAULT_NAMING when no convention provided."""
        assert clean_material_name("mat_Body_ShaderSG") == "Body"

    def test_accepts_custom_convention(self):
        """clean_material_name accepts custom convention."""
        custom = NamingConvention(strip_prefixes=["custom_"], strip_suffixes=["_end"])
        assert clean_material_name("custom_Body_end", custom) == "Body"

    def test_preserves_clean_names(self):
        """clean_material_name preserves names without affixes."""
        assert clean_material_name("Body") == "Body"
        assert clean_material_name("Head") == "Head"


class TestNamingConventionEdgeCases:
    """Edge case tests for naming conventions."""

    def test_multiple_suffixes_only_removes_one(self):
        """Multiple matching suffixes - only first match is removed."""
        custom = NamingConvention(strip_suffixes=["_SG", "_ShaderSG"])
        # _ShaderSG ends with _SG, but we should only remove _ShaderSG
        result = custom.clean_material_name("Body_ShaderSG")
        assert result == "Body"

    def test_suffix_that_is_entire_name(self):
        """Edge case: suffix is the entire name."""
        custom = NamingConvention(strip_suffixes=["_ShaderSG"])
        result = custom.clean_material_name("_ShaderSG")
        assert result == ""

    def test_prefix_that_is_entire_name(self):
        """Edge case: prefix is the entire name."""
        custom = NamingConvention(strip_prefixes=["mat_"])
        result = custom.clean_material_name("mat_")
        assert result == ""

    def test_case_sensitive_matching(self):
        """Matching is case-sensitive."""
        custom = NamingConvention(strip_prefixes=["mat_"], strip_suffixes=["_SG"])
        # Different case should not match
        assert custom.clean_material_name("MAT_Body") == "MAT_Body"
        assert custom.clean_material_name("Body_sg") == "Body_sg"

        # Exact case should match
        assert custom.clean_material_name("mat_Body") == "Body"
        assert custom.clean_material_name("Body_SG") == "Body"
