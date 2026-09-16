#!/usr/bin/env python3
"""
Tests for extract_images_from_zip function from zipped_imgs_to_pdf.py
"""

import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

import pytest

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from python.zipped_imgs_to_pdf import extract_images_from_zip
from shared import DEFAULT_PRIORITY_CHARS


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def create_test_zip():
    """Factory fixture to create test ZIP files"""
    def _create_zip(zip_path, files):
        """
        Create a ZIP file with specified files

        Args:
            zip_path: Path where ZIP should be created
            files: Dict of {filename: content} or list of filenames
        """
        with zipfile.ZipFile(zip_path, 'w') as zf:
            if isinstance(files, dict):
                for filename, content in files.items():
                    zf.writestr(filename, content)
            else:
                for filename in files:
                    zf.writestr(filename, b'fake image content')
        return zip_path

    return _create_zip


class TestExtractImagesBasic:
    """Basic functionality tests for extract_images_from_zip"""

    @pytest.mark.unit
    def test_extract_single_image(self, temp_dir, create_test_zip):
        """Test extracting a single image from ZIP"""
        zip_path = temp_dir / "single.zip"
        create_test_zip(zip_path, ['image.jpg'])

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 1
        assert result[0].name == 'image.jpg'
        assert result[0].exists()

    @pytest.mark.unit
    def test_extract_multiple_images(self, temp_dir, create_test_zip):
        """Test extracting multiple images from ZIP"""
        files = ['img1.jpg', 'img2.png', 'img3.gif']
        zip_path = temp_dir / "multiple.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 3
        for img_path in result:
            assert img_path.exists()

    @pytest.mark.unit
    def test_filter_non_image_files(self, temp_dir, create_test_zip):
        """Test that non-image files are filtered out"""
        files = [
            'image1.jpg',
            'document.pdf',
            'image2.png',
            'text.txt',
            'data.json'
        ]
        zip_path = temp_dir / "mixed.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 2
        assert all(f.suffix.lower() in ['.jpg', '.png'] for f in result)

    @pytest.mark.unit
    def test_empty_zip(self, temp_dir, create_test_zip):
        """Test handling of ZIP with no images"""
        zip_path = temp_dir / "empty.zip"
        create_test_zip(zip_path, [])

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 0

    @pytest.mark.unit
    def test_zip_with_only_non_images(self, temp_dir, create_test_zip):
        """Test ZIP containing only non-image files"""
        files = ['document.pdf', 'text.txt', 'data.csv']
        zip_path = temp_dir / "no_images.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 0


class TestExtractImagesSorting:
    """Test sorting functionality in extract_images_from_zip"""

    @pytest.mark.unit
    def test_natural_sorting_enabled(self, temp_dir, create_test_zip):
        """Test that natural sorting is applied by default"""
        files = ['img_10.jpg', 'img_1.jpg', 'img_2.jpg', 'img_20.jpg']
        zip_path = temp_dir / "sorting.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir, use_natural_sort=True)

        names = [f.name for f in result]
        assert names == ['img_1.jpg', 'img_2.jpg', 'img_10.jpg', 'img_20.jpg']

    @pytest.mark.unit
    def test_natural_sorting_disabled(self, temp_dir, create_test_zip):
        """Test lexical sorting when natural sort is disabled"""
        files = ['img_10.jpg', 'img_1.jpg', 'img_2.jpg']
        zip_path = temp_dir / "lexical.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir, use_natural_sort=False)

        names = [f.name for f in result]
        # Lexical sort: 1 < 10 < 2
        assert names == ['img_1.jpg', 'img_10.jpg', 'img_2.jpg']

    @pytest.mark.unit
    def test_priority_files_first(self, temp_dir, create_test_zip):
        """Test that priority files (with !) are placed first"""
        files = ['page_1.jpg', '!cover.jpg', 'page_2.jpg', '!back.jpg']
        zip_path = temp_dir / "priority.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        names = [f.name for f in result]
        assert names[:2] == ['!back.jpg', '!cover.jpg']
        assert names[2:] == ['page_1.jpg', 'page_2.jpg']

    @pytest.mark.unit
    def test_custom_priority_chars(self, temp_dir, create_test_zip):
        """Test using custom priority characters"""
        files = ['page_1.jpg', '@special.jpg', 'page_2.jpg', '@bonus.jpg']
        zip_path = temp_dir / "custom_priority.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir, priority_chars='@')

        names = [f.name for f in result]
        assert names[:2] == ['@bonus.jpg', '@special.jpg']
        assert names[2:] == ['page_1.jpg', 'page_2.jpg']


class TestExtractImagesDirectories:
    """Test handling of directories within ZIP files"""

    @pytest.mark.unit
    def test_skip_directories(self, temp_dir):
        """Test that directories in ZIP are skipped"""
        zip_path = temp_dir / "with_dirs.zip"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Add directory entries
            zf.writestr('images/', '')
            zf.writestr('images/subfolder/', '')
            # Add files
            zf.writestr('images/img1.jpg', b'content')
            zf.writestr('images/subfolder/img2.png', b'content')

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 2
        assert all(f.is_file() for f in result)

    @pytest.mark.unit
    def test_nested_directories(self, temp_dir):
        """Test extracting images from nested directories"""
        zip_path = temp_dir / "nested.zip"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('level1/image1.jpg', b'content')
            zf.writestr('level1/level2/image2.png', b'content')
            zf.writestr('level1/level2/level3/image3.gif', b'content')

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 3


class TestExtractImagesErrors:
    """Test error handling in extract_images_from_zip"""

    @pytest.mark.unit
    def test_invalid_zip_file(self, temp_dir):
        """Test handling of invalid ZIP file"""
        # Create a file that's not a valid ZIP
        invalid_zip = temp_dir / "invalid.zip"
        invalid_zip.write_text("This is not a ZIP file")

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(invalid_zip, extract_dir)

        # Should return empty list and print error
        assert len(result) == 0

    @pytest.mark.unit
    def test_corrupted_zip(self, temp_dir):
        """Test handling of corrupted ZIP file"""
        zip_path = temp_dir / "corrupted.zip"

        # Create a ZIP then corrupt it
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('image.jpg', b'content')

        # Corrupt the file by truncating it
        with open(zip_path, 'rb') as f:
            content = f.read()

        with open(zip_path, 'wb') as f:
            f.write(content[:len(content)//2])

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Should handle error gracefully
        assert len(result) == 0

    @pytest.mark.unit
    def test_permission_error_handling(self, temp_dir, create_test_zip):
        """Test handling of permission errors during extraction"""
        zip_path = temp_dir / "test.zip"
        create_test_zip(zip_path, ['image.jpg'])

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        # Mock zipfile.ZipFile to raise PermissionError
        with mock.patch('zipfile.ZipFile') as mock_zip:
            mock_zip.side_effect = PermissionError("Permission denied")

            result = extract_images_from_zip(zip_path, extract_dir)

            assert len(result) == 0


class TestExtractImagesImageFormats:
    """Test support for various image formats"""

    @pytest.mark.unit
    def test_all_supported_formats(self, temp_dir, create_test_zip):
        """Test extraction of all supported image formats"""
        files = [
            'image.jpg',
            'image.jpeg',
            'image.png',
            'image.gif',
            'image.bmp',
            'image.tiff',
            'image.webp'
        ]
        zip_path = temp_dir / "formats.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 7
        extensions = {f.suffix.lower() for f in result}
        assert extensions == {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}

    @pytest.mark.unit
    def test_case_insensitive_extensions(self, temp_dir, create_test_zip):
        """Test that image detection is case-insensitive"""
        files = [
            'image1.JPG',
            'image2.PNG',
            'image3.GIF',
            'image4.jpg'
        ]
        zip_path = temp_dir / "case_test.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 4


class TestExtractImagesRealWorld:
    """Real-world scenario tests"""

    @pytest.mark.integration
    def test_archive_file(self, temp_dir, create_test_zip):
        """Test extracting a archive-style ZIP archive"""
        files = [
            '!cover.jpg',
            'page_001.jpg',
            'page_002.jpg',
            'page_003.jpg',
            'page_010.jpg',
            'page_011.jpg',
            '!credits.jpg'
        ]
        zip_path = temp_dir / "archive.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Priority files first, then naturally sorted pages
        names = [f.name for f in result]
        assert names[0] == '!cover.jpg'
        assert names[1] == '!credits.jpg'
        assert 'page_001.jpg' in names[2:]
        assert 'page_010.jpg' in names[2:]

    @pytest.mark.integration
    def test_photo_album_archive(self, temp_dir, create_test_zip):
        """Test extracting a photo album ZIP"""
        files = [
            'IMG_0010.jpg',
            'IMG_0001.jpg',
            'IMG_0002.jpg',
            'IMG_0100.jpg',
            'Thumbs.db',  # Windows thumbnail cache
            '.DS_Store'   # macOS metadata
        ]
        zip_path = temp_dir / "photos.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Should only extract images, not metadata files
        assert len(result) == 4
        names = [f.name for f in result]
        assert 'Thumbs.db' not in names
        assert '.DS_Store' not in names

    @pytest.mark.integration
    def test_mixed_content_archive(self, temp_dir, create_test_zip):
        """Test ZIP with images, documents, and other files"""
        files = {
            'photo1.jpg': b'image content',
            'photo2.png': b'image content',
            'readme.txt': b'text content',
            'document.pdf': b'pdf content',
            'data.json': b'{"key": "value"}',
            'script.py': b'print("hello")',
            'photo3.gif': b'image content'
        }
        zip_path = temp_dir / "mixed.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Should only extract the 3 image files
        assert len(result) == 3
        extensions = {f.suffix.lower() for f in result}
        assert extensions == {'.jpg', '.png', '.gif'}
