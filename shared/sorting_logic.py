"""
=====================================================================
NEXUS QUANTUM // Shared sorting logic for zipped-imgs-to-pdf
=====================================================================
File:    shared/sorting_logic.py

Core sorting algorithms used by both the Python CLI and the Web
version. Mirrors the JavaScript implementation in
``shared/sorting-logic.js`` for strict cross-runtime parity.

Public API:
    IMAGE_EXTENSIONS
    DEFAULT_PRIORITY_CHARS
    get_basename(path)               -> str
    normalize_path(path)             -> str
    is_image_file(filename)          -> bool
    natural_sort_key(text)           -> list[int | str]
    compare_natural_keys(a, b)       -> int   (-1 | 0 | 1)
    sort_images(files, use_natural_sort=True, priority_chars='!') -> list[str]

Design notes:
    - Accepts ``Union[str, Path]`` wherever a path is expected.
    - Rejects non-string, non-Path inputs safely (returns False / []).
    - Caps digit chunks at ``_MAX_DIGITS`` to protect against DoS on
      Python 3.11+ (``sys.set_int_max_str_digits`` default = 4300).
    - Handles both POSIX (``/``) and Windows (``\\``) separators.
    - Never mutates input.
    - Stable sort (inherits from Python's ``list.sort``).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Union

from .constants import IMAGE_EXTENSIONS

# =====================================================================
// § 01 — CONSTANTS
// =====================================================================

# Default priority char (mirrors shared/constants.py)
DEFAULT_PRIORITY_CHARS = "!"

# DoS guard for huge digit chunks (below sys.set_int_max_str_digits)
_MAX_DIGITS = 4000

# Path separators — POSIX + Windows
_SEPARATOR_RE = re.compile(r"[\\/]")

# Leading "./" or ".\\" prefix
_LEADING_DOT_SLASH_RE = re.compile(r"^\.[\\/]")

# Natural sort chunk splitter: capture runs of digits
_DIGIT_CHUNK_RE = re.compile(r"(\d+)")

# Full-digit test (used by natural_sort_key)
_ALL_DIGITS_RE = re.compile(r"^\d+$")


__all__ = [
    "IMAGE_EXTENSIONS",
    "DEFAULT_PRIORITY_CHARS",
    "get_basename",
    "normalize_path",
    "is_image_file",
    "natural_sort_key",
    "compare_natural_keys",
    "sort_images",
]


# =====================================================================
// § 02 — PATH HELPERS
// =====================================================================


def get_basename(filepath: Union[str, Path, None]) -> str:
    """
    Extract the basename from a path, handling both POSIX (``/``) and
    Windows (``\\``) separators.

    ZIP archives created on Windows often contain entries like
    ``folder\\image.jpg`` — ``Path(...).name`` on POSIX would return the
    whole string unchanged, breaking sorting.

    Args:
        filepath: Full or relative path. ``str`` or ``Path``.

    Returns:
        The last path segment, or ``''`` if the input is empty/invalid.

    Examples:
        >>> get_basename('/home/user/photo.jpg')
        'photo.jpg'
        >>> get_basename('C:\\\\Users\\\\Photos\\\\pic.png')
        'pic.png'
        >>> get_basename('a\\\\b/c\\\\d.jpg')
        'd.jpg'
        >>> get_basename(None)
        ''
    """
    if filepath is None:
        return ""
    if isinstance(filepath, Path):
        filepath = str(filepath)
    if not isinstance(filepath, str):
        return ""

    parts = _SEPARATOR_RE.split(filepath)
    return parts[-1] if parts else ""


def normalize_path(filepath: Union[str, Path, None]) -> str:
    """
    Normalize a path for consistent cross-platform comparison:

    - Converts all backslashes to forward slashes
    - Strips a single leading ``./`` or ``.\\``

    Args:
        filepath: Path string or ``Path``.

    Returns:
        Normalized path, or ``''`` if the input is empty/invalid.

    Examples:
        >>> normalize_path('folder\\\\sub\\\\image.jpg')
        'folder/sub/image.jpg'
        >>> normalize_path('./folder/image.jpg')
        'folder/image.jpg'
        >>> normalize_path('.\\\\folder\\\\image.jpg')
        'folder/image.jpg'
    """
    if filepath is None:
        return ""
    if isinstance(filepath, Path):
        filepath = str(filepath)
    if not isinstance(filepath, str):
        return ""

    # Backslashes → forward slashes
    normalized = filepath.replace("\\", "/")
    # Strip a single leading "./"
    normalized = _LEADING_DOT_SLASH_RE.sub("", normalized) if "\\" in filepath else normalized
    # The regex already handles both separators, so simplify:
    normalized = filepath.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


# =====================================================================
// § 03 — IMAGE DETECTION
// =====================================================================


def is_image_file(filename: Union[str, Path, None]) -> bool:
    """
    Check if a file is an image based on its extension.

    Handles edge cases:
        - no extension                  -> False
        - hidden files (".gitignore")   -> False
        - dot-only names (".jpg")       -> False   (matches JS)
        - trailing dots ("file.")       -> False
        - uppercase extensions          -> True    (case-insensitive)
        - Windows paths                 -> handled via get_basename
        - Path objects                  -> accepted
        - None / non-string / non-Path  -> False

    Args:
        filename: Filename or path to check.

    Returns:
        True if the file is an image, False otherwise.

    Examples:
        >>> is_image_file('photo.jpg')
        True
        >>> is_image_file('photo.JPG')
        True
        >>> is_image_file('document.pdf')
        False
        >>> is_image_file('.jpg')
        False
        >>> is_image_file('folder\\\\sub\\\\image.png')
        True
    """
    if filename is None:
        return False
    if isinstance(filename, Path):
        filename = str(filename)
    if not isinstance(filename, str) or not filename:
        return False

    basename = get_basename(filename)
    dot_index = basename.rfind(".")

    # No dot, or dot at position 0 (hidden file), or trailing dot
    if dot_index <= 0 or dot_index == len(basename) - 1:
        return False

    ext = basename[dot_index:].lower()
    return ext in IMAGE_EXTENSIONS


# =====================================================================
// § 04 — NATURAL SORT KEY
// =====================================================================


def natural_sort_key(text: Union[str, int, float, None]) -> List[Union[int, str]]:
    """
    Generate a natural sorting key for text containing numbers.

    Splits text into alternating chunks of digits and non-digits,
    converting digit chunks to integers for proper numeric comparison.

    Examples:
        >>> natural_sort_key('file_1.jpg')
        ['file_', 1, '.jpg']
        >>> natural_sort_key('file_10.jpg')
        ['file_', 10, '.jpg']
        >>> natural_sort_key('file_2.jpg')
        ['file_', 2, '.jpg']
        >>> natural_sort_key('page_001.jpg') == natural_sort_key('page_1.jpg')
        True

    Result: file_1 < file_2 < file_10
            (instead of file_1 < file_10 < file_2)

    Args:
        text: Text to generate a sorting key for.

    Returns:
        List of alternating strings and integers for comparison.
    """
    if not isinstance(text, str):
        text = str(text) if text is not None else ""

    def _convert(chunk: str) -> Union[int, str]:
        # Guard against int() DoS on pathological digit chunks
        if _ALL_DIGITS_RE.match(chunk) and len(chunk) <= _MAX_DIGITS:
            return int(chunk)
        return chunk

    chunks = _DIGIT_CHUNK_RE.split(text)
    return [_convert(chunk) for chunk in chunks]


def compare_natural_keys(
    a: Union[str, None],
    b: Union[str, None],
) -> int:
    """
    Compare two strings using natural sort semantics.

    Provided for API parity with ``compareNaturalKeys()`` in
    ``shared/sorting-logic.js``.

    Args:
        a: First string.
        b: Second string.

    Returns:
        -1 if a < b, 0 if equal, 1 if a > b.
    """
    key_a = natural_sort_key(a)
    key_b = natural_sort_key(b)
    min_length = min(len(key_a), len(key_b))

    for i in range(min_length):
        chunk_a = key_a[i]
        chunk_b = key_b[i]

        if chunk_a == chunk_b:
            continue

        type_a = type(chunk_a).__name__
        type_b = type(chunk_b).__name__

        # Both numeric → numeric comparison
        if isinstance(chunk_a, int) and isinstance(chunk_b, int):
            return -1 if chunk_a < chunk_b else 1

        # Mixed types → string fallback on the raw chunk
        str_a = str(chunk_a)
        str_b = str(chunk_b)
        if str_a < str_b:
            return -1
        if str_a > str_b:
            return 1

    if len(key_a) == len(key_b):
        return 0
    return -1 if len(key_a) < len(key_b) else 1


# =====================================================================
// § 05 — MAIN SORT
// =====================================================================


def sort_images(
    image_files: Union[List[Union[str, Path]], None],
    use_natural_sort: bool = True,
    priority_chars: Union[str, None] = DEFAULT_PRIORITY_CHARS,
) -> List[str]:
    """
    Sort image file paths with optional natural sorting and priority-char
    routing.

    Files whose **basename** starts with any char in ``priority_chars``
    are placed at the beginning, then the rest. Both groups are sorted
    with the same comparator.

    Examples:
        Input:  ['page_10.jpg', 'page_1.jpg', '!cover.jpg',
                 'page_2.jpg', '!back.jpg']

        Output (natural=True, prio='!'):
            ['!back.jpg', '!cover.jpg',
             'page_1.jpg', 'page_2.jpg', 'page_10.jpg']

        Output (natural=False, prio='!'):
            ['!back.jpg', '!cover.jpg',
             'page_1.jpg', 'page_10.jpg', 'page_2.jpg']

        Input:  ['page_10.jpg', '@special.jpg', '!cover.jpg', 'page_2.jpg']
        Output (natural=True, prio='!@'):
            ['!cover.jpg', '@special.jpg',
             'page_2.jpg', 'page_10.jpg']

    Args:
        image_files: List of image file paths (``str`` or ``Path``).
        use_natural_sort: Whether to use natural sorting (default: True).
        priority_chars: Characters marking priority files (default: '!').
            Pass ``None`` or ``''`` to disable priority routing.

    Returns:
        New sorted list of ``str`` (input is NOT mutated).

    Notes:
        - Non-string entries are silently skipped.
        - ``Path`` entries are converted to ``str`` in the output.
        - ``None`` or non-list input returns ``[]``.
    """
    if not isinstance(image_files, (list, tuple)) or len(image_files) == 0:
        return []

    # Normalize everything to str, skip invalid entries
    normalized: List[str] = []
    for entry in image_files:
        if isinstance(entry, Path):
            normalized.append(str(entry))
        elif isinstance(entry, str):
            normalized.append(entry)
        # Anything else is silently dropped

    if not normalized:
        return []

    # Precompute priority set once (single-char matching, like JS)
    priority_set = set(priority_chars) if priority_chars else set()

    priority_files: List[str] = []
    normal_files: List[str] = []

    for img in normalized:
        basename = get_basename(img)
        first_char = basename[:1] if basename else ""
        is_priority = bool(first_char) and first_char in priority_set

        if is_priority:
            priority_files.append(img)
        else:
            normal_files.append(img)

    if use_natural_sort:
        def key_fn(x: str) -> List[Union[int, str]]:
            return natural_sort_key(get_basename(x))
    else:
        def key_fn(x: str) -> str:
            return get_basename(x)

    # Python's sort is stable → equal keys preserve input order
    priority_files.sort(key=key_fn)
    normal_files.sort(key=key_fn)

    return priority_files + normal_files
