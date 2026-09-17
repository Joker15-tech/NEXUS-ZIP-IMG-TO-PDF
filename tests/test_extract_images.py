#!/usr/bin/env python3
"""
=====================================================================
NEXUS QUANTUM // Tests for extract_images_from_zip()
=====================================================================
File:    tests/test_extract_images.py
Target:  python/zipped_imgs_to_pdf.extract_images_from_zip

Covers:
    1.  Basic extraction (single, multiple, filters, empty)
    2.  Sorting (natural, lexical, priority-char routing)
    3.  Directory entries (skip dirs, nested dirs)
    4.  Error handling (invalid, corrupted, permission, missing)
    5.  Image formats (all 7 extensions, case-insensitivity)
    6.  Real-world scenarios (archive, photo album, mixed content)
    7.  Content verification (extracted bytes == original bytes) [NEW]
    8.  Windows paths inside ZIP [NEW]
    9.  Extract-dir auto-creation [NEW]
    10. Priority chars edge cases (empty, None) [NEW]

CONTRACT (from the corrected CLI):
    - ``extract_images_from_zip`` RAISES on:
        * FileNotFoundError  — ZIP path missing
        * zipfile.BadZipFile — invalid / truncated archive
        * ZipSecurityError   — security limits exceeded
        * PermissionError    — cannot read / write
        * OSError            — disk full, etc.
      It RETURNS ``[]`` (not raises) when the archive is valid but
      contains no images.

    - Return value is a sorted ``List[Path]`` of extracted images.
"""

import os
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------
from python.zipped_imgs_to_pdf import (  # noqa: E402
    extract_images_from_zip,
    ZipSecurityError,
)
from shared import DEFAULT_PRIORITY_CHARS  # noqa: E402


IS_WINDOWS = os.name == "nt"

# =====================================================================
# § 01 — FIXTURES
# =====================================================================


@pytest.fixture
def temp_dir():
    """Yield a fresh temporary directory (auto-cleaned)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def create_test_zip():
    """
    Factory: builds a ZIP from a mapping {name: bytes} or list of names.

    When a list is given, each entry receives a deterministic payload
    ``b'fake image content:<name>'`` so we can verify content later.
    """
    def _create(zip_path, files):
        zip_path = Path(zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if isinstance(files, dict):
                for name, content in files.items():
                    zf.writestr(name, content)
            else:
                for name in files:
                    zf.writestr(name, f"fake image content:{name}".encode())
        return zip_path
    return _create


@pytest.fixture
def extract_dir(temp_dir):
    """Fresh, existing extraction directory."""
    d = temp_dir / "extract"
    d.mkdir()
    return d


# =====================================================================
# § 02 — BASIC EXTRACTION
# =====================================================================


class TestExtractImagesBasic:

    @pytest.mark.unit
    def test_extract_single_image(self, temp_dir, create_test_zip, extract_dir):
        zip_path = create_test_zip(temp_dir / "single.zip", ["image.jpg"])

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 1
        assert result[0].name == "image.jpg"
        assert result[0].exists()

    @pytest.mark.unit
    def test_extract_multiple_images(self, temp_dir, create_test_zip, extract_dir):
        zip_path = create_test_zip(
            temp_dir / "multiple.zip",
            ["img1.jpg", "img2.png", "img3.gif"],
        )

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 3
        for p in result:
            assert p.exists()
            assert p.is_file()

    @pytest.mark.unit
    def test_filter_non_image_files(self, temp_dir, create_test_zip, extract_dir):
        zip_path = create_test_zip(
            temp_dir / "mixed.zip",
            ["image1.jpg", "document.pdf", "image2.png", "text.txt", "data.json"],
        )

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 2
        suffixes = {f.suffix.lower() for f in result}
        assert suffixes == {".jpg", ".png"}

    @pytest.mark.unit
    def test_empty_zip_returns_empty_list(self, temp_dir, create_test_zip, extract_dir):
        zip_path = create_test_zip(temp_dir / "empty.zip", [])

        result = extract_images_from_zip(zip_path, extract_dir)

        assert result == []

    @pytest.mark.unit
    def test_zip_with_only_non_images(self, temp_dir, create_test_zip, extract_dir):
        zip_path = create_test_zip(
            temp_dir / "no_images.zip",
            ["document.pdf", "text.txt", "data.csv"],
        )

        result = extract_images_from_zip(zip_path, extract_dir)

        assert result == []

    @pytest.mark.unit
    def test_extracted_files_have_correct_content(
        self, temp_dir, create_test_zip, extract_dir
    ):
        """Verify the bytes on disk match what was inside the ZIP."""
        payloads = {
            "a.jpg": b"\xAA\xBB\xCC" * 100,
            "b.png": b"\x01\x02\x03" * 50,
        }
        zip_path = create_test_zip(temp_dir / "content.zip", payloads)

        result = extract_images_from_zip(zip_path, extract_dir)

        extracted = {p.name: p.read_bytes() for p in result}
        assert extracted["a.jpg"] == payloads["a.jpg"]
        assert extracted["b.png"] == payloads["b.png"]

    @pytest.mark.unit
    def test_extract_dir_is_auto_created(self, temp_dir, create_test_zip):
        """extract_images_from_zip must create the target dir if missing."""
        zip_path = create_test_zip(temp_dir / "auto.zip", ["image.jpg"])

        # Not pre-created
        target = temp_dir / "auto_created" / "nested"

        result = extract_images_from_zip(zip_path, target)

        assert target.exists()
        assert target.is_dir()
        assert len(result) == 1


# =====================================================================
# § 03 — SORTING
# =====================================================================


class TestExtractImagesSorting:

    @pytest.mark.unit
    def test_natural_sorting_default(self, temp_dir, create_test_zip, extract_dir):
        zip_path = create_test_zip(
            temp_dir / "sorting.zip",
            ["img_10.jpg", "img_1.jpg", "img_2.jpg", "img_20.jpg"],
        )

        result = extract_images_from_zip(zip_path, extract_dir)

        names = [f.name for f in result]
        assert names == ["img_1.jpg", "img_2.jpg", "img_10.jpg", "img_20.jpg"]

    @pytest.mark.unit
    def test_natural_sorting_enabled_explicitly(
        self, temp_dir, create_test_zip, extract_dir
    ):
        zip_path = create_test_zip(
            temp_dir / "nat.zip",
            ["img_10.jpg", "img_1.jpg", "img_2.jpg", "img_20.jpg"],
        )

        result = extract_images_from_zip(
            zip_path, extract_dir, use_natural_sort=True
        )

        names = [f.name for f in result]
        assert names == ["img_1.jpg", "img_2.jpg", "img_10.jpg", "img_20.jpg"]

    @pytest.mark.unit
    def test_natural_sorting_disabled_uses_lexical(
        self, temp_dir, create_test_zip, extract_dir
    ):
        zip_path = create_test_zip(
            temp_dir / "lexical.zip",
            ["img_10.jpg", "img_1.jpg", "img_2.jpg"],
        )

        result = extract_images_from_zip(
            zip_path, extract_dir, use_natural_sort=False
        )

        names = [f.name for f in result]
        # Lexical: '1' < '10' < '2'
        assert names == ["img_1.jpg", "img_10.jpg", "img_2.jpg"]

    @pytest.mark.unit
    def test_default_priority_char_from_shared(self, temp_dir, create_test_zip, extract_dir):
        """The CLI's default priority char comes from shared constants."""
        assert DEFAULT_PRIORITY_CHARS == "!"

        zip_path = create_test_zip(
            temp_dir / "def_prio.zip",
            ["page_1.jpg", "!cover.jpg", "page_2.jpg"],
        )

        result = extract_images_from_zip(zip_path, extract_dir)

        names = [f.name for f in result]
        assert names[0] == "!cover.jpg"

    @pytest.mark.unit
    def test_priority_files_first(self, temp_dir, create_test_zip, extract_dir):
        zip_path = create_test_zip(
            temp_dir / "priority.zip",
            ["page_1.jpg", "!cover.jpg", "page_2.jpg", "!back.jpg"],
        )

        result = extract_images_from_zip(zip_path, extract_dir)

        names = [f.name for f in result]
        assert names[:2] == ["!back.jpg", "!cover.jpg"]
        assert names[2:] == ["page_1.jpg", "page_2.jpg"]

    @pytest.mark.unit
    def test_custom_priority_chars(self, temp_dir, create_test_zip, extract_dir):
        zip_path = create_test_zip(
            temp_dir / "custom_prio.zip",
            ["page_1.jpg", "@special.jpg", "page_2.jpg", "@bonus.jpg"],
        )

        result = extract_images_from_zip(
            zip_path, extract_dir, priority_chars="@"
        )

        names = [f.name for f in result]
        assert names[:2] == ["@bonus.jpg", "@special.jpg"]
        assert names[2:] == ["page_1.jpg", "page_2.jpg"]

    @pytest.mark.unit
    def test_empty_priority_chars(self, temp_dir, create_test_zip, extract_dir):
        """Empty string → no priority routing."""
        zip_path = create_test_zip(
            temp_dir / "empty_prio.zip",
            ["page_1.jpg", "!cover.jpg", "page_2.jpg"],
        )

        result = extract_images_from_zip(
            zip_path, extract_dir, priority_chars=""
        )

        names = [f.name for f in result]
        # No priority → all files sorted together
        assert len(names) == 3

    @pytest.mark.unit
    def test_multi_char_priority(self, temp_dir, create_test_zip, extract_dir):
        zip_path = create_test_zip(
            temp_dir / "multi_prio.zip",
            ["page_10.jpg", "@special.jpg", "!cover.jpg", "page_2.jpg"],
        )

        result = extract_images_from_zip(
            zip_path, extract_dir, priority_chars="!@"
        )

        names = [f.name for f in result]
        # Both '!' and '@' entries come first (lexical order within group)
        assert names[0] == "!cover.jpg"
        assert names[1] == "@special.jpg"


# =====================================================================
# § 04 — DIRECTORIES
# =====================================================================


class TestExtractImagesDirectories:

    @pytest.mark.unit
    def test_skip_directory_entries(self, temp_dir, extract_dir):
        zip_path = temp_dir / "with_dirs.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("images/", "")
            zf.writestr("images/subfolder/", "")
            zf.writestr("images/img1.jpg", b"content1")
            zf.writestr("images/subfolder/img2.png", b"content2")

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 2
        for p in result:
            assert p.is_file()
            assert not p.is_dir()

        # Directory entries must not appear as returned Paths
        names = {p.name for p in result}
        assert names == {"img1.jpg", "img2.png"}

    @pytest.mark.unit
    def test_nested_directories_extract_successfully(self, temp_dir, extract_dir):
        zip_path = temp_dir / "nested.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("level1/image1.jpg", b"c1")
            zf.writestr("level1/level2/image2.png", b"c2")
            zf.writestr("level1/level2/level3/image3.gif", b"c3")

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 3
        # Subdirectories preserved on disk
        for p in result:
            assert p.exists()
            assert p.parent != extract_dir  # they're in subdirs

    @pytest.mark.unit
    def test_deeply_nested_path_preserved(self, temp_dir, extract_dir):
        zip_path = temp_dir / "deep.zip"
        deep = "/".join([f"lvl{i}" for i in range(15)]) + "/photo.jpg"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(deep, b"x")

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 1
        assert result[0].name == "photo.jpg"
        assert result[0].exists()


# =====================================================================
# § 05 — ERROR HANDLING
# =====================================================================


class TestExtractImagesErrors:

    @pytest.mark.unit
    def test_invalid_zip_raises_badzipfile(self, temp_dir, extract_dir):
        invalid = temp_dir / "invalid.zip"
        invalid.write_text("This is not a ZIP file")

        with pytest.raises(zipfile.BadZipFile):
            extract_images_from_zip(invalid, extract_dir)

    @pytest.mark.unit
    def test_corrupted_zip_raises_badzipfile(self, temp_dir, extract_dir):
        zip_path = temp_dir / "corrupted.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("image.jpg", b"content")

        # Truncate to half
        data = zip_path.read_bytes()
        zip_path.write_bytes(data[: len(data) // 2])

        with pytest.raises(zipfile.BadZipFile):
            extract_images_from_zip(zip_path, extract_dir)

    @pytest.mark.unit
    def test_nonexistent_zip_raises_filenotfound(self, temp_dir, extract_dir):
        ghost = temp_dir / "ghost.zip"

        with pytest.raises(FileNotFoundError):
            extract_images_from_zip(ghost, extract_dir)

    @pytest.mark.unit
    @pytest.mark.skipif(IS_WINDOWS, reason="chmod semantics differ on Windows")
    def test_permission_error_propagates(self, temp_dir, create_test_zip):
        zip_path = create_test_zip(temp_dir / "perm.zip", ["image.jpg"])

        extract_dir = temp_dir / "readonly"
        extract_dir.mkdir()
        os.chmod(extract_dir, 0o444)  # r--r--r--

        try:
            with pytest.raises(PermissionError):
                extract_images_from_zip(zip_path, extract_dir)
        finally:
            os.chmod(extract_dir, 0o755)

    @pytest.mark.unit
    def test_zip_security_error_propagates(self, temp_dir, create_test_zip, monkeypatch):
        """Security guard raises ZipSecurityError (not a silent return)."""
        import python.zipped_imgs_to_pdf as cli

        zip_path = create_test_zip(temp_dir / "bomb.zip", ["bomb.jpg"])
        monkeypatch.setattr(cli, "MAX_COMPRESSION_RATIO", 0)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        with pytest.raises(ZipSecurityError):
            extract_images_from_zip(zip_path, extract_dir)


# =====================================================================
# § 06 — IMAGE FORMATS
# =====================================================================


class TestExtractImagesImageFormats:

    @pytest.mark.unit
    def test_all_seven_supported_formats(self, temp_dir, create_test_zip, extract_dir):
        files = [
            "image.jpg", "image.jpeg", "image.png", "image.gif",
            "image.bmp", "image.tiff", "image.webp",
        ]
        zip_path = create_test_zip(temp_dir / "formats.zip", files)

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 7
        extensions = {f.suffix.lower() for f in result}
        assert extensions == {
            ".jpg", ".jpeg", ".png", ".gif",
            ".bmp", ".tiff", ".webp",
        }

    @pytest.mark.unit
    def test_case_insensitive_extensions(self, temp_dir, create_test_zip, extract_dir):
        files = ["image1.JPG", "image2.PNG", "image3.GIF", "image4.jpg"]
        zip_path = create_test_zip(temp_dir / "case.zip", files)

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 4

    @pytest.mark.unit
    def test_rejects_removed_extensions(self, temp_dir, create_test_zip, extract_dir):
        """`.tif` and `.svg` were dropped during constants sync."""
        files = ["scan.tif", "logo.svg", "valid.jpg"]
        zip_path = create_test_zip(temp_dir / "removed.zip", files)

        result = extract_images_from_zip(zip_path, extract_dir)

        names = {p.name for p in result}
        assert names == {"valid.jpg"}


# =====================================================================
# § 07 — WINDOWS PATHS INSIDE ZIP  [NEW]
# =====================================================================


class TestWindowsPathsInZip:

    @pytest.mark.unit
    def test_backslash_paths_extracted(self, temp_dir, extract_dir):
        """ZIP entries with backslash separators (Windows-built archives)."""
        zip_path = temp_dir / "winpaths.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            # zipfile always writes forward slashes, so we inject the
            # entry manually by using a ZipInfo with a custom filename.
            info = zipfile.ZipInfo("folder\\subfolder\\image.jpg")
            zf.writestr(info, b"windows-style")

        result = extract_images_from_zip(zip_path, extract_dir)

        # The basename must still be detected as an image
        assert len(result) == 1
        assert result[0].name == "image.jpg"
        assert result[0].exists()

    @pytest.mark.unit
    def test_windows_nested_backslash_path_normalized(
        self, temp_dir, extract_dir
    ):
        zip_path = temp_dir / "winpath2.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            info = zipfile.ZipInfo("a\\b\\c\\photo.png")
            zf.writestr(info, b"data")

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 1
        assert result[0].name == "photo.png"
        # Backslashes must have been normalized to subdirectories
        assert result[0].parent.name == "c"


# =====================================================================
// § 08 — REAL-WORLD SCENARIOS
// =====================================================================


class TestExtractImagesRealWorld:

    @pytest.mark.integration
    def test_archive_file(self, temp_dir, create_test_zip, extract_dir):
        files = [
            "!cover.jpg",
            "page_001.jpg",
            "page_002.jpg",
            "page_003.jpg",
            "page_010.jpg",
            "page_011.jpg",
            "!credits.jpg",
        ]
        zip_path = create_test_zip(temp_dir / "archive.zip", files)

        result = extract_images_from_zip(zip_path, extract_dir)

        names = [f.name for f in result]

        # Priority group: !cover, !credits (lexical: '!' + 'c' both, then
        # 'co' < 'cr' → !cover before !credits)
        assert names[0] == "!cover.jpg"
        assert names[1] == "!credits.jpg"

        # Normal group: natural order
        assert names[2:] == [
            "page_001.jpg", "page_002.jpg", "page_003.jpg",
            "page_010.jpg", "page_011.jpg",
        ]

    @pytest.mark.integration
    def test_photo_album_archive(self, temp_dir, create_test_zip, extract_dir):
        files = [
            "IMG_0010.jpg",
            "IMG_0001.jpg",
            "IMG_0002.jpg",
            "IMG_0100.jpg",
            "Thumbs.db",
            ".DS_Store",
        ]
        zip_path = create_test_zip(temp_dir / "photos.zip", files)

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 4
        names = {f.name for f in result}

        # Natural sort with leading zeros
        ordered = [f.name for f in result]
        assert ordered == [
            "IMG_0001.jpg", "IMG_0002.jpg", "IMG_0010.jpg", "IMG_0100.jpg",
        ]

        assert "Thumbs.db" not in names
        assert ".DS_Store" not in names

    @pytest.mark.integration
    def test_mixed_content_archive(self, temp_dir, create_test_zip, extract_dir):
        files = {
            "photo1.jpg": b"image-1",
            "photo2.png": b"image-2",
            "readme.txt": b"text",
            "document.pdf": b"pdf",
            "data.json": b"{}",
            "script.py": b"print()",
            "photo3.gif": b"image-3",
        }
        zip_path = create_test_zip(temp_dir / "mixed.zip", files)

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 3
        extensions = {f.suffix.lower() for f in result}
        assert extensions == {".jpg", ".png", ".gif"}

        # Content preserved
        contents = {p.name: p.read_bytes() for p in result}
        assert contents["photo1.jpg"] == b"image-1"
        assert contents["photo2.png"] == b"image-2"
        assert contents["photo3.gif"] == b"image-3"

    @pytest.mark.integration
    def test_returned_paths_are_absolute_and_resolved(
        self, temp_dir, create_test_zip, extract_dir
    ):
        zip_path = create_test_zip(temp_dir / "abs.zip", ["photo.jpg"])

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 1
        # Paths are Path objects and exist on disk
        assert isinstance(result[0], Path)
        assert result[0].exists()
        # They point inside the extract_dir
        assert extract_dir.resolve() in result[0].resolve().parents


# =====================================================================
// § 09 — SHARED CONTRACT
// =====================================================================


class TestSharedContract:

    @pytest.mark.unit
    def test_default_priority_chars_is_bang(self):
        """The default priority char comes from shared/constants."""
        assert DEFAULT_PRIORITY_CHARS == "!"

    @pytest.mark.unit
    def test_explicit_none_priority_chars(self, temp_dir, create_test_zip, extract_dir):
        """`priority_chars=None` must not crash."""
        zip_path = create_test_zip(
            temp_dir / "none_prio.zip",
            ["page_1.jpg", "!cover.jpg"],
        )

        result = extract_images_from_zip(
            zip_path, extract_dir, priority_chars=None
        )

        # No routing — all files extracted
        assert len(result) == 2
