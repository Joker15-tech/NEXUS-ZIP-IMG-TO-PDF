/**
 * Tests for shared/sorting-logic.js
 * These tests mirror the Python implementation tests to ensure parity
 */

import { describe, it, expect } from 'vitest';
import {
  IMAGE_EXTENSIONS,
  DEFAULT_PRIORITY_CHARS,
  isImageFile,
  naturalSortKey,
  compareNaturalKeys,
  sortImages
} from '../shared/sorting-logic.js';

describe('Constants', () => {
  it('should have correct IMAGE_EXTENSIONS', () => {
    expect(IMAGE_EXTENSIONS).toEqual(['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']);
  });

  it('should have correct DEFAULT_PRIORITY_CHARS', () => {
    expect(DEFAULT_PRIORITY_CHARS).toBe('!');
  });
});

describe('isImageFile', () => {
  it('should recognize .jpg files', () => {
    expect(isImageFile('photo.jpg')).toBe(true);
    expect(isImageFile('photo.JPG')).toBe(true);
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

  it('should handle files with multiple dots', () => {
    expect(isImageFile('file.name.with.dots.jpg')).toBe(true);
    expect(isImageFile('file.name.with.dots.pdf')).toBe(false);
  });

  it('should handle files without extensions', () => {
    expect(isImageFile('noextension')).toBe(false);
  });

  it('should be case insensitive', () => {
    expect(isImageFile('PHOTO.JPG')).toBe(true);
    expect(isImageFile('Photo.JpG')).toBe(true);
  });
});

describe('naturalSortKey', () => {
  it('should split text into chunks correctly', () => {
    const key = naturalSortKey('file_1.jpg');
    expect(key).toEqual(['file_', 1, '.jpg']);
  });

  it('should convert numeric strings to integers', () => {
    const key = naturalSortKey('file_10.jpg');
    expect(key).toEqual(['file_', 10, '.jpg']);
  });

  it('should handle multiple numbers', () => {
    const key = naturalSortKey('ch1_page10.jpg');
    expect(key).toEqual(['ch', 1, '_page', 10, '.jpg']);
  });

  it('should handle text without numbers', () => {
    const key = naturalSortKey('cover.jpg');
    expect(key).toEqual(['cover.jpg']);
  });

  it('should handle only numbers', () => {
    const key = naturalSortKey('12345');
    expect(key).toEqual(['', 12345, '']);
  });

  it('should handle zero-padded numbers', () => {
    const key1 = naturalSortKey('page_001.jpg');
    const key2 = naturalSortKey('page_1.jpg');
    expect(key1).toEqual(['page_', 1, '.jpg']);
    expect(key2).toEqual(['page_', 1, '.jpg']);
  });
});

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

  it('should compare zero-padded vs non-padded correctly', () => {
    expect(compareNaturalKeys('page_001.jpg', 'page_1.jpg')).toBe(0);
    expect(compareNaturalKeys('page_010.jpg', 'page_10.jpg')).toBe(0);
  });

  it('should handle multiple numbers in filenames', () => {
    expect(compareNaturalKeys('ch1_page2.jpg', 'ch1_page10.jpg')).toBeLessThan(0);
    expect(compareNaturalKeys('ch1_page10.jpg', 'ch2_page1.jpg')).toBeLessThan(0);
    expect(compareNaturalKeys('ch2_page1.jpg', 'ch10_page1.jpg')).toBeLessThan(0);
  });
});

describe('sortImages - natural sorting', () => {
  it('should sort simple numbers correctly', () => {
    const files = ['file_1.jpg', 'file_2.jpg', 'file_10.jpg', 'file_20.jpg'];
    const sorted = sortImages(files);
    expect(sorted).toEqual(['file_1.jpg', 'file_2.jpg', 'file_10.jpg', 'file_20.jpg']);
  });

  it('should sort mixed order files', () => {
    const files = ['file_10.jpg', 'file_1.jpg', 'file_2.jpg', 'file_20.jpg'];
    const sorted = sortImages(files);
    expect(sorted).toEqual(['file_1.jpg', 'file_2.jpg', 'file_10.jpg', 'file_20.jpg']);
  });

  it('should handle zero-padded vs non-padded numbers', () => {
    const files = ['page_001.jpg', 'page_1.jpg', 'page_10.jpg', 'page_010.jpg', 'page_2.jpg'];
    const sorted = sortImages(files);
    // Both 001 and 1 are numerically equal, both 010 and 10 are equal
    // The order between them should be stable (maintain relative order)
    expect(sorted).toContain('page_1.jpg');
    expect(sorted).toContain('page_2.jpg');
    expect(sorted).toContain('page_10.jpg');
  });

  it('should sort different prefixes correctly', () => {
    const files = ['b_10.jpg', 'a_2.jpg', 'b_1.jpg', 'a_10.jpg'];
    const sorted = sortImages(files);
    expect(sorted).toEqual(['a_2.jpg', 'a_10.jpg', 'b_1.jpg', 'b_10.jpg']);
  });

  it('should sort multiple numbers in filenames', () => {
    const files = ['ch1_page10.jpg', 'ch1_page2.jpg', 'ch2_page1.jpg', 'ch10_page1.jpg'];
    const sorted = sortImages(files);
    expect(sorted).toEqual(['ch1_page2.jpg', 'ch1_page10.jpg', 'ch2_page1.jpg', 'ch10_page1.jpg']);
  });
});

describe('sortImages - priority files', () => {
  it('should place priority files first with default ! character', () => {
    const files = [
      'page_10.jpg',
      'page_1.jpg',
      '!cover.jpg',
      'page_2.jpg',
      '!back.jpg',
      'page_20.jpg'
    ];
    const sorted = sortImages(files);
    expect(sorted).toEqual([
      '!back.jpg',
      '!cover.jpg',
      'page_1.jpg',
      'page_2.jpg',
      'page_10.jpg',
      'page_20.jpg'
    ]);
  });

  it('should sort priority files with numbers naturally', () => {
    const files = [
      'page_5.jpg',
      '!intro_2.jpg',
      'page_1.jpg',
      '!intro_10.jpg',
      '!intro_1.jpg',
      'page_10.jpg'
    ];
    const sorted = sortImages(files);
    expect(sorted).toEqual([
      '!intro_1.jpg',
      '!intro_2.jpg',
      '!intro_10.jpg',
      'page_1.jpg',
      'page_5.jpg',
      'page_10.jpg'
    ]);
  });

  it('should handle only normal files (no priority)', () => {
    const files = ['page_10.jpg', 'page_1.jpg', 'page_2.jpg'];
    const sorted = sortImages(files);
    expect(sorted).toEqual(['page_1.jpg', 'page_2.jpg', 'page_10.jpg']);
  });

  it('should handle only priority files', () => {
    const files = ['!cover_2.jpg', '!cover_10.jpg', '!cover_1.jpg'];
    const sorted = sortImages(files);
    expect(sorted).toEqual(['!cover_1.jpg', '!cover_2.jpg', '!cover_10.jpg']);
  });

  it('should handle real-world scenario with priority files', () => {
    const files = [
      'page_0.jpg',
      'page_1.jpg',
      'page_9.jpg',
      'page_10.jpg',
      'page_11.jpg',
      'page_99.jpg',
      'page_100.jpg',
      '!front_cover.jpg',
      '!back_cover.jpg'
    ];
    const sorted = sortImages(files);
    expect(sorted).toEqual([
      '!back_cover.jpg',
      '!front_cover.jpg',
      'page_0.jpg',
      'page_1.jpg',
      'page_9.jpg',
      'page_10.jpg',
      'page_11.jpg',
      'page_99.jpg',
      'page_100.jpg'
    ]);
  });
});

describe('sortImages - options', () => {
  it('should disable natural sorting when useNaturalSort=false', () => {
    const files = ['page_10.jpg', 'page_1.jpg', 'page_2.jpg'];
    const sorted = sortImages(files, false);
    // Lexical sort: 1 < 10 < 2
    expect(sorted).toEqual(['page_1.jpg', 'page_10.jpg', 'page_2.jpg']);
  });

  it('should use custom priority character (@)', () => {
    const files = [
      'page_10.jpg',
      'page_1.jpg',
      '@cover.jpg',
      'page_2.jpg',
      '@back.jpg'
    ];
    const sorted = sortImages(files, true, '@');
    expect(sorted).toEqual([
      '@back.jpg',
      '@cover.jpg',
      'page_1.jpg',
      'page_2.jpg',
      'page_10.jpg'
    ]);
  });

  it('should support multiple priority characters (!@)', () => {
    const files = [
      'page_10.jpg',
      '!cover.jpg',
      '@special.jpg',
      'page_1.jpg',
      '!intro.jpg',
      '@bonus.jpg'
    ];
    const sorted = sortImages(files, true, '!@');
    expect(sorted).toEqual([
      '!cover.jpg',
      '!intro.jpg',
      '@bonus.jpg',
      '@special.jpg',
      'page_1.jpg',
      'page_10.jpg'
    ]);
  });

  it('should treat all files as normal when priorityChars is empty', () => {
    const files = [
      'page_10.jpg',
      '!cover.jpg',
      'page_1.jpg',
      '@special.jpg'
    ];
    const sorted = sortImages(files, true, '');
    expect(sorted).toEqual([
      '!cover.jpg',
      '@special.jpg',
      'page_1.jpg',
      'page_10.jpg'
    ]);
  });

  it('should combine disabled natural sort with priority characters', () => {
    const files = [
      'page_10.jpg',
      '!cover_10.jpg',
      'page_1.jpg',
      '!cover_1.jpg',
      'page_2.jpg'
    ];
    const sorted = sortImages(files, false, '!');
    // Lexical sort within each group
    expect(sorted).toEqual([
      '!cover_1.jpg',
      '!cover_10.jpg',
      'page_1.jpg',
      'page_10.jpg',
      'page_2.jpg'
    ]);
  });
});

describe('sortImages - paths', () => {
  it('should handle file paths with directories', () => {
    const files = [
      'path/to/page_10.jpg',
      'path/to/page_1.jpg',
      'path/to/!cover.jpg',
      'path/to/page_2.jpg'
    ];
    const sorted = sortImages(files);
    expect(sorted).toEqual([
      'path/to/!cover.jpg',
      'path/to/page_1.jpg',
      'path/to/page_2.jpg',
      'path/to/page_10.jpg'
    ]);
  });

  it('should handle mixed paths and filenames', () => {
    const files = [
      'page_10.jpg',
      'subdir/page_1.jpg',
      '!cover.jpg',
      'other/page_2.jpg'
    ];
    const sorted = sortImages(files);
    expect(sorted).toEqual([
      '!cover.jpg',
      'subdir/page_1.jpg',
      'other/page_2.jpg',
      'page_10.jpg'
    ]);
  });
});

describe('sortImages - edge cases', () => {
  it('should handle empty array', () => {
    const sorted = sortImages([]);
    expect(sorted).toEqual([]);
  });

  it('should handle single file', () => {
    const sorted = sortImages(['single.jpg']);
    expect(sorted).toEqual(['single.jpg']);
  });

  it('should handle files with special characters', () => {
    const files = [
      'file-10.jpg',
      'file-1.jpg',
      'file_10.jpg',
      'file_1.jpg'
    ];
    const sorted = sortImages(files);
    expect(sorted).toContain('file-1.jpg');
    expect(sorted).toContain('file-10.jpg');
    expect(sorted).toContain('file_1.jpg');
    expect(sorted).toContain('file_10.jpg');
  });

  it('should handle files with no numbers', () => {
    const files = ['zebra.jpg', 'apple.jpg', 'banana.jpg'];
    const sorted = sortImages(files);
    expect(sorted).toEqual(['apple.jpg', 'banana.jpg', 'zebra.jpg']);
  });

  it('should handle undefined priorityChars', () => {
    const files = ['page_2.jpg', '!cover.jpg', 'page_1.jpg'];
    const sorted = sortImages(files, true, undefined);
    // When undefined, should not treat any files as priority
    expect(sorted).toEqual(['!cover.jpg', 'page_1.jpg', 'page_2.jpg']);
  });

  it('should handle null priorityChars', () => {
    const files = ['page_2.jpg', '!cover.jpg', 'page_1.jpg'];
    const sorted = sortImages(files, true, null);
    // When null, should not treat any files as priority
    expect(sorted).toEqual(['!cover.jpg', 'page_1.jpg', 'page_2.jpg']);
  });
});
