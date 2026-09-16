# Zipped Images to PDF Converter

[![Build Status](https://github.com/9bow/zipped-imgs-to-pdf/actions/workflows/build.yml/badge.svg)](https://github.com/9bow/zipped-imgs-to-pdf/actions/workflows/build.yml)
[![codecov](https://codecov.io/gh/9bow/zipped-imgs-to-pdf/branch/master/graph/badge.svg)](https://codecov.io/gh/9bow/zipped-imgs-to-pdf)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)

A tool for converting images contained in ZIP files to PDF.

- **Web App**: Use directly in your browser (no installation required, 100% client-side)
- **Python CLI**: Command-line interface (useful for batch processing)

## Key Features

- Automatically extracts images from ZIP files and converts them into a single PDF file
- Organizes PDF pages in filename order
- **Configurable Natural Sorting**: Naturally sorts numbers in filenames (e.g., page_1, page_2, page_10)
- **Configurable Priority Characters**: Places images starting with specific characters at the beginning (default: `!`)
- **Recursive Directory Processing**: Process all ZIP files in a directory at once (CLI)
- **Settings Persistence**: Automatically saves options used in the web app (localStorage)
- Generated PDF filename matches the ZIP filename
- Cross-platform support (Windows, macOS, Linux)
- Supports various image formats (JPG, PNG, GIF, BMP, TIFF, WebP)
- 100% client-side processing (web app) - files are not sent to any server

## Project Structure

This project is managed as a **Monorepo** structure, ensuring consistency between Python and JavaScript versions through shared logic:

```
zipped-imgs-to-pdf/
├── shared/              # Shared logic (sorting algorithms, constants)
│   ├── sorting_logic.py     # Python shared module
│   ├── sorting-logic.js     # JavaScript shared module
│   └── constants.py         # Common constants
├── python/              # Python CLI version
│   ├── zipped_imgs_to_pdf.py
│   └── requirements.txt
├── web/                 # Web app version
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/               # Tests (Python & JavaScript)
│   ├── test_natural_sort.py
│   ├── test_cli.py
│   ├── app.test.js
│   └── ...
└── .github/
    └── workflows/
        ├── build.yml    # Automated tests
        └── deploy.yml   # GitHub Pages deployment
```

## Using the Web App

This is the simplest method. You can use it directly in your browser.

### Online Usage

Use it directly on GitHub Pages: [Zipped Images to PDF Converter](https://9bow.github.io/zipped-imgs-to-pdf/)

### Local Usage

1. Download or clone this repository
2. Open the `web/index.html` file in your browser
3. Adjust settings as desired (Natural sorting, priority characters)
4. Drag and drop or select a ZIP file
5. Click the "Convert to PDF" button

**Advantages:**
- No installation required
- 100% client-side processing - files are not sent to any server
- Intuitive UI
- Works in all major browsers (Chrome, Firefox, Safari, Edge)
- **Automatic Settings Persistence**: Your options are saved in the browser and automatically applied on your next visit

## Using Python CLI

Use this when you need batch processing from the command line.

### Requirements

- Python 3.7 or higher

### Installing Dependencies

```bash
pip install -r python/requirements.txt
```

Or

```bash
pip install Pillow
```

### Usage

#### Basic Usage

Convert a single ZIP file:
```bash
python python/zipped_imgs_to_pdf.py images1.zip
```

Convert multiple ZIP files simultaneously:
```bash
python python/zipped_imgs_to_pdf.py images1.zip images2.zip images3.zip
```

Using wildcards:
```bash
python python/zipped_imgs_to_pdf.py *.zip
```

#### Recursive Directory Processing

Recursively process all ZIP files in a directory:
```bash
python python/zipped_imgs_to_pdf.py /path/to/zip-files/ -r
```

Or:
```bash
python python/zipped_imgs_to_pdf.py /path/to/zip-files/ --recursive
```

#### Advanced Options

Specify output directory:
```bash
python python/zipped_imgs_to_pdf.py images1.zip -o /path/to/output/
```

Use with recursive processing:
```bash
python python/zipped_imgs_to_pdf.py /path/to/zip-files/ -r -o /path/to/output/
```

#### Sorting Options

Disable natural sorting:
```bash
python python/zipped_imgs_to_pdf.py images1.zip --no-natural-sort
```

Change priority characters:
```bash
python python/zipped_imgs_to_pdf.py images1.zip --priority-chars "!@#"
```

#### Help

```bash
python python/zipped_imgs_to_pdf.py --help
```


## Image Sorting Rules

### Natural Sorting

This tool uses **natural sorting** by default:

**Regular string sorting (incorrect order):**
```
page_1.jpg → page_10.jpg → page_2.jpg
```

**Natural sorting (correct order):**
```
page_1.jpg → page_2.jpg → page_10.jpg
```

Natural sorting can be disabled in settings.

### Priority Characters

By default, files starting with `!` are placed at the beginning. This character can be changed in settings.

**Example 1: Default setting (`!`)**

ZIP file contents:
```
- page03.jpg
- page01.jpg
- !cover.jpg
- page02.jpg
- !back.jpg
```

PDF page order:
```
1. !back.jpg
2. !cover.jpg
3. page01.jpg
4. page02.jpg
5. page03.jpg
```

**Example 2: Multiple priority characters (`!@`)**

ZIP file contents:
```
- page_10.jpg
- @special.jpg
- !cover.jpg
- page_2.jpg
```

PDF page order (with natural sorting enabled):
```
1. !cover.jpg
2. @special.jpg
3. page_2.jpg
4. page_10.jpg
```


## Supported Image Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp) - Python only
- TIFF (.tiff) - Python only
- WebP (.webp)

## Developer Information

- PDF files are created in the same directory as the ZIP file by default
- PDF filename changes only the extension to `.pdf` from the ZIP filename
  - Example: `archive1.zip` → `archive1.pdf`

### Running Tests

```bash
python tests/test_natural_sort.py
```

### Local Build

Build locally using PyInstaller:

```bash
pip install pyinstaller
cd python
pyinstaller --onefile --name zipped-imgs-to-pdf --add-data "../shared:shared" zipped_imgs_to_pdf.py
```

## Examples

### Windows

```cmd
python python/zipped_imgs_to_pdf.py C:\Archives\manga1.zip
python python/zipped_imgs_to_pdf.py C:\Archives\*.zip -o C:\PDF\
python python/zipped_imgs_to_pdf.py C:\Archives\ -r -o C:\PDF\
```

### macOS / Linux

```bash
python python/zipped_imgs_to_pdf.py ~/Archives/manga1.zip
python python/zipped_imgs_to_pdf.py ~/Archives/*.zip -o ~/PDF/
python python/zipped_imgs_to_pdf.py ~/Archives/ -r -o ~/PDF/
```

## Troubleshooting

### Pillow Installation Error

If Pillow installation fails on Windows:
```bash
python -m pip install --upgrade pip
pip install Pillow
```

## License

MIT License
