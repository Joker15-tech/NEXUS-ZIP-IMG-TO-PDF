"""
Shared constants for zipped-imgs-to-pdf project.
"""

# Image file extensions supported by the application
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}

# Default priority characters for file sorting
DEFAULT_PRIORITY_CHARS = '!'

# Security limits
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100MB
MAX_EXTRACTED_SIZE_BYTES = 500 * 1024 * 1024  # 500MB (ZIP bomb protection)
MAX_FILES_IN_ZIP = 10000  # Maximum number of files to extract

# Image processing constants
MAX_IMAGE_DIMENSION = 2000  # Maximum dimension in pixels
IMAGE_SCALE_FACTOR = 4  # Scale factor for PDF conversion
