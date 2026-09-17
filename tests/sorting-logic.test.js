/**
 * =====================================================================
 * NEXUS QUANTUM // Tests for shared/sorting-logic.js
 * =====================================================================
 * File:    tests/sorting-logic.test.js
 *
 * These tests mirror the Python implementation in shared/sorting_logic.py
 * to guarantee cross-runtime parity (JS ↔ Python).
 *
 * Covers:
 *   1.  Constants parity with shared/constants.py
 *   2.  isImageFile (extension, case, edge cases, Windows paths)
 *   3.  naturalSortKey (chunking, zero-padding, non-string input)
 *   4.  compareNaturalKeys (numeric vs lexical, mixed types)
 *   5.  sortImages — natural sorting
 *   6.  sortImages — priority-char routing
 *   7.  sortImages — options (natural off, custom chars, multi-char)
 *   8.  sortImages — path handling (POSIX, Windows, mixed)
 *   9.  sortImages — edge cases (empty, single, undefined/null chars)
 *   10. Non-mutation guarantee
 *   11. getBasename / normalizePath (path helpers)
 *
 * Runtime: Vitest
 * =====================================================================
 */

import { describe, it, expect } from 'vitest';
import {
    IMAGE_EXTENSIONS,
    DEFAULT_PRIORITY_CHARS,
    getBasename,
    normalizePath,
    isImageFile,
    naturalSortKey,
    compareNaturalKeys,
    sortImages
} from '../shared/sorting-logic.js';

// =====================================================================
// § 01 — CONSTANTS PARITY
// =====================================================================

describe('Constants', () => {
    it('should expose exactly 7 IMAGE_EXTENSIONS in canonical order', () => {
        expect(IMAGE_EXTENSIONS).toEqual([
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'
        ]);
    });

    it('should not include extensions removed during constants sync', () => {
        // These were dropped to align with shared/constants.py
        expect(IMAGE_EXTENSIONS).not.toContain('.tif');
        expect(IMAGE_EXTENSIONS).not.toContain('.svg');
    });

    it('should default priority char to "!"', () => {
        expect(DEFAULT_PRIORITY_CHARS).toBe('!');
    });
});

// =====================================================================
// § 02 — getBasename / normalizePath
// =====================================================================

describe('getBasename', () => {
    it('should extract the last segment of a POSIX path', () => {
        expect(getBasename('folder/subfolder/image.jpg')).toBe('image.jpg');
        expect(getBasename('/absolute/path/photo.png')).toBe('photo.png');
    });

    it('should extract the last segment of a Windows path', () => {
        expect(getBasename('folder\\subfolder\\image.jpg')).toBe('image.jpg');
        expect(getBasename('C:\\Users\\Photos\\pic.png')).toBe('pic.png');
    });

    it('should handle mixed separators', () => {
        expect(getBasename('folder\\sub/photo.jpg')).toBe('photo.jpg');
        expect(getBasename('a\\b/c\\d.jpg')).toBe('d.jpg');
    });

    it('should return the input when there is no separator', () => {
        expect(getBasename('image.jpg')).toBe('image.jpg');
    });

    it('should return empty string for empty / null / non-string input', () => {
        expect(getBasename('')).toBe('');
        expect(getBasename(null)).toBe('');
        expect(getBasename(undefined)).toBe('');
        expect(getBasename(42)).toBe('');
    });
});

describe('normalizePath', () => {
    it('should convert backslashes to forward slashes', () => {
        expect(normalizePath('folder\\subfolder\\image.jpg'))
            .toBe('folder/subfolder/image.jpg');
    });

    it('should strip a leading "./"', () => {
        expect(normalizePath('./folder/image.jpg')).toBe('folder/image.jpg');
    });

    it('should combine both normalizations', () => {
        expect(normalizePath('.\\folder\\image.jpg')).toBe('folder/image.jpg');
    });

    it('should leave already-normalized paths untouched', () => {
        expect(normalizePath('folder/image.jpg')).toBe('folder/image.jpg');
    });

    it('should handle empty / null / non-string input', () => {
        expect(normalizePath('')).toBe('');
        expect(normalizePath(null)).toBe('');
        expect(normalizePath(undefined)).toBe('');
    });
});

// =====================================================================
// § 03 — isImageFile
// =====================================================================

describe('isImageFile', () => {
    it('should recognize .jpg files (case-insensitive)', () => {
        expect(isImageFile('photo.jpg')).toBe(true);
        expect(isImageFile('photo.JPG')).toBe(true);
        expect(isImageFile('photo.JpG')).toBe(true);
    });

    it('should recognize .jpeg files', () => {
        expect(isImageFile('photo.jpeg')).toBe(true);
        expect(isImageFile('photo.JPEG')).toBe(true);
    });

    it('should recognize .png files', () => {
        expect(isImageFile('photo.png')).toBe(true);
        expect(isImageFile('photo.PNG')).toBe(true);
    });

    it('should recognize .gif files', () => {
        expect(isImageFile('animation.gif')).toBe(true);
    });

    it('should recognize .bmp files', () => {
        expect(isImageFile('bitmap.bmp')).toBe(true);
    });

    it('should recognize .tiff files', () => {
        expect(isImageFile('photo.tiff')).toBe(true);
    });

    it('should recognize .webp files', () => {
        expect(isImageFile('photo.webp')).toBe(true);
    });

    it('should reject non-image files', () => {
        expect(isImageFile('document.pdf')).toBe(false);
        expect(isImageFile('text.txt')).toBe(false);
        expect(isImageFile('data.json')).toBe(false);
        expect(isImageFile('script.js')).toBe(false);
    });

    it('should reject extensions removed during sync', () => {
        expect(isImageFile('scan.tif')).toBe(false);
        expect(isImageFile('logo.svg')).toBe(false);
    });

    it('should handle files with multiple dots', () => {
        expect(isImageFile('file.name.with.dots.jpg')).toBe(true);
        expect(isImageFile('file.name.with.dots.pdf')).toBe(false);
    });

    it('should handle files without extensions', () => {
        expect(isImageFile('noextension')).toBe(false);
    });

    it('should reject hidden files (dot-prefixed, no real ext)', () => {
        expect(isImageFile('.jpg')).toBe(false);
        expect(isImageFile('.gitignore')).toBe(false);
    });

    it('should accept dotfiles that still have a valid extension', () => {
        expect(isImageFile('.hidden.jpg')).toBe(true);
    });

    it('should reject trailing-dot filenames', () => {
        expect(isImageFile('file.')).toBe(false);
    });

    it('should handle POSIX paths', () => {
        expect(isImageFile('folder/subfolder/image.jpg')).toBe(true);
        expect(isImageFile('/absolute/path/photo.gif')).toBe(true);
    });

    it('should handle Windows paths', () => {
        expect(isImageFile('folder\\subfolder\\image.jpg')).toBe(true);
        expect(isImageFile('C:\\Users\\Photos\\pic.png')).toBe(true);
    });

    it('should return false for empty / null / non-string input', () => {
        expect(isImageFile('')).toBe(false);
        expect(isImageFile(null)).toBe(false);
        expect(isImageFile(undefined)).toBe(false);
        expect(isImageFile(42)).toBe(false);
        expect(isImageFile({})).toBe(false);
    });
});

// =====================================================================
// § 04 — naturalSortKey
// =====================================================================

describe('naturalSortKey', () => {
    it('should split text into alternating string / number chunks', () => {
        expect(naturalSortKey('file_1.jpg')).toEqual(['file_', 1, '.jpg']);
        expect(naturalSortKey('file_10.jpg')).toEqual(['file_', 10, '.jpg']);
    });

    it('should handle multiple numbers', () => {
        expect(naturalSortKey('ch1_page10.jpg'))
            .toEqual(['ch', 1, '_page', 10, '.jpg']);
    });

    it('should handle text without numbers', () => {
        expect(naturalSortKey('cover.jpg')).toEqual(['cover.jpg']);
    });

    it('should handle only numbers (leading/trailing empty chunks)', () => {
        expect(naturalSortKey('12345')).toEqual(['', 12345, '']);
    });

    it('should normalize zero-padded numbers', () => {
        expect(naturalSortKey('page_001.jpg')).toEqual(['page_', 1, '.jpg']);
        expect(naturalSortKey('page_1.jpg')).toEqual(['page_', 1, '.jpg']);
    });

    it('should coerce non-string input safely', () => {
        expect(naturalSortKey(null)).toEqual(['']);
        expect(naturalSortKey(undefined)).toEqual(['']);
        expect(naturalSortKey(42)).toEqual(['42']);
        expect(naturalSortKey({})).toEqual(['[object Object]']);
    });
});

// =====================================================================
// § 05 — compareNaturalKeys
// =====================================================================

describe('compareNaturalKeys', () => {
    it('should compare simple numbers correctly', () => {
        expect(compareNaturalKeys('file_1.jpg', 'file_2.jpg')).toBeLessThan(0);
        expect(compareNaturalKeys('file_2.jpg', 'file_1.jpg')).toBeGreaterThan(0);
        expect(compareNaturalKeys('file_1.jpg', 'file_1.jpg')).toBe(0);
    });

    it('should compare numbers numerically not lexically', () => {
        expect(compareNaturalKeys('file_2.jpg', 'file_10.jpg')).toBeLessThan(0);
        expect(compareNaturalKeys('file_10.jpg', 'file_2.jpg')).toBeGreaterThan(0);
    });

    it('should handle different prefixes', () => {
        expect(compareNaturalKeys('a_10.jpg', 'b_1.jpg')).toBeLessThan(0);
        expect(compareNaturalKeys('b_1.jpg', 'a_10.jpg')).toBeGreaterThan(0);
    });

    it('should treat zero-padded and non-padded as equal', () => {
        expect(compareNaturalKeys('page_001.jpg', 'page_1.jpg')).toBe(0);
        expect(compareNaturalKeys('page_010.jpg', 'page_10.jpg')).toBe(0);
    });

    it('should handle multiple numbers in filenames', () => {
        expect(compareNaturalKeys('ch1_page2.jpg', 'ch1_page10.jpg')).toBeLessThan(0);
        expect(compareNaturalKeys('ch1_page10.jpg', 'ch2_page1.jpg')).toBeLessThan(0);
        expect(compareNaturalKeys('ch2_page1.jpg', 'ch10_page1.jpg')).toBeLessThan(0);
    });

    it('should fall back to string comparison for mixed types', () => {
        // "01a" (string chunk) vs "a" (string chunk) — both strings
        expect(compareNaturalKeys('01a', 'a')).not.toBe(0);
        // Numeric vs string at the same position — deterministic
        expect(typeof compareNaturalKeys('1a', 'a1')).toBe('number');
    });

    it('should order shorter keys before longer ones when prefixes match', () => {
        // 'file_1.jpg' vs 'file_1_extra.jpg'
        expect(compareNaturalKeys('file_1.jpg', 'file_1_extra.jpg'))
            .toBeLessThan(0);
    });
});

// =====================================================================
// § 06 — sortImages: natural sorting
// =====================================================================

describe('sortImages — natural sorting', () => {
    it('should sort simple numbers correctly', () => {
        const files = ['file_1.jpg', 'file_2.jpg', 'file_10.jpg', 'file_20.jpg'];
        expect(sortImages(files)).toEqual([
            'file_1.jpg', 'file_2.jpg', 'file_10.jpg', 'file_20.jpg'
        ]);
    });

    it('should sort mixed order files', () => {
        const files = ['file_10.jpg', 'file_1.jpg', 'file_2.jpg', 'file_20.jpg'];
        expect(sortImages(files)).toEqual([
            'file_1.jpg', 'file_2.jpg', 'file_10.jpg', 'file_20.jpg'
        ]);
    });

    it('should treat zero-padded and non-padded as stable-equal', () => {
        const files = [
            'page_001.jpg', 'page_1.jpg',
            'page_10.jpg', 'page_010.jpg', 'page_2.jpg'
        ];
        const sorted = sortImages(files);

        // All items preserved
        expect(sorted).toHaveLength(5);
        expect(new Set(sorted)).toEqual(new Set(files));

        // Relative ordering by numeric value
        const idx = (s) => sorted.indexOf(s);
        expect(idx('page_1.jpg')).toBeLessThan(idx('page_2.jpg'));
        expect(idx('page_2.jpg')).toBeLessThan(idx('page_10.jpg'));
    });

    it('should sort different prefixes correctly', () => {
        const files = ['b_10.jpg', 'a_2.jpg', 'b_1.jpg', 'a_10.jpg'];
        expect(sortImages(files)).toEqual([
            'a_2.jpg', 'a_10.jpg', 'b_1.jpg', 'b_10.jpg'
        ]);
    });

    it('should sort multiple numbers in filenames', () => {
        const files = [
            'ch1_page10.jpg', 'ch1_page2.jpg',
            'ch2_page1.jpg', 'ch10_page1.jpg'
        ];
        expect(sortImages(files)).toEqual([
            'ch1_page2.jpg', 'ch1_page10.jpg',
            'ch2_page1.jpg', 'ch10_page1.jpg'
        ]);
    });
});

// =====================================================================
// § 07 — sortImages: priority files
// =====================================================================

describe('sortImages — priority files', () => {
    it('should place priority files first with default ! character', () => {
        const files = [
            'page_10.jpg', 'page_1.jpg', '!cover.jpg',
            'page_2.jpg', '!back.jpg', 'page_20.jpg'
        ];
        expect(sortImages(files)).toEqual([
            '!back.jpg', '!cover.jpg',
            'page_1.jpg', 'page_2.jpg', 'page_10.jpg', 'page_20.jpg'
        ]);
    });

    it('should sort priority files with numbers naturally', () => {
        const files = [
            'page_5.jpg', '!intro_2.jpg', 'page_1.jpg',
            '!intro_10.jpg', '!intro_1.jpg', 'page_10.jpg'
        ];
        expect(sortImages(files)).toEqual([
            '!intro_1.jpg', '!intro_2.jpg', '!intro_10.jpg',
            'page_1.jpg', 'page_5.jpg', 'page_10.jpg'
        ]);
    });

    it('should handle only normal files (no priority)', () => {
        const files = ['page_10.jpg', 'page_1.jpg', 'page_2.jpg'];
        expect(sortImages(files)).toEqual([
            'page_1.jpg', 'page_2.jpg', 'page_10.jpg'
        ]);
    });

    it('should handle only priority files', () => {
        const files = ['!cover_2.jpg', '!cover_10.jpg', '!cover_1.jpg'];
        expect(sortImages(files)).toEqual([
            '!cover_1.jpg', '!cover_2.jpg', '!cover_10.jpg'
        ]);
    });

    it('should handle real-world scenario with priority files', () => {
        const files = [
            'page_0.jpg', 'page_1.jpg', 'page_9.jpg',
            'page_10.jpg', 'page_11.jpg', 'page_99.jpg', 'page_100.jpg',
            '!front_cover.jpg', '!back_cover.jpg'
        ];
        expect(sortImages(files)).toEqual([
            '!back_cover.jpg', '!front_cover.jpg',
            'page_0.jpg', 'page_1.jpg', 'page_9.jpg',
            'page_10.jpg', 'page_11.jpg', 'page_99.jpg', 'page_100.jpg'
        ]);
    });
});

// =====================================================================
// § 08 — sortImages: options
// =====================================================================

describe('sortImages — options', () => {
    it('should disable natural sorting when useNaturalSort=false', () => {
        const files = ['page_10.jpg', 'page_1.jpg', 'page_2.jpg'];
        // Lexical sort: 1 < 10 < 2
        expect(sortImages(files, false)).toEqual([
            'page_1.jpg', 'page_10.jpg', 'page_2.jpg'
        ]);
    });

    it('should use custom priority character (@)', () => {
        const files = [
            'page_10.jpg', 'page_1.jpg', '@cover.jpg',
            'page_2.jpg', '@back.jpg'
        ];
        expect(sortImages(files, true, '@')).toEqual([
            '@back.jpg', '@cover.jpg',
            'page_1.jpg', 'page_2.jpg', 'page_10.jpg'
        ]);
    });

    it('should support multiple priority characters (!@)', () => {
        const files = [
            'page_10.jpg', '!cover.jpg', '@special.jpg',
            'page_1.jpg', '!intro.jpg', '@bonus.jpg'
        ];
        expect(sortImages(files, true, '!@')).toEqual([
            // Priority group: '!' sorts before '@' in ASCII
            '!cover.jpg', '!intro.jpg', '@bonus.jpg', '@special.jpg',
            // Normal group
            'page_1.jpg', 'page_10.jpg'
        ]);
    });

    it('should disable priority routing when priorityChars is empty string', () => {
        const files = [
            'page_10.jpg', '!cover.jpg', 'page_1.jpg', '@special.jpg'
        ];
        // Empty string → no priority. Natural sort places '!' and '@'
        // before letters (ASCII), so the visible order is the same as
        // the priority-routed order, but no priority logic is applied.
        expect(sortImages(files, true, '')).toEqual([
            '!cover.jpg', '@special.jpg', 'page_1.jpg', 'page_10.jpg'
        ]);
    });

    it('should combine disabled natural sort with priority characters', () => {
        const files = [
            'page_10.jpg', '!cover_10.jpg', 'page_1.jpg',
            '!cover_1.jpg', 'page_2.jpg'
        ];
        // Priority group: lexical sort → !cover_1, !cover_10
        // Normal group  : lexical sort → page_1, page_10, page_2
        expect(sortImages(files, false, '!')).toEqual([
            '!cover_1.jpg', '!cover_10.jpg',
            'page_1.jpg', 'page_10.jpg', 'page_2.jpg'
        ]);
    });
});

// =====================================================================
// § 09 — sortImages: path handling
// =====================================================================

describe('sortImages — paths', () => {
    it('should handle POSIX file paths with directories', () => {
        const files = [
            'path/to/page_10.jpg', 'path/to/page_1.jpg',
            'path/to/!cover.jpg', 'path/to/page_2.jpg'
        ];
        expect(sortImages(files)).toEqual([
            'path/to/!cover.jpg',
            'path/to/page_1.jpg',
            'path/to/page_2.jpg',
            'path/to/page_10.jpg'
        ]);
    });

    it('should handle Windows file paths', () => {
        const files = [
            'folder\\page_10.jpg',
            'folder\\page_1.jpg',
            'folder\\!cover.jpg',
            'folder\\page_2.jpg'
        ];
        expect(sortImages(files)).toEqual([
            'folder\\!cover.jpg',
            'folder\\page_1.jpg',
            'folder\\page_2.jpg',
            'folder\\page_10.jpg'
        ]);
    });

    it('should handle mixed POSIX and Windows paths', () => {
        const files = [
            'page_10.jpg',
            'subdir/page_1.jpg',
            '!cover.jpg',
            'other\\page_2.jpg'
        ];
        expect(sortImages(files)).toEqual([
            '!cover.jpg',
            'subdir/page_1.jpg',
            'other\\page_2.jpg',
            'page_10.jpg'
        ]);
    });
});

// =====================================================================
// § 10 — sortImages: edge cases
// =====================================================================

describe('sortImages — edge cases', () => {
    it('should handle empty array', () => {
        expect(sortImages([])).toEqual([]);
    });

    it('should return empty array for non-array input', () => {
        expect(sortImages(null)).toEqual([]);
        expect(sortImages(undefined)).toEqual([]);
        expect(sortImages(42)).toEqual([]);
        expect(sortImages('not-an-array')).toEqual([]);
    });

    it('should handle single file', () => {
        expect(sortImages(['single.jpg'])).toEqual(['single.jpg']);
    });

    it('should handle files with special characters (- and _)', () => {
        const files = ['file-10.jpg', 'file-1.jpg', 'file_10.jpg', 'file_1.jpg'];
        const sorted = sortImages(files);

        // Membership check (order between '-' and '_' depends on ASCII)
        expect(sorted).toContain('file-1.jpg');
        expect(sorted).toContain('file-10.jpg');
        expect(sorted).toContain('file_1.jpg');
        expect(sorted).toContain('file_10.jpg');
        expect(sorted).toHaveLength(4);
    });

    it('should sort files with no numbers alphabetically', () => {
        const files = ['zebra.jpg', 'apple.jpg', 'banana.jpg'];
        expect(sortImages(files)).toEqual([
            'apple.jpg', 'banana.jpg', 'zebra.jpg'
        ]);
    });

    it('should apply default priority when undefined is passed', () => {
        const files = ['page_2.jpg', '!cover.jpg', 'page_1.jpg'];
        // undefined → default param kicks in → priorityChars = '!'
        // So `!cover.jpg` IS treated as priority (goes first)
        expect(sortImages(files, true, undefined)).toEqual([
            '!cover.jpg', 'page_1.jpg', 'page_2.jpg'
        ]);
    });

    it('should NOT apply priority when null is passed', () => {
        const files = ['page_2.jpg', '!cover.jpg', 'page_1.jpg'];
        // null → NOT a string → empty prioritySet → no routing
        // But natural sort still places '!' before letters (ASCII 0x21)
        // so the visible order happens to be the same
        expect(sortImages(files, true, null)).toEqual([
            '!cover.jpg', 'page_1.jpg', 'page_2.jpg'
        ]);
    });

    it('should skip non-string entries silently', () => {
        const mixed = ['img_1.jpg', 42, null, 'img_2.jpg', undefined];
        const result = sortImages(mixed, true, '!');

        expect(result).toContain('img_1.jpg');
        expect(result).toContain('img_2.jpg');
        expect(result).not.toContain(42);
        expect(result).not.toContain(null);
        expect(result).not.toContain(undefined);
    });

    it('should be stable across multiple calls', () => {
        const files = ['page_10.jpg', 'page_2.jpg', 'page_1.jpg'];
        const a = sortImages(files);
        const b = sortImages(files);
        const c = sortImages(files);
        expect(a).toEqual(b);
        expect(b).toEqual(c);
    });
});

// =====================================================================
// § 11 — Non-mutation guarantee
// =====================================================================

describe('sortImages — non-mutation guarantee', () => {
    it('should NOT mutate the input array', () => {
        const files = ['b.jpg', 'a.jpg', 'c.jpg'];
        const copy = [...files];

        sortImages(files);

        expect(files).toEqual(copy);
    });

    it('should return a NEW array (not the same reference)', () => {
        const files = ['b.jpg', 'a.jpg'];
        const result = sortImages(files);
        expect(result).not.toBe(files);
    });

    it('should not mutate even when priority routing is active', () => {
        const files = ['page_1.jpg', '!cover.jpg', 'page_2.jpg'];
        const copy = [...files];

        sortImages(files, true, '!');

        expect(files).toEqual(copy);
    });
});

// =====================================================================
// § 12 — Python/JS parity spot-checks
// =====================================================================

describe('Python ↔ JS parity spot-checks', () => {
    it('should match Python behavior for priority + natural sort', () => {
        // Input mirroring the Python docstring example
        const input = [
            'page_10.jpg', 'page_1.jpg', '!cover.jpg',
            'page_2.jpg', '!back.jpg'
        ];
        const expected = [
            '!back.jpg', '!cover.jpg',
            'page_1.jpg', 'page_2.jpg', 'page_10.jpg'
        ];
        expect(sortImages(input, true, '!')).toEqual(expected);
    });

    it('should match Python behavior for disabled natural sort', () => {
        const input = ['page_10.jpg', 'page_1.jpg', '!cover.jpg', 'page_2.jpg', '!back.jpg'];
        const expected = [
            '!back.jpg', '!cover.jpg',
            'page_1.jpg', 'page_10.jpg', 'page_2.jpg'
        ];
        expect(sortImages(input, false, '!')).toEqual(expected);
    });

    it('should match Python behavior for multi-char priority', () => {
        const input = ['page_10.jpg', '@special.jpg', '!cover.jpg', 'page_2.jpg'];
        const expected = [
            '!cover.jpg', '@special.jpg',
            'page_2.jpg', 'page_10.jpg'
        ];
        expect(sortImages(input, true, '!@')).toEqual(expected);
    });
});
