"""
Shared constants for the zipped-imgs-to-pdf project.

⚠️  KEEP IN SYNC with ``shared/constants.js`` (the JS mirror).
    Any change here must be reflected there, and vice-versa.
"""

from __future__ import annotations

__all__ = [
    "IMAGE_EXTENSIONS",
    "DEFAULT_PRIORITY_CHARS",
    "MAX_FILE_SIZE_BYTES",
    "MAX_EXTRACTED_SIZE_BYTES",
    "MAX_FILES_IN_ZIP",
    "MAX_IMAGE_DIMENSION",
    "IMAGE_SCALE_FACTOR",
    "MAX_COMPRESSION_RATIO",
]

# =====================================================================
# SORTING / FILTERING
# =====================================================================

# Image file extensions supported by the application.
# Must match `IMAGE_EXTENSIONS` in shared/constants.js EXACTLY.
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}

# Default priority characters for file sorting.
DEFAULT_PRIORITY_CHARS = '!'

# =====================================================================
# SECURITY LIMITS
# =====================================================================

# Maximum accepted input file size (single ZIP or image).
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

# Maximum cumulative uncompressed size extracted from a ZIP (bomb protection).
MAX_EXTRACTED_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB

# Maximum number of files allowed in a single ZIP.
MAX_FILES_IN_ZIP = 10000

# Maximum allowed compression ratio (uncompressed / compressed).
# Anything above is treated as a possible ZIP bomb.
MAX_COMPRESSION_RATIO = 100

# =====================================================================
# IMAGE PROCESSING
# =====================================================================

# Maximum pixel dimension (width or height) before downscaling.
MAX_IMAGE_DIMENSION = 2000

# Scale factor applied when converting pixels to PDF points.
IMAGE_SCALE_FACTOR = 4
