#!/usr/bin/env python3
"""
Zipped Images to PDF Converter
Converts ZIP files containing images into PDF files.
"""

__version__ = "2.0.0"

import argparse
import sys
import zipfile
from pathlib import Path
from typing import List, Optional
import tempfile
import shutil

# Add parent directory to path to import shared module
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import (  # noqa: E402
    is_image_file,
    sort_images,
    DEFAULT_PRIORITY_CHARS,
    MAX_FILE_SIZE_BYTES,
    MAX_EXTRACTED_SIZE_BYTES,
    MAX_FILES_IN_ZIP
)

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None


def extract_images_from_zip(
    zip_path: Path,
    temp_dir: Path,
    use_natural_sort: bool = True,
    priority_chars: str = DEFAULT_PRIORITY_CHARS
) -> List[Path]:
    """
    Extract all image files from a ZIP archive with security checks.

    Args:
        zip_path: Path to the ZIP file
        temp_dir: Temporary directory to extract files to
        use_natural_sort: Whether to use natural sorting (default: True)
        priority_chars: Characters that trigger priority sorting (default: '!')

    Returns:
        List of paths to extracted image files

    Raises:
        ValueError: If ZIP file exceeds security limits
        zipfile.BadZipFile: If ZIP file is invalid
    """
    image_files = []
    total_extracted_size = 0

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # First pass: validate and count image files
            image_file_infos = []
            for file_info in zip_ref.filelist:
                if file_info.is_dir():
                    continue

                # Security: Check for path traversal
                if '..' in file_info.filename or \
                   file_info.filename.startswith('/'):
                    print(f"Warning: Skipping suspicious path: "
                          f"{file_info.filename}")
                    continue

                if is_image_file(file_info.filename):
                    # Security: Check extracted size (ZIP bomb protection)
                    total_extracted_size += file_info.file_size
                    if total_extracted_size > MAX_EXTRACTED_SIZE_BYTES:
                        raise ValueError(
                            f"ZIP file exceeds maximum extraction size "
                            f"({MAX_EXTRACTED_SIZE_BYTES / (1024*1024):.0f}MB). "
                            f"Possible ZIP bomb attack."
                        )
                    image_file_infos.append(file_info)

            total_images = len(image_file_infos)

            # Security: Check file count
            if total_images > MAX_FILES_IN_ZIP:
                raise ValueError(
                    f"ZIP file contains too many files ({total_images} > {MAX_FILES_IN_ZIP})"
                )

            if total_images == 0:
                print(f"Warning: No image files found in {zip_path.name}")
                return []

            # Second pass: extract with progress
            for idx, file_info in enumerate(image_file_infos, 1):
                # Extract the file
                filename = Path(file_info.filename).name
                print(f"  Extracting image {idx}/{total_images}: {filename}")
                zip_ref.extract(file_info, temp_dir)
                extracted_path = temp_dir / file_info.filename
                image_files.append(str(extracted_path))

        # Sort images with priority handling
        sorted_images = sort_images(image_files, use_natural_sort, priority_chars)
        return [Path(img) for img in sorted_images]

    except zipfile.BadZipFile:
        print(f"Error: {zip_path.name} is not a valid ZIP file")
        return []
    except ValueError as e:
        print(f"Security error: {e}")
        return []
    except Exception as e:
        print(f"Error extracting {zip_path.name}: {e}")
        return []


def convert_images_to_pdf(image_paths: List[Path], output_pdf: Path) -> bool:
    """
    Convert a list of images to a single PDF file.

    Args:
        image_paths: List of paths to image files
        output_pdf: Path for the output PDF file

    Returns:
        True if successful, False otherwise
    """
    if not image_paths:
        return False

    try:
        total_images = len(image_paths)
        print(f"Converting {total_images} image(s) to PDF...")

        # Open all images and convert to RGB if necessary
        images = []
        white_background = (255, 255, 255)

        for idx, img_path in enumerate(image_paths, 1):
            try:
                print(f"  Converting image {idx}/{total_images}: "
                      f"{img_path.name}")
                img = Image.open(img_path)
                # Convert to RGB if image is in RGBA or other modes
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create a white background
                    rgb_img = Image.new('RGB', img.size, white_background)
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    has_alpha = img.mode in ('RGBA', 'LA')
                    mask = img.split()[-1] if has_alpha else None
                    rgb_img.paste(img, mask=mask)
                    images.append(rgb_img)
                elif img.mode != 'RGB':
                    images.append(img.convert('RGB'))
                else:
                    images.append(img)
            except (IOError, OSError) as e:
                print(f"  Warning: Could not process image "
                      f"{img_path.name}: {e}")
                continue

        if not images:
            print("Error: No valid images to convert")
            return False

        # Save as PDF
        print(f"  Saving PDF with {len(images)} page(s)...")
        first_image = images[0]
        remaining_images = images[1:] if len(images) > 1 else []

        first_image.save(
            str(output_pdf),
            'PDF',
            save_all=True,
            append_images=remaining_images,
            resolution=100.0
        )

        print(f"Successfully created: {output_pdf.name}")
        print(f"  - Pages: {len(images)}")
        return True

    except Exception as e:
        print(f"Error creating PDF: {e}")
        return False


def process_zip_file(
    zip_path: Path,
    output_dir: Optional[Path] = None,
    use_natural_sort: bool = True,
    priority_chars: str = DEFAULT_PRIORITY_CHARS
) -> bool:
    """
    Process a single ZIP file and convert it to PDF.

    Args:
        zip_path: Path to the ZIP file
        output_dir: Directory to save the PDF (defaults to same directory as ZIP)
        use_natural_sort: Whether to use natural sorting (default: True)
        priority_chars: Characters that trigger priority sorting (default: '!')

    Returns:
        True if successful, False otherwise
    """
    if not zip_path.exists():
        print(f"Error: File not found: {zip_path}")
        return False

    if not zip_path.suffix.lower() == '.zip':
        print(f"Error: Not a ZIP file: {zip_path}")
        return False

    # Security: Check file size
    file_size = zip_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        max_size_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        current_size_mb = file_size / (1024 * 1024)
        print(
            f"Error: File too large: {zip_path.name} "
            f"({current_size_mb:.1f}MB > {max_size_mb:.0f}MB)"
        )
        return False

    # Determine output directory and filename
    if output_dir is None:
        output_dir = zip_path.parent

    output_pdf = output_dir / f"{zip_path.stem}.pdf"

    # Create temporary directory for extraction
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Extract images
        image_paths = extract_images_from_zip(zip_path, temp_dir, use_natural_sort, priority_chars)

        if not image_paths:
            return False

        print(f"Found {len(image_paths)} image(s) in archive")
        print()

        # Convert to PDF
        success = convert_images_to_pdf(image_paths, output_pdf)

        return success

    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Warning: Could not remove temporary directory: {e}")


def find_zip_files_recursive(directory: Path) -> List[Path]:
    """
    Recursively find all ZIP files in a directory and its subdirectories.

    Args:
        directory: Path to the directory to search

    Returns:
        List of paths to ZIP files found
    """
    zip_files = []

    try:
        # Use glob to recursively find all .zip files
        for zip_path in directory.rglob('*.zip'):
            if zip_path.is_file():
                zip_files.append(zip_path)

        # Also check for .ZIP (uppercase)
        for zip_path in directory.rglob('*.ZIP'):
            if zip_path.is_file() and zip_path not in zip_files:
                zip_files.append(zip_path)

    except Exception as e:
        print(f"Error searching directory {directory}: {e}")

    return sorted(zip_files)


def main():
    """Main function to handle command-line arguments and process files."""
    # Check if Pillow is available
    if not PILLOW_AVAILABLE:
        print("Error: Pillow library is required. Install it with: pip install Pillow")
        sys.exit(1)
        return

    parser = argparse.ArgumentParser(
        description='Convert ZIP files containing images to PDF files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s images1.zip
  %(prog)s images1.zip images2.zip images3.zip
  %(prog)s *.zip
  %(prog)s images1.zip -o /path/to/output/
  %(prog)s images1.zip --no-natural-sort
  %(prog)s images1.zip --priority-chars "!@"
  %(prog)s /path/to/archives/ -r
  %(prog)s /path/to/archives/ --recursive -o /path/to/output/
        """
    )

    parser.add_argument(
        'zip_files',
        nargs='+',
        type=str,
        help='ZIP file(s) or directory to convert'
    )

    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output directory for PDF files (default: same as input file)'
    )

    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Recursively process all ZIP files in specified directories'
    )

    parser.add_argument(
        '--natural-sort',
        dest='natural_sort',
        action='store_true',
        default=True,
        help='Use natural sorting for numbers in filenames (default: enabled)'
    )

    parser.add_argument(
        '--no-natural-sort',
        dest='natural_sort',
        action='store_false',
        help='Disable natural sorting (use standard lexical sorting)'
    )

    parser.add_argument(
        '--priority-chars',
        type=str,
        default=DEFAULT_PRIORITY_CHARS,
        help=(
            'Characters that mark images for priority placement '
            'at the beginning (default: "!")'
        )
    )

    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s version {__version__}'
    )

    args = parser.parse_args()

    # Determine output directory
    output_dir = None
    if args.output:
        output_dir = Path(args.output)
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error creating output directory: {e}")
                sys.exit(1)
                return

    # Print configuration
    print("Configuration:")
    enabled_str = 'enabled' if args.natural_sort else 'disabled'
    print(f"  Natural sorting: {enabled_str}")
    if args.priority_chars:
        print(f"  Priority characters: '{args.priority_chars}'")
    else:
        print("  Priority characters: none")
    recursive_str = 'enabled' if args.recursive else 'disabled'
    print(f"  Recursive mode: {recursive_str}")
    print()

    # Collect all ZIP files to process
    zip_files_to_process = []

    for path_str in args.zip_files:
        path = Path(path_str)

        if path.is_dir():
            if args.recursive:
                # Recursively find all ZIP files in the directory
                found_zips = find_zip_files_recursive(path)
                if found_zips:
                    print(f"Found {len(found_zips)} ZIP file(s) in {path}")
                    zip_files_to_process.extend(found_zips)
                else:
                    print(f"Warning: No ZIP files found in {path}")
            else:
                print(f"Warning: {path} is a directory. Use --recursive to process directories.")
        elif path.is_file():
            zip_files_to_process.append(path)
        else:
            print(f"Warning: {path} not found")

    if not zip_files_to_process:
        print("Error: No ZIP files to process")
        sys.exit(1)
        return

    print(f"\nProcessing {len(zip_files_to_process)} ZIP file(s)...\n")

    # Process each ZIP file
    success_count = 0
    failure_count = 0
    total_files = len(zip_files_to_process)

    for idx, zip_path in enumerate(zip_files_to_process, 1):
        print(f"[{idx}/{total_files}] Processing: {zip_path.name}")
        print("-" * 60)
        if process_zip_file(zip_path, output_dir, args.natural_sort, args.priority_chars):
            success_count += 1
        else:
            failure_count += 1

        print()  # Empty line between files

    # Print summary
    print("=" * 50)
    print(f"Summary: {success_count} successful, {failure_count} failed")

    sys.exit(0 if failure_count == 0 else 1)


if __name__ == '__main__':
    main()
