#!/usr/bin/env python3
"""
Tests for convert_images_to_pdf function from zipped_imgs_to_pdf.py
"""

import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if Pillow is available
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

if PILLOW_AVAILABLE:
    from python.zipped_imgs_to_pdf import convert_images_to_pdf


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def create_test_image():
    """Factory fixture to create test images"""
    def _create_image(path, mode='RGB', size=(100, 100), color=(255, 0, 0)):
        """
        Create a test image

        Args:
            path: Path where image should be saved
            mode: Image mode (RGB, RGBA, L, etc.)
            size: Image dimensions (width, height)
            color: Fill color
        """
        img = Image.new(mode, size, color)
        img.save(path)
        return path

    return _create_image


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFBasic:
    """Basic functionality tests for convert_images_to_pdf"""

    @pytest.mark.unit
    def test_convert_single_image(self, temp_dir, create_test_image):
        """Test converting a single image to PDF"""
        img_path = temp_dir / "image.jpg"
        create_test_image(img_path, mode='RGB')

        output_pdf = temp_dir / "output.pdf"

        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True
        assert output_pdf.exists()
        assert output_pdf.stat().st_size > 0

    @pytest.mark.unit
    def test_convert_multiple_images(self, temp_dir, create_test_image):
        """Test converting multiple images to multi-page PDF"""
        images = []
        for i in range(3):
            img_path = temp_dir / f"image_{i}.jpg"
            create_test_image(img_path, mode='RGB')
            images.append(img_path)

        output_pdf = temp_dir / "output.pdf"

        result = convert_images_to_pdf(images, output_pdf)

        assert result is True
        assert output_pdf.exists()

    @pytest.mark.unit
    def test_empty_image_list(self, temp_dir):
        """Test that empty image list returns False"""
        output_pdf = temp_dir / "output.pdf"

        result = convert_images_to_pdf([], output_pdf)

        assert result is False
        assert not output_pdf.exists()


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFImageModes:
    """Test conversion of different image modes"""

    @pytest.mark.unit
    def test_rgb_image(self, temp_dir, create_test_image):
        """Test RGB image conversion"""
        img_path = temp_dir / "rgb.jpg"
        create_test_image(img_path, mode='RGB')

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True

    @pytest.mark.unit
    def test_rgba_image_conversion(self, temp_dir, create_test_image):
        """Test RGBA image is converted to RGB with white background"""
        img_path = temp_dir / "rgba.png"
        create_test_image(img_path, mode='RGBA', color=(255, 0, 0, 128))

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True
        assert output_pdf.exists()

    @pytest.mark.unit
    def test_palette_mode_image(self, temp_dir):
        """Test palette mode (P) image conversion"""
        img_path = temp_dir / "palette.png"

        # Create a palette mode image
        img = Image.new('P', (100, 100))
        img.putpalette([i % 256 for i in range(768)])  # Simple palette
        img.save(img_path)

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True

    @pytest.mark.unit
    def test_grayscale_with_alpha(self, temp_dir):
        """Test LA (grayscale + alpha) image conversion"""
        img_path = temp_dir / "gray_alpha.png"

        img = Image.new('LA', (100, 100), (128, 255))
        img.save(img_path)

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True

    @pytest.mark.unit
    def test_grayscale_image(self, temp_dir):
        """Test grayscale (L) image conversion"""
        img_path = temp_dir / "gray.png"

        img = Image.new('L', (100, 100), 128)
        img.save(img_path)

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True

    @pytest.mark.unit
    def test_cmyk_image(self, temp_dir):
        """Test CMYK image conversion"""
        img_path = temp_dir / "cmyk.jpg"

        img = Image.new('CMYK', (100, 100), (0, 100, 100, 0))
        img.save(img_path)

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFMixedModes:
    """Test conversion of images with mixed color modes"""

    @pytest.mark.unit
    def test_mixed_rgb_and_rgba(self, temp_dir, create_test_image):
        """Test converting mix of RGB and RGBA images"""
        img1 = temp_dir / "rgb.jpg"
        img2 = temp_dir / "rgba.png"
        img3 = temp_dir / "rgb2.jpg"

        create_test_image(img1, mode='RGB')
        create_test_image(img2, mode='RGBA')
        create_test_image(img3, mode='RGB')

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img1, img2, img3], output_pdf)

        assert result is True

    @pytest.mark.unit
    def test_mixed_all_modes(self, temp_dir):
        """Test converting images with various color modes"""
        images = []

        # RGB
        img_rgb = temp_dir / "rgb.jpg"
        Image.new('RGB', (100, 100), (255, 0, 0)).save(img_rgb)
        images.append(img_rgb)

        # RGBA
        img_rgba = temp_dir / "rgba.png"
        Image.new('RGBA', (100, 100), (0, 255, 0, 128)).save(img_rgba)
        images.append(img_rgba)

        # L
        img_gray = temp_dir / "gray.jpg"
        Image.new('L', (100, 100), 128).save(img_gray)
        images.append(img_gray)

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf(images, output_pdf)

        assert result is True


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFErrors:
    """Test error handling in convert_images_to_pdf"""

    @pytest.mark.unit
    def test_invalid_image_file(self, temp_dir):
        """Test handling of invalid image file"""
        # Create a non-image file
        invalid_img = temp_dir / "invalid.jpg"
        invalid_img.write_text("This is not an image")

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([invalid_img], output_pdf)

        # Should handle error gracefully and return False
        assert result is False

    @pytest.mark.unit
    def test_corrupted_image_skipped(self, temp_dir, create_test_image):
        """Test that corrupted images are skipped but others are processed"""
        good_img1 = temp_dir / "good1.jpg"
        bad_img = temp_dir / "bad.jpg"
        good_img2 = temp_dir / "good2.jpg"

        create_test_image(good_img1, mode='RGB')
        create_test_image(good_img2, mode='RGB')

        # Create corrupted image
        bad_img.write_text("corrupted image data")

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([good_img1, bad_img, good_img2], output_pdf)

        # Should still succeed with the good images
        assert result is True
        assert output_pdf.exists()

    @pytest.mark.unit
    def test_all_images_corrupted(self, temp_dir):
        """Test when all images fail to open"""
        bad_img1 = temp_dir / "bad1.jpg"
        bad_img2 = temp_dir / "bad2.jpg"

        bad_img1.write_text("corrupted")
        bad_img2.write_text("corrupted")

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([bad_img1, bad_img2], output_pdf)

        assert result is False

    @pytest.mark.unit
    def test_nonexistent_image(self, temp_dir):
        """Test handling of nonexistent image file"""
        nonexistent = temp_dir / "nonexistent.jpg"

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([nonexistent], output_pdf)

        assert result is False

    @pytest.mark.unit
    def test_write_permission_error(self, temp_dir, create_test_image):
        """Test handling of write permission errors"""
        img_path = temp_dir / "image.jpg"
        create_test_image(img_path, mode='RGB')

        # Try to write to a directory (should fail)
        invalid_output = temp_dir / "subdir"
        invalid_output.mkdir()

        result = convert_images_to_pdf([img_path], invalid_output)

        assert result is False


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFSizes:
    """Test conversion of images with different sizes"""

    @pytest.mark.unit
    def test_small_images(self, temp_dir, create_test_image):
        """Test converting small images"""
        img_path = temp_dir / "small.jpg"
        create_test_image(img_path, mode='RGB', size=(50, 50))

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True

    @pytest.mark.unit
    def test_large_images(self, temp_dir, create_test_image):
        """Test converting large images"""
        img_path = temp_dir / "large.jpg"
        create_test_image(img_path, mode='RGB', size=(2000, 2000))

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True

    @pytest.mark.unit
    def test_different_aspect_ratios(self, temp_dir, create_test_image):
        """Test images with different aspect ratios"""
        images = []

        # Wide image
        wide = temp_dir / "wide.jpg"
        create_test_image(wide, size=(200, 100))
        images.append(wide)

        # Tall image
        tall = temp_dir / "tall.jpg"
        create_test_image(tall, size=(100, 200))
        images.append(tall)

        # Square image
        square = temp_dir / "square.jpg"
        create_test_image(square, size=(100, 100))
        images.append(square)

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf(images, output_pdf)

        assert result is True

    @pytest.mark.unit
    @pytest.mark.slow
    def test_many_images(self, temp_dir, create_test_image):
        """Test converting many images"""
        images = []
        for i in range(20):
            img_path = temp_dir / f"image_{i:03d}.jpg"
            create_test_image(img_path, mode='RGB')
            images.append(img_path)

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf(images, output_pdf)

        assert result is True
        assert output_pdf.exists()


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFResolution:
    """Test PDF resolution settings"""

    @pytest.mark.unit
    def test_pdf_resolution_setting(self, temp_dir, create_test_image):
        """Test that PDF is created with correct resolution (100.0)"""
        img_path = temp_dir / "image.jpg"
        create_test_image(img_path, mode='RGB')

        output_pdf = temp_dir / "output.pdf"

        # Mock the Image.save to check resolution parameter
        with mock.patch.object(Image.Image, 'save') as mock_save:
            result = convert_images_to_pdf([img_path], output_pdf)

            assert result is True
            # Verify save was called with resolution parameter
            # The first call to save is the one that matters
            save_call = mock_save.call_args
            assert save_call is not None
            assert 'resolution' in save_call.kwargs
            assert save_call.kwargs['resolution'] == 100.0


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestConvertToPDFRealWorld:
    """Real-world scenario tests"""

    @pytest.mark.integration
    def test_archive_pages(self, temp_dir, create_test_image):
        """Test converting archive pages to PDF"""
        images = []
        for i in range(10):
            img_path = temp_dir / f"page_{i:03d}.jpg"
            # Archive pages are typically tall
            create_test_image(img_path, mode='RGB', size=(800, 1200))
            images.append(img_path)

        output_pdf = temp_dir / "archive.pdf"
        result = convert_images_to_pdf(images, output_pdf)

        assert result is True
        assert output_pdf.exists()

    @pytest.mark.integration
    def test_scanned_documents(self, temp_dir):
        """Test converting scanned document images"""
        images = []

        # Mix of grayscale and color scans
        for i in range(5):
            img_path = temp_dir / f"scan_{i}.jpg"
            mode = 'L' if i % 2 == 0 else 'RGB'
            img = Image.new(mode, (1700, 2200), 255 if mode == 'L' else (255, 255, 255))
            img.save(img_path)
            images.append(img_path)

        output_pdf = temp_dir / "scans.pdf"
        result = convert_images_to_pdf(images, output_pdf)

        assert result is True

    @pytest.mark.integration
    def test_photo_album(self, temp_dir, create_test_image):
        """Test converting photos to PDF album"""
        images = []

        # Mix of landscape and portrait photos
        for i in range(8):
            img_path = temp_dir / f"photo_{i}.jpg"
            if i % 2 == 0:
                size = (1920, 1080)  # Landscape
            else:
                size = (1080, 1920)  # Portrait
            create_test_image(img_path, mode='RGB', size=size)
            images.append(img_path)

        output_pdf = temp_dir / "album.pdf"
        result = convert_images_to_pdf(images, output_pdf)

        assert result is True

    @pytest.mark.integration
    def test_mixed_formats_and_sizes(self, temp_dir):
        """Test converting images with mixed formats and sizes"""
        images = []

        formats = [
            ('image1.jpg', 'RGB', (800, 600)),
            ('image2.png', 'RGBA', (1024, 768)),
            ('image3.gif', 'P', (640, 480)),
            ('image4.bmp', 'RGB', (1280, 720)),
        ]

        for filename, mode, size in formats:
            img_path = temp_dir / filename
            img = Image.new(mode, size)
            if mode == 'P':
                img.putpalette([i % 256 for i in range(768)])
            img.save(img_path)
            images.append(img_path)

        output_pdf = temp_dir / "mixed.pdf"
        result = convert_images_to_pdf(images, output_pdf)

        assert result is True
        assert output_pdf.exists()
