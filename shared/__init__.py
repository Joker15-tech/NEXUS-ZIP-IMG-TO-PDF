"""
Shared module for the zipped-imgs-to-pdf project.

Contains common logic used by both the Python CLI and the Web version.
The JS mirrors live in `shared/constants.js` and `shared/sorting-logic.js`.

Public API:
    # Constants (mirror of shared/constants.py)
    IMAGE_EXTENSIONS
    DEFAULT_PRIORITY_CHARS
    MAX_FILE_SIZE_BYTES
    MAX_EXTRACTED_SIZE_BYTES
    MAX_FILES_IN_ZIP
    MAX_COMPRESSION_RATIO
    MAX_IMAGE_DIMENSION
    IMAGE_SCALE_FACTOR

    # Sorting / path helpers (mirror of shared/sorting_logic.py)
    get_basename
    normalize_path
    is_image_file
    natural_sort_key
    sort_images
"""

from __future__ import annotations

from .constants import (
    IMAGE_EXTENSIONS,
    DEFAULT_PRIORITY_CHARS,
    MAX_FILE_SIZE_BYTES,
    MAX_EXTRACTED_SIZE_BYTES,
    MAX_FILES_IN_ZIP,
    MAX_COMPRESSION_RATIO,
    MAX_IMAGE_DIMENSION,
    IMAGE_SCALE_FACTOR,
)
from .sorting_logic import (
    get_basename,
    normalize_path,
    is_image_file,
    natural_sort_key,
    sort_images,
)

__all__ = [
    # ---- Constants ----
    "IMAGE_EXTENSIONS",
    "DEFAULT_PRIORITY_CHARS",
    "MAX_FILE_SIZE_BYTES",
    "MAX_EXTRACTED_SIZE_BYTES",
    "MAX_FILES_IN_ZIP",
    "MAX_COMPRESSION_RATIO",
    "MAX_IMAGE_DIMENSION",
    "IMAGE_SCALE_FACTOR",
    # ---- Sorting / path helpers ----
    "get_basename",
    "normalize_path",
    "is_image_file",
    "natural_sort_key",
    "sort_images",
]
