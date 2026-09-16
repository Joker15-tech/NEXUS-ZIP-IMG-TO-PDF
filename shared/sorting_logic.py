"""
Shared sorting logic for zipped-imgs-to-pdf project.

This module contains the core sorting algorithms used by both
Python CLI and Web versions of the application.
"""

import re
from pathlib import Path
from typing import List, Union

from .constants import IMAGE_EXTENSIONS


def is_image_file(filename: str) -> bool:
    """
    Check if a file is an image based on its extension.

    Args:
        filename: The filename to check

    Returns:
        True if the file is an image, False otherwise
    """
    path = Path(filename)
    suffix = path.suffix.lower()

    # Handle case where filename is just an extension (e.g. ".jpg")
    # Path('.jpg').suffix is empty, but name is '.jpg'
    if not suffix and filename.startswith('.'):
        return filename.lower() in IMAGE_EXTENSIONS

    return suffix in IMAGE_EXTENSIONS


def natural_sort_key(text: str) -> List[Union[int, str]]:
    """
    Generate a natural sorting key for text containing numbers.

    This function splits the text into chunks of digits and non-digits,
    converting digit chunks to integers for proper numerical comparison.

    Examples:
        "file_1.jpg" -> ['file_', 1, '.jpg']
        "file_10.jpg" -> ['file_', 10, '.jpg']
        "file_2.jpg" -> ['file_', 2, '.jpg']

    This ensures that file_1.jpg < file_2.jpg < file_10.jpg
    instead of file_1.jpg < file_10.jpg < file_2.jpg

    Args:
        text: The text to generate a sorting key for

    Returns:
        List of alternating strings and integers for comparison
    """
    def convert(chunk: str) -> Union[int, str]:
        """Convert chunk to int if it's a digit, otherwise return as-is."""
        return int(chunk) if chunk.isdigit() else chunk

    # Split by digits, keeping the delimiters
    # r'(\d+)' captures one or more digits and keeps them in the result
    chunks = re.split(r'(\d+)', text)
    return [convert(chunk) for chunk in chunks]


def sort_images(
    image_files: List[str],
    use_natural_sort: bool = True,
    priority_chars: str = '!'
) -> List[str]:
    """
    Sort image files with optional natural number sorting and special
    handling for priority characters.

    Files starting with priority characters are placed at the beginning,
    followed by other files. Both groups are sorted using natural sorting
    (numbers sorted numerically, not lexically) if enabled.

    Examples:
        Input: ['page_10.jpg', 'page_1.jpg', '!cover.jpg',
                'page_2.jpg', '!back.jpg']
        Output (natural_sort=True, priority_chars='!'):
            ['!back.jpg', '!cover.jpg', 'page_1.jpg',
             'page_2.jpg', 'page_10.jpg']
        Output (natural_sort=False, priority_chars='!'):
            ['!back.jpg', '!cover.jpg', 'page_1.jpg',
             'page_10.jpg', 'page_2.jpg']

        Input: ['page_10.jpg', '@special.jpg', '!cover.jpg', 'page_2.jpg']
        Output (natural_sort=True, priority_chars='!@'):
            ['!cover.jpg', '@special.jpg', 'page_2.jpg', 'page_10.jpg']

    Args:
        image_files: List of image file paths
        use_natural_sort: Whether to use natural sorting (default: True)
        priority_chars: Characters that trigger priority sorting
            (default: '!')

    Returns:
        Sorted list of image file paths
    """
    priority_files = []
    normal_files = []

    for img in image_files:
        filename = Path(img).name
        # Check if filename starts with any of the priority characters
        is_priority = (
            any(filename.startswith(char) for char in priority_chars)
            if priority_chars
            else False
        )

        if is_priority:
            priority_files.append(img)
        else:
            normal_files.append(img)

    # Define sorting function based on options
    def get_natural_sort_key(x: str) -> List[Union[int, str]]:
        return natural_sort_key(Path(x).name)

    def get_name_key(x: str) -> str:
        return Path(x).name

    # Sort each group
    if use_natural_sort:
        priority_files.sort(key=get_natural_sort_key)
        normal_files.sort(key=get_natural_sort_key)
    else:
        priority_files.sort(key=get_name_key)
        normal_files.sort(key=get_name_key)

    # Combine: priority files first, then normal files
    return priority_files + normal_files
