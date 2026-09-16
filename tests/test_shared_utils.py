#!/usr/bin/env python3
"""
Tests for shared utility functions
Tests is_image_file, constants, and other shared utilities
"""

import sys
from pathlib import Path

import pytest

# Add parent directory to path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import (
    is_image_file,
    IMAGE_EXTENSIONS,
    DEFAULT_PRIORITY_CHARS
)


class TestConstants:
    """Test shared constants"""

    def test_image_extensions_defined(self):
        """Test that IMAGE_EXTENSIONS is properly defined"""
        assert IMAGE_EXTENSIONS is not None
        assert isinstance(IMAGE_EXTENSIONS, set)
        assert len(IMAGE_EXTENSIONS) > 0

    def test_image_extensions_content(self):
        """Test that IMAGE_EXTENSIONS contains expected formats"""
        expected_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        assert IMAGE_EXTENSIONS == expected_formats

    def test_default_priority_chars(self):
        """Test DEFAULT_PRIORITY_CHARS constant"""
        assert DEFAULT_PRIORITY_CHARS == '!'
        assert isinstance(DEFAULT_PRIORITY_CHARS, str)
        assert len(DEFAULT_PRIORITY_CHARS) == 1


class TestIsImageFile:
    """Test is_image_file function"""

    def test_jpg_files(self):
        """Test .jpg file detection"""
        assert is_image_file('photo.jpg') is True
        assert is_image_file('image.JPG') is True
        assert is_image_file('/path/to/photo.jpg') is True

    def test_jpeg_files(self):
        """Test .jpeg file detection"""
        assert is_image_file('photo.jpeg') is True
        assert is_image_file('image.JPEG') is True

    def test_png_files(self):
        """Test .png file detection"""
        assert is_image_file('screenshot.png') is True
        assert is_image_file('image.PNG') is True

    def test_gif_files(self):
        """Test .gif file detection"""
        assert is_image_file('animation.gif') is True
        assert is_image_file('image.GIF') is True

    def test_bmp_files(self):
        """Test .bmp file detection"""
        assert is_image_file('bitmap.bmp') is True
        assert is_image_file('image.BMP') is True

    def test_tiff_files(self):
        """Test .tiff file detection"""
        assert is_image_file('scan.tiff') is True
        assert is_image_file('image.TIFF') is True

    def test_webp_files(self):
        """Test .webp file detection"""
        assert is_image_file('modern.webp') is True
        assert is_image_file('image.WEBP') is True

    def test_non_image_files(self):
        """Test that non-image files are rejected"""
        assert is_image_file('document.pdf') is False
        assert is_image_file('text.txt') is False
        assert is_image_file('data.json') is False
        assert is_image_file('script.py') is False
        assert is_image_file('archive.zip') is False
        assert is_image_file('video.mp4') is False
        assert is_image_file('audio.mp3') is False

    def test_case_insensitivity(self):
        """Test that extension matching is case-insensitive"""
        assert is_image_file('Photo.JpG') is True
        assert is_image_file('IMAGE.PnG') is True
        assert is_image_file('SCAN.TiFf') is True

    def test_files_with_multiple_dots(self):
        """Test files with multiple dots in name"""
        assert is_image_file('file.name.with.dots.jpg') is True
        assert is_image_file('file.name.with.dots.pdf') is False
        assert is_image_file('archive.tar.gz') is False

    def test_files_without_extension(self):
        """Test files without extensions"""
        assert is_image_file('noextension') is False
        assert is_image_file('README') is False

    def test_hidden_files(self):
        """Test hidden files (starting with .)"""
        assert is_image_file('.hidden.jpg') is True
        assert is_image_file('.DS_Store') is False

    def test_paths_with_directories(self):
        """Test full paths with directories"""
        assert is_image_file('/home/user/photos/IMG_001.jpg') is True
        assert is_image_file('C:\\Users\\Photos\\image.png') is True
        assert is_image_file('relative/path/to/photo.gif') is True
        assert is_image_file('/path/to/document.pdf') is False

    def test_filenames_with_spaces(self):
        """Test filenames with spaces"""
        assert is_image_file('my photo.jpg') is True
        assert is_image_file('photo album.png') is True
        assert is_image_file('my document.pdf') is False

    def test_unicode_filenames(self):
        """Test Unicode characters in filenames"""
        assert is_image_file('图片.jpg') is True  # Chinese
        assert is_image_file('صورة.png') is True  # Arabic
        assert is_image_file('фото.gif') is True  # Cyrillic

    def test_special_characters_in_filename(self):
        """Test special characters"""
        assert is_image_file('photo (1).jpg') is True
        assert is_image_file('image [copy].png') is True
        assert is_image_file('file-name_123.gif') is True
        assert is_image_file('image@2x.jpg') is True
        assert is_image_file('photo#1.png') is True

    def test_empty_string(self):
        """Test empty string"""
        assert is_image_file('') is False

    def test_only_extension(self):
        """Test filenames that are only extension"""
        assert is_image_file('.jpg') is True
        assert is_image_file('.png') is True

    def test_trailing_dots(self):
        """Test filenames with trailing dots"""
        assert is_image_file('photo.jpg.') is False
        assert is_image_file('photo.') is False

    def test_numeric_filenames(self):
        """Test numeric filenames"""
        assert is_image_file('123.jpg') is True
        assert is_image_file('001.png') is True
        assert is_image_file('0.gif') is True

    def test_very_long_filenames(self):
        """Test very long filenames"""
        long_name = 'a' * 200 + '.jpg'
        assert is_image_file(long_name) is True

        long_name_no_ext = 'a' * 255
        assert is_image_file(long_name_no_ext) is False

    def test_priority_marked_files(self):
        """Test files with priority markers"""
        assert is_image_file('!cover.jpg') is True
        assert is_image_file('@special.png') is True
        assert is_image_file('#important.gif') is True

    def test_common_non_image_extensions(self):
        """Test common non-image file extensions"""
        non_images = [
            'file.txt', 'doc.docx', 'sheet.xlsx', 'slide.pptx',
            'archive.zip', 'archive.rar', 'archive.7z',
            'video.mp4', 'video.avi', 'video.mkv',
            'audio.mp3', 'audio.wav', 'audio.flac',
            'code.py', 'code.js', 'code.cpp',
            'data.json', 'data.xml', 'data.csv'
        ]

        for filename in non_images:
            assert is_image_file(filename) is False, f"{filename} should not be detected as image"

    def test_pathlib_path_objects(self):
        """Test that Path objects work correctly"""
        from pathlib import Path

        assert is_image_file(Path('photo.jpg')) is True
        assert is_image_file(Path('/path/to/image.png')) is True
        assert is_image_file(Path('document.pdf')) is False

    def test_windows_paths(self):
        """Test Windows-style paths"""
        assert is_image_file('C:\\Photos\\IMG_001.jpg') is True
        assert is_image_file('D:\\Images\\photo.png') is True
        assert is_image_file('\\\\network\\share\\image.gif') is True

    def test_unix_paths(self):
        """Test Unix-style paths"""
        assert is_image_file('/home/user/photos/img.jpg') is True
        assert is_image_file('/var/www/images/banner.png') is True
        assert is_image_file('~/Pictures/photo.gif') is True

    def test_relative_paths(self):
        """Test relative paths"""
        assert is_image_file('./photo.jpg') is True
        assert is_image_file('../images/photo.png') is True
        assert is_image_file('../../gallery/img.gif') is True

    def test_url_like_paths(self):
        """Test URL-like paths (should still work based on extension)"""
        assert is_image_file('http://example.com/photo.jpg') is True
        assert is_image_file('https://example.com/image.png') is True
        assert is_image_file('file:///path/to/image.gif') is True


class TestImageExtensionsSet:
    """Test IMAGE_EXTENSIONS set properties"""

    def test_is_set_type(self):
        """Test that IMAGE_EXTENSIONS is a set"""
        assert isinstance(IMAGE_EXTENSIONS, set)

    def test_contains_lowercase_only(self):
        """Test that all extensions are lowercase"""
        for ext in IMAGE_EXTENSIONS:
            assert ext == ext.lower(), f"{ext} should be lowercase"

    def test_all_start_with_dot(self):
        """Test that all extensions start with a dot"""
        for ext in IMAGE_EXTENSIONS:
            assert ext.startswith('.'), f"{ext} should start with dot"

    def test_no_empty_strings(self):
        """Test that no empty strings in set"""
        assert '' not in IMAGE_EXTENSIONS

    def test_no_duplicates(self):
        """Test that there are no duplicates (sets don't allow duplicates anyway)"""
        extensions_list = list(IMAGE_EXTENSIONS)
        assert len(extensions_list) == len(set(extensions_list))

    def test_common_formats_included(self):
        """Test that common image formats are included"""
        common_formats = ['.jpg', '.jpeg', '.png', '.gif']
        for fmt in common_formats:
            assert fmt in IMAGE_EXTENSIONS, f"{fmt} should be in IMAGE_EXTENSIONS"

    def test_modern_formats_included(self):
        """Test that modern formats are included"""
        assert '.webp' in IMAGE_EXTENSIONS

    def test_traditional_formats_included(self):
        """Test that traditional formats are included"""
        assert '.bmp' in IMAGE_EXTENSIONS
        assert '.tiff' in IMAGE_EXTENSIONS


class TestPriorityCharsConstant:
    """Test DEFAULT_PRIORITY_CHARS constant"""

    def test_is_string(self):
        """Test that it's a string"""
        assert isinstance(DEFAULT_PRIORITY_CHARS, str)

    def test_not_empty(self):
        """Test that it's not empty"""
        assert len(DEFAULT_PRIORITY_CHARS) > 0

    def test_default_value(self):
        """Test the default value"""
        assert DEFAULT_PRIORITY_CHARS == '!'

    def test_single_character(self):
        """Test that it's a single character (by default)"""
        assert len(DEFAULT_PRIORITY_CHARS) == 1


class TestModuleExports:
    """Test that the shared module exports all necessary items"""

    def test_exports_is_image_file(self):
        """Test that is_image_file is exported"""
        from shared import is_image_file
        assert callable(is_image_file)

    def test_exports_image_extensions(self):
        """Test that IMAGE_EXTENSIONS is exported"""
        from shared import IMAGE_EXTENSIONS
        assert IMAGE_EXTENSIONS is not None

    def test_exports_default_priority_chars(self):
        """Test that DEFAULT_PRIORITY_CHARS is exported"""
        from shared import DEFAULT_PRIORITY_CHARS
        assert DEFAULT_PRIORITY_CHARS is not None

    def test_exports_natural_sort_key(self):
        """Test that natural_sort_key is exported"""
        from shared import natural_sort_key
        assert callable(natural_sort_key)

    def test_exports_sort_images(self):
        """Test that sort_images is exported"""
        from shared import sort_images
        assert callable(sort_images)
