/**
 * Shared sorting logic for zipped-imgs-to-pdf project.
 *
 * This module contains the core sorting algorithms used by the web version.
 * It mirrors the Python implementation in sorting_logic.py
 */

// Supported image extensions
const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'];

// Default priority characters
const DEFAULT_PRIORITY_CHARS = '!';

/**
 * Check if a file is an image based on its extension
 *
 * @param {string} filename - The filename to check
 * @returns {boolean} True if the file is an image, false otherwise
 */
function isImageFile(filename) {
    const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
    return IMAGE_EXTENSIONS.includes(ext);
}

/**
 * Generate a natural sorting key for text containing numbers.
 *
 * This function splits the text into chunks of digits and non-digits,
 * converting digit chunks to integers for proper numerical comparison.
 *
 * Examples:
 *   "file_1.jpg" -> ['file_', 1, '.jpg']
 *   "file_10.jpg" -> ['file_', 10, '.jpg']
 *   "file_2.jpg" -> ['file_', 2, '.jpg']
 *
 * This ensures that file_1.jpg < file_2.jpg < file_10.jpg
 * instead of file_1.jpg < file_10.jpg < file_2.jpg
 *
 * @param {string} text - The text to generate a sorting key for
 * @returns {Array} Array of alternating strings and numbers for comparison
 */
function naturalSortKey(text) {
    // Split by digits, keeping the delimiters
    const chunks = text.split(/(\d+)/);
    return chunks.map(chunk => {
        // Convert chunk to number if it's all digits
        return /^\d+$/.test(chunk) ? parseInt(chunk, 10) : chunk;
    });
}

/**
 * Compare two natural sort keys
 *
 * @param {string} a - First string to compare
 * @param {string} b - Second string to compare
 * @returns {number} -1 if a < b, 1 if a > b, 0 if equal
 */
function compareNaturalKeys(a, b) {
    const keyA = naturalSortKey(a);
    const keyB = naturalSortKey(b);

    const minLength = Math.min(keyA.length, keyB.length);

    for (let i = 0; i < minLength; i++) {
        const chunkA = keyA[i];
        const chunkB = keyB[i];

        if (chunkA === chunkB) continue;

        // If both are numbers, compare numerically
        if (typeof chunkA === 'number' && typeof chunkB === 'number') {
            return chunkA - chunkB;
        }

        // Otherwise, compare as strings
        if (chunkA < chunkB) return -1;
        if (chunkA > chunkB) return 1;
    }

    return keyA.length - keyB.length;
}

/**
 * Sort image files with optional natural number sorting and special handling for priority characters.
 *
 * Files starting with priority characters are placed at the beginning, followed by other files.
 * Both groups are sorted using natural sorting (numbers sorted numerically, not lexically) if enabled.
 *
 * Examples:
 *   Input: ['page_10.jpg', 'page_1.jpg', '!cover.jpg', 'page_2.jpg', '!back.jpg']
 *   Output (naturalSort=true, priorityChars='!'):
 *     ['!back.jpg', '!cover.jpg', 'page_1.jpg', 'page_2.jpg', 'page_10.jpg']
 *   Output (naturalSort=false, priorityChars='!'):
 *     ['!back.jpg', '!cover.jpg', 'page_1.jpg', 'page_10.jpg', 'page_2.jpg']
 *
 *   Input: ['page_10.jpg', '@special.jpg', '!cover.jpg', 'page_2.jpg']
 *   Output (naturalSort=true, priorityChars='!@'):
 *     ['!cover.jpg', '@special.jpg', 'page_2.jpg', 'page_10.jpg']
 *
 * @param {Array<string>} imageFiles - Array of image file paths
 * @param {boolean} useNaturalSort - Whether to use natural sorting (default: true)
 * @param {string} priorityChars - Characters that mark images for priority placement (default: '!')
 * @returns {Array<string>} Sorted array of image file paths
 */
function sortImages(imageFiles, useNaturalSort = true, priorityChars = DEFAULT_PRIORITY_CHARS) {
    const priorityFiles = [];
    const normalFiles = [];

    for (const imgPath of imageFiles) {
        const filename = imgPath.split('/').pop();
        // Check if filename starts with any of the priority characters
        const isPriority = priorityChars ? priorityChars.split('').some(char => filename.startsWith(char)) : false;

        if (isPriority) {
            priorityFiles.push(imgPath);
        } else {
            normalFiles.push(imgPath);
        }
    }

    // Define sorting function based on options
    const sortFn = useNaturalSort
        ? (a, b) => {
            const nameA = a.split('/').pop();
            const nameB = b.split('/').pop();
            return compareNaturalKeys(nameA, nameB);
        }
        : (a, b) => {
            const nameA = a.split('/').pop();
            const nameB = b.split('/').pop();
            return nameA.localeCompare(nameB);
        };

    // Sort each group
    priorityFiles.sort(sortFn);
    normalFiles.sort(sortFn);

    // Combine: priority files first, then normal files
    return [...priorityFiles, ...normalFiles];
}

// Export for use in web application
if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        IMAGE_EXTENSIONS,
        DEFAULT_PRIORITY_CHARS,
        isImageFile,
        naturalSortKey,
        compareNaturalKeys,
        sortImages
    };
}
