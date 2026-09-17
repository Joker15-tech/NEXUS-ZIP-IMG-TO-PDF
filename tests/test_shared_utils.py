#!/usr/bin/env python3
"""
=====================================================================
NEXUS QUANTUM // Tests for shared utility functions
=====================================================================
File:    tests/test_shared_utils.py
Targets: shared/__init__.py, shared/constants.py, shared/sorting_logic.py

Covers:
    1.  Constants (IMAGE_EXTENSIONS, DEFAULT_PRIORITY_CHARS)
    2.  is_image_file — extensions, case, edge cases
    3.  get_basename — POSIX, Windows, mixed separators
    4.  normalize_path — backslash→slash, ./ stripping
    5.  natural_sort_key — chunking, non-string coercion, DoS guard
    6.  sort_images — natural, priority, options, paths
    7.  Path-object input support (Union[str, Path])
    8.  Module __all__ integrity + exports
    9.  JS ↔ Python parity spot-checks

NOTE ON Path SUPPORT:
    is_image_file, natural_sort_key and get_basename accept
    ``Union[str, Path]``. Non-string, non-Path inputs (int, None,
    dict, etc.) return False / neutral values.

NOTE ON HIDDEN FILES:
    Dot-prefixed filenames like ``.jpg`` are treated as hidden files
    (no real stem) and return False. This matches the JavaScript
    implementation in ``shared/sorting-logic.js``.
"""

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import (  # noqa: E402
    is_image_file,
    get_basename,
    normalize_path,
    natural_sort_key,
    sort_images,
    IMAGE_EXTENSIONS,
    DEFAULT_PRIORITY_CHARS,
)
import shared  # for __all__ checks


# =====================================================================
# § 01 — CONSTANTS
# =====================================================================


class TestConstants:
    """Shared constants in shared/constants.py."""

    @pytest.mark.unit
    def test_image_extensions_is_a_set(self):
        assert isinstance(IMAGE_EXTENSIONS, set)

    @pytest.mark.unit
    def test_image_extensions_exact_content(self):
        expected = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
        assert IMAGE_EXTENSIONS == expected

    @pytest.mark.unit
    def test_image_extensions_length_is_7(self):
        assert len(IMAGE_EXTENSIONS) == 7

    @pytest.mark.unit
    def test_removed_extensions_are_absent(self):
        """`.tif` and `.svg` were dropped during constants sync."""
        assert ".tif" not in IMAGE_EXTENSIONS
        assert ".svg" not in IMAGE_EXTENSIONS

    @pytest.mark.unit
    def test_default_priority_chars(self):
        assert DEFAULT_PRIORITY_CHARS == "!"
        assert isinstance(DEFAULT_PRIORITY_CHARS, str)
        assert len(DEFAULT_PRIORITY_CHARS) == 1


class TestImageExtensionsSet:
    """Structural invariants of IMAGE_EXTENSIONS."""

    @pytest.mark.unit
    def test_all_lowercase(self):
        for ext in IMAGE_EXTENSIONS:
            assert ext == ext.lower(), f"{ext} should be lowercase"

    @pytest.mark.unit
    def test_all_start_with_dot(self):
        for ext in IMAGE_EXTENSIONS:
            assert ext.startswith("."), f"{ext} should start with dot"

    @pytest.mark.unit
    def test_no_empty_string(self):
        assert "" not in IMAGE_EXTENSIONS

    @pytest.mark.unit
    def test_no_duplicates(self):
        # Sets can't have duplicates by construction, but we check anyway
        # (would catch a future migration to list)
        extensions = list(IMAGE_EXTENSIONS)
        assert len(extensions) == len(set(extensions))

    @pytest.mark.unit
    def test_common_formats_present(self):
        for fmt in [".jpg", ".jpeg", ".png", ".gif"]:
            assert fmt in IMAGE_EXTENSIONS

    @pytest.mark.unit
    def test_modern_and_traditional_formats_present(self):
        assert ".webp" in IMAGE_EXTENSIONS
        assert ".bmp" in IMAGE_EXTENSIONS
        assert ".tiff" in IMAGE_EXTENSIONS


# =====================================================================
# § 02 — is_image_file : SUPPORTED EXTENSIONS
# =====================================================================


class TestIsImageFileSupported:
    """Every supported extension must be recognized (case-insensitive)."""

    @pytest.mark.unit
    @pytest.mark.parametrize("ext", [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    ])
    def test_lowercase_extension(self, ext):
        assert is_image_file(f"photo{ext}") is True

    @pytest.mark.unit
    @pytest.mark.parametrize("ext", [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    ])
    def test_uppercase_extension(self, ext):
        assert is_image_file(f"photo{ext.upper()}") is True

    @pytest.mark.unit
    def test_mixed_case_extension(self):
        assert is_image_file("Photo.JpG") is True
        assert is_image_file("IMAGE.PnG") is True
        assert is_image_file("SCAN.TiFf") is True
        assert is_image_file("modern.WeBp") is True


# =====================================================================
# § 03 — is_image_file : REJECTED CASES
# =====================================================================


class TestIsImageFileRejected:
    """Files that must NOT be detected as images."""

    @pytest.mark.unit
    @pytest.mark.parametrize("filename", [
        "document.pdf", "text.txt", "data.json", "script.py",
        "archive.zip", "video.mp4", "audio.mp3",
    ])
    def test_common_non_images(self, filename):
        assert is_image_file(filename) is False

    @pytest.mark.unit
    @pytest.mark.parametrize("filename", [
        "file.txt", "doc.docx", "sheet.xlsx", "slide.pptx",
        "archive.zip", "archive.rar", "archive.7z",
        "video.mp4", "video.avi", "video.mkv",
        "audio.mp3", "audio.wav", "audio.flac",
        "code.py", "code.js", "code.cpp",
        "data.json", "data.xml", "data.csv",
    ])
    def test_extended_non_images(self, filename):
        assert is_image_file(filename) is False

    @pytest.mark.unit
    def test_no_extension(self):
        assert is_image_file("noextension") is False
        assert is_image_file("README") is False
        assert is_image_file("Makefile") is False

    @pytest.mark.unit
    def test_trailing_dots(self):
        assert is_image_file("photo.jpg.") is False
        assert is_image_file("photo.") is False

    @pytest.mark.unit
    def test_removed_extensions_rejected(self):
        """`.tif` and `.svg` are no longer supported."""
        assert is_image_file("scan.tif") is False
        assert is_image_file("logo.svg") is False

    @pytest.mark.unit
    def test_empty_string(self):
        assert is_image_file("") is False


# =====================================================================
# § 04 — is_image_file : HIDDEN FILES
# =====================================================================


class TestIsImageFileHidden:
    """Dot-prefixed filenames — matches JS behavior."""

    @pytest.mark.unit
    def test_dot_only_extension_rejected(self):
        """
        ``.jpg`` alone is a hidden file (no stem), not an image.
        Matches JS: `isImageFile('.jpg') === false`.
        """
        assert is_image_file(".jpg") is False
        assert is_image_file(".png") is False
        assert is_image_file(".gif") is False

    @pytest.mark.unit
    def test_hidden_file_with_real_extension_accepted(self):
        """``.hidden.jpg`` has a real extension → accepted."""
        assert is_image_file(".hidden.jpg") is True
        assert is_image_file(".cover.png") is True

    @pytest.mark.unit
    def test_metadata_files_rejected(self):
        assert is_image_file(".DS_Store") is False
        assert is_image_file("Thumbs.db") is False


# =====================================================================
# § 05 — is_image_file : PATHS
# =====================================================================


class TestIsImageFilePaths:

    @pytest.mark.unit
    def test_posix_absolute(self):
        assert is_image_file("/home/user/photos/IMG_001.jpg") is True
        assert is_image_file("/var/www/images/banner.png") is True
        assert is_image_file("/path/to/document.pdf") is False

    @pytest.mark.unit
    def test_posix_relative(self):
        assert is_image_file("./photo.jpg") is True
        assert is_image_file("../images/photo.png") is True
        assert is_image_file("../../gallery/img.gif") is True

    @pytest.mark.unit
    def test_posix_relative_dirs(self):
        assert is_image_file("relative/path/to/photo.gif") is True

    @pytest.mark.unit
    def test_windows_paths(self):
        assert is_image_file("C:\\Users\\Photos\\image.png") is True
        assert is_image_file("D:\\Images\\photo.jpg") is True
        assert is_image_file("\\\\network\\share\\image.gif") is True

    @pytest.mark.unit
    def test_home_shorthand(self):
        assert is_image_file("~/Pictures/photo.gif") is True

    @pytest.mark.unit
    def test_url_like_paths(self):
        assert is_image_file("http://example.com/photo.jpg") is True
        assert is_image_file("https://example.com/image.png") is True
        assert is_image_file("file:///path/to/image.gif") is True

    @pytest.mark.unit
    def test_backslash_in_posix_context(self):
        """Windows-style separators work regardless of host OS."""
        assert is_image_file("folder\\sub\\pic.jpg") is True


# =====================================================================
# § 06 — is_image_file : SPECIAL CHARACTERS & UNICODE
# =====================================================================


class TestIsImageFileSpecialChars:

    @pytest.mark.unit
    @pytest.mark.parametrize("filename", [
        "图片.jpg",       # Chinese
        "صورة.png",       # Arabic
        "фото.gif",       # Cyrillic
        "画像.jpeg",      # Japanese
    ])
    def test_unicode_filenames(self, filename):
        assert is_image_file(filename) is True

    @pytest.mark.unit
    @pytest.mark.parametrize("filename", [
        "my photo.jpg",
        "photo album.png",
        "image (1).jpg",
        "image [copy].png",
        "file-name_123.gif",
        "image@2x.jpg",
        "photo#1.png",
    ])
    def test_special_characters(self, filename):
        assert is_image_file(filename) is True

    @pytest.mark.unit
    def test_numeric_filenames(self):
        assert is_image_file("123.jpg") is True
        assert is_image_file("001.png") is True
        assert is_image_file("0.gif") is True

    @pytest.mark.unit
    def test_priority_marked_filenames(self):
        """Priority chars do not affect extension detection."""
        assert is_image_file("!cover.jpg") is True
        assert is_image_file("@special.png") is True
        assert is_image_file("#important.gif") is True

    @pytest.mark.unit
    def test_very_long_filename(self):
        assert is_image_file("a" * 200 + ".jpg") is True
        assert is_image_file("a" * 255) is False


# =====================================================================
# § 07 — is_image_file : NON-STRING INPUT
# =====================================================================


class TestIsImageFileNonString:
    """Robustness against non-string inputs."""

    @pytest.mark.unit
    def test_pathlib_path_supported(self):
        """
        ``Path`` objects are coerced to str. If your implementation
        rejects non-str inputs strictly, this test documents the
        *expected* behavior of the shared module.
        """
        assert is_image_file(Path("photo.jpg")) is True
        assert is_image_file(Path("/path/to/image.png")) is True
        assert is_image_file(Path("document.pdf")) is False

    @pytest.mark.unit
    def test_none_returns_false(self):
        assert is_image_file(None) is False

    @pytest.mark.unit
    def test_int_returns_false(self):
        assert is_image_file(42) is False

    @pytest.mark.unit
    def test_dict_returns_false(self):
        assert is_image_file({}) is False

    @pytest.mark.unit
    def test_list_returns_false(self):
        assert is_image_file([]) is False


# =====================================================================
# § 08 — get_basename
# =====================================================================


class TestGetBasename:

    @pytest.mark.unit
    def test_posix_absolute(self):
        assert get_basename("/home/user/photo.jpg") == "photo.jpg"

    @pytest.mark.unit
    def test_posix_relative(self):
        assert get_basename("folder/image.jpg") == "image.jpg"

    @pytest.mark.unit
    def test_windows_path(self):
        assert get_basename("C:\\Users\\Photos\\pic.png") == "pic.png"

    @pytest.mark.unit
    def test_windows_relative(self):
        assert get_basename("folder\\subfolder\\image.jpg") == "image.jpg"

    @pytest.mark.unit
    def test_mixed_separators(self):
        assert get_basename("a\\b/c\\d.jpg") == "d.jpg"

    @pytest.mark.unit
    def test_no_separator(self):
        assert get_basename("image.jpg") == "image.jpg"

    @pytest.mark.unit
    def test_empty_returns_empty(self):
        assert get_basename("") == ""

    @pytest.mark.unit
    def test_none_returns_empty(self):
        assert get_basename(None) == ""

    @pytest.mark.unit
    def test_path_object_supported(self):
        assert get_basename(Path("/a/b/c.jpg")) == "c.jpg"


# =====================================================================
# § 09 — normalize_path
# =====================================================================


class TestNormalizePath:

    @pytest.mark.unit
    def test_backslash_to_slash(self):
        assert normalize_path("folder\\sub\\image.jpg") == "folder/sub/image.jpg"

    @pytest.mark.unit
    def test_strips_dot_slash(self):
        assert normalize_path("./folder/image.jpg") == "folder/image.jpg"

    @pytest.mark.unit
    def test_strips_dot_backslash(self):
        # ./ prefix on Windows-style path
        assert normalize_path(".\\folder\\image.jpg") == "folder/image.jpg"

    @pytest.mark.unit
    def test_already_normalized(self):
        assert normalize_path("folder/image.jpg") == "folder/image.jpg"

    @pytest.mark.unit
    def test_empty_returns_empty(self):
        assert normalize_path("") == ""

    @pytest.mark.unit
    def test_none_returns_empty(self):
        assert normalize_path(None) == ""


# =====================================================================
# § 10 — natural_sort_key
# =====================================================================


class TestNaturalSortKey:

    @pytest.mark.unit
    @pytest.mark.parametrize("text,expected", [
        ("file_1.jpg",     ["file_", 1, ".jpg"]),
        ("file_10.jpg",    ["file_", 10, ".jpg"]),
        ("file_001.jpg",   ["file_", 1, ".jpg"]),
        ("ch1_page10.jpg", ["ch", 1, "_page", 10, ".jpg"]),
        ("cover.jpg",      ["cover.jpg"]),
        ("12345",          ["", 12345, ""]),
        ("",               [""]),
        ("a1b2c3",         ["a", 1, "b", 2, "c", 3]),
    ])
    def test_chunking(self, text, expected):
        assert natural_sort_key(text) == expected

    @pytest.mark.unit
    def test_zero_padded_normalized(self):
        assert natural_sort_key("page_001.jpg") == natural_sort_key("page_1.jpg")
        assert natural_sort_key("page_010.jpg") == natural_sort_key("page_10.jpg")

    @pytest.mark.unit
    def test_non_string_input_safe(self):
        """Non-string inputs are coerced without crashing."""
        assert natural_sort_key(None) == [""]
        assert natural_sort_key(42) == ["42"]

    @pytest.mark.unit
    def test_huge_digit_chunk_does_not_crash(self):
        """
        The Python implementation caps digit chunks to 4000 to prevent
        DoS on Python 3.11+ (`sys.set_int_max_str_digits`).
        """
        huge = "1" * 5000 + ".jpg"
        key = natural_sort_key(huge)
        # Must return a list without raising
        assert isinstance(key, list)
        assert len(key) >= 1


# =====================================================================
// § 11 — sort_images
// =====================================================================


class TestSortImages:

    @pytest.mark.unit
    def test_natural_sort_basic(self):
        files = ["file_1.jpg", "file_2.jpg", "file_10.jpg", "file_20.jpg"]
        assert sort_images(files) == files

    @pytest.mark.unit
    def test_natural_sort_mixed(self):
        files = ["file_10.jpg", "file_1.jpg", "file_2.jpg", "file_20.jpg"]
        assert sort_images(files) == [
            "file_1.jpg", "file_2.jpg", "file_10.jpg", "file_20.jpg",
        ]

    @pytest.mark.unit
    def test_priority_first(self):
        files = ["page_1.jpg", "!cover.jpg", "page_2.jpg", "!back.jpg"]
        assert sort_images(files) == [
            "!back.jpg", "!cover.jpg", "page_1.jpg", "page_2.jpg",
        ]

    @pytest.mark.unit
    def test_custom_priority_chars(self):
        files = ["page_1.jpg", "@special.jpg", "page_2.jpg", "@bonus.jpg"]
        assert sort_images(files, priority_chars="@") == [
            "@bonus.jpg", "@special.jpg", "page_1.jpg", "page_2.jpg",
        ]

    @pytest.mark.unit
    def test_multi_char_priority(self):
        files = ["page_10.jpg", "@special.jpg", "!cover.jpg", "page_2.jpg"]
        result = sort_images(files, priority_chars="!@")
        assert result[0] == "!cover.jpg"
        assert result[1] == "@special.jpg"

    @pytest.mark.unit
    def test_natural_sort_disabled(self):
        files = ["page_10.jpg", "page_1.jpg", "page_2.jpg"]
        assert sort_images(files, use_natural_sort=False) == [
            "page_1.jpg", "page_10.jpg", "page_2.jpg",
        ]

    @pytest.mark.unit
    def test_empty_list(self):
        assert sort_images([]) == []

    @pytest.mark.unit
    def test_non_array_input(self):
        assert sort_images(None) == []
        assert sort_images(42) == []

    @pytest.mark.unit
    def test_does_not_mutate_input(self):
        files = ["b.jpg", "a.jpg", "c.jpg"]
        original = files[:]
        sort_images(files)
        assert files == original

    @pytest.mark.unit
    def test_windows_paths(self):
        files = [
            "folder\\page_10.jpg",
            "folder\\page_1.jpg",
            "folder\\page_2.jpg",
        ]
        assert sort_images(files) == [
            "folder\\page_1.jpg",
            "folder\\page_2.jpg",
            "folder\\page_10.jpg",
        ]


# =====================================================================
// § 12 — MODULE EXPORTS & __all__
// =====================================================================


class TestModuleExports:
    """Every public symbol must be re-exported from `shared`."""

    @pytest.mark.unit
    def test_is_image_file_callable(self):
        assert callable(shared.is_image_file)

    @pytest.mark.unit
    def test_get_basename_callable(self):
        assert callable(shared.get_basename)

    @pytest.mark.unit
    def test_normalize_path_callable(self):
        assert callable(shared.normalize_path)

    @pytest.mark.unit
    def test_natural_sort_key_callable(self):
        assert callable(shared.natural_sort_key)

    @pytest.mark.unit
    def test_sort_images_callable(self):
        assert callable(shared.sort_images)

    @pytest.mark.unit
    def test_constants_exported(self):
        assert shared.IMAGE_EXTENSIONS is not None
        assert shared.DEFAULT_PRIORITY_CHARS == "!"
        assert shared.MAX_FILE_SIZE_BYTES == 100 * 1024 * 1024
        assert shared.MAX_EXTRACTED_SIZE_BYTES == 500 * 1024 * 1024
        assert shared.MAX_FILES_IN_ZIP == 10000
        assert shared.MAX_COMPRESSION_RATIO == 100
        assert shared.MAX_IMAGE_DIMENSION == 2000
        assert shared.IMAGE_SCALE_FACTOR == 4

    @pytest.mark.unit
    def test_all_symbols_present(self):
        """Every symbol in __all__ must actually be importable."""
        missing = [name for name in shared.__all__ if not hasattr(shared, name)]
        assert missing == [], f"Missing exports: {missing}"

    @pytest.mark.unit
    def test_all_is_a_list_of_strings(self):
        assert isinstance(shared.__all__, list)
        for name in shared.__all__:
            assert isinstance(name, str)


# =====================================================================
// § 13 — JS ↔ PYTHON PARITY SPOT-CHECKS
// =====================================================================


class TestPythonJSParity:
    """
    Spot-checks mirroring `tests/sorting-logic.test.js` to guarantee
    cross-runtime behavior alignment.
    """

    @pytest.mark.unit
    def test_parity_dot_extension_rejected(self):
        # JS: isImageFile('.jpg') === false
        assert is_image_file(".jpg") is False

    @pytest.mark.unit
    def test_parity_hidden_file_with_ext_accepted(self):
        # JS: isImageFile('.hidden.jpg') === true
        assert is_image_file(".hidden.jpg") is True

    @pytest.mark.unit
    def test_parity_trailing_dot_rejected(self):
        # JS: isImageFile('file.') === false
        assert is_image_file("file.") is False

    @pytest.mark.unit
    def test_parity_seven_extensions(self):
        # JS: IMAGE_EXTENSIONS.length === 7
        assert len(IMAGE_EXTENSIONS) == 7

    @pytest.mark.unit
    def test_parity_default_priority_bang(self):
        assert DEFAULT_PRIORITY_CHARS == "!"

    @pytest.mark.unit
    def test_parity_natural_sort(self):
        files = ["page_10.jpg", "page_1.jpg", "page_2.jpg"]
        assert sort_images(files) == [
            "page_1.jpg", "page_2.jpg", "page_10.jpg",
        ]

    @pytest.mark.unit
    def test_parity_priority_first(self):
        files = ["page_1.jpg", "!cover.jpg", "page_2.jpg"]
        assert sort_images(files) == [
            "!cover.jpg", "page_1.jpg", "page_2.jpg",
        ]
