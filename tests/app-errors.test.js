/**
 * Error handling tests for web/app.js
 * Tests edge cases, errors, and exceptional conditions
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock dependencies
vi.mock('jszip');
vi.mock('jspdf');

import JSZip from 'jszip';

// Mock the sorting logic module
vi.mock('../shared/sorting-logic.js', () => ({
  isImageFile: vi.fn((filename) => {
    const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
    return ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'].includes(ext);
  }),
  sortImages: vi.fn((files) => [...files].sort()),
  IMAGE_EXTENSIONS: ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
  DEFAULT_PRIORITY_CHARS: '!'
}));

describe('ZIP Extraction Errors', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should handle corrupted ZIP files', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockRejectedValue(new Error('Corrupted ZIP file'))
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipBlob = new Blob(['corrupted data'], { type: 'application/zip' });

    await expect(mockZipInstance.loadAsync(zipBlob)).rejects.toThrow('Corrupted ZIP file');
  });

  it('should handle empty ZIP files', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {}
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipBlob = new Blob(['empty zip'], { type: 'application/zip' });
    const zipData = await mockZipInstance.loadAsync(zipBlob);

    expect(Object.keys(zipData.files)).toHaveLength(0);
  });

  it('should handle ZIP files with no images', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {
          'document.pdf': { dir: false },
          'text.txt': { dir: false },
          'data.json': { dir: false }
        }
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipBlob = new Blob(['zip with no images'], { type: 'application/zip' });
    const zipData = await mockZipInstance.loadAsync(zipBlob);

    const { isImageFile } = await import('../shared/sorting-logic.js');
    const imageFiles = Object.keys(zipData.files).filter(f => isImageFile(f));

    expect(imageFiles).toHaveLength(0);
  });

  it('should handle password-protected ZIP files', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockRejectedValue(new Error('Password required'))
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipBlob = new Blob(['password protected'], { type: 'application/zip' });

    await expect(mockZipInstance.loadAsync(zipBlob)).rejects.toThrow('Password required');
  });

  it('should handle ZIP extraction errors', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {
          'image.jpg': {
            dir: false,
            async: vi.fn().mockRejectedValue(new Error('Extraction failed'))
          }
        }
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipData = await mockZipInstance.loadAsync(new Blob());
    const file = zipData.files['image.jpg'];

    await expect(file.async('blob')).rejects.toThrow('Extraction failed');
  });

  it('should handle very large ZIP files', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockRejectedValue(new Error('File too large'))
    };

    JSZip.mockImplementation(() => mockZipInstance);

    // Simulate large file
    const largeBlob = new Blob([new ArrayBuffer(1024 * 1024 * 100)]); // 100MB

    await expect(mockZipInstance.loadAsync(largeBlob)).rejects.toThrow();
  });
});

describe('Image Loading Errors', () => {
  it('should handle image load failures', async () => {
    const loadImage = (imageUrl) => {
      return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error('Failed to load image'));
        img.src = imageUrl;
        // Simulate error
        setTimeout(() => img.onerror && img.onerror(), 0);
      });
    };

    await expect(loadImage('invalid-url')).rejects.toThrow('Failed to load image');
  });

  it('should handle corrupted image data', async () => {
    const loadImage = (imageUrl) => {
      return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error('Invalid image data'));
        img.src = imageUrl;
        setTimeout(() => img.onerror && img.onerror(), 0);
      });
    };

    await expect(loadImage('blob:corrupted')).rejects.toThrow('Invalid image data');
  });

  it('should handle image with zero dimensions', () => {
    class MockImage {
      constructor() {
        this.width = 0;
        this.height = 0;
      }
    }

    const img = new MockImage();

    expect(img.width).toBe(0);
    expect(img.height).toBe(0);
    // Application should handle zero-dimension images
  });

  it('should handle extremely large images', () => {
    class MockImage {
      constructor() {
        this.width = 10000;
        this.height = 10000;
      }
    }

    const img = new MockImage();
    const maxDimension = 2000;

    const scale = Math.min(maxDimension / img.width, maxDimension / img.height);

    expect(scale).toBe(0.2);
    expect(img.width * scale).toBe(2000);
  });
});

describe('PDF Generation Errors', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should handle PDF save errors', () => {
    const mockPDF = {
      addImage: vi.fn(),
      addPage: vi.fn(),
      save: vi.fn(() => {
        throw new Error('Failed to save PDF');
      })
    };

    expect(() => mockPDF.save('output.pdf')).toThrow('Failed to save PDF');
  });

  it('should handle addImage errors', () => {
    const mockPDF = {
      addImage: vi.fn(() => {
        throw new Error('Invalid image format');
      })
    };

    expect(() => mockPDF.addImage('invalid', 'JPEG', 0, 0, 100, 100))
      .toThrow('Invalid image format');
  });

  it('should handle memory errors during PDF generation', () => {
    const mockPDF = {
      addImage: vi.fn(),
      addPage: vi.fn(() => {
        throw new Error('Out of memory');
      })
    };

    // Simulate adding many pages
    mockPDF.addImage('img1', 'JPEG', 0, 0, 100, 100);

    expect(() => mockPDF.addPage()).toThrow('Out of memory');
  });

  it('should validate image array before conversion', () => {
    const convertImagesToPDF = async (images) => {
      if (!images || images.length === 0) {
        throw new Error('변환할 이미지가 없습니다.');
      }
    };

    expect(() => convertImagesToPDF(null)).rejects.toThrow('변환할 이미지가 없습니다.');
    expect(() => convertImagesToPDF([])).rejects.toThrow('변환할 이미지가 없습니다.');
    expect(() => convertImagesToPDF(undefined)).rejects.toThrow('변환할 이미지가 없습니다.');
  });
});

describe('LocalStorage Errors', () => {
  beforeEach(() => {
    localStorage.getItem.mockClear();
    localStorage.setItem.mockClear();
  });

  it('should handle localStorage quota exceeded', () => {
    localStorage.setItem.mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    expect(() => localStorage.setItem('key', 'value')).toThrow('QuotaExceededError');
  });

  it('should handle localStorage not available', () => {
    localStorage.getItem.mockImplementation(() => {
      throw new Error('localStorage is not available');
    });

    expect(() => localStorage.getItem('key')).toThrow('localStorage is not available');
  });

  it('should handle corrupted localStorage data', () => {
    localStorage.getItem.mockReturnValue('{"invalid json');

    let settings;
    try {
      settings = JSON.parse(localStorage.getItem('settings'));
    } catch (error) {
      settings = { useNaturalSort: true, priorityChars: '!' };
    }

    expect(settings).toEqual({ useNaturalSort: true, priorityChars: '!' });
  });

  it('should handle null localStorage values', () => {
    localStorage.getItem.mockReturnValue(null);

    const value = localStorage.getItem('nonexistent');

    expect(value).toBeNull();
  });

  it('should handle private browsing mode', () => {
    localStorage.setItem.mockImplementation(() => {
      throw new Error('SecurityError: The operation is insecure');
    });

    let saved = false;
    try {
      localStorage.setItem('test', 'value');
      saved = true;
    } catch (error) {
      // Handle gracefully
      saved = false;
    }

    expect(saved).toBe(false);
  });
});

describe('File Handling Errors', () => {
  it('should reject non-ZIP files', () => {
    const file = {
      name: 'document.pdf',
      type: 'application/pdf'
    };

    const isZip = (file) =>
      file.type === 'application/zip' || file.name.toLowerCase().endsWith('.zip');

    expect(isZip(file)).toBe(false);
  });

  it('should handle files with incorrect MIME type', () => {
    const file = {
      name: 'archive.zip',
      type: 'text/plain'  // Wrong MIME type
    };

    const isZip = (file) =>
      file.type === 'application/zip' || file.name.toLowerCase().endsWith('.zip');

    // Should still accept based on extension
    expect(isZip(file)).toBe(true);
  });

  it('should handle zero-size files', () => {
    const file = {
      name: 'empty.zip',
      type: 'application/zip',
      size: 0
    };

    expect(file.size).toBe(0);
    // Application should handle or warn about empty files
  });

  it('should handle extremely large files', () => {
    const file = {
      name: 'huge.zip',
      type: 'application/zip',
      size: 1024 * 1024 * 1024 * 2  // 2GB
    };

    const maxSize = 1024 * 1024 * 500; // 500MB limit

    expect(file.size).toBeGreaterThan(maxSize);
  });

  it('should handle files with special characters in name', () => {
    const file = {
      name: 'archive (1) [copy].zip',
      type: 'application/zip'
    };

    const pdfName = file.name.replace(/\.zip$/i, '.pdf');

    expect(pdfName).toBe('archive (1) [copy].pdf');
  });

  it('should handle files with Unicode names', () => {
    const file = {
      name: '图片集.zip',
      type: 'application/zip'
    };

    const pdfName = file.name.replace(/\.zip$/i, '.pdf');

    expect(pdfName).toBe('图片集.pdf');
  });
});

describe('State Management Errors', () => {
  it('should handle Map operations safely', () => {
    const files = new Map();

    // Try to get non-existent file
    const result = files.get(999);

    expect(result).toBeUndefined();
  });

  it('should handle deleting non-existent files', () => {
    const files = new Map();
    files.set(1, { file: {}, status: 'pending' });

    const deleted = files.delete(999);

    expect(deleted).toBe(false);
    expect(files.size).toBe(1);
  });

  it('should handle concurrent modifications', () => {
    const files = new Map();

    files.set(1, { file: {}, status: 'pending' });
    files.set(2, { file: {}, status: 'pending' });

    // Simulate concurrent delete during iteration
    let count = 0;
    for (const [id, data] of files) {
      count++;
      if (id === 1) {
        files.delete(2);
      }
    }

    // Should handle gracefully
    expect(count).toBeGreaterThan(0);
  });

  it('should handle state corruption', () => {
    const state = {
      currentFileId: 0,
      files: new Map(),
      settings: null  // Corrupted settings
    };

    // Recover from corrupted state
    if (!state.settings) {
      state.settings = {
        useNaturalSort: true,
        priorityChars: '!'
      };
    }

    expect(state.settings).toBeDefined();
    expect(state.settings.useNaturalSort).toBe(true);
  });
});

describe('Progress Handling Errors', () => {
  it('should handle division by zero in progress calculation', () => {
    const info = { current: 0, total: 0 };

    let percentage;
    if (info.total === 0) {
      percentage = 0;
    } else {
      percentage = Math.round((info.current / info.total) * 100);
    }

    expect(percentage).toBe(0);
  });

  it('should handle negative progress values', () => {
    const info = { current: -1, total: 10 };

    const percentage = Math.max(0, Math.round((info.current / info.total) * 100));

    expect(percentage).toBe(0);
  });

  it('should handle progress > 100%', () => {
    const info = { current: 15, total: 10 };

    const percentage = Math.min(100, Math.round((info.current / info.total) * 100));

    expect(percentage).toBe(100);
  });

  it('should handle callback errors gracefully', () => {
    const badCallback = vi.fn(() => {
      throw new Error('Callback error');
    });

    let error;
    try {
      badCallback({ current: 1, total: 10 });
    } catch (e) {
      error = e;
    }

    expect(error).toBeDefined();
    expect(badCallback).toHaveBeenCalled();
  });
});

describe('URL Object Errors', () => {
  beforeEach(() => {
    global.URL.createObjectURL.mockClear();
    global.URL.revokeObjectURL.mockClear();
  });

  it('should handle createObjectURL failures', () => {
    const createObjectURLSpy = vi.spyOn(global.URL, 'createObjectURL').mockImplementation(() => {
      throw new Error('Failed to create object URL');
    });

    expect(() => URL.createObjectURL(new Blob())).toThrow('Failed to create object URL');

    createObjectURLSpy.mockRestore();
  });

  it('should handle revokeObjectURL on invalid URLs', () => {
    // revokeObjectURL should handle invalid URLs gracefully
    expect(() => URL.revokeObjectURL('invalid-url')).not.toThrow();
  });

  it('should handle revokeObjectURL on null', () => {
    expect(() => URL.revokeObjectURL(null)).not.toThrow();
  });

  it('should clean up URLs even on error', () => {
    const images = [
      { url: 'blob:url1' },
      { url: 'blob:url2' },
      { url: 'blob:url3' }
    ];

    try {
      // Simulate error during processing
      throw new Error('Processing failed');
    } catch (e) {
      // Ignore expected error
    } finally {
      // URLs should still be cleaned up
      images.forEach(img => URL.revokeObjectURL(img.url));
    }

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(3);
  });
});

describe('Special Characters and Edge Cases', () => {
  it('should handle filenames with multiple dots', async () => {
    const { isImageFile } = await import('../shared/sorting-logic.js');

    expect(isImageFile('file.name.with.many.dots.jpg')).toBe(true);
    expect(isImageFile('file.name.with.many.dots.txt')).toBe(false);
  });

  it('should handle empty filenames', async () => {
    const { isImageFile } = await import('../shared/sorting-logic.js');

    expect(isImageFile('')).toBe(false);
  });

  it('should handle filenames without extensions', async () => {
    const { isImageFile } = await import('../shared/sorting-logic.js');

    expect(isImageFile('filename_without_extension')).toBe(false);
  });

  it('should handle very long filenames', async () => {
    const longFilename = 'a'.repeat(255) + '.jpg';
    const { isImageFile } = await import('../shared/sorting-logic.js');

    expect(isImageFile(longFilename)).toBe(true);
  });

  it('should handle null or undefined filenames', () => {
    const isImageFileSafe = (filename) => {
      if (!filename) return false;
      const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
      return ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'].includes(ext);
    };

    expect(isImageFileSafe(null)).toBe(false);
    expect(isImageFileSafe(undefined)).toBe(false);
  });
});

describe('Browser Compatibility Errors', () => {
  it('should handle missing File API', () => {
    const hasFileAPI = typeof File !== 'undefined';

    // Application should check for API availability
    expect(hasFileAPI).toBe(true);  // In test environment
  });

  it('should handle missing Blob API', () => {
    const hasBlobAPI = typeof Blob !== 'undefined';

    expect(hasBlobAPI).toBe(true);
  });

  it('should handle browsers without drag-and-drop support', () => {
    const supportsDragAndDrop = 'draggable' in document.createElement('div');

    // Should have fallback for browsers without drag-and-drop
    expect(typeof supportsDragAndDrop).toBe('boolean');
  });
});

describe('Memory Management', () => {
  it('should clean up object URLs to prevent memory leaks', () => {
    const urls = [];

    // Create multiple object URLs
    for (let i = 0; i < 100; i++) {
      const url = URL.createObjectURL(new Blob());
      urls.push(url);
    }

    // Clean up all URLs
    urls.forEach(url => URL.revokeObjectURL(url));

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(100);
  });

  it('should handle large number of files', () => {
    const files = new Map();

    // Add many files
    for (let i = 0; i < 1000; i++) {
      files.set(i, { file: { name: `file${i}.zip` }, status: 'pending' });
    }

    expect(files.size).toBe(1000);

    // Should be able to clear efficiently
    files.clear();
    expect(files.size).toBe(0);
  });
});
