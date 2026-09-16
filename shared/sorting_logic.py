"""
Shared sorting logic for zipped-imgs-to-pdf project.

Contains the core sorting algorithms used by both the Python CLI and the
Web version. Mirrors the JavaScript implementation in `sorting-logic.js`
for cross-runtime parity.

Public API:
    IMAGE_EXTENSIONS
    DEFAULT_PRIORITY_CHARS
    get_basename(path)      -> str
    normalize_path(path)    -> str
    is_image_file(filename) -> bool
    natural_sort_key(text)  -> list[int | str]
    sort_images(files, use_natural_sort=True, priority_chars='!') -> list[str]
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Union

from .constants import IMAGE_EXTENSIONS

# Fallback if the shared constant isn't defined
DEFAULT_PRIORITY_CHARS = '!'

# Safety: cap digit chunk length to avoid int() DoS on Python 3.11+
_MAX_DIGITS = 4000  # below sys.set_int_max_str_digits default (4300)

__all__ = [
    "IMAGE_EXTENSIONS",
    "DEFAULT_PRIORITY_CHARS",
    "get_basename",
    "normalize_path",
    "is_image_file",
    "natural_sort_key",
    "sort_images",
]


# =====================================================================
# PATH HELPERS
# =====================================================================

def get_basename(filepath: str) -> str:
    """
    Extract the basename from a path, handling both POSIX (``/``) and
    Windows (``\\``) separators.

    ZIP archives created on Windows often contain entries like
    ``folder\\image.jpg`` — ``Path(...).name`` on POSIX would return the
    whole string unchanged, breaking sorting.

    Args:
        filepath: Full or relative path.

    Returns:
        The last path segment, or ``''`` if the input is empty/invalid.
    """
    if not filepath or not isinstance(filepath, str):
        return ""
    # Split on BOTH separators in a single pass — no OS dependency
    parts = re.split(r'[\\/]', filepath)
    return parts[-1] if parts else ""


def normalize_path(filepath: str) -> str:
    """
    Normalize a path: convert all backslashes to forward slashes and
    strip a leading ``./`` for consistent comparison across platforms.

    Args:
        filepath: Path string.

    Returns:
        Normalized path, or ``''`` if the input is empty/invalid.
    """
    if not filepath or not isinstance(filepath, str):
        return ""
    return re.sub(r'^\./', '', filepath.replace('\\', '/'))


# =====================================================================
# IMAGE DETECTION
# =====================================================================

def is_image_file(filename: str) -> bool:
    """
    Check if a file is an image based on its extension.

    Handles edge cases:
        - no extension                  -> False
        - hidden files (".gitignore")   -> False
        - uppercase extensions          -> True  (case-insensitive)
        - trailing dots ("file.")       -> False
        - basename with Windows paths   -> handled via get_basename

    Args:
        filename: Filename or path to check.

    Returns:
        True if the file is an image, False otherwise.
    """
    if not filename or not isinstance(filename, str):
        return False

    basename = get_basename(filename)
    dot_index = basename.rfind('.')

    # No dot, dot at position 0 (hidden file), or trailing dot
    if dot_index <= 0 or dot_index == len(basename) - 1:
        return False

    ext = basename[dot_index:].lower()
    return ext in IMAGE_EXTENSIONS


# =====================================================================
# NATURAL SORT
# =====================================================================

def natural_sort_key(text: str) -> List[Union[int, str]]:
    """
    Generate a natural sorting key for text containing numbers.

    Splits text into alternating chunks of digits and non-digits,
    converting digit chunks to integers for proper numeric comparison.

    Examples:
        "file_1.jpg"  -> ['file_', 1,  '.jpg']
        "file_10.jpg" -> ['file_', 10, '.jpg']
        "file_2.jpg"  -> ['file_', 2,  '.jpg']

    Result: file_1 < file_2 < file_10 (instead of file_1 < file_10 < file_2).

    Args:
        text: Text to generate a sorting key for.

    Returns:
        List of alternating strings and integers for comparison.
    """
    if not isinstance(text, str):
        return [str(text or "")]

    def convert(chunk: str) -> Union[int, str]:
        # Guard against int() DoS on pathological digit chunks
        if chunk.isdigit() and len(chunk) <= _MAX_DIGITS:
            return int(chunk)
        return chunk

    chunks = re.split(r'(\d+)', text)
    return [convert(chunk) for chunk in chunks]


# =====================================================================
# MAIN SORT
# =====================================================================

def sort_images(
    image_files: List[str],
    use_natural_sort: bool = True,
    priority_chars: str = DEFAULT_PRIORITY_CHARS,
) -> List[str]:
    """
    Sort image file paths with optional natural sorting and priority-char
    routing. Files whose basename starts with any char in ``priority_chars``
    are placed at the beginning, then the rest. Both groups are sorted with
    the same comparator.

    Examples:
        Input:  ['page_10.jpg', 'page_1.jpg', '!cover.jpg',
                 'page_2.jpg', '!back.jpg']

        Output (natural=True, prio='!'):
            ['!back.jpg', '!cover.jpg', 'page_1.jpg',
             'page_2.jpg', 'page_10.jpg']

        Output (natural=False, prio='!'):
            ['!back.jpg', '!cover.jpg', 'page_1.jpg',
             'page_10.jpg', 'page_2.jpg']

        Input:  ['page_10.jpg', '@special.jpg', '!cover.jpg', 'page_2.jpg']
        Output (natural=True, prio='!@'):
            ['!cover.jpg', '@special.jpg', 'page_2.jpg', 'page_10.jpg']

    Args:
        image_files: List of image file paths.
        use_natural_sort: Whether to use natural sorting (default: True).
        priority_chars: Characters marking priority files (default: '!').

    Returns:
        New sorted list (input is NOT mutated).
    """
    if not image_files:
        return []

    priority_files: List[str] = []
    normal_files: List[str] = []

    # Precompute priority set once (single-char matching, like JS)
    priority_set = set(priority_chars) if priority_chars else set()

    for img in image_files:
        if not isinstance(img, str):
            continue
        basename = get_basename(img)
        first_char = basename[:1]
        is_priority = bool(first_char) and first_char in priority_set

        if is_priority:
            priority_files.append(img)
        else:
            normal_files.append(img)

    if use_natural_sort:
        def key_natural(x: str):
            return natural_sort_key(get_basename(x))
        priority_files.sort(key=key_natural)
        normal_files.sort(key=key_natural)
    else:
        def key_name(x: str):
            return get_basename(x)
        priority_files.sort(key=key_name)
        normal_files.sort(key=key_name)

    return priority_files + normal_files
