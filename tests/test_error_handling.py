#!/usr/bin/env python3
"""
=====================================================================
NEXUS QUANTUM // Error Handling Tests for python/zipped_imgs_to_pdf
=====================================================================
File:    tests/test_error_handling.py
Targets: edge cases, error paths, exceptional conditions in the CLI

Covers:
    1.  Special characters & unicode filenames
    2.  File system errors (read-only, permission, disk full)
    3.  ZIP file errors (truncated, empty, encrypted, ZIP64)
    4.  process_zip_file errors
    5.  find_zip_files_recursive errors
    6.  Pillow / image decode errors
    7.  Security limits (ZIP bomb, path traversal, drive paths) [NEW]
    8.  ZipSecurityError propagation [NEW]
    9.  Path-safety helpers in isolation [NEW]
    10. Edge cases (hidden files, duplicates, deep nesting)

IMPORTANT CONTRACT:
    - ``extract_images_from_zip`` raises on:
        * FileNotFoundError  — ZIP missing
        * ZipSecurityError   — size / ratio / count / traversal limits
        * zipfile.BadZipFile — corrupted archive
        * OSError            — disk full / permission
      It returns ``[]`` (not raises) when there are simply no images.

    - ``process_zip_file`` catches those and returns True/False.
"""

import io
import logging
import os
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------
# Pillow (optional)
# ---------------------------------------------------------------------
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None  # type: ignore

# ---------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------
from python.zipped_imgs_to_pdf import (  # noqa: E402
    extract_images_from_zip,
    process_zip_file,
    find_zip_files_recursive,
    ZipSecurityError,
    _is_safe_entry,
    _normalize_zip_entry,
    _is_contained,
    _safe_extract_member,
)

if PILLOW_AVAILABLE:
    from python.zipped_imgs_to_pdf import convert_images_to_pdf  # noqa: E402
else:
    convert_images_to_pdf = None  # type: ignore


IS_WINDOWS = os.name == "nt"

# =====================================================================
# § 01 — FIXTURES
# =====================================================================


@pytest.fixture
def temp_dir():
    """Yield a fresh temporary directory (auto-cleaned)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(autouse=True)
def reset_logging():
    """
    Reset the root logger between tests so logging.basicConfig in the
    CLI actually reconfigures. Without this, the first test that calls
    `main()` freezes the handler set.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    root.handlers = []
    root.setLevel(logging.NOTSET)
    yield
    root.handlers = saved_handlers
    root.setLevel(saved_level)


@pytest.fixture
def make_zip():
    """
    Factory that builds a ZIP from a mapping {inner_name: raw_bytes}.
    """
    def _make(zip_path, entries):
        zip_path = Path(zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries.items():
                zf.writestr(name, data)
        return zip_path
    return _make


@pytest.fixture
def create_test_zip():
    """
    Legacy-shaped fixture used by many existing tests:
    ``create_test_zip(path, ['a.jpg', 'b.png'])``  → fake bytes
    ``create_test_zip(path, {'a.jpg': b'...'})``   → custom bytes
    """
    def _create(zip_path, files):
        zip_path = Path(zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w") as zf:
            if isinstance(files, dict):
                for filename, content in files.items():
                    zf.writestr(filename, content)
            else:
                for filename in files:
                    zf.writestr(filename, b"fake content")
        return zip_path
    return _create


@pytest.fixture
def make_real_image():
    """Factory that writes a real JPEG/PNG to disk (requires Pillow)."""
    def _make(path, mode="RGB", size=(50, 50), color=(255, 0, 0)):
        if not PILLOW_AVAILABLE:
            pytest.skip("Pillow not available")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new(mode, size, color).save(path)
        return path
    return _make


@pytest.fixture
def make_zip_with_real_image(make_real_image):
    """Factory that builds a ZIP containing one real JPEG."""
    def _make(zip_path, inner_name="image.jpg"):
        tmp_img = Path(zip_path).parent / "_tmp_source.jpg"
        make_real_image(tmp_img)
        data = tmp_img.read_bytes()
        tmp_img.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(inner_name, data)
        return zip_path
    return _make


# =====================================================================
# § 02 — HELPERS
# =====================================================================


def _extract(zip_path, extract_dir):
    """
    Convenience wrapper that mirrors the CLI call and normalizes
    the two possible outcomes: list of Path or exception.
    """
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    return extract_images_from_zip(zip_path, extract_dir)


# =====================================================================
# § 03 — SPECIAL CHARACTERS
# =====================================================================


class TestSpecialCharactersHandling:

    @pytest.mark.unit
    def test_unicode_filenames(self, temp_dir, create_test_zip):
        files = [
            "图片1.jpg",         # Chinese
            "صورة2.png",         # Arabic
            "изображение3.gif",  # Cyrillic
            "画像4.jpg",         # Japanese
        ]
        zip_path = create_test_zip(temp_dir / "unicode.zip", files)
        extract_dir = temp_dir / "extract"

        result = _extract(zip_path, extract_dir)

        assert len(result) == 4
        for path in result:
            assert path.exists()

    @pytest.mark.unit
    def test_special_chars_in_filename(self, temp_dir, create_test_zip):
        files = [
            "image (1).jpg",
            "image [2].png",
            "image {3}.gif",
            "image-4.jpg",
            "image_5.png",
            "image.number.6.jpg",
        ]
        zip_path = create_test_zip(temp_dir / "special.zip", files)
        extract_dir = temp_dir / "extract"

        result = _extract(zip_path, extract_dir)

        assert len(result) == 6

    @pytest.mark.unit
    def test_spaces_in_filename(self, temp_dir, create_test_zip):
        files = [
            "my image 1.jpg",
            "photo with spaces.png",
            "  leading spaces.jpg",
            "trailing spaces  .png",
        ]
        zip_path = create_test_zip(temp_dir / "spaces.zip", files)
        extract_dir = temp_dir / "extract"

        result = _extract(zip_path, extract_dir)

        assert len(result) == 4

    @pytest.mark.unit
    def test_very_long_filename(self, temp_dir, create_test_zip):
        """200-char basename + '.jpg' = 204 chars — fits most FS limits."""
        long_name = "a" * 200 + ".jpg"
        zip_path = create_test_zip(temp_dir / "long.zip", [long_name])
        extract_dir = temp_dir / "extract"

        result = _extract(zip_path, extract_dir)

        # Must succeed on any modern filesystem (255 chars/component limit)
        assert len(result) == 1
        assert result[0].exists()


# =====================================================================
# § 04 — FILE SYSTEM ERRORS
# =====================================================================


class TestFileSystemErrors:

    @pytest.mark.unit
    @pytest.mark.skipif(IS_WINDOWS, reason="chmod semantics differ on Windows")
    def test_readonly_extract_directory_raises(self, temp_dir, create_test_zip):
        zip_path = create_test_zip(temp_dir / "test.zip", ["image.jpg"])

        extract_dir = temp_dir / "readonly"
        extract_dir.mkdir()
        os.chmod(extract_dir, 0o444)  # r--r--r--

        try:
            with pytest.raises(PermissionError):
                extract_images_from_zip(zip_path, extract_dir)
        finally:
            os.chmod(extract_dir, 0o755)

    @pytest.mark.unit
    def test_disk_full_propagates_oserror(
        self, temp_dir, create_test_zip, monkeypatch
    ):
        """
        Simulate 'no space left' by patching shutil.copyfileobj — the
        CLI uses open+copyfileobj, NOT ZipFile.extract().
        """
        import shutil

        zip_path = create_test_zip(temp_dir / "test.zip", ["image.jpg"])
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        def _boom(*args, **kwargs):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(shutil, "copyfileobj", _boom)

        with pytest.raises(OSError):
            extract_images_from_zip(zip_path, extract_dir)

    @pytest.mark.unit
    def test_nonexistent_zip_raises_filenotfound(self, temp_dir):
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            extract_images_from_zip(
                temp_dir / "nonexistent.zip", extract_dir
            )


# =====================================================================
# § 05 — ZIP FILE ERRORS
# =====================================================================


class TestZipFileErrors:

    @pytest.mark.unit
    def test_encrypted_entry_is_skipped(
        self, temp_dir, create_test_zip, monkeypatch
    ):
        """
        stdlib `zipfile` cannot *write* encrypted entries. We simulate
        the encrypted flag on read via a tiny wrapper around ZipFile.
        """
        zip_path = create_test_zip(
            temp_dir / "enc.zip",
            {"encrypted.jpg": b"x", "plain.jpg": b"x"},
        )

        import python.zipped_imgs_to_pdf as cli

        original_zipfile = cli.zipfile.ZipFile

        class FlaggedZipFile(original_zipfile):
            def infolist(self):
                infos = super().infolist()
                for info in infos:
                    if info.filename == "encrypted.jpg":
                        # Set the encryption bit on the info object
                        info.flag_bits |= 0x1
                return infos

        monkeypatch.setattr(cli.zipfile, "ZipFile", FlaggedZipFile)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Only the non-encrypted entry survives
        names = {p.name for p in result}
        assert names == {"plain.jpg"}

    @pytest.mark.unit
    def test_zip64_format(self, temp_dir, create_test_zip):
        zip_path = temp_dir / "zip64.zip"
        with zipfile.ZipFile(zip_path, "w", allowZip64=True) as zf:
            zf.writestr("image.jpg", b"content")

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 1

    @pytest.mark.unit
    def test_empty_zip_returns_empty_list(self, temp_dir):
        zip_path = temp_dir / "empty.zip"
        with zipfile.ZipFile(zip_path, "w"):
            pass

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert result == []

    @pytest.mark.unit
    def test_truncated_zip_raises_badzipfile(
        self, temp_dir, create_test_zip
    ):
        zip_path = create_test_zip(temp_dir / "truncated.zip", ["image.jpg"])

        # Truncate to half its size
        data = zip_path.read_bytes()
        zip_path.write_bytes(data[: len(data) // 2])

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        with pytest.raises(zipfile.BadZipFile):
            extract_images_from_zip(zip_path, extract_dir)

    @pytest.mark.unit
    def test_corrupt_zip_header_raises(self, temp_dir):
        zip_path = temp_dir / "corrupt.zip"
        zip_path.write_bytes(b"Not a zip file at all")

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        with pytest.raises(zipfile.BadZipFile):
            extract_images_from_zip(zip_path, extract_dir)


# =====================================================================
# § 06 — process_zip_file ERRORS
# =====================================================================


class TestProcessZipFileErrors:

    @pytest.mark.unit
    def test_nonexistent_zip_returns_false(self, temp_dir):
        result = process_zip_file(temp_dir / "nonexistent.zip")
        assert result is False

    @pytest.mark.unit
    def test_non_zip_extension_returns_false(self, temp_dir):
        not_zip = temp_dir / "not_a_zip.txt"
        not_zip.write_text("This is a text file")

        assert process_zip_file(not_zip) is False

    @pytest.mark.unit
    def test_wrong_extension_returns_false(self, temp_dir):
        wrong_ext = temp_dir / "file.pdf"
        wrong_ext.write_bytes(b"fake content")

        assert process_zip_file(wrong_ext) is False

    @pytest.mark.unit
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_output_dir_is_a_file_returns_false(
        self, temp_dir, make_zip_with_real_image
    ):
        zip_path = make_zip_with_real_image(temp_dir / "test.zip")

        # Create a regular file where a directory is expected
        not_a_dir = temp_dir / "file.txt"
        not_a_dir.write_text("I'm a file, not a directory")

        # The CLI calls output_dir.mkdir(parents=True, exist_ok=True)
        # which raises if a file already exists at that path.
        result = process_zip_file(zip_path, output_dir=not_a_dir)

        assert result is False

    @pytest.mark.unit
    def test_zip_security_error_caught_and_returns_false(
        self, temp_dir, create_test_zip, monkeypatch
    ):
        """process_zip_file must catch ZipSecurityError → return False."""
        import python.zipped_imgs_to_pdf as cli

        zip_path = create_test_zip(temp_dir / "bomb.zip", ["bomb.jpg"])
        monkeypatch.setattr(cli, "MAX_COMPRESSION_RATIO", 0)  # force fail

        # Wrap the tiny entry so the ratio check trips
        # (compress_size will be > 0 for a stored small file)
        result = process_zip_file(zip_path)

        # Either the ratio triggers (returns False) or the empty-image
        # path returns False. Both must be False — never an exception.
        assert result is False


# =====================================================================
# § 07 — find_zip_files_recursive ERRORS
# =====================================================================


class TestFindZipFilesErrors:

    @pytest.mark.unit
    def test_nonexistent_directory_returns_empty(self, temp_dir):
        result = find_zip_files_recursive(temp_dir / "nonexistent")
        assert result == []

    @pytest.mark.unit
    def test_file_instead_of_directory_returns_empty(self, temp_dir):
        f = temp_dir / "file.txt"
        f.write_text("content")

        result = find_zip_files_recursive(f)
        assert result == []

    @pytest.mark.unit
    @pytest.mark.skipif(IS_WINDOWS, reason="chmod semantics differ on Windows")
    def test_permission_denied_directory_returns_list(self, temp_dir):
        restricted = temp_dir / "restricted"
        restricted.mkdir()
        (restricted / "test.zip").write_bytes(b"fake")

        os.chmod(restricted, 0o000)
        try:
            result = find_zip_files_recursive(restricted)
            assert isinstance(result, list)
        finally:
            os.chmod(restricted, 0o755)

    @pytest.mark.unit
    def test_symlink_to_directory(self, temp_dir):
        real_dir = temp_dir / "real"
        real_dir.mkdir()
        (real_dir / "test.zip").write_bytes(b"fake")

        link_dir = temp_dir / "link"
        try:
            link_dir.symlink_to(real_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

        result = find_zip_files_recursive(link_dir)
        assert len(result) == 1
        assert result[0].name == "test.zip"


# =====================================================================
# § 08 — PILLOW ERRORS
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestPillowErrors:

    @pytest.mark.unit
    def test_truncated_jpeg_returns_false(self, temp_dir):
        fake = temp_dir / "fake.jpg"
        # JPEG SOI marker + garbage
        fake.write_bytes(b"\xFF\xD8\xFF\xE0" + b"garbage data")

        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([fake], out) is False
        assert not out.exists()

    @pytest.mark.unit
    def test_zero_byte_image_returns_false(self, temp_dir):
        empty = temp_dir / "empty.jpg"
        empty.write_bytes(b"")

        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([empty], out) is False

    @pytest.mark.unit
    def test_unsupported_format_returns_false(self, temp_dir):
        unsupported = temp_dir / "file.xyz"
        unsupported.write_bytes(b"fake image data")

        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([unsupported], out) is False

    @pytest.mark.unit
    def test_directory_as_image_returns_false(self, temp_dir):
        """Passing a directory instead of a file must fail cleanly."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([subdir], out) is False


# =====================================================================
# § 09 — SECURITY LIMITS  [NEW]
# =====================================================================


class TestSecurityLimits:

    @pytest.mark.unit
    def test_path_traversal_entries_skipped(self, temp_dir, create_test_zip):
        """Entries with '..' in the path must be skipped, not extracted."""
        zip_path = create_test_zip(
            temp_dir / "trav.zip",
            {
                "../evil.jpg": b"x",
                "sub/../../evil2.jpg": b"x",
                "safe.jpg": b"x",
            },
        )
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        names = {p.name for p in result}
        assert "safe.jpg" in names
        assert "evil.jpg" not in names
        assert "evil2.jpg" not in names

    @pytest.mark.unit
    def test_absolute_paths_skipped(self, temp_dir, create_test_zip):
        zip_path = create_test_zip(
            temp_dir / "abs.zip",
            {
                "/etc/passwd.jpg": b"x",
                "safe.jpg": b"x",
            },
        )
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        names = {p.name for p in result}
        assert names == {"safe.jpg"}

    @pytest.mark.unit
    def test_windows_drive_paths_skipped(self, temp_dir, create_test_zip):
        zip_path = create_test_zip(
            temp_dir / "win.zip",
            {
                "C:\\Windows\\evil.jpg": b"x",
                "D:/data/evil2.jpg": b"x",
                "safe.jpg": b"x",
            },
        )
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        names = {p.name for p in result}
        assert names == {"safe.jpg"}

    @pytest.mark.unit
    def test_compression_ratio_guard_raises(
        self, temp_dir, monkeypatch
    ):
        """10 MB of zeros compresses to ~10 KB → ratio > 100:1."""
        import python.zipped_imgs_to_pdf as cli

        zip_path = temp_dir / "bomb.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bomb.jpg", b"\x00" * (10 * 1024 * 1024))

        monkeypatch.setattr(cli, "MAX_COMPRESSION_RATIO", 5)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        with pytest.raises(ZipSecurityError, match="compression ratio"):
            extract_images_from_zip(zip_path, extract_dir)

    @pytest.mark.unit
    def test_extracted_size_guard_raises(self, temp_dir, monkeypatch):
        import python.zipped_imgs_to_pdf as cli

        zip_path = temp_dir / "big.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("img1.jpg", b"x" * (2 * 1024 * 1024))
            zf.writestr("img2.jpg", b"x" * (2 * 1024 * 1024))

        monkeypatch.setattr(cli, "MAX_EXTRACTED_SIZE_BYTES", 1024 * 1024)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        with pytest.raises(ZipSecurityError):
            extract_images_from_zip(zip_path, extract_dir)

    @pytest.mark.unit
    def test_file_count_guard_raises(self, temp_dir, monkeypatch):
        import python.zipped_imgs_to_pdf as cli

        zip_path = temp_dir / "many.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i in range(20):
                zf.writestr(f"img_{i}.jpg", b"x")

        monkeypatch.setattr(cli, "MAX_FILES_IN_ZIP", 5)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        with pytest.raises(ZipSecurityError, match="too many"):
            extract_images_from_zip(zip_path, extract_dir)

    @pytest.mark.unit
    def test_nul_byte_in_entry_name_rejected(self, temp_dir, create_test_zip):
        """NUL bytes in entry names are silently skipped."""
        zip_path = create_test_zip(
            temp_dir / "nul.zip",
            {
                "bad\x00name.jpg": b"x",
                "safe.jpg": b"x",
            },
        )
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        names = {p.name for p in result}
        assert "safe.jpg" in names
        # The NUL entry is skipped by `_is_safe_entry`
        assert len(result) == 1


# =====================================================================
# § 10 — ZipSecurityError TYPE  [NEW]
# =====================================================================


class TestZipSecurityErrorType:

    @pytest.mark.unit
    def test_is_value_error_subclass(self):
        assert issubclass(ZipSecurityError, ValueError)

    @pytest.mark.unit
    def test_raisable_and_catchable(self):
        with pytest.raises(ZipSecurityError):
            raise ZipSecurityError("ZIP bomb suspected")

    @pytest.mark.unit
    def test_catchable_as_value_error(self):
        with pytest.raises(ValueError):
            raise ZipSecurityError("ratio exceeded")

    @pytest.mark.unit
    def test_message_preserved(self):
        try:
            raise ZipSecurityError("specific message")
        except ZipSecurityError as exc:
            assert "specific message" in str(exc)


# =====================================================================
# § 11 — PATH SAFETY HELPERS  [NEW]
# =====================================================================


class TestPathSafetyHelpers:

    @pytest.mark.unit
    def test_is_safe_entry_accepts_normal_paths(self):
        assert _is_safe_entry("image.jpg") is True
        assert _is_safe_entry("folder/image.jpg") is True
        assert _is_safe_entry("a/b/c/photo.png") is True

    @pytest.mark.unit
    def test_is_safe_entry_rejects_traversal(self):
        assert _is_safe_entry("../evil.jpg") is False
        assert _is_safe_entry("sub/../../evil.jpg") is False
        assert _is_safe_entry("..") is False
        assert _is_safe_entry("./../x.jpg") is False

    @pytest.mark.unit
    def test_is_safe_entry_rejects_absolute_posix(self):
        assert _is_safe_entry("/etc/passwd") is False
        assert _is_safe_entry("\\Windows\\System32\\evil.jpg") is False

    @pytest.mark.unit
    def test_is_safe_entry_rejects_windows_drive(self):
        assert _is_safe_entry("C:\\evil.jpg") is False
        assert _is_safe_entry("D:/data/evil.jpg") is False

    @pytest.mark.unit
    def test_is_safe_entry_rejects_nul_and_empty(self):
        assert _is_safe_entry("") is False
        assert _is_safe_entry("bad\x00name.jpg") is False

    @pytest.mark.unit
    def test_normalize_zip_entry_converts_backslashes(self):
        assert _normalize_zip_entry("a\\b\\c.jpg") == "a/b/c.jpg"

    @pytest.mark.unit
    def test_normalize_zip_entry_strips_leading_slash(self):
        assert _normalize_zip_entry("/a/b.jpg") == "a/b.jpg"

    @pytest.mark.unit
    def test_normalize_zip_entry_strips_dot_slash(self):
        assert _normalize_zip_entry("./a/b.jpg") == "a/b.jpg"

    @pytest.mark.unit
    def test_normalize_zip_entry_collapses_double_dots_slash(self):
        # Should still strip leading './' but keep '..' for the safety check
        assert _normalize_zip_entry("./../x.jpg") == "../x.jpg"

    @pytest.mark.unit
    def test_is_contained_accepts_inner_path(self, temp_dir):
        target = temp_dir / "sub" / "file.jpg"
        assert _is_contained(temp_dir, target) is True

    @pytest.mark.unit
    def test_is_contained_rejects_outside_path(self, temp_dir):
        target = temp_dir / ".." / "escaped.jpg"
        assert _is_contained(temp_dir, target) is False

    @pytest.mark.unit
    def test_safe_extract_member_rejects_unsafe_entry(
        self, temp_dir, create_test_zip
    ):
        """Direct test of _safe_extract_member's guard path."""
        zip_path = create_test_zip(temp_dir / "t.zip", {"evil.jpg": b"x"})
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        with zipfile.ZipFile(zip_path, "r") as zf:
            info = zf.infolist()[0]
            # Simulate a traversal entry
            info.filename = "../evil.jpg"

            result = _safe_extract_member(zf, info, extract_dir)

        assert result is None


# =====================================================================
# § 12 — EDGE CASES
# =====================================================================


class TestEdgeCases:

    @pytest.mark.unit
    def test_zip_with_hidden_files(self, temp_dir, create_test_zip):
        files = [
            ".hidden.jpg",   # hidden, but valid ext → included
            "visible.jpg",   # valid → included
            ".DS_Store",     # no valid ext → excluded
            "image.png",     # valid → included
        ]
        zip_path = create_test_zip(temp_dir / "hidden.zip", files)
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Exactly 3 valid images
        assert len(result) == 3
        names = {p.name for p in result}
        assert names == {".hidden.jpg", "visible.jpg", "image.png"}

    @pytest.mark.unit
    def test_duplicate_filenames_in_different_dirs(self, temp_dir):
        zip_path = temp_dir / "dup.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("dir1/image.jpg", b"c1")
            zf.writestr("dir2/image.jpg", b"c2")
            zf.writestr("image.jpg", b"c3")

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 3
        for path in result:
            assert path.exists()

    @pytest.mark.unit
    def test_case_sensitivity_in_extensions(self, temp_dir, create_test_zip):
        files = ["image.JPG", "image.jpg", "photo.PNG", "photo.png"]
        zip_path = create_test_zip(temp_dir / "case.zip", files)
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 4

    @pytest.mark.unit
    def test_deeply_nested_directories(self, temp_dir):
        zip_path = temp_dir / "nested.zip"
        deep = "/".join([f"lvl{i}" for i in range(20)]) + "/image.jpg"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(deep, b"x")

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 1
        assert result[0].exists()

    @pytest.mark.unit
    def test_directory_entries_skipped(self, temp_dir):
        """Entries that end in '/' are directories — must be skipped."""
        zip_path = temp_dir / "dirs.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("folder/", b"")
            zf.writestr("folder/image.jpg", b"x")
            zf.writestr("other/", b"")

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 1
        assert result[0].name == "image.jpg"

    @pytest.mark.unit
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_single_pixel_image(self, temp_dir, make_real_image):
        img = make_real_image(temp_dir / "tiny.png", size=(1, 1))
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert out.exists()

    @pytest.mark.unit
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_extremely_wide_image(self, temp_dir, make_real_image):
        img = make_real_image(temp_dir / "wide.png", size=(5000, 10))
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True

    @pytest.mark.unit
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_extremely_tall_image(self, temp_dir, make_real_image):
        img = make_real_image(temp_dir / "tall.png", size=(10, 5000))
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True

    @pytest.mark.unit
    def test_no_images_returns_empty_list(self, temp_dir, create_test_zip):
        zip_path = create_test_zip(
            temp_dir / "noimg.zip",
            {
                "document.pdf": b"x",
                "text.txt": b"x",
                "data.json": b"x",
            },
        )
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert result == []


# =====================================================================
# § 13 — PILLOW MISSING (smoke)
# =====================================================================


class TestPillowMissing:
    """Check the module's behavior contract regarding Pillow availability."""

    @pytest.mark.unit
    def test_module_exposes_pillow_flag(self):
        import python.zipped_imgs_to_pdf as module

        assert hasattr(module, "PILLOW_AVAILABLE")
        assert isinstance(module.PILLOW_AVAILABLE, bool)

    @pytest.mark.unit
    def test_main_returns_1_when_pillow_missing(self, monkeypatch):
        """If PILLOW_AVAILABLE is False, main() must return 1."""
        import python.zipped_imgs_to_pdf as module

        monkeypatch.setattr(module, "PILLOW_AVAILABLE", False)

        rc = module.main([])
        assert rc == 1
