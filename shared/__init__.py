"""
Shared module for zipped-imgs-to-pdf project.

This module contains common logic used by both Python CLI and Web versions.
"""

from .constants import (
    IMAGE_EXTENSIONS,
    DEFAULT_PRIORITY_CHARS,
    MAX_FILE_SIZE_BYTES,
    MAX_EXTRACTED_SIZE_BYTES,
    MAX_FILES_IN_ZIP,
    MAX_IMAGE_DIMENSION,
    IMAGE_SCALE_FACTOR
)
from .sorting_logic import is_image_file, natural_sort_key, sort_images

__all__ = [
    'IMAGE_EXTENSIONS',
    'DEFAULT_PRIORITY_CHARS',
    'MAX_FILE_SIZE_BYTES',
    'MAX_EXTRACTED_SIZE_BYTES',
    'MAX_FILES_IN_ZIP',
    'MAX_IMAGE_DIMENSION',
    'IMAGE_SCALE_FACTOR',
    'is_image_file',
    'natural_sort_key',
    'sort_images',
]
