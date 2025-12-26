"""Tests for UpdateChecker - version comparison."""

import pytest

from commander.utils.update_checker import compare_versions, parse_version


class TestVersionParsing:
    """Test version string parsing."""

    def test_parse_version_with_v_prefix(self):
        """Test parsing version with v prefix."""
        assert parse_version("v1.2.3") == "1.2.3"

    def test_parse_version_without_prefix(self):
        """Test parsing version without prefix."""
        assert parse_version("1.2.3") == "1.2.3"

    def test_parse_version_multiple_v(self):
        """Test parsing with multiple v's."""
        assert parse_version("vvv1.2.3") == "1.2.3"


class TestVersionComparison:
    """Test version comparison logic."""

    def test_equal_versions(self):
        """Test equal versions."""
        assert compare_versions("1.0.0", "1.0.0") == 0
        assert compare_versions("0.0.1", "0.0.1") == 0

    def test_greater_major(self):
        """Test greater major version."""
        assert compare_versions("2.0.0", "1.0.0") == 1
        assert compare_versions("2.0.0", "1.9.9") == 1

    def test_greater_minor(self):
        """Test greater minor version."""
        assert compare_versions("1.2.0", "1.1.0") == 1
        assert compare_versions("1.2.0", "1.1.9") == 1

    def test_greater_patch(self):
        """Test greater patch version."""
        assert compare_versions("1.0.2", "1.0.1") == 1

    def test_lesser_versions(self):
        """Test lesser versions."""
        assert compare_versions("1.0.0", "2.0.0") == -1
        assert compare_versions("1.0.0", "1.1.0") == -1
        assert compare_versions("1.0.0", "1.0.1") == -1

    def test_different_length_versions(self):
        """Test versions with different number of parts."""
        assert compare_versions("1.0", "1.0.0") == 0
        assert compare_versions("1.0.0.0", "1.0") == 0
        assert compare_versions("1.0.1", "1.0") == 1
        assert compare_versions("1.0", "1.0.1") == -1

    def test_double_digit_versions(self):
        """Test versions with double digit numbers."""
        assert compare_versions("1.10.0", "1.9.0") == 1
        assert compare_versions("1.2.10", "1.2.9") == 1
        assert compare_versions("10.0.0", "9.0.0") == 1
