# Python CLI

A Python command-line tool for converting images in ZIP files to PDF.

## Files

- `zipped_imgs_to_pdf.py` - Main script
- `requirements.txt` - Python dependencies

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install directly:

```bash
pip install Pillow>=10.0.0
```

### 2. Shared Module Dependencies

This script uses shared modules from the `../shared/` directory. It must be run within the cloned repository.

## Usage

### Basic Usage

```bash
python zipped_imgs_to_pdf.py image.zip
```

### Processing Multiple Files

```bash
python zipped_imgs_to_pdf.py file1.zip file2.zip file3.zip
```

### Using Wildcards

```bash
python zipped_imgs_to_pdf.py *.zip
```

### Specifying Output Directory

```bash
python zipped_imgs_to_pdf.py image.zip -o /path/to/output/
```

### Sorting Options

Disable natural sorting:
```bash
python zipped_imgs_to_pdf.py image.zip --no-natural-sort
```

Change priority characters:
```bash
python zipped_imgs_to_pdf.py image.zip --priority-chars "!@#"
```

### Help

```bash
python zipped_imgs_to_pdf.py --help
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `zip_files` | ZIP files to convert (required) | - |
| `-o`, `--output` | Output directory | Same as input file |
| `--natural-sort` | Enable natural sorting | Enabled |
| `--no-natural-sort` | Disable natural sorting | - |
| `--priority-chars` | Set priority characters | `!` |

## Examples

### Example 1: Basic Conversion

```bash
$ python zipped_imgs_to_pdf.py manga_vol1.zip

Configuration:
  Natural sorting: enabled
  Priority characters: '!'

Processing: manga_vol1.zip
Found 42 image(s)
Successfully created: manga_vol1.pdf
  - Pages: 42

==================================================
Summary: 1 successful, 0 failed
```

### Example 2: Batch Processing

```bash
$ python zipped_imgs_to_pdf.py *.zip -o ~/PDFs/

Configuration:
  Natural sorting: enabled
  Priority characters: '!'

Processing: vol1.zip
Found 25 image(s)
Successfully created: vol1.pdf
  - Pages: 25

Processing: vol2.zip
Found 30 image(s)
Successfully created: vol2.pdf
  - Pages: 30

==================================================
Summary: 2 successful, 0 failed
```

### Example 3: Custom Settings

```bash
$ python zipped_imgs_to_pdf.py zipped-images.zip --no-natural-sort --priority-chars "@!"

Configuration:
  Natural sorting: disabled
  Priority characters: '@!'

Processing: zipped-images.zip
Found 20 image(s)
Successfully created: zipped-images.pdf
  - Pages: 20

==================================================
Summary: 1 successful, 0 failed
```

## How It Works

1. **ZIP Extraction**: Extract only image files from ZIP to temporary directory
2. **Sorting**: Use sorting algorithm from shared module
   - Separate files starting with priority characters
   - Apply natural sorting (optional)
3. **PDF Conversion**: Convert images to PDF using Pillow
   - RGBA images are converted to RGB by compositing with white background
   - Each image becomes one page in the PDF
4. **Cleanup**: Delete temporary directory

## Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)
- TIFF (.tiff)
- WebP (.webp)

## Build (Creating Executable)

You can create a standalone executable using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile \
    --name zipped-imgs-to-pdf \
    --add-data "../shared:shared" \
    zipped_imgs_to_pdf.py
```

The generated executable will be located in the `dist/` directory.

## Troubleshooting

### ImportError: No module named 'PIL'

```bash
pip install Pillow
```

### ModuleNotFoundError: No module named 'shared'

Run the script from the project root or `python/` directory:

```bash
# From project root
python python/zipped_imgs_to_pdf.py image.zip

# From python directory
cd python
python zipped_imgs_to_pdf.py image.zip
```

### Permission Error (Linux/macOS)

Add execute permission to the script:

```bash
chmod +x zipped_imgs_to_pdf.py
./zipped_imgs_to_pdf.py image.zip
```

## Development

### Code Structure

```python
# Import shared modules
from shared import is_image_file, sort_images, DEFAULT_PRIORITY_CHARS

# Main functions
- extract_images_from_zip()  # Extract images from ZIP
- convert_images_to_pdf()    # Convert images to PDF
- process_zip_file()          # Orchestrate entire process
- main()                      # CLI interface
```

### Testing

```bash
python ../tests/test_natural_sort.py
```

## License

MIT License - See LICENSE file in parent directory
