#!/usr/bin/env python3
"""
=====================================================================
NEXUS QUANTUM // Tests for natural sorting (Python ↔ JS parity)
=====================================================================
File:    tests/test_natural_sort.py
Targets: shared.sorting_logic.natural_sort_key
         shared.sorting_logic.sort_images

These tests mirror `tests/sorting-logic.test.js` to guarantee
cross-runtime parity between the Python CLI and the Web version.

Covers:
    1.  natural_sort_key — basic chunking
    2.  natural_sort_key — edge cases (empty, non-string, zero-pad)
    3.  sort_images — natural sorting
    4.  sort_images — priority-char routing (single, multi, custom)
    5.  sort_images — options (natural off, empty priority, None)
    6.  sort_images — path handling (POSIX, Windows, mixed)
    7.  sort_images — edge cases (empty, single, stability)
    8.  JS ↔ Python parity spot-checks
"""

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import (  # noqa: E402
    natural_sort_key,
    sort_images,
    DEFAULT_PRIORITY_CHARS,
)


# =====================================================================
# § 01 — natural_sort_key : BASIC
# =====================================================================


class TestNaturalSortKeyBasic:
    """Verify chunking behavior of natural_sort_key()."""

    @pytest.mark.unit
    def test_simple_number_chunk(self):
        assert natural_sort_key("file_1.jpg") == ["file_", 1, ".jpg"]
        assert natural_sort_key("file_10.jpg") == ["file_", 10, ".jpg"]

    @pytest.mark.unit
    def test_multiple_numbers(self):
        assert natural_sort_key("ch1_page10.jpg") == [
            "ch", 1, "_page", 10, ".jpg"
        ]

    @pytest.mark.unit
    def test_no_numbers(self):
        assert natural_sort_key("cover.jpg") == ["cover.jpg"]

    @pytest.mark.unit
    def test_only_numbers(self):
        # re.split produces empty string at both ends
        assert natural_sort_key("12345") == ["", 12345, ""]

    @pytest.mark.unit
    def test_leading_number(self):
        assert natural_sort_key("001_file.jpg") == [1, "_file.jpg"]

    @pytest.mark.unit
    def test_zero_padded_normalized(self):
        # Zero-padding is folded into the integer value
        assert natural_sort_key("page_001.jpg") == ["page_", 1, ".jpg"]
        assert natural_sort_key("page_1.jpg") == ["page_", 1, ".jpg"]
        assert natural_sort_key("page_010.jpg") == ["page_", 10, ".jpg"]
        assert natural_sort_key("page_10.jpg") == ["page_", 10, ".jpg"]


# =====================================================================
# § 02 — natural_sort_key : EDGE CASES
# =====================================================================


class TestNaturalSortKeyEdgeCases:
    """Edge cases for input handling."""

    @pytest.mark.unit
    def test_empty_string(self):
        assert natural_sort_key("") == [""]

    @pytest.mark.unit
    def test_non_string_coerced_safely(self):
        """Non-string input must not crash."""
        assert natural_sort_key(None) == [""]
        assert natural_sort_key(42) == ["42"]
        # Objects are stringified
        assert natural_sort_key({"a": 1}) == ["{'a': 1}"]

    @pytest.mark.unit
    def test_very_large_number_does_not_crash(self):
        """The Python implementation caps digit chunks to prevent DoS."""
        # 5000 digits — over the _MAX_DIGITS guard (4000)
        huge = "1" * 5000 + ".jpg"
        # Must not raise; falls back to returning the string chunk
        key = natural_sort_key(huge)
        assert isinstance(key, list)
        assert len(key) >= 1

    @pytest.mark.unit
    def test_mixed_case_preserved(self):
        # natural_sort_key does NOT normalize case
        assert natural_sort_key("Img_1.JPG") == ["Img_", 1, ".JPG"]


# =====================================================================
# § 03 — sort_images : NATURAL SORTING
# =====================================================================


class TestSortImagesNatural:
    """sort_images with natural sorting enabled (default)."""

    @pytest.mark.unit
    def test_simple_numbers_sorted_numerically(self):
        files = ["file_1.jpg", "file_2.jpg", "file_10.jpg", "file_20.jpg"]
        assert sort_images(files) == [
            "file_1.jpg", "file_2.jpg", "file_10.jpg", "file_20.jpg"
        ]

    @pytest.mark.unit
    def test_mixed_order_input(self):
        files = ["file_10.jpg", "file_1.jpg", "file_2.jpg", "file_20.jpg"]
        assert sort_images(files) == [
            "file_1.jpg", "file_2.jpg", "file_10.jpg", "file_20.jpg"
        ]

    @pytest.mark.unit
    def test_zero_padded_stable(self):
        """
        Equal natural keys (page_001 == page_1) preserve input order
        thanks to Python's stable sort.
        """
        files = [
            "page_001.jpg", "page_1.jpg",
            "page_10.jpg", "page_010.jpg", "page_2.jpg",
        ]
        result = sort_images(files)

        # All 5 preserved
        assert len(result) == 5
        assert set(result) == set(files)

        # Numeric ordering
        idx = result.index
        assert idx("page_1.jpg") < idx("page_2.jpg")
        assert idx("page_2.jpg") < idx("page_10.jpg")

        # Stability: page_001 before page_1 (both key == 1)
        assert idx("page_001.jpg") < idx("page_1.jpg")
        # Stability: page_10 before page_010 (both key == 10)
        assert idx("page_10.jpg") < idx("page_010.jpg")

    @pytest.mark.unit
    def test_different_prefixes(self):
        files = ["b_10.jpg", "a_2.jpg", "b_1.jpg", "a_10.jpg"]
        assert sort_images(files) == [
            "a_2.jpg", "a_10.jpg", "b_1.jpg", "b_10.jpg"
        ]

    @pytest.mark.unit
    def test_multiple_numbers(self):
        files = [
            "ch1_page10.jpg", "ch1_page2.jpg",
            "ch2_page1.jpg", "ch10_page1.jpg",
        ]
        assert sort_images(files) == [
            "ch1_page2.jpg", "ch1_page10.jpg",
            "ch2_page1.jpg", "ch10_page1.jpg",
        ]


# =====================================================================
# § 04 — sort_images : PRIORITY FILES
# =====================================================================


class TestSortImagesPriority:

    @pytest.mark.unit
    def test_default_priority_char_is_bang(self):
        assert DEFAULT_PRIORITY_CHARS == "!"

    @pytest.mark.unit
    def test_priority_files_first(self):
        files = [
            "page_10.jpg", "page_1.jpg", "!cover.jpg",
            "page_2.jpg", "!back.jpg", "page_20.jpg",
        ]
        assert sort_images(files) == [
            "!back.jpg", "!cover.jpg",
            "page_1.jpg", "page_2.jpg", "page_10.jpg", "page_20.jpg",
        ]

    @pytest.mark.unit
    def test_priority_files_with_numbers(self):
        files = [
            "page_5.jpg", "!intro_2.jpg", "page_1.jpg",
            "!intro_10.jpg", "!intro_1.jpg", "page_10.jpg",
        ]
        assert sort_images(files) == [
            "!intro_1.jpg", "!intro_2.jpg", "!intro_10.jpg",
            "page_1.jpg", "page_5.jpg", "page_10.jpg",
        ]

    @pytest.mark.unit
    def test_only_normal_files(self):
        files = ["page_10.jpg", "page_1.jpg", "page_2.jpg"]
        assert sort_images(files) == [
            "page_1.jpg", "page_2.jpg", "page_10.jpg"
        ]

    @pytest.mark.unit
    def test_only_priority_files(self):
        files = ["!cover_2.jpg", "!cover_10.jpg", "!cover_1.jpg"]
        assert sort_images(files) == [
            "!cover_1.jpg", "!cover_2.jpg", "!cover_10.jpg"
        ]

    @pytest.mark.unit
    def test_real_world_archive_scenario(self):
        files = [
            "page_0.jpg", "page_1.jpg", "page_9.jpg",
            "page_10.jpg", "page_11.jpg", "page_99.jpg", "page_100.jpg",
            "!front_cover.jpg", "!back_cover.jpg",
        ]
        assert sort_images(files) == [
            "!back_cover.jpg", "!front_cover.jpg",
            "page_0.jpg", "page_1.jpg", "page_9.jpg",
            "page_10.jpg", "page_11.jpg", "page_99.jpg", "page_100.jpg",
        ]


# =====================================================================
# § 05 — sort_images : OPTIONS
# =====================================================================


class TestSortImagesOptions:

    @pytest.mark.unit
    def test_natural_sort_disabled_uses_lexical(self):
        files = ["page_10.jpg", "page_1.jpg", "page_2.jpg"]
        # Lexical: '1' < '10' < '2'
        assert sort_images(files, use_natural_sort=False) == [
            "page_1.jpg", "page_10.jpg", "page_2.jpg"
        ]

    @pytest.mark.unit
    def test_custom_priority_char(self):
        files = [
            "page_10.jpg", "page_1.jpg", "@cover.jpg",
            "page_2.jpg", "@back.jpg",
        ]
        assert sort_images(files, priority_chars="@") == [
            "@back.jpg", "@cover.jpg",
            "page_1.jpg", "page_2.jpg", "page_10.jpg",
        ]

    @pytest.mark.unit
    def test_multi_char_priority(self):
        files = [
            "page_10.jpg", "!cover.jpg", "@special.jpg",
            "page_1.jpg", "!intro.jpg", "@bonus.jpg",
        ]
        assert sort_images(files, priority_chars="!@") == [
            # Priority group: '!' sorts before '@' in ASCII
            "!cover.jpg", "!intro.jpg",
            "@bonus.jpg", "@special.jpg",
            # Normal group
            "page_1.jpg", "page_10.jpg",
        ]

    @pytest.mark.unit
    def test_empty_priority_chars_disables_routing(self):
        files = [
            "page_10.jpg", "!cover.jpg",
            "page_1.jpg", "@special.jpg",
        ]
        # No routing — all files sorted together
        result = sort_images(files, priority_chars="")
        assert len(result) == 4
        assert set(result) == set(files)
        # Natural order: '!' < '@' < letters (ASCII)
        assert result == [
            "!cover.jpg", "@special.jpg",
            "page_1.jpg", "page_10.jpg",
        ]

    @pytest.mark.unit
    def test_none_priority_chars_no_routing(self):
        files = ["page_1.jpg", "!cover.jpg", "page_2.jpg"]
        result = sort_images(files, priority_chars=None)
        assert len(result) == 3
        # No exception, all files preserved
        assert set(result) == set(files)

    @pytest.mark.unit
    def test_disabled_natural_with_priority(self):
        files = [
            "page_10.jpg", "!cover_10.jpg", "page_1.jpg",
            "!cover_1.jpg", "page_2.jpg",
        ]
        assert sort_images(files, use_natural_sort=False, priority_chars="!") == [
            "!cover_1.jpg", "!cover_10.jpg",
            "page_1.jpg", "page_10.jpg", "page_2.jpg",
        ]


# =====================================================================
# § 06 — sort_images : PATH HANDLING
# =====================================================================


class TestSortImagesPaths:

    @pytest.mark.unit
    def test_posix_paths(self):
        files = [
            "path/to/page_10.jpg",
            "path/to/page_1.jpg",
            "path/to/!cover.jpg",
            "path/to/page_2.jpg",
        ]
        assert sort_images(files) == [
            "path/to/!cover.jpg",
            "path/to/page_1.jpg",
            "path/to/page_2.jpg",
            "path/to/page_10.jpg",
        ]

    @pytest.mark.unit
    def test_windows_paths(self):
        files = [
            "folder\\page_10.jpg",
            "folder\\page_1.jpg",
            "folder\\!cover.jpg",
            "folder\\page_2.jpg",
        ]
        assert sort_images(files) == [
            "folder\\!cover.jpg",
            "folder\\page_1.jpg",
            "folder\\page_2.jpg",
            "folder\\page_10.jpg",
        ]

    @pytest.mark.unit
    def test_mixed_paths(self):
        files = [
            "page_10.jpg",
            "subdir/page_1.jpg",
            "!cover.jpg",
            "other\\page_2.jpg",
        ]
        assert sort_images(files) == [
            "!cover.jpg",
            "subdir/page_1.jpg",
            "other\\page_2.jpg",
            "page_10.jpg",
        ]


# =====================================================================
# § 07 — sort_images : EDGE CASES
# =====================================================================


class TestSortImagesEdgeCases:

    @pytest.mark.unit
    def test_empty_array(self):
        assert sort_images([]) == []

    @pytest.mark.unit
    def test_single_file(self):
        assert sort_images(["single.jpg"]) == ["single.jpg"]

    @pytest.mark.unit
    def test_non_array_input_returns_empty(self):
        assert sort_images(None) == []
        assert sort_images(42) == []
        assert sort_images("not-an-array") == []

    @pytest.mark.unit
    def test_non_string_entries_skipped(self):
        mixed = ["img_1.jpg", 42, None, "img_2.jpg", {"x": 1}]
        result = sort_images(mixed)
        assert "img_1.jpg" in result
        assert "img_2.jpg" in result
        # Non-strings filtered out
        assert 42 not in result
        assert None not in result

    @pytest.mark.unit
    def test_does_not_mutate_input(self):
        files = ["b.jpg", "a.jpg", "c.jpg"]
        original = files[:]
        sort_images(files)
        assert files == original

    @pytest.mark.unit
    def test_returns_new_list(self):
        files = ["b.jpg", "a.jpg"]
        result = sort_images(files)
        assert result is not files

    @pytest.mark.unit
    def test_stable_across_calls(self):
        files = ["page_10.jpg", "page_2.jpg", "page_1.jpg"]
        a = sort_images(files)
        b = sort_images(files)
        c = sort_images(files)
        assert a == b == c

    @pytest.mark.unit
    def test_special_chars_dash_and_underscore(self):
        files = ["file-10.jpg", "file-1.jpg", "file_10.jpg", "file_1.jpg"]
        result = sort_images(files)
        # Membership
        assert set(result) == set(files)
        assert len(result) == 4

    @pytest.mark.unit
    def test_no_numbers_alphabetical(self):
        files = ["zebra.jpg", "apple.jpg", "banana.jpg"]
        assert sort_images(files) == ["apple.jpg", "banana.jpg", "zebra.jpg"]


# =====================================================================
# § 08 — PYTHON ↔ JS PARITY SPOT-CHECKS
# =====================================================================
# These mirror the exact assertions in tests/sorting-logic.test.js so
# that any divergence between runtimes breaks CI.


class TestPythonJSParity:
    """Same input → same output in both runtimes."""

    @pytest.mark.unit
    def test_parity_natural_sort(self):
        files = ["file_10.jpg", "file_1.jpg", "file_2.jpg", "file_20.jpg"]
        expected = ["file_1.jpg", "file_2.jpg", "file_10.jpg", "file_20.jpg"]
        assert sort_images(files) == expected

    @pytest.mark.unit
    def test_parity_priority_first(self):
        files = [
            "page_10.jpg", "page_1.jpg", "!cover.jpg",
            "page_2.jpg", "!back.jpg",
        ]
        expected = [
            "!back.jpg", "!cover.jpg",
            "page_1.jpg", "page_2.jpg", "page_10.jpg",
        ]
        assert sort_images(files, use_natural_sort=True, priority_chars="!") == expected

    @pytest.mark.unit
    def test_parity_natural_disabled(self):
        files = [
            "page_10.jpg", "page_1.jpg", "!cover.jpg",
            "page_2.jpg", "!back.jpg",
        ]
        expected = [
            "!back.jpg", "!cover.jpg",
            "page_1.jpg", "page_10.jpg", "page_2.jpg",
        ]
        assert sort_images(files, use_natural_sort=False, priority_chars="!") == expected

    @pytest.mark.unit
    def test_parity_multi_char_priority(self):
        files = ["page_10.jpg", "@special.jpg", "!cover.jpg", "page_2.jpg"]
        expected = [
            "!cover.jpg", "@special.jpg",
            "page_2.jpg", "page_10.jpg",
        ]
        assert sort_images(files, use_natural_sort=True, priority_chars="!@") == expected


# =====================================================================
# § 09 — PYTEST PARAMETRIZED COVERAGE
# =====================================================================


@pytest.mark.unit
@pytest.mark.parametrize("text,expected", [
    ("file_1.jpg",    ["file_", 1, ".jpg"]),
    ("file_10.jpg",   ["file_", 10, ".jpg"]),
    ("file_001.jpg",  ["file_", 1, ".jpg"]),
    ("a1b2c3",        ["a", 1, "b", 2, "c", 3]),
    ("no_digits",     ["no_digits"]),
    ("42",            ["", 42, ""]),
    ("",              [""]),
])
def test_natural_sort_key_parametrized(text, expected):
    assert natural_sort_key(text) == expected


@pytest.mark.unit
@pytest.mark.parametrize("files,expected", [
    (
        ["a_10.jpg", "a_1.jpg", "a_2.jpg"],
        ["a_1.jpg", "a_2.jpg", "a_10.jpg"],
    ),
    (
        ["!b.jpg", "a.jpg"],
        ["!b.jpg", "a.jpg"],
    ),
    (
        ["b.jpg", "a.jpg", "c.jpg"],
        ["a.jpg", "b.jpg", "c.jpg"],
    ),
    (
        ["x_100.jpg", "x_20.jpg", "x_3.jpg"],
        ["x_3.jpg", "x_20.jpg", "x_100.jpg"],
    ),
])
def test_sort_images_parametrized(files, expected):
    assert sort_images(files) == expected
