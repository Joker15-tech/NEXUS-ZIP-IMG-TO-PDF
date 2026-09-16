# Shared Module

This directory contains core logic shared between the Python CLI and JavaScript web app.

## File Structure

```
shared/
├── __init__.py          # Python package initialization
├── constants.py         # Common constants
├── sorting_logic.py     # Python sorting algorithm
└── sorting-logic.js     # JavaScript sorting algorithm
```

## Core Features

### 1. Image File Validation

**Python:**
```python
from shared import is_image_file

is_image_file('photo.jpg')  # True
is_image_file('document.pdf')  # False
```

**JavaScript:**
```javascript
isImageFile('photo.jpg')  // true
isImageFile('document.pdf')  // false
```

### 2. Natural Sort Key Generation

Generates keys for correctly sorting numbers in filenames.

**Python:**
```python
from shared import natural_sort_key

files = ['page_1.jpg', 'page_10.jpg', 'page_2.jpg']
sorted_files = sorted(files, key=natural_sort_key)
# ['page_1.jpg', 'page_2.jpg', 'page_10.jpg']
```

**JavaScript:**
```javascript
const files = ['page_1.jpg', 'page_10.jpg', 'page_2.jpg'];
const sorted = files.sort((a, b) => compareNaturalKeys(a, b));
// ['page_1.jpg', 'page_2.jpg', 'page_10.jpg']
```

### 3. Image Sorting

Sorts images considering priority characters and natural sorting.

**Python:**
```python
from shared import sort_images

images = ['page_10.jpg', '!cover.jpg', 'page_2.jpg']
sorted_images = sort_images(
    images,
    use_natural_sort=True,
    priority_chars='!'
)
# ['!cover.jpg', 'page_2.jpg', 'page_10.jpg']
```

**JavaScript:**
```javascript
const images = ['page_10.jpg', '!cover.jpg', 'page_2.jpg'];
const sorted = sortImages(images, true, '!');
// ['!cover.jpg', 'page_2.jpg', 'page_10.jpg']
```

## Supported Image Formats

```python
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
```

## Default Settings

```python
DEFAULT_PRIORITY_CHARS = '!'
```

## Algorithm Details

### Natural Sorting

Unlike regular string sorting, natural sorting recognizes numbers within filenames as numbers:

- Regular sort: `page_1.jpg` < `page_10.jpg` < `page_2.jpg` (incorrect order)
- Natural sort: `page_1.jpg` < `page_2.jpg` < `page_10.jpg` (correct order)

**Implementation:**
1. Split filename into numeric and non-numeric chunks
2. Convert numeric chunks to integers
3. Compare chunk lists for sorting

### Priority Sorting

Places files starting with specific characters (default: `!`) at the beginning:

1. Separate files into priority files and regular files
2. Sort each group independently
3. Merge in order: priority files + regular files

## Testing

The Python shared module is tested in `tests/test_natural_sort.py`:

```bash
python tests/test_natural_sort.py
```

## Maintenance Guide

When modifying this module, **both Python and JavaScript implementations must be updated simultaneously**:

1. Modify `sorting_logic.py`
2. Apply same logic to `sorting-logic.js`
3. Run tests for verification
4. Confirm both implementations return identical results

## Dependencies

- **Python**: Standard library only (no external dependencies)
  - `re` - Regular expressions
  - `pathlib` - Path handling

- **JavaScript**: Pure JavaScript (ES6+)
  - No external libraries

## License

MIT License - See LICENSE file in parent directory
