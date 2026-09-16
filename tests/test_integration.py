#!/usr/bin/env python3
"""
End-to-End integration tests for zipped_imgs_to_pdf.py
Tests complete workflows from ZIP file to PDF output
"""

import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import mock
import io

import pytest

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

from python.zipped_imgs_to_pdf import (
    extract_images_from_zip,
    convert_images_to_pdf,
    process_zip_file,
    find_zip_files_recursive,
    main
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def create_image_zip():
    """Factory fixture to create ZIP files with actual images"""
    def _create_zip(zip_path, images_config):
        """
        Create a ZIP file with actual image files

        Args:
            zip_path: Path where ZIP should be created
            images_config: List of tuples (filename, mode, size, color)
        """
        if not PILLOW_AVAILABLE:
            pytest.skip("Pillow not available")

        with zipfile.ZipFile(zip_path, 'w') as zf:
            for config in images_config:
                if len(config) == 1:
                    # Just filename, use defaults
                    filename = config[0]
                    mode = 'RGB'
                    size = (100, 100)
                    color = (255, 0, 0)
                elif len(config) == 4:
                    filename, mode, size, color = config
                else:
                    raise ValueError("Invalid config")

                # Create image in memory
                img = Image.new(mode, size, color)
                img_bytes = io.BytesIO()
                # Save as appropriate format based on extension
                if filename.lower().endswith('.png'):
                    img.save(img_bytes, 'PNG')
                elif filename.lower().endswith('.gif'):
                    img.save(img_bytes, 'GIF')
                else:
                    img.save(img_bytes, 'JPEG')

                zf.writestr(filename, img_bytes.getvalue())

        return zip_path

    return _create_zip


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestCompleteWorkflow:
    """Test complete ZIP to PDF conversion workflow"""

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_simple_zip_to_pdf(self, temp_dir, create_image_zip):
        """Test basic ZIP to PDF conversion"""
        # Create a ZIP with 3 images
        images = [
            ('img1.jpg', 'RGB', (200, 150), (255, 0, 0)),
            ('img2.jpg', 'RGB', (200, 150), (0, 255, 0)),
            ('img3.jpg', 'RGB', (200, 150), (0, 0, 255))
        ]
        zip_path = temp_dir / "test.zip"
        create_image_zip(zip_path, images)

        # Process the ZIP
        result = process_zip_file(zip_path)

        # Verify success
        assert result is True

        # Verify PDF was created
        pdf_path = temp_dir / "test.pdf"
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_zip_with_priority_files(self, temp_dir, create_image_zip):
        """Test ZIP with priority files (!) are placed first in PDF"""
        images = [
            ('page1.jpg', 'RGB', (100, 100), (255, 0, 0)),
            ('!cover.jpg', 'RGB', (100, 100), (0, 255, 0)),
            ('page2.jpg', 'RGB', (100, 100), (0, 0, 255)),
            ('!back.jpg', 'RGB', (100, 100), (255, 255, 0))
        ]
        zip_path = temp_dir / "priority.zip"
        create_image_zip(zip_path, images)

        # Extract and verify order
        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        extracted = extract_images_from_zip(zip_path, extract_dir)

        # Priority files should be first
        assert extracted[0].name == '!back.jpg'
        assert extracted[1].name == '!cover.jpg'

        # Then convert to PDF
        pdf_path = temp_dir / "priority.pdf"
        result = convert_images_to_pdf(extracted, pdf_path)

        assert result is True
        assert pdf_path.exists()

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_natural_sorting_workflow(self, temp_dir, create_image_zip):
        """Test that natural sorting is applied correctly"""
        images = [
            ('page_10.jpg', 'RGB', (100, 100), (255, 0, 0)),
            ('page_1.jpg', 'RGB', (100, 100), (0, 255, 0)),
            ('page_2.jpg', 'RGB', (100, 100), (0, 0, 255)),
            ('page_20.jpg', 'RGB', (100, 100), (255, 255, 0))
        ]
        zip_path = temp_dir / "sorted.zip"
        create_image_zip(zip_path, images)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        extracted = extract_images_from_zip(zip_path, extract_dir, use_natural_sort=True)

        # Verify natural sorting order
        names = [p.name for p in extracted]
        assert names == ['page_1.jpg', 'page_2.jpg', 'page_10.jpg', 'page_20.jpg']

        # Convert to PDF
        pdf_path = temp_dir / "sorted.pdf"
        result = convert_images_to_pdf(extracted, pdf_path)

        assert result is True

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_mixed_image_formats(self, temp_dir, create_image_zip):
        """Test ZIP with mixed image formats"""
        images = [
            ('image1.jpg', 'RGB', (100, 100), (255, 0, 0)),
            ('image2.png', 'RGBA', (100, 100), (0, 255, 0, 128)),
            ('image3.gif', 'P', (100, 100), None)
        ]

        zip_path = temp_dir / "mixed.zip"

        # Create ZIP manually to handle palette mode
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for filename, mode, size, color in images:
                img = Image.new(mode, size)
                if mode == 'P':
                    img.putpalette([i % 256 for i in range(768)])
                elif color:
                    # For RGBA and RGB with color
                    if mode == 'RGBA':
                        img = Image.new(mode, size, color)
                    else:
                        img = Image.new(mode, size, color)

                img_bytes = io.BytesIO()
                if filename.lower().endswith('.png'):
                    img.save(img_bytes, 'PNG')
                elif filename.lower().endswith('.gif'):
                    img.save(img_bytes, 'GIF')
                else:
                    img.save(img_bytes, 'JPEG')

                zf.writestr(filename, img_bytes.getvalue())

        result = process_zip_file(zip_path)

        assert result is True

        pdf_path = temp_dir / "mixed.pdf"
        assert pdf_path.exists()

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_custom_output_directory(self, temp_dir, create_image_zip):
        """Test specifying custom output directory"""
        images = [('image.jpg', 'RGB', (100, 100), (255, 0, 0))]
        zip_path = temp_dir / "test.zip"
        create_image_zip(zip_path, images)

        # Create custom output directory
        output_dir = temp_dir / "output"
        output_dir.mkdir()

        result = process_zip_file(zip_path, output_dir=output_dir)

        assert result is True

        # PDF should be in output directory
        pdf_path = output_dir / "test.pdf"
        assert pdf_path.exists()

    @pytest.mark.integration
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_large_number_of_images(self, temp_dir, create_image_zip):
        """Test processing ZIP with many images"""
        images = [
            (f'page_{i:03d}.jpg', 'RGB', (50, 50), (i * 10 % 256, 0, 0))
            for i in range(50)
        ]

        zip_path = temp_dir / "large.zip"
        create_image_zip(zip_path, images)

        result = process_zip_file(zip_path)

        assert result is True

        pdf_path = temp_dir / "large.pdf"
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestRecursiveProcessing:
    """Test recursive directory processing"""

    @pytest.mark.integration
    def test_find_zip_files_in_directory(self, temp_dir, create_image_zip):
        """Test finding ZIP files recursively"""
        # Create directory structure with ZIPs
        dir1 = temp_dir / "dir1"
        dir2 = temp_dir / "dir2"
        subdir = dir1 / "subdir"

        dir1.mkdir()
        dir2.mkdir()
        subdir.mkdir()

        # Create ZIP files
        images = [('img.jpg', 'RGB', (50, 50), (255, 0, 0))]

        create_image_zip(dir1 / "file1.zip", images)
        create_image_zip(dir2 / "file2.zip", images)
        create_image_zip(subdir / "file3.zip", images)

        # Find all ZIPs
        found = find_zip_files_recursive(temp_dir)

        assert len(found) == 3
        assert all(f.suffix.lower() == '.zip' for f in found)

    @pytest.mark.integration
    def test_find_zip_files_case_insensitive(self, temp_dir, create_image_zip):
        """Test finding .ZIP (uppercase) files"""
        images = [('img.jpg', 'RGB', (50, 50), (255, 0, 0))]

        create_image_zip(temp_dir / "lower.zip", images)

        # Create uppercase ZIP
        uppercase_zip = temp_dir / "UPPER.ZIP"
        create_image_zip(uppercase_zip, images)

        found = find_zip_files_recursive(temp_dir)

        assert len(found) == 2

    @pytest.mark.integration
    def test_recursive_with_no_zips(self, temp_dir):
        """Test recursive search with no ZIP files"""
        # Create some non-ZIP files
        (temp_dir / "file1.txt").write_text("content")
        (temp_dir / "file2.pdf").write_bytes(b"pdf content")

        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "file3.doc").write_text("doc")

        found = find_zip_files_recursive(temp_dir)

        assert len(found) == 0


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestRealWorldScenarios:
    """Test real-world usage scenarios"""

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_archive_conversion(self, temp_dir, create_image_zip):
        """Test converting a archive archive"""
        images = [
            ('!000_cover.jpg', 'RGB', (800, 1200), (255, 0, 0)),
            ('001.jpg', 'RGB', (800, 1200), (255, 255, 255)),
            ('002.jpg', 'RGB', (800, 1200), (255, 255, 255)),
            ('003.jpg', 'RGB', (800, 1200), (255, 255, 255)),
            ('!999_credits.jpg', 'RGB', (800, 1200), (0, 0, 0))
        ]

        zip_path = temp_dir / "archive.zip"
        create_image_zip(zip_path, images)

        result = process_zip_file(zip_path)

        assert result is True

        pdf_path = temp_dir / "archive.pdf"
        assert pdf_path.exists()

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_photo_album_conversion(self, temp_dir, create_image_zip):
        """Test converting a photo album"""
        images = [
            ('IMG_0001.jpg', 'RGB', (1920, 1080), (255, 0, 0)),
            ('IMG_0002.jpg', 'RGB', (1080, 1920), (0, 255, 0)),
            ('IMG_0010.jpg', 'RGB', (1920, 1080), (0, 0, 255)),
            ('IMG_0100.jpg', 'RGB', (1920, 1080), (255, 255, 0))
        ]

        zip_path = temp_dir / "photos.zip"
        create_image_zip(zip_path, images)

        result = process_zip_file(zip_path)

        assert result is True

        pdf_path = temp_dir / "photos.pdf"
        assert pdf_path.exists()

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_scanned_documents(self, temp_dir):
        """Test converting scanned documents"""
        if not PILLOW_AVAILABLE:
            pytest.skip("Pillow not available")

        zip_path = temp_dir / "scans.zip"

        images = []
        with zipfile.ZipFile(zip_path, 'w') as zf:
            for i in range(5):
                # Alternate between grayscale and color
                mode = 'L' if i % 2 == 0 else 'RGB'
                color = 255 if mode == 'L' else (255, 255, 255)

                img = Image.new(mode, (1700, 2200), color)
                img_bytes = io.BytesIO()
                img.save(img_bytes, 'JPEG')

                zf.writestr(f'scan_{i:03d}.jpg', img_bytes.getvalue())

        result = process_zip_file(zip_path)

        assert result is True

        pdf_path = temp_dir / "scans.pdf"
        assert pdf_path.exists()


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestMultipleFilesProcessing:
    """Test processing multiple ZIP files"""

    @pytest.mark.integration
    @pytest.mark.e2e
    def test_process_multiple_zips(self, temp_dir, create_image_zip):
        """Test processing multiple ZIP files"""
        images = [('img.jpg', 'RGB', (100, 100), (255, 0, 0))]

        zip1 = temp_dir / "file1.zip"
        zip2 = temp_dir / "file2.zip"
        zip3 = temp_dir / "file3.zip"

        create_image_zip(zip1, images)
        create_image_zip(zip2, images)
        create_image_zip(zip3, images)

        # Process each
        results = []
        for zip_path in [zip1, zip2, zip3]:
            result = process_zip_file(zip_path)
            results.append(result)

        assert all(results)

        # Verify all PDFs created
        assert (temp_dir / "file1.pdf").exists()
        assert (temp_dir / "file2.pdf").exists()
        assert (temp_dir / "file3.pdf").exists()


class TestCLIIntegration:
    """Test command-line interface integration"""

    @pytest.mark.integration
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_main_with_single_file(self, temp_dir, create_image_zip, monkeypatch):
        """Test main() with single ZIP file argument"""
        images = [('img.jpg', 'RGB', (100, 100), (255, 0, 0))]
        zip_path = temp_dir / "test.zip"
        create_image_zip(zip_path, images)

        # Mock sys.argv
        test_args = ['zipped_imgs_to_pdf.py', str(zip_path)]
        monkeypatch.setattr(sys, 'argv', test_args)

        # Capture output
        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        # Verify PDF created
        pdf_path = temp_dir / "test.pdf"
        assert pdf_path.exists()

    @pytest.mark.integration
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_main_with_natural_sort_option(self, temp_dir, create_image_zip, monkeypatch):
        """Test main() with --no-natural-sort option"""
        images = [
            ('img_10.jpg', 'RGB', (50, 50), (255, 0, 0)),
            ('img_1.jpg', 'RGB', (50, 50), (0, 255, 0)),
            ('img_2.jpg', 'RGB', (50, 50), (0, 0, 255))
        ]
        zip_path = temp_dir / "test.zip"
        create_image_zip(zip_path, images)

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '--no-natural-sort']
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

    @pytest.mark.integration
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_main_with_output_directory(self, temp_dir, create_image_zip, monkeypatch):
        """Test main() with -o output directory option"""
        images = [('img.jpg', 'RGB', (100, 100), (255, 0, 0))]
        zip_path = temp_dir / "test.zip"
        create_image_zip(zip_path, images)

        output_dir = temp_dir / "output"

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '-o', str(output_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        # Verify PDF in output directory
        pdf_path = output_dir / "test.pdf"
        assert pdf_path.exists()

    @pytest.mark.integration
    def test_main_with_nonexistent_file(self, temp_dir, monkeypatch):
        """Test main() with nonexistent file"""
        test_args = ['zipped_imgs_to_pdf.py', str(temp_dir / "nonexistent.zip")]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(1)


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestDataIntegrity:
    """Test that data integrity is maintained through conversion"""

    @pytest.mark.integration
    def test_image_count_preserved(self, temp_dir, create_image_zip):
        """Test that all images are included in PDF"""
        num_images = 10
        images = [
            (f'img_{i:03d}.jpg', 'RGB', (100, 100), (i * 25 % 256, 0, 0))
            for i in range(num_images)
        ]

        zip_path = temp_dir / "test.zip"
        create_image_zip(zip_path, images)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        extracted = extract_images_from_zip(zip_path, extract_dir)

        # Verify count
        assert len(extracted) == num_images

        # Convert to PDF
        pdf_path = temp_dir / "test.pdf"
        result = convert_images_to_pdf(extracted, pdf_path)

        assert result is True

    @pytest.mark.integration
    def test_filename_order_preserved(self, temp_dir, create_image_zip):
        """Test that filename order is preserved correctly"""
        images = [
            ('001.jpg', 'RGB', (50, 50), (255, 0, 0)),
            ('002.jpg', 'RGB', (50, 50), (0, 255, 0)),
            ('003.jpg', 'RGB', (50, 50), (0, 0, 255))
        ]

        zip_path = temp_dir / "ordered.zip"
        create_image_zip(zip_path, images)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        extracted = extract_images_from_zip(zip_path, extract_dir)

        names = [p.name for p in extracted]
        assert names == ['001.jpg', '002.jpg', '003.jpg']
