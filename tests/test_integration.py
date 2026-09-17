#!/usr/bin/env python3
"""
=====================================================================
NEXUS QUANTUM // End-to-End Integration Tests
=====================================================================
File:    tests/test_integration.py
Targets: full pipeline ZIP → extract → sort → convert → PDF

Covers:
    1.  Complete workflow (basic, priority, natural sort, formats)
    2.  Output directory handling
    3.  Recursive processing
    4.  Real-world scenarios (archive, photo album, scans)
    5.  Multiple file processing
    6.  CLI integration (main() return code, not sys.exit)
    7.  Data integrity (image count, page count, order) [NEW]
    8.  Security limits in E2E context [NEW]
    9.  Quiet mode [NEW]
    10. Shared constants parity

CONTRACT:
    main() RETURNS an int (0/1). It does NOT call sys.exit().
    Use `rc = main([...])` and assert on rc.
"""

import io
import os
import re
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
# Pillow
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
    convert_images_to_pdf,
    process_zip_file,
    find_zip_files_recursive,
    main,
    ZipSecurityError,
)
from shared import DEFAULT_PRIORITY_CHARS  # noqa: E402


IS_WINDOWS = os.name == "nt"
pillow_required = pytest.mark.skipif(
    not PILLOW_AVAILABLE, reason="Pillow not available"
)


# =====================================================================
# § 01 — FIXTURES
# =====================================================================


@pytest.fixture
def temp_dir():
    """Fresh temporary directory (auto-cleaned)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def create_image_zip():
    """
    Factory that builds a ZIP containing real Pillow images.

    Signature:
        create_image_zip(zip_path, images_config)

    Where ``images_config`` is a list of:
        - filename                         (uses RGB 100x100 red)
        - (filename, mode, size, color)    (full control)

    Saves each image in the correct format based on extension.
    Creates parent directories automatically.
    """
    def _create(zip_path, images_config):
        if not PILLOW_AVAILABLE:
            pytest.skip("Pillow not available")

        zip_path = Path(zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for config in images_config:
                if len(config) == 1:
                    filename = config[0]
                    mode, size, color = "RGB", (100, 100), (255, 0, 0)
                elif len(config) == 4:
                    filename, mode, size, color = config
                else:
                    raise ValueError(
                        f"Invalid config: {config!r} — "
                        f"expected (name,) or (name, mode, size, color)"
                    )

                img = _build_image(mode, size, color)
                data = _encode_image(img, filename)
                zf.writestr(filename, data)

        return zip_path

    return _create


# =====================================================================
# § 02 — HELPERS
# =====================================================================


def _build_image(mode, size, color):
    """Build a Pillow image handling all supported modes safely."""
    if mode == "P":
        img = Image.new("P", size)
        # Palette MUST be set before save
        img.putpalette([i % 256 for i in range(768)])
        return img

    if mode == "LA":
        return Image.new("LA", size, (128, 255) if color is None else color)

    if mode == "CMYK":
        return Image.new("CMYK", size, (0, 100, 100, 0))

    if mode == "RGBA":
        return Image.new("RGBA", size, color or (0, 255, 0, 128))

    return Image.new(mode, size, color or (255, 0, 0))


def _encode_image(img, filename):
    """Encode a Pillow image to bytes using the format implied by extension."""
    name = filename.lower()
    buf = io.BytesIO()

    if name.endswith(".png"):
        img.save(buf, "PNG")
    elif name.endswith(".gif"):
        # GIF only supports P/RGB/L — convert if needed
        if img.mode not in ("P", "L", "RGB"):
            img = img.convert("RGB")
        img.save(buf, "GIF")
    elif name.endswith(".bmp"):
        img.save(buf, "BMP")
    elif name.endswith(".webp"):
        img.save(buf, "WEBP")
    else:
        # JPEG default
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(buf, "JPEG")

    return buf.getvalue()


def assert_valid_pdf(path: Path):
    """Assert a file exists and starts with the %PDF magic header."""
    assert path.exists(), f"PDF not found: {path}"
    assert path.stat().st_size > 0, f"PDF is empty: {path}"
    with open(path, "rb") as fh:
        assert fh.read(5).startswith(b"%PDF"), f"Not a PDF: {path}"


def count_pdf_pages(pdf_path: Path) -> int:
    """
    Count pages via regex over raw PDF bytes.

    Pillow writes ``/Type /Page`` (singular) per page.
    The catalog is ``/Type /Pages`` (plural) — excluded via negative
    lookahead.
    """
    data = Path(pdf_path).read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?![s])", data))


def run_main(*args) -> int:
    """Run main() with explicit CLI args and return the exit code."""
    return main(list(args))


# =====================================================================
# § 03 — COMPLETE WORKFLOW
# =====================================================================


@pillow_required
class TestCompleteWorkflow:

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_simple_zip_to_pdf(self, temp_dir, create_image_zip):
        images = [
            ("img1.jpg", "RGB", (200, 150), (255, 0, 0)),
            ("img2.jpg", "RGB", (200, 150), (0, 255, 0)),
            ("img3.jpg", "RGB", (200, 150), (0, 0, 255)),
        ]
        zip_path = create_image_zip(temp_dir / "test.zip", images)

        result = process_zip_file(zip_path)

        assert result is True
        pdf = temp_dir / "test.pdf"
        assert_valid_pdf(pdf)
        assert count_pdf_pages(pdf) == 3

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_priority_files_ordered_first(self, temp_dir, create_image_zip):
        images = [
            ("page1.jpg", "RGB", (100, 100), (255, 0, 0)),
            ("!cover.jpg", "RGB", (100, 100), (0, 255, 0)),
            ("page2.jpg", "RGB", (100, 100), (0, 0, 255)),
            ("!back.jpg", "RGB", (100, 100), (255, 255, 0)),
        ]
        zip_path = create_image_zip(temp_dir / "priority.zip", images)

        extract_dir = temp_dir / "extract"
        extracted = extract_images_from_zip(zip_path, extract_dir)

        names = [p.name for p in extracted]
        # Priority group first (lexical within group: !back < !cover)
        assert names == [
            "!back.jpg", "!cover.jpg", "page1.jpg", "page2.jpg"
        ]

        pdf = temp_dir / "priority.pdf"
        assert convert_images_to_pdf(extracted, pdf) is True
        assert count_pdf_pages(pdf) == 4

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_natural_sorting_workflow(self, temp_dir, create_image_zip):
        images = [
            ("page_10.jpg", "RGB", (100, 100), (255, 0, 0)),
            ("page_1.jpg", "RGB", (100, 100), (0, 255, 0)),
            ("page_2.jpg", "RGB", (100, 100), (0, 0, 255)),
            ("page_20.jpg", "RGB", (100, 100), (255, 255, 0)),
        ]
        zip_path = create_image_zip(temp_dir / "sorted.zip", images)

        extract_dir = temp_dir / "extract"
        extracted = extract_images_from_zip(
            zip_path, extract_dir, use_natural_sort=True
        )

        names = [p.name for p in extracted]
        assert names == [
            "page_1.jpg", "page_2.jpg", "page_10.jpg", "page_20.jpg"
        ]

        pdf = temp_dir / "sorted.pdf"
        assert convert_images_to_pdf(extracted, pdf) is True
        assert count_pdf_pages(pdf) == 4

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_mixed_image_formats(self, temp_dir, create_image_zip):
        images = [
            ("image1.jpg", "RGB", (100, 100), (255, 0, 0)),
            ("image2.png", "RGBA", (100, 100), (0, 255, 0, 128)),
            ("image3.gif", "P", (100, 100), None),
        ]
        zip_path = create_image_zip(temp_dir / "mixed.zip", images)

        result = process_zip_file(zip_path)

        assert result is True
        pdf = temp_dir / "mixed.pdf"
        assert_valid_pdf(pdf)
        assert count_pdf_pages(pdf) == 3

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_custom_output_directory(self, temp_dir, create_image_zip):
        images = [("image.jpg", "RGB", (100, 100), (255, 0, 0))]
        zip_path = create_image_zip(temp_dir / "test.zip", images)

        output_dir = temp_dir / "output"

        result = process_zip_file(zip_path, output_dir=output_dir)

        assert result is True
        assert_valid_pdf(output_dir / "test.pdf")

    @pytest.mark.integration
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_fifty_images(self, temp_dir, create_image_zip):
        images = [
            (f"page_{i:03d}.jpg", "RGB", (50, 50), (i * 10 % 256, 0, 0))
            for i in range(50)
        ]
        zip_path = create_image_zip(temp_dir / "large.zip", images)

        result = process_zip_file(zip_path)

        assert result is True
        pdf = temp_dir / "large.pdf"
        assert_valid_pdf(pdf)
        assert count_pdf_pages(pdf) == 50


# =====================================================================
# § 04 — RECURSIVE PROCESSING
# =====================================================================


@pillow_required
class TestRecursiveProcessing:

    @pytest.mark.integration
    def test_find_zip_files_recursively(self, temp_dir, create_image_zip):
        images = [("img.jpg", "RGB", (50, 50), (255, 0, 0))]

        (temp_dir / "dir1" / "subdir").mkdir(parents=True)
        (temp_dir / "dir2").mkdir()

        create_image_zip(temp_dir / "dir1" / "file1.zip", images)
        create_image_zip(temp_dir / "dir2" / "file2.zip", images)
        create_image_zip(temp_dir / "dir1" / "subdir" / "file3.zip", images)

        found = find_zip_files_recursive(temp_dir)

        assert len(found) == 3
        assert all(f.suffix.lower() == ".zip" for f in found)

    @pytest.mark.integration
    def test_find_zip_case_insensitive(self, temp_dir, create_image_zip):
        images = [("img.jpg", "RGB", (50, 50), (255, 0, 0))]
        create_image_zip(temp_dir / "lower.zip", images)
        create_image_zip(temp_dir / "UPPER.ZIP", images)
        create_image_zip(temp_dir / "Mixed.Zip", images)

        found = find_zip_files_recursive(temp_dir)

        assert len(found) == 3

    @pytest.mark.integration
    def test_find_zip_deduplicates(self, temp_dir):
        """The new impl dedupes by resolved path — no double counting."""
        (temp_dir / "a.zip").write_bytes(b"fake")

        found = find_zip_files_recursive(temp_dir)

        assert len(found) == 1

    @pytest.mark.integration
    def test_recursive_no_zips_returns_empty(self, temp_dir):
        (temp_dir / "file1.txt").write_text("content")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file3.doc").write_text("doc")

        assert find_zip_files_recursive(temp_dir) == []


# =====================================================================
# § 05 — REAL-WORLD SCENARIOS
# =====================================================================


@pillow_required
class TestRealWorldScenarios:

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_archive_conversion(self, temp_dir, create_image_zip):
        images = [
            ("!000_cover.jpg", "RGB", (800, 1200), (255, 0, 0)),
            ("001.jpg", "RGB", (800, 1200), (255, 255, 255)),
            ("002.jpg", "RGB", (800, 1200), (255, 255, 255)),
            ("003.jpg", "RGB", (800, 1200), (255, 255, 255)),
            ("!999_credits.jpg", "RGB", (800, 1200), (0, 0, 0)),
        ]
        zip_path = create_image_zip(temp_dir / "archive.zip", images)

        assert process_zip_file(zip_path) is True
        assert count_pdf_pages(temp_dir / "archive.pdf") == 5

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_photo_album_mixed_orientation(self, temp_dir, create_image_zip):
        images = [
            ("IMG_0001.jpg", "RGB", (1920, 1080), (255, 0, 0)),   # landscape
            ("IMG_0002.jpg", "RGB", (1080, 1920), (0, 255, 0)),   # portrait
            ("IMG_0010.jpg", "RGB", (1920, 1080), (0, 0, 255)),   # landscape
            ("IMG_0100.jpg", "RGB", (1920, 1080), (255, 255, 0)), # landscape
        ]
        zip_path = create_image_zip(temp_dir / "photos.zip", images)

        assert process_zip_file(zip_path) is True
        assert count_pdf_pages(temp_dir / "photos.pdf") == 4

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_scanned_documents_mixed_modes(self, temp_dir):
        if not PILLOW_AVAILABLE:
            pytest.skip("Pillow not available")

        zip_path = temp_dir / "scans.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i in range(5):
                if i % 2 == 0:
                    img = Image.new("L", (1700, 2200), 255)
                else:
                    img = Image.new("RGB", (1700, 2200), (255, 255, 255))
                buf = io.BytesIO()
                img.save(buf, "JPEG")
                zf.writestr(f"scan_{i:03d}.jpg", buf.getvalue())

        assert process_zip_file(zip_path) is True
        assert count_pdf_pages(temp_dir / "scans.pdf") == 5


# =====================================================================
# § 06 — MULTIPLE FILE PROCESSING
# =====================================================================


@pillow_required
class TestMultipleFilesProcessing:

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_process_multiple_zips_individually(self, temp_dir, create_image_zip):
        images = [("img.jpg", "RGB", (100, 100), (255, 0, 0))]

        zips = [
            create_image_zip(temp_dir / f"file{i}.zip", images)
            for i in range(1, 4)
        ]

        results = [process_zip_file(z) for z in zips]

        assert all(results)
        for i in range(1, 4):
            assert_valid_pdf(temp_dir / f"file{i}.pdf")


# =====================================================================
# § 07 — CLI INTEGRATION (return-code based)
# =====================================================================


@pillow_required
class TestCLIIntegration:

    @pytest.mark.integration
    def test_main_single_file(self, temp_dir, create_image_zip):
        images = [("img.jpg", "RGB", (100, 100), (255, 0, 0))]
        zip_path = create_image_zip(temp_dir / "test.zip", images)

        rc = run_main(str(zip_path))

        assert rc == 0
        assert_valid_pdf(temp_dir / "test.pdf")

    @pytest.mark.integration
    def test_main_no_natural_sort(self, temp_dir, create_image_zip):
        images = [
            ("img_10.jpg", "RGB", (50, 50), (255, 0, 0)),
            ("img_1.jpg", "RGB", (50, 50), (0, 255, 0)),
            ("img_2.jpg", "RGB", (50, 50), (0, 0, 255)),
        ]
        zip_path = create_image_zip(temp_dir / "test.zip", images)

        rc = run_main(str(zip_path), "--no-natural-sort")

        assert rc == 0
        assert_valid_pdf(temp_dir / "test.pdf")

    @pytest.mark.integration
    def test_main_output_directory(self, temp_dir, create_image_zip):
        images = [("img.jpg", "RGB", (100, 100), (255, 0, 0))]
        zip_path = create_image_zip(temp_dir / "test.zip", images)
        output_dir = temp_dir / "output"

        rc = run_main(str(zip_path), "-o", str(output_dir))

        assert rc == 0
        assert_valid_pdf(output_dir / "test.pdf")

    @pytest.mark.integration
    def test_main_nonexistent_file_returns_1(self, temp_dir):
        rc = run_main(str(temp_dir / "nonexistent.zip"))
        assert rc == 1

    @pytest.mark.integration
    def test_main_invalid_zip_returns_1(self, temp_dir):
        bad = temp_dir / "bad.zip"
        bad.write_text("not a zip")

        rc = run_main(str(bad))
        assert rc == 1

    @pytest.mark.integration
    def test_main_quiet_mode(self, temp_dir, create_image_zip, capsys):
        images = [("img.jpg", "RGB", (100, 100), (255, 0, 0))]
        zip_path = create_image_zip(temp_dir / "test.zip", images)

        rc = run_main(str(zip_path), "--quiet")

        assert rc == 0
        captured = capsys.readouterr()
        # Quiet suppresses the configuration banner
        assert "Configuration" not in captured.out
        assert "Summary" not in captured.out

    @pytest.mark.integration
    def test_main_verbose_mode(self, temp_dir, create_image_zip, capsys):
        images = [("img.jpg", "RGB", (100, 100), (255, 0, 0))]
        zip_path = create_image_zip(temp_dir / "test.zip", images)

        rc = run_main(str(zip_path), "--verbose")

        assert rc == 0
        captured = capsys.readouterr()
        assert "Configuration" in captured.out

    @pytest.mark.integration
    def test_main_recursive_mode(self, temp_dir, create_image_zip):
        images = [("img.jpg", "RGB", (100, 100), (255, 0, 0))]
        (temp_dir / "nested").mkdir()
        create_image_zip(temp_dir / "nested" / "file.zip", images)

        rc = run_main(str(temp_dir), "-r")

        assert rc == 0
        assert_valid_pdf(temp_dir / "nested" / "file.pdf")


# =====================================================================
// § 08 — DATA INTEGRITY
// =====================================================================


@pillow_required
class TestDataIntegrity:

    @pytest.mark.integration
    def test_image_count_preserved(self, temp_dir, create_image_zip):
        num = 10
        images = [
            (f"img_{i:03d}.jpg", "RGB", (100, 100), (i * 25 % 256, 0, 0))
            for i in range(num)
        ]
        zip_path = create_image_zip(temp_dir / "test.zip", images)

        extract_dir = temp_dir / "extract"
        extracted = extract_images_from_zip(zip_path, extract_dir)

        assert len(extracted) == num

        pdf = temp_dir / "test.pdf"
        assert convert_images_to_pdf(extracted, pdf) is True
        assert count_pdf_pages(pdf) == num

    @pytest.mark.integration
    def test_filename_order_preserved(self, temp_dir, create_image_zip):
        images = [
            ("001.jpg", "RGB", (50, 50), (255, 0, 0)),
            ("002.jpg", "RGB", (50, 50), (0, 255, 0)),
            ("003.jpg", "RGB", (50, 50), (0, 0, 255)),
        ]
        zip_path = create_image_zip(temp_dir / "ordered.zip", images)

        extract_dir = temp_dir / "extract"
        extracted = extract_images_from_zip(zip_path, extract_dir)

        assert [p.name for p in extracted] == ["001.jpg", "002.jpg", "003.jpg"]

    @pytest.mark.integration
    def test_extracted_content_matches_zip_source(self, temp_dir, create_image_zip):
        """Verify bytes on disk equal bytes inside the ZIP."""
        images = [("only.jpg", "RGB", (100, 100), (12, 34, 56))]
        zip_path = create_image_zip(temp_dir / "content.zip", images)

        # Read the original bytes from the ZIP
        with zipfile.ZipFile(zip_path, "r") as zf:
            original = zf.read("only.jpg")

        extract_dir = temp_dir / "extract"
        extracted = extract_images_from_zip(zip_path, extract_dir)

        assert extracted[0].read_bytes() == original

    @pytest.mark.integration
    def test_pdf_grows_with_page_count(self, temp_dir, create_image_zip):
        one = create_image_zip(
            temp_dir / "one.zip",
            [("a.jpg", "RGB", (100, 100), (255, 0, 0))],
        )
        five = create_image_zip(
            temp_dir / "five.zip",
            [(f"a{i}.jpg", "RGB", (100, 100), (255, 0, 0)) for i in range(5)],
        )

        process_zip_file(one)
        process_zip_file(five)

        size_one = (temp_dir / "one.pdf").stat().st_size
        size_five = (temp_dir / "five.pdf").stat().st_size

        assert size_five > size_one


# =====================================================================
// § 09 — SECURITY IN E2E CONTEXT  [NEW]
// =====================================================================


class TestSecurityInE2E:

    @pytest.mark.integration
    def test_path_traversal_filtered_in_workflow(self, temp_dir, create_image_zip):
        """Malicious entries are skipped but the workflow continues."""
        zip_path = temp_dir / "evil.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            # Inject a traversal entry manually
            info = zipfile.ZipInfo("../evil.jpg")
            zf.writestr(info, b"\xFF\xD8\xFF\xE0fake")
            # Plus a safe one
            zf.writestr("safe.jpg", b"\xFF\xD8\xFF\xE0fake")

        extract_dir = temp_dir / "extract"
        result = extract_images_from_zip(zip_path, extract_dir)

        names = {p.name for p in result}
        assert "safe.jpg" in names
        assert "evil.jpg" not in names
        assert len(result) == 1

    @pytest.mark.integration
    def test_zip_bomb_ratio_guard(self, temp_dir, monkeypatch):
        """E2E: extreme compression ratio → ZipSecurityError."""
        import python.zipped_imgs_to_pdf as cli

        zip_path = temp_dir / "bomb.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bomb.jpg", b"\x00" * (10 * 1024 * 1024))

        monkeypatch.setattr(cli, "MAX_COMPRESSION_RATIO", 5)

        with pytest.raises(ZipSecurityError):
            process_zip_file(zip_path)

    @pytest.mark.integration
    def test_process_zip_file_returns_false_on_security_error(
        self, temp_dir, monkeypatch
    ):
        """process_zip_file must CATCH security errors, not propagate."""
        import python.zipped_imgs_to_pdf as cli

        zip_path = temp_dir / "bomb.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bomb.jpg", b"\x00" * (10 * 1024 * 1024))

        monkeypatch.setattr(cli, "MAX_COMPRESSION_RATIO", 5)

        # No exception — returns False
        assert process_zip_file(zip_path) is False


// =====================================================================
// § 10 — SHARED CONSTANTS PARITY
// =====================================================================


class TestSharedParity:

    @pytest.mark.unit
    def test_default_priority_char(self):
        assert DEFAULT_PRIORITY_CHARS == "!"

    @pytest.mark.unit
    def test_priority_char_used_in_workflow(self, temp_dir, create_image_zip):
        if not PILLOW_AVAILABLE:
            pytest.skip("Pillow not available")

        images = [
            ("page_1.jpg", "RGB", (50, 50), (255, 0, 0)),
            ("!cover.jpg", "RGB", (50, 50), (0, 255, 0)),
        ]
        zip_path = create_image_zip(temp_dir / "prio.zip", images)

        extract_dir = temp_dir / "extract"
        result = extract_images_from_zip(zip_path, extract_dir)

        # Priority file comes first
        assert result[0].name == "!cover.jpg"


// =====================================================================
// § 11 — PDF STRUCTURE VERIFICATION
// =====================================================================


@pillow_required
class TestPDFStructure:

    @pytest.mark.integration
    def test_pdf_has_eof_marker(self, temp_dir, create_image_zip):
        images = [("img.jpg", "RGB", (100, 100), (255, 0, 0))]
        zip_path = create_image_zip(temp_dir / "test.zip", images)
        process_zip_file(zip_path)

        pdf = temp_dir / "test.pdf"
        data = pdf.read_bytes()

        assert data.startswith(b"%PDF")
        assert b"%%EOF" in data

    @pytest.mark.integration
    def test_pdf_has_catalog_and_pages(self, temp_dir, create_image_zip):
        images = [
            ("a.jpg", "RGB", (100, 100), (255, 0, 0)),
            ("b.jpg", "RGB", (100, 100), (0, 255, 0)),
        ]
        zip_path = create_image_zip(temp_dir / "test.zip", images)
        process_zip_file(zip_path)

        data = (temp_dir / "test.pdf").read_bytes()

        assert b"/Type /Catalog" in data
        assert b"/Type /Page" in data
        assert count_pdf_pages(temp_dir / "test.pdf") == 2
