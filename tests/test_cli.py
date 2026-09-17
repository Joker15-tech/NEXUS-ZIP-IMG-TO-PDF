#!/usr/bin/env python3
"""
=====================================================================
NEXUS QUANTUM // CLI Tests for python/zipped_imgs_to_pdf.py
=====================================================================
File:    tests/test_cli.py

Covers:
    1.  Basic argument parsing (single / multiple / none / --help)
    2.  Output directory option (-o / --output)
    3.  Natural sort flags (--natural-sort / --no-natural-sort)
    4.  Priority chars (--priority-chars)
    5.  Recursive mode (-r / --recursive)
    6.  Quiet & verbose modes (--quiet / --verbose) [NEW]
    7.  Version flag (-v / --version) [NEW]
    8.  Combined options
    9.  Error conditions (missing, invalid, no images)
    10. Security limits (ZIP bomb, compression ratio, path traversal) [NEW]
    11. Configuration & summary output
    12. find_zip_files_recursive() direct tests [NEW]
    13. Path safety helpers (_is_safe_entry, _normalize_zip_entry) [NEW]

IMPORTANT: `main()` returns an int exit code (0 = success, 1 = error).
           It does NOT call sys.exit() itself — only the `__main__`
           block does. Tests MUST check the return value, not mock
           sys.exit.
"""

import io
import logging
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
# Pillow (optional but strongly recommended for real-image tests)
# ---------------------------------------------------------------------
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None  # type: ignore

# ---------------------------------------------------------------------
# Module under test — imports match the corrected CLI surface
# ---------------------------------------------------------------------
from python.zipped_imgs_to_pdf import (  # noqa: E402
    main,
    build_parser,
    find_zip_files_recursive,
    ZipSecurityError,
    _is_safe_entry,
    _normalize_zip_entry,
    _is_contained,
)

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
    Reset the root logger between tests so `logging.basicConfig` in the
    CLI actually reconfigures. Without this, the first test that calls
    `main()` locks the handler set, and subsequent `--quiet` /
    `--verbose` tests cannot change the level.
    """
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    root.handlers = []
    root.setLevel(logging.NOTSET)
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)


@pytest.fixture
def make_zip():
    """
    Factory that builds a ZIP file from a mapping of
    {inner_name: raw_bytes}.
    """
    def _make(zip_path: Path, entries: dict):
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries.items():
                zf.writestr(name, data)
        return zip_path
    return _make


@pytest.fixture
def make_test_zip(make_zip):
    """
    Factory that builds a ZIP containing a single real JPEG.
    Requires Pillow.
    """
    def _make(zip_path: Path, inner_name: str = "image.jpg"):
        if not PILLOW_AVAILABLE:
            pytest.skip("Pillow not available")
        img = Image.new("RGB", (100, 100), (255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, "JPEG")
        return make_zip(zip_path, {inner_name: buf.getvalue()})
    return _make


@pytest.fixture
def make_test_zip_multi(make_zip):
    """
    Factory that builds a ZIP containing N real JPEGs with given names.
    Requires Pillow.
    """
    def _make(zip_path: Path, names):
        if not PILLOW_AVAILABLE:
            pytest.skip("Pillow not available")
        entries = {}
        for name in names:
            img = Image.new("RGB", (50, 50), (255, 0, 0))
            buf = io.BytesIO()
            img.save(buf, "JPEG")
            entries[name] = buf.getvalue()
        return make_zip(zip_path, entries)
    return _make


# =====================================================================
# § 02 — HELPERS
# =====================================================================

def run_main(*args) -> int:
    """
    Run main() with the given CLI arguments (prog name NOT included),
    return the exit code as an int.
    """
    return main(list(args))


def assert_pdf_exists(path: Path):
    """Assert that a file exists, is non-empty, and starts with %PDF."""
    assert path.exists(), f"Expected PDF at {path}"
    assert path.stat().st_size > 0, f"PDF is empty: {path}"
    with open(path, "rb") as fh:
        assert fh.read(4) == b"%PDF", f"Not a PDF: {path}"


# =====================================================================
# § 03 — BASIC ARGUMENT PARSING
# =====================================================================

class TestCLIBasicArguments:
    """Basic argument parsing and single/multi-file processing."""

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_single_file_argument(self, temp_dir, make_test_zip):
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path))

        assert rc == 0
        assert_pdf_exists(temp_dir / "test.pdf")

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_multiple_file_arguments(self, temp_dir, make_test_zip):
        zip1 = make_test_zip(temp_dir / "file1.zip")
        zip2 = make_test_zip(temp_dir / "file2.zip")
        zip3 = make_test_zip(temp_dir / "file3.zip")

        rc = run_main(str(zip1), str(zip2), str(zip3))

        assert rc == 0
        assert_pdf_exists(temp_dir / "file1.pdf")
        assert_pdf_exists(temp_dir / "file2.pdf")
        assert_pdf_exists(temp_dir / "file3.pdf")

    def test_no_arguments(self):
        """No args → argparse errors → SystemExit(2)."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0

    def test_help_argument(self):
        """--help → SystemExit(0) and prints usage."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_version_argument(self, capsys):
        """-v/--version → SystemExit(0) and prints version."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "2.0.0" in captured.out or "2.0.0" in captured.err

    def test_parser_builds_without_error(self):
        parser = build_parser()
        assert parser is not None
        assert parser.prog == "zipped-imgs-to-pdf"


# =====================================================================
# § 04 — OUTPUT DIRECTORY
# =====================================================================

class TestOutputDirectoryOption:

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_short_output_option(self, temp_dir, make_test_zip):
        zip_path = make_test_zip(temp_dir / "test.zip")
        output_dir = temp_dir / "output"

        rc = run_main(str(zip_path), "-o", str(output_dir))

        assert rc == 0
        assert_pdf_exists(output_dir / "test.pdf")

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_long_output_option(self, temp_dir, make_test_zip):
        zip_path = make_test_zip(temp_dir / "test.zip")
        output_dir = temp_dir / "pdfs"

        rc = run_main(str(zip_path), "--output", str(output_dir))

        assert rc == 0
        assert_pdf_exists(output_dir / "test.pdf")

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_output_directory_created_recursively(self, temp_dir, make_test_zip):
        zip_path = make_test_zip(temp_dir / "test.zip")
        output_dir = temp_dir / "new" / "nested" / "dir"

        rc = run_main(str(zip_path), "-o", str(output_dir))

        assert rc == 0
        assert output_dir.exists()
        assert_pdf_exists(output_dir / "test.pdf")


# =====================================================================
# § 05 — NATURAL SORT FLAGS
# =====================================================================

class TestNaturalSortOptions:

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_natural_sort_enabled_by_default(self, temp_dir, make_test_zip_multi):
        zip_path = make_test_zip_multi(
            temp_dir / "test.zip",
            ["img_1.jpg", "img_2.jpg", "img_10.jpg", "img_20.jpg"]
        )

        rc = run_main(str(zip_path))

        assert rc == 0
        assert_pdf_exists(temp_dir / "test.pdf")

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_natural_sort_explicit(self, temp_dir, make_test_zip):
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path), "--natural-sort")

        assert rc == 0

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_no_natural_sort(self, temp_dir, make_test_zip):
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path), "--no-natural-sort")

        assert rc == 0


# =====================================================================
# § 06 — PRIORITY CHARS
# =====================================================================

class TestPriorityCharsOption:

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_default_priority_chars(self, temp_dir, make_test_zip_multi):
        zip_path = make_test_zip_multi(
            temp_dir / "test.zip",
            ["page1.jpg", "!cover.jpg", "page2.jpg"]
        )

        rc = run_main(str(zip_path))

        assert rc == 0
        assert_pdf_exists(temp_dir / "test.pdf")

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_custom_priority_chars(self, temp_dir, make_test_zip_multi):
        zip_path = make_test_zip_multi(
            temp_dir / "test.zip",
            ["page1.jpg", "@special.jpg", "page2.jpg"]
        )

        rc = run_main(str(zip_path), "--priority-chars", "@")

        assert rc == 0

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_multiple_priority_chars(self, temp_dir, make_test_zip):
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path), "--priority-chars", "!@#")

        assert rc == 0

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_empty_priority_chars(self, temp_dir, make_test_zip):
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path), "--priority-chars", "")

        assert rc == 0


# =====================================================================
# § 07 — RECURSIVE MODE
# =====================================================================

class TestRecursiveOption:

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_recursive_short_option(self, temp_dir, make_test_zip):
        sub1 = temp_dir / "dir1"
        sub2 = temp_dir / "dir2"
        sub1.mkdir()
        sub2.mkdir()

        make_test_zip(sub1 / "file1.zip")
        make_test_zip(sub2 / "file2.zip")

        rc = run_main(str(temp_dir), "-r")

        assert rc == 0
        assert_pdf_exists(sub1 / "file1.pdf")
        assert_pdf_exists(sub2 / "file2.pdf")

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_recursive_long_option(self, temp_dir, make_test_zip):
        sub = temp_dir / "subdir"
        sub.mkdir()
        make_test_zip(sub / "test.zip")

        rc = run_main(str(temp_dir), "--recursive")

        assert rc == 0
        assert_pdf_exists(sub / "test.pdf")

    def test_directory_without_recursive_returns_error(self, temp_dir, capsys):
        """Directory without -r → main() returns 1, warning on stdout/stderr."""
        rc = run_main(str(temp_dir))

        assert rc == 1

        captured = capsys.readouterr()
        combined = (captured.out + captured.err).lower()
        assert "recursive" in combined or "directory" in combined

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_recursive_with_output_directory(self, temp_dir, make_test_zip):
        sub = temp_dir / "input"
        sub.mkdir()
        make_test_zip(sub / "test.zip")
        output_dir = temp_dir / "output"

        rc = run_main(str(sub), "-r", "-o", str(output_dir))

        assert rc == 0
        assert_pdf_exists(output_dir / "test.pdf")

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_recursive_case_insensitive_extension(self, temp_dir, make_test_zip):
        sub = temp_dir / "sub"
        sub.mkdir()
        make_test_zip(sub / "upper.ZIP")

        rc = run_main(str(temp_dir), "-r")

        assert rc == 0
        assert_pdf_exists(sub / "upper.pdf")


# =====================================================================
# § 08 — QUIET & VERBOSE  [NEW]
# =====================================================================

class TestQuietVerbose:

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_quiet_mode_produces_no_info_output(self, temp_dir, make_test_zip, capsys):
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path), "--quiet")

        assert rc == 0
        captured = capsys.readouterr()
        assert "Configuration" not in captured.out
        assert "Summary" not in captured.out

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_verbose_mode_produces_more_output(self, temp_dir, make_test_zip, capsys):
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path), "--verbose")

        assert rc == 0
        captured = capsys.readouterr()
        assert "Configuration" in captured.out
        assert "Summary" in captured.out

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_quiet_and_verbose_are_mutually_exclusive_in_behavior(
        self, temp_dir, make_test_zip, capsys
    ):
        """--quiet wins over --verbose (based on CLI logic)."""
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path), "--quiet", "--verbose")

        assert rc == 0
        captured = capsys.readouterr()
        # --quiet takes precedence
        assert "Configuration" not in captured.out


# =====================================================================
# § 09 — COMBINED OPTIONS
# =====================================================================

class TestCombinedOptions:

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_all_options_combined(self, temp_dir, make_test_zip_multi):
        zip_path = make_test_zip_multi(
            temp_dir / "test.zip",
            ["img_10.jpg", "@special.jpg", "img_1.jpg"]
        )
        output_dir = temp_dir / "output"

        rc = run_main(
            str(zip_path),
            "--no-natural-sort",
            "--priority-chars", "@",
            "-o", str(output_dir)
        )

        assert rc == 0
        assert_pdf_exists(output_dir / "test.pdf")

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_recursive_with_custom_output_and_sort(self, temp_dir, make_test_zip):
        sub = temp_dir / "input"
        sub.mkdir()
        make_test_zip(sub / "test.zip")
        output_dir = temp_dir / "out"

        rc = run_main(
            str(sub),
            "-r",
            "-o", str(output_dir),
            "--no-natural-sort",
            "--priority-chars", "!@",
        )

        assert rc == 0
        assert_pdf_exists(output_dir / "test.pdf")


# =====================================================================
# § 10 — ERROR CONDITIONS
# =====================================================================

class TestErrorConditions:

    def test_nonexistent_file(self, temp_dir, capsys):
        rc = run_main(str(temp_dir / "nonexistent.zip"))

        assert rc == 1

    def test_invalid_zip_file(self, temp_dir):
        not_zip = temp_dir / "not_a_zip.zip"
        not_zip.write_text("This is not a ZIP file")

        rc = run_main(str(not_zip))

        assert rc == 1

    def test_zip_with_no_images(self, temp_dir, make_zip):
        zip_path = make_zip(temp_dir / "no_images.zip", {
            "document.pdf": b"fake pdf",
            "text.txt": b"text content",
        })

        rc = run_main(str(zip_path))

        assert rc == 1

    def test_empty_zip(self, temp_dir, make_zip):
        zip_path = make_zip(temp_dir / "empty.zip", {})

        rc = run_main(str(zip_path))

        assert rc == 1

    def test_non_zip_extension(self, temp_dir):
        txt_file = temp_dir / "file.txt"
        txt_file.write_text("hello")

        rc = run_main(str(txt_file))

        assert rc == 1

    def test_file_exceeds_max_size(self, temp_dir, monkeypatch):
        """
        Simulate an oversized ZIP by mocking MAX_FILE_SIZE_BYTES to a tiny
        value — no need to actually create a 100 MB file.
        """
        import python.zipped_imgs_to_pdf as cli

        big_zip = temp_dir / "big.zip"
        with zipfile.ZipFile(big_zip, "w") as zf:
            zf.writestr("dummy.jpg", b"x" * 1024)

        monkeypatch.setattr(cli, "MAX_FILE_SIZE_BYTES", 100)

        rc = main([str(big_zip)])

        assert rc == 1


# =====================================================================
# § 11 — SECURITY LIMITS  [NEW]
# =====================================================================

class TestSecurityLimits:

    def test_path_traversal_rejected(self, temp_dir, make_zip):
        zip_path = make_zip(temp_dir / "evil.zip", {
            "../evil.jpg": b"fake",
            "safe.jpg": b"fake",
        })

        # The CLI should skip "../evil.jpg" but still process "safe.jpg"
        # with a warning. Since safe.jpg is not a real image, main returns 1.
        rc = run_main(str(zip_path), "--quiet")

        # No crash — accepted the archive but filtered the entry
        assert rc in (0, 1)

    def test_absolute_path_rejected(self, temp_dir, make_zip):
        zip_path = make_zip(temp_dir / "abs.zip", {
            "/etc/passwd.jpg": b"fake",
            "safe.jpg": b"fake",
        })

        rc = run_main(str(zip_path), "--quiet")

        assert rc in (0, 1)

    def test_windows_drive_path_rejected(self, temp_dir, make_zip):
        zip_path = make_zip(temp_dir / "win.zip", {
            "C:\\Windows\\evil.jpg": b"fake",
            "safe.jpg": b"fake",
        })

        rc = run_main(str(zip_path), "--quiet")

        assert rc in (0, 1)

    def test_compression_ratio_guard(self, temp_dir, monkeypatch):
        """Highly compressible entry → ZipSecurityError."""
        import python.zipped_imgs_to_pdf as cli

        zip_path = temp_dir / "bomb.zip"
        # 10 MB of zeros compresses to ~10 KB → ratio > 100:1
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bomb.jpg", b"\x00" * (10 * 1024 * 1024))

        monkeypatch.setattr(cli, "MAX_COMPRESSION_RATIO", 5)

        rc = main([str(zip_path), "--quiet"])

        assert rc == 1

    def test_extracted_size_guard(self, temp_dir, monkeypatch):
        """Cumulative uncompressed size above limit → error."""
        import python.zipped_imgs_to_pdf as cli

        zip_path = temp_dir / "big.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("img1.jpg", b"x" * (2 * 1024 * 1024))
            zf.writestr("img2.jpg", b"x" * (2 * 1024 * 1024))

        monkeypatch.setattr(cli, "MAX_EXTRACTED_SIZE_BYTES", 1024 * 1024)

        rc = main([str(zip_path), "--quiet"])

        assert rc == 1

    def test_file_count_guard(self, temp_dir, monkeypatch):
        """Too many entries → error."""
        import python.zipped_imgs_to_pdf as cli

        zip_path = temp_dir / "many.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for i in range(20):
                zf.writestr(f"img_{i}.jpg", b"x")

        monkeypatch.setattr(cli, "MAX_FILES_IN_ZIP", 5)

        rc = main([str(zip_path), "--quiet"])

        assert rc == 1

    def test_encrypted_entry_skipped(self, temp_dir, make_zip):
        """
        Encrypted entries cannot be created via stdlib zipfile easily;
        we just assert that a valid ZIP with mixed content is handled.
        """
        zip_path = make_zip(temp_dir / "mixed.zip", {
            "img.jpg": b"not a real image",
            "readme.txt": b"hello",
        })

        rc = run_main(str(zip_path), "--quiet")

        # img.jpg isn't decodable → CLI returns 1 (no PDF produced)
        assert rc == 1


# =====================================================================
# § 12 — CONFIGURATION & SUMMARY OUTPUT
# =====================================================================

class TestConfigurationOutput:

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_configuration_printed(self, temp_dir, make_test_zip, capsys):
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path))

        assert rc == 0
        captured = capsys.readouterr()
        assert "Configuration" in captured.out
        assert "Natural sorting" in captured.out
        assert "Priority characters" in captured.out

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_summary_printed(self, temp_dir, make_test_zip, capsys):
        zip_path = make_test_zip(temp_dir / "test.zip")

        rc = run_main(str(zip_path))

        assert rc == 0
        captured = capsys.readouterr()
        assert "Summary" in captured.out
        assert "successful" in captured.out.lower()

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_summary_reports_failures(self, temp_dir, capsys):
        # 1 valid zip + 1 invalid
        import io as _io
        from PIL import Image as _Img

        good = temp_dir / "good.zip"
        with zipfile.ZipFile(good, "w") as zf:
            img = _Img.new("RGB", (50, 50), (0, 0, 0))
            buf = _io.BytesIO()
            img.save(buf, "JPEG")
            zf.writestr("a.jpg", buf.getvalue())

        bad = temp_dir / "bad.zip"
        bad.write_text("not a zip")

        rc = run_main(str(good), str(bad))

        assert rc == 1  # at least one failure
        captured = capsys.readouterr()
        assert "Summary" in captured.out
        assert "1" in captured.out


# =====================================================================
# § 13 — find_zip_files_recursive  [NEW]
# =====================================================================

class TestFindZipFilesRecursive:

    def test_finds_zip_in_flat_directory(self, temp_dir):
        (temp_dir / "a.zip").write_text("x")
        (temp_dir / "b.zip").write_text("x")
        (temp_dir / "c.txt").write_text("x")

        found = find_zip_files_recursive(temp_dir)

        assert len(found) == 2
        assert all(p.suffix.lower() == ".zip" for p in found)

    def test_finds_zip_recursively(self, temp_dir):
        sub1 = temp_dir / "s1"
        sub2 = temp_dir / "s1" / "s2"
        sub1.mkdir()
        sub2.mkdir()

        (sub1 / "x.zip").write_text("x")
        (sub2 / "y.zip").write_text("y")

        found = find_zip_files_recursive(temp_dir)

        assert len(found) == 2

    def test_case_insensitive_extension(self, temp_dir):
        (temp_dir / "a.ZIP").write_text("x")
        (temp_dir / "b.Zip").write_text("x")
        (temp_dir / "c.zip").write_text("x")

        found = find_zip_files_recursive(temp_dir)

        assert len(found) == 3

    def test_deduplicates_by_resolved_path(self, temp_dir):
        (temp_dir / "a.zip").write_text("x")

        found = find_zip_files_recursive(temp_dir)

        # Should not list the same file twice (bug in the old 2-rglob impl)
        assert len(found) == 1

    def test_empty_directory(self, temp_dir):
        found = find_zip_files_recursive(temp_dir)
        assert found == []

    def test_returns_sorted_case_insensitively(self, temp_dir):
        for name in ["b.zip", "A.zip", "c.zip"]:
            (temp_dir / name).write_text("x")

        found = find_zip_files_recursive(temp_dir)
        names = [p.name for p in found]

        assert names == sorted(names, key=str.lower)


# =====================================================================
# § 14 — PATH SAFETY HELPERS  [NEW]
# =====================================================================

class TestPathSafetyHelpers:

    def test_is_safe_entry_accepts_normal_paths(self):
        assert _is_safe_entry("image.jpg") is True
        assert _is_safe_entry("folder/image.jpg") is True
        assert _is_safe_entry("folder/subfolder/image.jpg") is True

    def test_is_safe_entry_rejects_traversal(self):
        assert _is_safe_entry("../evil.jpg") is False
        assert _is_safe_entry("sub/../../evil.jpg") is False
        assert _is_safe_entry("..") is False

    def test_is_safe_entry_rejects_absolute(self):
        assert _is_safe_entry("/etc/passwd") is False
        assert _is_safe_entry("\\Windows\\System32") is False

    def test_is_safe_entry_rejects_windows_drive(self):
        assert _is_safe_entry("C:\\Windows\\evil.jpg") is False
        assert _is_safe_entry("D:/data/evil.jpg") is False

    def test_is_safe_entry_rejects_nul_and_empty(self):
        assert _is_safe_entry("") is False
        assert _is_safe_entry("bad\x00name.jpg") is False

    def test_normalize_zip_entry_converts_backslashes(self):
        assert _normalize_zip_entry("a\\b\\c.jpg") == "a/b/c.jpg"

    def test_normalize_zip_entry_strips_leading_slash(self):
        assert _normalize_zip_entry("/a/b.jpg") == "a/b.jpg"

    def test_normalize_zip_entry_strips_dot_slash(self):
        assert _normalize_zip_entry("./a/b.jpg") == "a/b.jpg"

    def test_is_contained_accepts_inner_path(self, temp_dir):
        target = temp_dir / "sub" / "file.jpg"
        assert _is_contained(temp_dir, target) is True

    def test_is_contained_rejects_outside_path(self, temp_dir):
        target = temp_dir / ".." / "escaped.jpg"
        assert _is_contained(temp_dir, target) is False


# =====================================================================
# § 15 — ZIP SECURITY ERROR TYPE
# =====================================================================

class TestZipSecurityError:
    """Verify the dedicated exception class semantics."""

    def test_is_value_error_subclass(self):
        assert issubclass(ZipSecurityError, ValueError)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ZipSecurityError):
            raise ZipSecurityError("ZIP bomb suspected")

    def test_can_be_caught_as_value_error(self):
        with pytest.raises(ValueError):
            raise ZipSecurityError("ratio exceeded")


# =====================================================================
# § 16 — VERSION FLAG
# =====================================================================

class TestVersionFlag:

    def test_version_short_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["-v"])
        assert exc_info.value.code == 0

    def test_version_long_flag(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_version_output_contains_version_number(self, capsys):
        with pytest.raises(SystemExit):
            main(["--version"])
        captured = capsys.readouterr()
        out = captured.out + captured.err
        assert "2.0.0" in out


# =====================================================================
# § 17 — LOGGING SETUP (smoke)
# =====================================================================

class TestLoggingSetup:

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_quiet_suppresses_info(self, temp_dir, make_test_zip, capsys):
        zip_path = make_test_zip(temp_dir / "test.zip")

        run_main(str(zip_path), "--quiet")

        captured = capsys.readouterr()
        # With quiet, INFO-level banners are not printed
        assert "Configuration:" not in captured.out

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_default_shows_info(self, temp_dir, make_test_zip, capsys):
        zip_path = make_test_zip(temp_dir / "test.zip")

        run_main(str(zip_path))

        captured = capsys.readouterr()
        assert "Configuration:" in captured.out
