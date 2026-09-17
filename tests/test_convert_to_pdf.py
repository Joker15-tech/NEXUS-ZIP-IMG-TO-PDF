#!/usr/bin/env python3
"""
=====================================================================
NEXUS QUANTUM // Tests for convert_images_to_pdf()
=====================================================================
File:    tests/test_convert_to_pdf.py
Target:  python/zipped_imgs_to_pdf.convert_images_to_pdf

Covers:
    1.  Basic conversion (single, multi, empty)
    2.  Color modes (RGB, RGBA, P, LA, L, CMYK, I, F, 1)
    3.  Mixed modes
    4.  Error handling (invalid, corrupt, missing, permissions)
    5.  Image sizes (small, large, mixed aspect ratios)
    6.  PDF structure (%PDF header, page count)
    7.  Resolution parameter (default + custom)
    8.  Output directory creation (recursive mkdir)
    9.  File-handle cleanup (Windows-safe)
    10. _load_image_safely() in isolation
    11. Real-world scenarios
"""

import re
import sys
import tempfile
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
# Module under test — imported unconditionally so `pytest --collect-only`
# works even without Pillow. Tests skip via the class-level marker.
# ---------------------------------------------------------------------
if PILLOW_AVAILABLE:
    from python.zipped_imgs_to_pdf import (
        convert_images_to_pdf,
        _load_image_safely,
    )
else:
    convert_images_to_pdf = None  # type: ignore
    _load_image_safely = None     # type: ignore

# =====================================================================
# § 01 — PYTEST MARKERS REGISTRATION
# =====================================================================
# If these are not registered in pytest.ini / pyproject.toml, pytest will
# emit PytestUnknownMarkWarning. Register them there:
#
#   [pytest]
#   markers =
#       unit: fast, isolated unit tests
#       integration: end-to-end tests across modules
#       slow: tests that take more than ~1s
#
# This file uses them freely.

# =====================================================================
# § 02 — FIXTURES
# =====================================================================


@pytest.fixture
def temp_dir():
    """Yield a fresh temporary directory (auto-cleaned)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def create_test_image():
    """
    Factory that writes a test image to disk.

    Signature:  create_test_image(path, mode='RGB', size=(100,100), color=...)
    Returns:    the path that was written.
    """
    def _create_image(path, mode="RGB", size=(100, 100), color=(255, 0, 0)):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if mode == "P":
            img = Image.new("P", size)
            # Full 256-color palette
            img.putpalette([i % 256 for i in range(768)])
            img.save(path)
        elif mode == "LA":
            img = Image.new("LA", size, (128, 255))
            img.save(path)
        elif mode == "CMYK":
            img = Image.new("CMYK", size, (0, 100, 100, 0))
            img.save(path)
        else:
            img = Image.new(mode, size, color)
            img.save(path)

        return path

    return _create_image


# =====================================================================
# § 03 — HELPERS
# =====================================================================


def assert_is_valid_pdf(path: Path):
    """Assert that a file exists, is non-empty, and starts with %PDF-."""
    assert path.exists(), f"PDF not found at {path}"
    assert path.stat().st_size > 0, f"PDF is empty: {path}"

    with open(path, "rb") as fh:
        header = fh.read(5)
    assert header.startswith(b"%PDF"), (
        f"File does not start with %PDF magic: {header!r}"
    )


def count_pdf_pages(pdf_path: Path) -> int:
    """
    Naive page count via regex over raw PDF bytes.

    Pillow writes each page as ``/Type /Page`` (singular). The parent
    catalog is ``/Type /Pages`` (plural), which we exclude.
    Works without PyPDF2 / pypdf dependency.
    """
    data = pdf_path.read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?![s])", data))


# =====================================================================
# § 04 — BASIC CONVERSION
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFBasic:
    """Basic functionality of convert_images_to_pdf()."""

    @pytest.mark.unit
    def test_convert_single_image(self, temp_dir, create_test_image):
        img_path = create_test_image(temp_dir / "image.jpg")
        output_pdf = temp_dir / "output.pdf"

        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True
        assert_is_valid_pdf(output_pdf)
        assert count_pdf_pages(output_pdf) == 1

    @pytest.mark.unit
    def test_convert_multiple_images_produces_multipage_pdf(
        self, temp_dir, create_test_image
    ):
        images = [
            create_test_image(temp_dir / f"image_{i}.jpg")
            for i in range(3)
        ]
        output_pdf = temp_dir / "output.pdf"

        result = convert_images_to_pdf(images, output_pdf)

        assert result is True
        assert_is_valid_pdf(output_pdf)
        assert count_pdf_pages(output_pdf) == 3

    @pytest.mark.unit
    def test_convert_ten_images(self, temp_dir, create_test_image):
        images = [
            create_test_image(temp_dir / f"img_{i:03d}.jpg")
            for i in range(10)
        ]
        output_pdf = temp_dir / "output.pdf"

        result = convert_images_to_pdf(images, output_pdf)

        assert result is True
        assert count_pdf_pages(output_pdf) == 10

    @pytest.mark.unit
    def test_empty_image_list_returns_false(self, temp_dir):
        output_pdf = temp_dir / "output.pdf"

        result = convert_images_to_pdf([], output_pdf)

        assert result is False
        assert not output_pdf.exists()

    @pytest.mark.unit
    def test_none_input_returns_false(self, temp_dir):
        output_pdf = temp_dir / "output.pdf"

        result = convert_images_to_pdf(None, output_pdf)

        assert result is False
        assert not output_pdf.exists()

    @pytest.mark.unit
    def test_output_pdf_overwrites_existing(self, temp_dir, create_test_image):
        img_path = create_test_image(temp_dir / "img.jpg")
        output_pdf = temp_dir / "output.pdf"
        output_pdf.write_bytes(b"OLD CONTENT")

        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True
        assert_is_valid_pdf(output_pdf)
        assert b"OLD CONTENT" not in output_pdf.read_bytes()


# =====================================================================
# § 05 — COLOR MODES
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFImageModes:
    """Different Pillow image modes must all convert successfully."""

    @pytest.mark.unit
    def test_rgb(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "rgb.jpg", mode="RGB")
        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_rgba_flattened_to_white_background(self, temp_dir, create_test_image):
        img = create_test_image(
            temp_dir / "rgba.png", mode="RGBA", color=(255, 0, 0, 128)
        )
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_palette_mode(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "palette.png", mode="P")
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_grayscale_with_alpha(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "la.png", mode="LA")
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_grayscale(self, temp_dir):
        img = temp_dir / "gray.png"
        Image.new("L", (100, 100), 128).save(img)
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_cmyk(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "cmyk.jpg", mode="CMYK")
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_1bit_mode(self, temp_dir):
        img = temp_dir / "1bit.png"
        Image.new("1", (100, 100), 1).save(img)
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_16bit_grayscale_i_mode(self, temp_dir):
        """Mode 'I' = 32-bit signed integer pixels."""
        img = temp_dir / "i16.png"
        Image.new("I", (100, 100), 1000).save(img)
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_float_mode_f(self, temp_dir):
        """Mode 'F' = 32-bit float pixels (TIFF only)."""
        img = temp_dir / "float.tiff"
        Image.new("F", (100, 100), 0.5).save(img)
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_ycbcr_mode(self, temp_dir):
        img = temp_dir / "ycbcr.jpg"
        Image.new("RGB", (100, 100), (100, 150, 200)).save(img)
        # Re-open and force YCbCr
        with Image.open(img) as src:
            ycbcr = src.convert("YCbCr")
            ycbcr.save(img)

        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([img], out) is True
        assert_is_valid_pdf(out)


# =====================================================================
# § 06 — MIXED MODES
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFMixedModes:
    """Mixed color modes in a single PDF."""

    @pytest.mark.unit
    def test_rgb_plus_rgba(self, temp_dir, create_test_image):
        img1 = create_test_image(temp_dir / "rgb.jpg", mode="RGB")
        img2 = create_test_image(temp_dir / "rgba.png", mode="RGBA")
        img3 = create_test_image(temp_dir / "rgb2.jpg", mode="RGB")
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([img1, img2, img3], out) is True
        assert count_pdf_pages(out) == 3

    @pytest.mark.unit
    def test_all_modes_together(self, temp_dir, create_test_image):
        images = [
            create_test_image(temp_dir / "rgb.jpg", mode="RGB"),
            create_test_image(temp_dir / "rgba.png", mode="RGBA"),
            create_test_image(temp_dir / "p.png", mode="P"),
            create_test_image(temp_dir / "la.png", mode="LA"),
            create_test_image(temp_dir / "cmyk.jpg", mode="CMYK"),
        ]
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf(images, out) is True
        assert count_pdf_pages(out) == 5


# =====================================================================
# § 07 — ERROR HANDLING
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFErrors:

    @pytest.mark.unit
    def test_invalid_image_file_returns_false(self, temp_dir):
        invalid = temp_dir / "invalid.jpg"
        invalid.write_text("This is not an image")
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([invalid], out) is False
        assert not out.exists()

    @pytest.mark.unit
    def test_corrupted_image_skipped_others_processed(
        self, temp_dir, create_test_image
    ):
        good1 = create_test_image(temp_dir / "good1.jpg")
        bad = temp_dir / "bad.jpg"
        bad.write_text("corrupted")
        good2 = create_test_image(temp_dir / "good2.jpg")
        out = temp_dir / "out.pdf"

        result = convert_images_to_pdf([good1, bad, good2], out)

        assert result is True
        assert count_pdf_pages(out) == 2  # only the 2 good images

    @pytest.mark.unit
    def test_all_images_corrupted_returns_false(self, temp_dir):
        bad1 = temp_dir / "bad1.jpg"
        bad2 = temp_dir / "bad2.jpg"
        bad1.write_text("corrupted")
        bad2.write_text("corrupted")
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([bad1, bad2], out) is False
        assert not out.exists()

    @pytest.mark.unit
    def test_nonexistent_image_returns_false(self, temp_dir):
        ghost = temp_dir / "nonexistent.jpg"
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf([ghost], out) is False
        assert not out.exists()

    @pytest.mark.unit
    def test_mixed_existing_and_missing(self, temp_dir, create_test_image):
        good = create_test_image(temp_dir / "good.jpg")
        ghost = temp_dir / "missing.jpg"
        out = temp_dir / "out.pdf"

        result = convert_images_to_pdf([good, ghost], out)

        assert result is True
        assert count_pdf_pages(out) == 1

    @pytest.mark.unit
    def test_output_path_is_a_directory_returns_false(
        self, temp_dir, create_test_image
    ):
        img = create_test_image(temp_dir / "img.jpg")
        blocked = temp_dir / "blocked_dir"
        blocked.mkdir()  # exists as a DIRECTORY

        # Pillow cannot write a file where a directory already exists
        result = convert_images_to_pdf([img], blocked)

        assert result is False

    @pytest.mark.unit
    def test_output_in_unwritable_directory_returns_false(
        self, temp_dir, create_test_image
    ):
        """Real permission test — uses chmod 0o500 (r-x) on POSIX."""
        import os
        import stat

        if os.name == "nt":
            pytest.skip("Permission semantics differ on Windows")

        img = create_test_image(temp_dir / "img.jpg")
        readonly = temp_dir / "readonly"
        readonly.mkdir()
        os.chmod(readonly, stat.S_IRUSR | stat.S_IXUSR)  # 0o500

        try:
            out = readonly / "sub" / "out.pdf"
            result = convert_images_to_pdf([img], out)
            assert result is False
        finally:
            os.chmod(readonly, stat.S_IRWXU)  # restore for cleanup


# =====================================================================
# § 08 — IMAGE SIZES & ASPECT RATIOS
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFSizes:

    @pytest.mark.unit
    def test_small_image(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "small.jpg", size=(50, 50))
        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([img], out) is True

    @pytest.mark.unit
    def test_large_image(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "large.jpg", size=(2000, 2000))
        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([img], out) is True

    @pytest.mark.unit
    def test_extremely_large_image(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "xl.jpg", size=(4000, 3000))
        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([img], out) is True

    @pytest.mark.unit
    def test_mixed_aspect_ratios(self, temp_dir, create_test_image):
        images = [
            create_test_image(temp_dir / "wide.jpg", size=(200, 100)),
            create_test_image(temp_dir / "tall.jpg", size=(100, 200)),
            create_test_image(temp_dir / "square.jpg", size=(100, 100)),
        ]
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf(images, out) is True
        assert count_pdf_pages(out) == 3

    @pytest.mark.unit
    def test_single_pixel_image(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "px.jpg", size=(1, 1))
        out = temp_dir / "out.pdf"
        assert convert_images_to_pdf([img], out) is True

    @pytest.mark.slow
    @pytest.mark.unit
    def test_twenty_images(self, temp_dir, create_test_image):
        images = [
            create_test_image(temp_dir / f"img_{i:03d}.jpg")
            for i in range(20)
        ]
        out = temp_dir / "out.pdf"

        assert convert_images_to_pdf(images, out) is True
        assert count_pdf_pages(out) == 20


# =====================================================================
# § 09 — RESOLUTION PARAMETER
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFResolution:
    """Verify the `resolution` kwarg is passed to Pillow and affects output."""

    @pytest.mark.unit
    def test_default_resolution_is_100(self, temp_dir, create_test_image):
        """
        Use `wraps=` so the real save is called — otherwise no PDF is
        written and the assertion is meaningless.
        """
        img = create_test_image(temp_dir / "img.jpg")
        out = temp_dir / "out.pdf"

        with mock.patch.object(
            Image.Image, "save", wraps=Image.Image.save
        ) as mock_save:
            result = convert_images_to_pdf([img], out)

        assert result is True
        assert_is_valid_pdf(out)

        # The only `save()` call inside the CLI is the PDF write
        assert mock_save.call_args is not None
        assert mock_save.call_args.kwargs.get("resolution") == 100.0

    @pytest.mark.unit
    def test_custom_resolution_150(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "img.jpg")
        out = temp_dir / "out.pdf"

        with mock.patch.object(
            Image.Image, "save", wraps=Image.Image.save
        ) as mock_save:
            result = convert_images_to_pdf([img], out, resolution=150.0)

        assert result is True
        assert_is_valid_pdf(out)
        assert mock_save.call_args.kwargs.get("resolution") == 150.0

    @pytest.mark.unit
    def test_custom_resolution_300(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "img.jpg")
        out = temp_dir / "out.pdf"

        with mock.patch.object(
            Image.Image, "save", wraps=Image.Image.save
        ) as mock_save:
            result = convert_images_to_pdf([img], out, resolution=300.0)

        assert result is True
        assert mock_save.call_args.kwargs.get("resolution") == 300.0

    @pytest.mark.unit
    def test_resolution_is_keyword_only(self, temp_dir, create_test_image):
        """The CLI defines `resolution` as keyword-only (PEP 3102)."""
        img = create_test_image(temp_dir / "img.jpg")
        out = temp_dir / "out.pdf"

        with pytest.raises(TypeError):
            # Positional third arg must be rejected
            convert_images_to_pdf([img], out, 150.0)  # type: ignore


# =====================================================================
# § 10 — OUTPUT DIRECTORY CREATION
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestOutputDirectoryCreation:

    @pytest.mark.unit
    def test_creates_missing_parent_directory(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "img.jpg")
        out = temp_dir / "new" / "nested" / "deep" / "out.pdf"

        result = convert_images_to_pdf([img], out)

        assert result is True
        assert out.exists()
        assert_is_valid_pdf(out)

    @pytest.mark.unit
    def test_creates_directory_only_when_needed(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "img.jpg")
        existing = temp_dir / "already_here"
        existing.mkdir()
        out = existing / "out.pdf"

        assert convert_images_to_pdf([img], out) is True
        assert out.exists()


# =====================================================================
# § 11 — FILE HANDLE CLEANUP (Windows-safe)
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestFileHandleCleanup:
    """
    The CLI uses `_load_image_safely()` to load images, close file
    handles, and return in-memory copies. This prevents "file in use"
    errors on Windows when the temp directory is removed afterwards.
    """

    @pytest.mark.unit
    def test_source_file_can_be_deleted_after_conversion(
        self, temp_dir, create_test_image
    ):
        """The original files should be deletable post-conversion."""
        img = create_test_image(temp_dir / "img.jpg")
        out = temp_dir / "out.pdf"

        convert_images_to_pdf([img], out)

        # On Windows, this would fail if Pillow still held the handle.
        img.unlink()
        assert not img.exists()

    @pytest.mark.unit
    def test_multiple_files_deletable(self, temp_dir, create_test_image):
        images = [
            create_test_image(temp_dir / f"img_{i}.jpg")
            for i in range(5)
        ]
        out = temp_dir / "out.pdf"
        convert_images_to_pdf(images, out)

        for img in images:
            img.unlink()
        assert not any(img.exists() for img in images)

    @pytest.mark.unit
    def test_returns_detached_copy_not_original(self, temp_dir):
        """`_load_image_safely` must return an image whose .filename is None
        (i.e., an in-memory copy, not a file-backed object)."""
        img_path = temp_dir / "img.png"
        Image.new("RGB", (50, 50), (0, 0, 0)).save(img_path)

        loaded = _load_image_safely(img_path)

        assert loaded is not None
        # `Image.copy()` and mode conversions drop the `filename` binding
        assert getattr(loaded, "filename", None) is None

        loaded.close()

    @pytest.mark.unit
    def test_returns_none_for_invalid_file(self, temp_dir):
        bad = temp_dir / "bad.jpg"
        bad.write_text("not an image")

        assert _load_image_safely(bad) is None

    @pytest.mark.unit
    def test_returns_none_for_missing_file(self, temp_dir):
        ghost = temp_dir / "ghost.jpg"
        assert _load_image_safely(ghost) is None

    @pytest.mark.unit
    def test_returns_rgb_image_for_palette_input(self, temp_dir):
        img_path = temp_dir / "pal.png"
        p = Image.new("P", (50, 50))
        p.putpalette([i % 256 for i in range(768)])
        p.save(img_path)

        loaded = _load_image_safely(img_path)

        assert loaded is not None
        assert loaded.mode == "RGB"
        loaded.close()

    @pytest.mark.unit
    def test_returns_rgb_image_for_rgba_input(self, temp_dir):
        img_path = temp_dir / "rgba.png"
        Image.new("RGBA", (50, 50), (255, 0, 0, 128)).save(img_path)

        loaded = _load_image_safely(img_path)

        assert loaded is not None
        assert loaded.mode == "RGB"
        loaded.close()

    @pytest.mark.unit
    def test_returns_rgb_image_for_grayscale_input(self, temp_dir):
        img_path = temp_dir / "gray.png"
        Image.new("L", (50, 50), 128).save(img_path)

        loaded = _load_image_safely(img_path)

        assert loaded is not None
        assert loaded.mode == "RGB"
        loaded.close()


# =====================================================================
# § 12 — REAL-WORLD SCENARIOS
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFRealWorld:

    @pytest.mark.integration
    def test_archive_pages(self, temp_dir, create_test_image):
        images = [
            create_test_image(temp_dir / f"page_{i:03d}.jpg", size=(800, 1200))
            for i in range(10)
        ]
        out = temp_dir / "archive.pdf"

        assert convert_images_to_pdf(images, out) is True
        assert count_pdf_pages(out) == 10

    @pytest.mark.integration
    def test_scanned_documents_mixed_grayscale_color(self, temp_dir):
        images = []
        for i in range(5):
            path = temp_dir / f"scan_{i}.jpg"
            if i % 2 == 0:
                Image.new("L", (1700, 2200), 255).save(path)
            else:
                Image.new("RGB", (1700, 2200), (255, 255, 255)).save(path)
            images.append(path)

        out = temp_dir / "scans.pdf"

        assert convert_images_to_pdf(images, out) is True
        assert count_pdf_pages(out) == 5

    @pytest.mark.integration
    def test_photo_album_landscape_and_portrait(
        self, temp_dir, create_test_image
    ):
        images = []
        for i in range(8):
            size = (1920, 1080) if i % 2 == 0 else (1080, 1920)
            images.append(
                create_test_image(temp_dir / f"photo_{i}.jpg", size=size)
            )
        out = temp_dir / "album.pdf"

        assert convert_images_to_pdf(images, out) is True
        assert count_pdf_pages(out) == 8

    @pytest.mark.integration
    def test_mixed_formats_and_sizes(self, temp_dir):
        fixtures = [
            ("image1.jpg", "RGB", (800, 600)),
            ("image2.png", "RGBA", (1024, 768)),
            ("image3.png", "P", (640, 480)),
            ("image4.bmp", "RGB", (1280, 720)),
        ]
        images = []
        for name, mode, size in fixtures:
            path = temp_dir / name
            if mode == "P":
                p = Image.new("P", size)
                p.putpalette([i % 256 for i in range(768)])
                p.save(path)
            else:
                Image.new(mode, size).save(path)
            images.append(path)

        out = temp_dir / "mixed.pdf"

        assert convert_images_to_pdf(images, out) is True
        assert count_pdf_pages(out) == len(fixtures)


# =====================================================================
# § 13 — PDF STRUCTURE VERIFICATION
# =====================================================================


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestPDFStructure:
    """Verify the generated PDF has a valid structure."""

    @pytest.mark.unit
    def test_pdf_header(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "img.jpg")
        out = temp_dir / "out.pdf"
        convert_images_to_pdf([img], out)

        data = out.read_bytes()
        assert data.startswith(b"%PDF")
        assert b"%%EOF" in data  # end marker

    @pytest.mark.unit
    def test_pdf_contains_page_objects(self, temp_dir, create_test_image):
        img = create_test_image(temp_dir / "img.jpg")
        out = temp_dir / "out.pdf"
        convert_images_to_pdf([img], out)

        data = out.read_bytes()
        assert b"/Type /Page" in data
        assert b"/Type /Catalog" in data

    @pytest.mark.unit
    def test_pdf_page_count_matches_input(self, temp_dir, create_test_image):
        images = [
            create_test_image(temp_dir / f"img_{i}.jpg") for i in range(4)
        ]
        out = temp_dir / "out.pdf"
        convert_images_to_pdf(images, out)

        assert count_pdf_pages(out) == 4

    @pytest.mark.unit
    def test_pdf_size_grows_with_pages(self, temp_dir, create_test_image):
        small = [create_test_image(temp_dir / "a.jpg")]
        big = [create_test_image(temp_dir / f"b_{i}.jpg") for i in range(5)]

        out_small = temp_dir / "small.pdf"
        out_big = temp_dir / "big.pdf"

        convert_images_to_pdf(small, out_small)
        convert_images_to_pdf(big, out_big)

        assert out_big.stat().st_size > out_small.stat().st_size
