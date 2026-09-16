/**
 * Shared sorting logic for the zipped-imgs-to-pdf project.
 *
 * Contains the core sorting algorithms used by both the Web version
 * (browser) and the test suite (Node.js). Mirrors the Python
 * implementation in `shared/sorting_logic.py` for cross-runtime parity.
 *
 * ⚠️  IMAGE_EXTENSIONS must stay in sync with shared/constants.py.
 *     Prefers window.NexusConstants when available (shared/constants.js),
 *     otherwise falls back to an inline mirror.
 *
 * UMD wrapper: works in Node (CommonJS), AMD, and browser (global).
 *
 * Public API (browser global `NexusSorting` + spread on `window`):
 *   IMAGE_EXTENSIONS
 *   DEFAULT_PRIORITY_CHARS
 *   getBasename(path)          -> string
 *   normalizePath(path)        -> string
 *   isImageFile(filename)      -> boolean
 *   naturalSortKey(text)       -> Array<string|number>
 *   compareNaturalKeys(a, b)   -> -1 | 0 | 1
 *   sortImages(files, useNaturalSort=true, priorityChars='!') -> string[]
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        // Node.js / CommonJS
        module.exports = factory();
    } else if (typeof define === 'function' && define.amd) {
        // AMD
        define([], factory);
    } else {
        // Browser global
        const api = factory();
        root.NexusSorting = api;

        // Backward-compat: expose individual symbols globally
        root.IMAGE_EXTENSIONS       = api.IMAGE_EXTENSIONS;
        root.DEFAULT_PRIORITY_CHARS = api.DEFAULT_PRIORITY_CHARS;
        root.getBasename            = api.getBasename;
        root.normalizePath          = api.normalizePath;
        root.isImageFile            = api.isImageFile;
        root.naturalSortKey         = api.naturalSortKey;
        root.compareNaturalKeys     = api.compareNaturalKeys;
        root.sortImages             = api.sortImages;
    }
})(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    // =================================================================
    // § 00 — CONSTANTS
    // =================================================================

    // Prefer shared/constants.js when loaded — guarantees parity with
    // shared/constants.py. Fallback mirrors constants.py EXACTLY.
    const _C = (typeof NexusConstants !== 'undefined' && NexusConstants)
        ? NexusConstants
        : null;

    /**
     * Supported image extensions (lowercase, dot included).
     * MIRRORS: shared/constants.py → IMAGE_EXTENSIONS
     * 7 extensions: .jpg .jpeg .png .gif .bmp .tiff .webp
     */
    const IMAGE_EXTENSIONS = (_C && Array.isArray(_C.IMAGE_EXTENSIONS))
        ? _C.IMAGE_EXTENSIONS.slice()
        : ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'];

    /** Default priority characters. MIRRORS constants.py. */
    const DEFAULT_PRIORITY_CHARS = (_C && typeof _C.DEFAULT_PRIORITY_CHARS === 'string')
        ? _C.DEFAULT_PRIORITY_CHARS
        : '!';

    // =================================================================
    // § 01 — PATH HELPERS
    // =================================================================

    /**
     * Extract the basename from a path, handling both POSIX (`/`) and
     * Windows (`\`) separators — ZIP archives from Windows often contain
     * backslash-separated entries.
     *
     * @param {string} filepath
     * @returns {string} The basename (last segment of the path)
     */
    function getBasename(filepath) {
        if (!filepath || typeof filepath !== 'string') return '';
        // Split on both separators in a single pass
        const parts = filepath.split(/[\\/]/);
        return parts[parts.length - 1] || '';
    }

    /**
     * Normalize a path: convert all backslashes to forward slashes and
     * strip leading `./` for consistent comparison across platforms.
     *
     * @param {string} filepath
     * @returns {string}
     */
    function normalizePath(filepath) {
        if (!filepath || typeof filepath !== 'string') return '';
        return filepath.replace(/\\/g, '/').replace(/^\.\//, '');
    }

    // =================================================================
    // § 02 — IMAGE DETECTION
    // =================================================================

    /**
     * Check if a file is an image based on its extension.
     *
     * Handles edge cases:
     *   - no extension            -> false
     *   - hidden files (".gitignore") -> false
     *   - uppercase extensions    -> true (case-insensitive)
     *   - trailing dots ("file.") -> false
     *   - Windows paths           -> handled via getBasename
     *
     * @param {string} filename
     * @returns {boolean}
     */
    function isImageFile(filename) {
        if (!filename || typeof filename !== 'string') return false;

        const basename = getBasename(filename);
        const dotIndex = basename.lastIndexOf('.');

        // No dot, dot at position 0 (hidden file), or trailing dot
        if (dotIndex <= 0 || dotIndex === basename.length - 1) return false;

        const ext = basename.substring(dotIndex).toLowerCase();
        return IMAGE_EXTENSIONS.includes(ext);
    }

    // =================================================================
    // § 03 — NATURAL SORT
    // =================================================================

    /**
     * Generate a natural sorting key for text containing numbers.
     *
     * Splits text into alternating chunks of digits and non-digits,
     * converting digit chunks to integers for numeric comparison.
     *
     *   "file_1.jpg"  -> ['file_', 1,  '.jpg']
     *   "file_10.jpg" -> ['file_', 10, '.jpg']
     *   "file_2.jpg"  -> ['file_', 2,  '.jpg']
     *
     * Result: file_1 < file_2 < file_10 (instead of file_1 < file_10 < file_2)
     *
     * @param {string} text
     * @returns {Array<string|number>}
     */
    function naturalSortKey(text) {
        if (typeof text !== 'string') return [String(text == null ? '' : text)];
        const chunks = text.split(/(\d+)/);
        return chunks.map(chunk =>
            /^\d+$/.test(chunk) ? parseInt(chunk, 10) : chunk
        );
    }

    /**
     * Compare two strings using natural sort semantics.
     *
     * @param {string} a
     * @param {string} b
     * @returns {number} -1 | 0 | 1
     */
    function compareNaturalKeys(a, b) {
        const keyA = naturalSortKey(a);
        const keyB = naturalSortKey(b);
        const minLength = Math.min(keyA.length, keyB.length);

        for (let i = 0; i < minLength; i++) {
            const chunkA = keyA[i];
            const chunkB = keyB[i];

            if (chunkA === chunkB) continue;

            const typeA = typeof chunkA;
            const typeB = typeof chunkB;

            // Both numeric -> numeric comparison
            if (typeA === 'number' && typeB === 'number') {
                return chunkA - chunkB;
            }

            // Mixed types -> string fallback on the raw chunk
            return String(chunkA) < String(chunkB) ? -1 : 1;
        }

        return keyA.length - keyB.length;
    }

    // =================================================================
    // § 04 — MAIN SORT
    // =================================================================

    /**
     * Sort image file paths with optional natural sorting and priority-char
     * routing. Files whose basename starts with any char in `priorityChars`
     * are placed at the beginning, then the rest. Both groups are sorted
     * with the same comparator.
     *
     * Examples:
     *   Input : ['page_10.jpg', 'page_1.jpg', '!cover.jpg', 'page_2.jpg', '!back.jpg']
     *
     *   Out(natural=true,  prio='!')  : ['!back.jpg', '!cover.jpg',
     *                                    'page_1.jpg', 'page_2.jpg', 'page_10.jpg']
     *   Out(natural=false, prio='!')  : ['!back.jpg', '!cover.jpg',
     *                                    'page_1.jpg', 'page_10.jpg', 'page_2.jpg']
     *
     *   Input : ['page_10.jpg', '@special.jpg', '!cover.jpg', 'page_2.jpg']
     *   Out(natural=true,  prio='!@') : ['!cover.jpg', '@special.jpg',
     *                                    'page_2.jpg', 'page_10.jpg']
     *
     * @param {string[]} imageFiles
     * @param {boolean} [useNaturalSort=true]
     * @param {string}  [priorityChars='!']
     * @returns {string[]} New sorted array (input is NOT mutated)
     */
    function sortImages(imageFiles, useNaturalSort = true, priorityChars = DEFAULT_PRIORITY_CHARS) {
        if (!Array.isArray(imageFiles) || imageFiles.length === 0) return [];

        const priorityFiles = [];
        const normalFiles = [];

        // Precompute the priority set once for O(1) lookup
        const prioritySet = (typeof priorityChars === 'string' && priorityChars.length > 0)
            ? new Set(priorityChars.split(''))
            : new Set();

        for (const imgPath of imageFiles) {
            if (typeof imgPath !== 'string') continue;

            const basename  = getBasename(imgPath);
            const firstChar = basename.charAt(0);
            const isPriority = firstChar !== '' && prioritySet.has(firstChar);

            if (isPriority) priorityFiles.push(imgPath);
            else            normalFiles.push(imgPath);
        }

        const comparator = useNaturalSort
            ? (a, b) => compareNaturalKeys(getBasename(a), getBasename(b))
            : (a, b) => getBasename(a).localeCompare(getBasename(b));

        priorityFiles.sort(comparator);
        normalFiles.sort(comparator);

        return [...priorityFiles, ...normalFiles];
    }

    // =================================================================
    // § 05 — PUBLIC API
    // =================================================================

    return {
        IMAGE_EXTENSIONS,
        DEFAULT_PRIORITY_CHARS,
        getBasename,
        normalizePath,
        isImageFile,
        naturalSortKey,
        compareNaturalKeys,
        sortImages
    };
});
