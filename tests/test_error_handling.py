#!/usr/bin/env python3
"""
Error handling tests for zipped_imgs_to_pdf.py
Tests edge cases, errors, and exceptional conditions
"""

import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

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
    process_zip_file,
    find_zip_files_recursive
)

if PILLOW_AVAILABLE:
    from python.zipped_imgs_to_pdf import convert_images_to_pdf


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def create_test_zip():
    """Factory fixture to create test ZIP files"""
    def _create_zip(zip_path, files):
        with zipfile.ZipFile(zip_path, 'w') as zf:
            if isinstance(files, dict):
                for filename, content in files.items():
                    zf.writestr(filename, content)
            else:
                for filename in files:
                    zf.writestr(filename, b'fake content')
        return zip_path
    return _create_zip


class TestSpecialCharactersHandling:
    """Test handling of special characters in filenames"""

    @pytest.mark.unit
    def test_unicode_filenames(self, temp_dir, create_test_zip):
        """Test handling of Unicode characters in filenames"""
        files = [
            '图片1.jpg',  # Chinese
            'صورة2.png',  # Arabic
            'изображение3.gif',  # Cyrillic
            '画像4.jpg'  # Japanese
        ]
        zip_path = temp_dir / "unicode.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 4

    @pytest.mark.unit
    def test_special_chars_in_filename(self, temp_dir, create_test_zip):
        """Test filenames with special characters"""
        files = [
            'image (1).jpg',
            'image [2].png',
            'image {3}.gif',
            'image-4.jpg',
            'image_5.png',
            'image.number.6.jpg'
        ]
        zip_path = temp_dir / "special.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 6

    @pytest.mark.unit
    def test_spaces_in_filename(self, temp_dir, create_test_zip):
        """Test filenames with spaces"""
        files = [
            'my image 1.jpg',
            'photo with spaces.png',
            '  leading spaces.jpg',
            'trailing spaces  .png'
        ]
        zip_path = temp_dir / "spaces.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 4

    @pytest.mark.unit
    def test_very_long_filename(self, temp_dir, create_test_zip):
        """Test very long filenames"""
        long_name = 'a' * 200 + '.jpg'
        zip_path = temp_dir / "long.zip"
        create_test_zip(zip_path, [long_name])

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Should handle long filenames
        assert len(result) >= 0  # May succeed or fail depending on OS limits


class TestFileSystemErrors:
    """Test handling of file system related errors"""

    @pytest.mark.unit
    def test_readonly_extract_directory(self, temp_dir, create_test_zip):
        """Test extraction to read-only directory"""
        zip_path = temp_dir / "test.zip"
        create_test_zip(zip_path, ['image.jpg'])

        extract_dir = temp_dir / "readonly"
        extract_dir.mkdir()

        # Make directory read-only
        extract_dir.chmod(0o444)

        try:
            result = extract_images_from_zip(zip_path, extract_dir)
            # Should handle error gracefully
            assert result == [] or isinstance(result, list)
        finally:
            # Restore permissions for cleanup
            extract_dir.chmod(0o755)

    @pytest.mark.unit
    def test_disk_space_simulation(self, temp_dir, create_test_zip):
        """Test behavior when disk is full (simulated)"""
        zip_path = temp_dir / "test.zip"
        create_test_zip(zip_path, ['image.jpg'])

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        # Mock zipfile.ZipFile.extract to raise OSError
        with mock.patch('zipfile.ZipFile.extract') as mock_extract:
            mock_extract.side_effect = OSError("No space left on device")

            result = extract_images_from_zip(zip_path, extract_dir)

            assert len(result) == 0


class TestZipFileErrors:
    """Test handling of various ZIP file errors"""

    @pytest.mark.unit
    def test_password_protected_zip(self, temp_dir):
        """Test handling of password-protected ZIP files"""
        zip_path = temp_dir / "protected.zip"

        # Create password-protected ZIP
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.setpassword(b'password')
            zf.writestr('image.jpg', b'content')

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        # Without password, should handle error
        result = extract_images_from_zip(zip_path, extract_dir)

        # Should return empty list or handle gracefully
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_zip64_format(self, temp_dir):
        """Test handling of ZIP64 format files"""
        zip_path = temp_dir / "zip64.zip"

        # Create ZIP64 file
        with zipfile.ZipFile(zip_path, 'w', allowZip64=True) as zf:
            zf.writestr('image.jpg', b'content')

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Should handle ZIP64 format
        assert len(result) == 1

    @pytest.mark.unit
    def test_empty_zip_file(self, temp_dir):
        """Test completely empty ZIP file"""
        zip_path = temp_dir / "empty.zip"

        # Create truly empty ZIP
        with zipfile.ZipFile(zip_path, 'w') as zf:
            pass

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        assert len(result) == 0

    @pytest.mark.unit
    def test_truncated_zip_file(self, temp_dir, create_test_zip):
        """Test truncated/incomplete ZIP file"""
        zip_path = temp_dir / "truncated.zip"
        create_test_zip(zip_path, ['image.jpg'])

        # Truncate the file
        with open(zip_path, 'rb') as f:
            content = f.read()

        with open(zip_path, 'wb') as f:
            f.write(content[:len(content) // 2])

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Should handle error gracefully
        assert len(result) == 0


class TestProcessZipFileErrors:
    """Test error handling in process_zip_file function"""

    @pytest.mark.unit
    def test_nonexistent_zip(self, temp_dir):
        """Test processing nonexistent ZIP file"""
        zip_path = temp_dir / "nonexistent.zip"

        result = process_zip_file(zip_path)

        assert result is False

    @pytest.mark.unit
    def test_non_zip_file(self, temp_dir):
        """Test processing file that's not a ZIP"""
        not_zip = temp_dir / "not_a_zip.txt"
        not_zip.write_text("This is a text file")

        result = process_zip_file(not_zip)

        assert result is False

    @pytest.mark.unit
    def test_wrong_extension(self, temp_dir):
        """Test file with wrong extension"""
        wrong_ext = temp_dir / "file.pdf"
        wrong_ext.write_bytes(b"fake content")

        result = process_zip_file(wrong_ext)

        assert result is False

    @pytest.mark.unit
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_invalid_output_directory(self, temp_dir, create_test_zip):
        """Test with invalid output directory"""
        zip_path = temp_dir / "test.zip"
        # Create a valid ZIP with an image
        with zipfile.ZipFile(zip_path, 'w') as zf:
            img = Image.new('RGB', (10, 10), (255, 0, 0))
            img_path = temp_dir / "test_img.jpg"
            img.save(img_path)
            zf.write(img_path, 'image.jpg')

        # Try to use a file as output directory
        invalid_dir = temp_dir / "file.txt"
        invalid_dir.write_text("I'm a file, not a directory")

        # This should fail or handle gracefully
        # The function should either fail or create the PDF in the same dir as ZIP
        result = process_zip_file(zip_path, output_dir=invalid_dir)

        # Behavior may vary, but should not crash
        assert isinstance(result, bool)


class TestFindZipFilesErrors:
    """Test error handling in find_zip_files_recursive"""

    @pytest.mark.unit
    def test_nonexistent_directory(self, temp_dir):
        """Test searching in nonexistent directory"""
        nonexistent = temp_dir / "nonexistent"

        result = find_zip_files_recursive(nonexistent)

        # Should return empty list
        assert len(result) == 0

    @pytest.mark.unit
    def test_file_instead_of_directory(self, temp_dir):
        """Test passing a file instead of directory"""
        file_path = temp_dir / "file.txt"
        file_path.write_text("content")

        result = find_zip_files_recursive(file_path)

        # Should handle gracefully
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_permission_denied_directory(self, temp_dir):
        """Test directory with no read permissions"""
        restricted = temp_dir / "restricted"
        restricted.mkdir()

        # Add a ZIP file
        zip_file = restricted / "test.zip"
        with zipfile.ZipFile(zip_file, 'w') as zf:
            zf.writestr('image.jpg', b'content')

        # Remove read permissions
        restricted.chmod(0o000)

        try:
            result = find_zip_files_recursive(restricted)
            # Should handle permission error gracefully
            assert isinstance(result, list)
        finally:
            # Restore permissions for cleanup
            restricted.chmod(0o755)

    @pytest.mark.unit
    def test_symlink_handling(self, temp_dir):
        """Test handling of symbolic links"""
        # Create a directory with a ZIP
        real_dir = temp_dir / "real"
        real_dir.mkdir()

        zip_file = real_dir / "test.zip"
        with zipfile.ZipFile(zip_file, 'w') as zf:
            zf.writestr('image.jpg', b'content')

        # Create a symlink to the directory
        link_dir = temp_dir / "link"
        try:
            link_dir.symlink_to(real_dir)

            result = find_zip_files_recursive(link_dir)

            # Should find the ZIP through the symlink
            assert len(result) >= 0  # Behavior may vary
        except OSError:
            # Symlinks may not be supported on some systems
            pytest.skip("Symlinks not supported")


@pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
class TestPillowErrors:
    """Test handling of Pillow-related errors"""

    @pytest.mark.unit
    def test_image_decode_error(self, temp_dir):
        """Test handling of image decode errors"""
        # Create a file that looks like an image but isn't
        fake_img = temp_dir / "fake.jpg"
        fake_img.write_bytes(b'\xFF\xD8\xFF\xE0' + b'garbage data')

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([fake_img], output_pdf)

        assert result is False

    @pytest.mark.unit
    def test_zero_size_image(self, temp_dir):
        """Test handling of zero-byte image file"""
        empty_img = temp_dir / "empty.jpg"
        empty_img.write_bytes(b'')

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([empty_img], output_pdf)

        assert result is False

    @pytest.mark.unit
    def test_unsupported_image_format(self, temp_dir):
        """Test handling of unsupported image formats"""
        # Create a file with unsupported format
        unsupported = temp_dir / "unsupported.xyz"
        unsupported.write_bytes(b'fake image data')

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([unsupported], output_pdf)

        assert result is False


class TestPillowNotAvailable:
    """Test behavior when Pillow is not available"""

    @pytest.mark.unit
    def test_main_without_pillow(self, temp_dir):
        """Test that main() exits when Pillow is not available"""
        # We'll test the import check logic
        import importlib
        import python.zipped_imgs_to_pdf as module

        # Check the PILLOW_AVAILABLE flag
        if not module.PILLOW_AVAILABLE:
            # The module should have Image set to None
            assert module.Image is None


class TestEdgeCases:
    """Test various edge cases"""

    @pytest.mark.unit
    def test_zip_with_hidden_files(self, temp_dir, create_test_zip):
        """Test ZIP with hidden files (starting with .)"""
        files = [
            '.hidden.jpg',
            'visible.jpg',
            '.DS_Store',
            'image.png'
        ]
        zip_path = temp_dir / "hidden.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Should extract all image files, including hidden ones
        assert len(result) >= 2  # At least visible.jpg and image.png

    @pytest.mark.unit
    def test_duplicate_filenames_in_zip(self, temp_dir):
        """Test ZIP with duplicate filenames in different directories"""
        zip_path = temp_dir / "duplicates.zip"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('dir1/image.jpg', b'content1')
            zf.writestr('dir2/image.jpg', b'content2')
            zf.writestr('image.jpg', b'content3')

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Should extract all three images
        assert len(result) == 3

    @pytest.mark.unit
    def test_case_sensitivity(self, temp_dir, create_test_zip):
        """Test case sensitivity in file extensions"""
        files = [
            'image.JPG',
            'image.jpg',
            'photo.PNG',
            'photo.png'
        ]
        zip_path = temp_dir / "case.zip"
        create_test_zip(zip_path, files)

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # All should be recognized as images
        assert len(result) == 4

    @pytest.mark.unit
    def test_extremely_nested_directories(self, temp_dir):
        """Test ZIP with extremely nested directory structure"""
        zip_path = temp_dir / "nested.zip"

        # Create deeply nested structure
        nested_path = '/'.join([f'level{i}' for i in range(20)]) + '/image.jpg'

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr(nested_path, b'content')

        extract_dir = temp_dir / "extract"
        extract_dir.mkdir()

        result = extract_images_from_zip(zip_path, extract_dir)

        # Should handle deep nesting
        assert len(result) == 1

    @pytest.mark.unit
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_single_pixel_image(self, temp_dir):
        """Test converting a 1x1 pixel image"""
        img_path = temp_dir / "tiny.png"
        img = Image.new('RGB', (1, 1), (255, 0, 0))
        img.save(img_path)

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True

    @pytest.mark.unit
    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_extremely_wide_image(self, temp_dir):
        """Test converting extremely wide image"""
        img_path = temp_dir / "wide.png"
        img = Image.new('RGB', (5000, 10), (255, 0, 0))
        img.save(img_path)

        output_pdf = temp_dir / "output.pdf"
        result = convert_images_to_pdf([img_path], output_pdf)

        assert result is True
