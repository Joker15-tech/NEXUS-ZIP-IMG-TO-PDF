#!/usr/bin/env python3
"""
Tests for CLI argument parsing and main() function
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

from python.zipped_imgs_to_pdf import main, find_zip_files_recursive


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def create_test_zip_with_image():
    """Create a test ZIP with a real image"""
    def _create(zip_path):
        if not PILLOW_AVAILABLE:
            pytest.skip("Pillow not available")

        with zipfile.ZipFile(zip_path, 'w') as zf:
            img = Image.new('RGB', (100, 100), (255, 0, 0))
            img_bytes = io.BytesIO()
            img.save(img_bytes, 'JPEG')
            zf.writestr('image.jpg', img_bytes.getvalue())

        return zip_path

    return _create


class TestCLIBasicArguments:
    """Test basic CLI argument parsing"""

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_single_file_argument(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test processing single ZIP file"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        # Verify PDF created
        pdf_path = temp_dir / "test.pdf"
        assert pdf_path.exists()

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_multiple_file_arguments(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test processing multiple ZIP files"""
        zip1 = temp_dir / "file1.zip"
        zip2 = temp_dir / "file2.zip"
        zip3 = temp_dir / "file3.zip"

        create_test_zip_with_image(zip1)
        create_test_zip_with_image(zip2)
        create_test_zip_with_image(zip3)

        test_args = ['zipped_imgs_to_pdf.py', str(zip1), str(zip2), str(zip3)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        # Verify all PDFs created
        assert (temp_dir / "file1.pdf").exists()
        assert (temp_dir / "file2.pdf").exists()
        assert (temp_dir / "file3.pdf").exists()

    def test_no_arguments(self, monkeypatch):
        """Test that no arguments shows error"""
        test_args = ['zipped_imgs_to_pdf.py']
        monkeypatch.setattr(sys, 'argv', test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        # Should exit with error code
        assert exc_info.value.code != 0

    def test_help_argument(self, monkeypatch):
        """Test --help shows help message"""
        test_args = ['zipped_imgs_to_pdf.py', '--help']
        monkeypatch.setattr(sys, 'argv', test_args)

        with pytest.raises(SystemExit) as exc_info:
            main()

        # --help exits with 0
        assert exc_info.value.code == 0


class TestOutputDirectoryOption:
    """Test -o/--output option"""

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_short_output_option(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test -o option"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        output_dir = temp_dir / "output"

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '-o', str(output_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        # PDF should be in output directory
        assert (output_dir / "test.pdf").exists()

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_long_output_option(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test --output option"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        output_dir = temp_dir / "pdfs"

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '--output', str(output_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        assert (output_dir / "test.pdf").exists()

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_output_directory_created(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test that non-existent output directory is created"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        output_dir = temp_dir / "new" / "nested" / "dir"

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '-o', str(output_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        assert output_dir.exists()
        assert (output_dir / "test.pdf").exists()


class TestNaturalSortOptions:
    """Test --natural-sort and --no-natural-sort options"""

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_natural_sort_enabled_by_default(self, temp_dir, monkeypatch):
        """Test that natural sort is enabled by default"""
        # Create ZIP with numbered images
        zip_path = temp_dir / "test.zip"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            for i in [1, 2, 10, 20]:
                img = Image.new('RGB', (50, 50), (255, 0, 0))
                img_bytes = io.BytesIO()
                img.save(img_bytes, 'JPEG')
                zf.writestr(f'img_{i}.jpg', img_bytes.getvalue())

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_natural_sort_explicit(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test --natural-sort option"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '--natural-sort']
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_no_natural_sort(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test --no-natural-sort option"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '--no-natural-sort']
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)


class TestPriorityCharsOption:
    """Test --priority-chars option"""

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_default_priority_chars(self, temp_dir, monkeypatch):
        """Test default priority character (!)"""
        zip_path = temp_dir / "test.zip"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            for name in ['page1.jpg', '!cover.jpg', 'page2.jpg']:
                img = Image.new('RGB', (50, 50), (255, 0, 0))
                img_bytes = io.BytesIO()
                img.save(img_bytes, 'JPEG')
                zf.writestr(name, img_bytes.getvalue())

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_custom_priority_chars(self, temp_dir, monkeypatch):
        """Test custom priority characters"""
        zip_path = temp_dir / "test.zip"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            for name in ['page1.jpg', '@special.jpg', 'page2.jpg']:
                img = Image.new('RGB', (50, 50), (255, 0, 0))
                img_bytes = io.BytesIO()
                img.save(img_bytes, 'JPEG')
                zf.writestr(name, img_bytes.getvalue())

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '--priority-chars', '@']
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_multiple_priority_chars(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test multiple priority characters"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '--priority-chars', '!@#']
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_empty_priority_chars(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test empty priority characters"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path), '--priority-chars', '']
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)


class TestRecursiveOption:
    """Test -r/--recursive option"""

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_recursive_short_option(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test -r option"""
        # Create directory structure
        subdir1 = temp_dir / "dir1"
        subdir2 = temp_dir / "dir2"
        subdir1.mkdir()
        subdir2.mkdir()

        create_test_zip_with_image(subdir1 / "file1.zip")
        create_test_zip_with_image(subdir2 / "file2.zip")

        test_args = ['zipped_imgs_to_pdf.py', str(temp_dir), '-r']
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        # Verify PDFs created
        assert (subdir1 / "file1.pdf").exists()
        assert (subdir2 / "file2.pdf").exists()

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_recursive_long_option(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test --recursive option"""
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        create_test_zip_with_image(subdir / "test.zip")

        test_args = ['zipped_imgs_to_pdf.py', str(temp_dir), '--recursive']
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        assert (subdir / "test.pdf").exists()

    def test_directory_without_recursive_warns(self, temp_dir, monkeypatch, capsys):
        """Test that directory without -r flag shows warning"""
        test_args = ['zipped_imgs_to_pdf.py', str(temp_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(1)

        captured = capsys.readouterr()
        assert "recursive" in captured.out.lower() or "directory" in captured.out.lower()

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_recursive_with_output_directory(self, temp_dir, create_test_zip_with_image, monkeypatch):
        """Test -r with -o option"""
        subdir = temp_dir / "input"
        subdir.mkdir()

        create_test_zip_with_image(subdir / "test.zip")

        output_dir = temp_dir / "output"

        test_args = ['zipped_imgs_to_pdf.py', str(subdir), '-r', '-o', str(output_dir)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        # PDF should be in output directory
        assert (output_dir / "test.pdf").exists()


class TestCombinedOptions:
    """Test combinations of options"""

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_all_options_combined(self, temp_dir, monkeypatch):
        """Test using all options together"""
        # Create test ZIP
        zip_path = temp_dir / "test.zip"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            for name in ['img_10.jpg', '@special.jpg', 'img_1.jpg']:
                img = Image.new('RGB', (50, 50), (255, 0, 0))
                img_bytes = io.BytesIO()
                img.save(img_bytes, 'JPEG')
                zf.writestr(name, img_bytes.getvalue())

        output_dir = temp_dir / "output"

        test_args = [
            'zipped_imgs_to_pdf.py',
            str(zip_path),
            '--no-natural-sort',
            '--priority-chars', '@',
            '-o', str(output_dir)
        ]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(0)

        assert (output_dir / "test.pdf").exists()


class TestErrorConditions:
    """Test error handling in CLI"""

    def test_nonexistent_file(self, temp_dir, monkeypatch):
        """Test nonexistent ZIP file"""
        test_args = ['zipped_imgs_to_pdf.py', str(temp_dir / "nonexistent.zip")]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(1)

    def test_invalid_zip_file(self, temp_dir, monkeypatch):
        """Test invalid ZIP file"""
        not_zip = temp_dir / "not_a_zip.zip"
        not_zip.write_text("This is not a ZIP file")

        test_args = ['zipped_imgs_to_pdf.py', str(not_zip)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(1)

    def test_zip_with_no_images(self, temp_dir, monkeypatch):
        """Test ZIP file with no images"""
        zip_path = temp_dir / "no_images.zip"

        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('document.pdf', b'fake pdf')
            zf.writestr('text.txt', b'text content')

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit') as mock_exit:
            main()
            mock_exit.assert_called_once_with(1)

    @pytest.mark.skipif(PILLOW_AVAILABLE, reason="Test requires Pillow to be unavailable")
    def test_pillow_not_available(self, temp_dir, monkeypatch):
        """Test behavior when Pillow is not available"""
        # This test would need to mock the import
        # In real scenario, if Pillow is not available, main() should exit with error
        test_args = ['zipped_imgs_to_pdf.py', 'test.zip']
        monkeypatch.setattr(sys, 'argv', test_args)

        # The actual test depends on how the module handles missing Pillow
        # Usually it should exit with error message
        pass


class TestConfigurationOutput:
    """Test that configuration is printed correctly"""

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_configuration_printed(self, temp_dir, create_test_zip_with_image, monkeypatch, capsys):
        """Test that configuration is printed"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit'):
            main()

        captured = capsys.readouterr()
        assert "Configuration" in captured.out
        assert "Natural sorting" in captured.out
        assert "Priority characters" in captured.out

    @pytest.mark.skipif(not PILLOW_AVAILABLE, reason="Pillow not available")
    def test_summary_printed(self, temp_dir, create_test_zip_with_image, monkeypatch, capsys):
        """Test that summary is printed at the end"""
        zip_path = temp_dir / "test.zip"
        create_test_zip_with_image(zip_path)

        test_args = ['zipped_imgs_to_pdf.py', str(zip_path)]
        monkeypatch.setattr(sys, 'argv', test_args)

        with mock.patch('sys.exit'):
            main()

        captured = capsys.readouterr()
        assert "Summary" in captured.out
        assert "successful" in captured.out.lower()
