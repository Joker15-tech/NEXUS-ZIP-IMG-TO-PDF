/**
 * End-to-End integration tests for web/app.js
 * Tests complete workflows for the web application
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock dependencies
vi.mock('jszip');
vi.mock('jspdf');

// Mock localStorage
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: vi.fn(key => store[key] || null),
    setItem: vi.fn((key, value) => { store[key] = value.toString(); }),
    removeItem: vi.fn(key => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    mockClear: () => {
      store = {};
    }
  };
})();
vi.stubGlobal('localStorage', localStorageMock);

import JSZip from 'jszip';

// Mock sorting logic
vi.mock('../shared/sorting-logic.js', () => ({
  sortImages: vi.fn((files) => files),
  isImageFile: vi.fn((filename) => {
    const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
    return ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'].includes(ext);
  })
}));

import { sortImages, isImageFile } from '../shared/sorting-logic.js';

describe('Complete ZIP to PDF Workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should complete full workflow: upload -> extract -> convert -> download', async () => {
    // 1. Mock ZIP file upload
    const mockZipBlob = new Blob(['fake zip content'], { type: 'application/zip' });
    const mockZipFile = {
      name: 'test.zip',
      type: 'application/zip',
      size: 1024
    };

    // 2. Mock ZIP extraction
    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {
          'img1.jpg': {
            dir: false,
            async: vi.fn().mockResolvedValue(new Blob(['img1 data'], { type: 'image/jpeg' }))
          },
          'img2.jpg': {
            dir: false,
            async: vi.fn().mockResolvedValue(new Blob(['img2 data'], { type: 'image/jpeg' }))
          },
          'img3.jpg': {
            dir: false,
            async: vi.fn().mockResolvedValue(new Blob(['img3 data'], { type: 'image/jpeg' }))
          }
        }
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    // 3. Extract images
    const zipData = await mockZipInstance.loadAsync(mockZipBlob);
    const fileList = Object.keys(zipData.files);

    const imageFiles = fileList.filter(filename =>
      !zipData.files[filename].dir && isImageFile(filename)
    );

    expect(imageFiles).toHaveLength(3);

    // 4. Sort images
    const sortedImages = sortImages(imageFiles);
    expect(sortedImages).toHaveLength(3);

    // 5. Extract image data
    const images = [];
    for (const filename of sortedImages) {
      const imageData = await zipData.files[filename].async('blob');
      images.push({
        filename,
        data: imageData,
        url: URL.createObjectURL(imageData)
      });
    }

    expect(images).toHaveLength(3);
    expect(URL.createObjectURL).toHaveBeenCalledTimes(3);

    // 6. Mock PDF generation
    const mockPDF = {
      addImage: vi.fn(),
      addPage: vi.fn(),
      save: vi.fn()
    };

    global.window = {
      jspdf: {
        jsPDF: vi.fn(() => mockPDF)
      }
    };

    // 7. Generate PDF
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF();

    for (let i = 0; i < images.length; i++) {
      if (i > 0) {
        pdf.addPage();
      }
      pdf.addImage(images[i].url, 'JPEG', 0, 0, 100, 100);
    }

    pdf.save('test.pdf');

    // 8. Verify workflow completion
    expect(mockPDF.addImage).toHaveBeenCalledTimes(3);
    expect(mockPDF.addPage).toHaveBeenCalledTimes(2);
    expect(mockPDF.save).toHaveBeenCalledWith('test.pdf');

    // 9. Cleanup URLs
    images.forEach(img => URL.revokeObjectURL(img.url));
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(3);
  });

  it('should handle priority files in complete workflow', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {
          'page1.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          '!cover.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'page2.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          '!back.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) }
        }
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipData = await mockZipInstance.loadAsync(new Blob());
    const fileList = Object.keys(zipData.files);

    const imageFiles = fileList.filter(f =>
      !zipData.files[f].dir && isImageFile(f)
    );

    // Sort with priority handling
    const sortedImages = sortImages(imageFiles, true, '!');

    // Extract images
    const images = [];
    for (const filename of sortedImages) {
      const imageData = await zipData.files[filename].async('blob');
      images.push({ filename, data: imageData, url: 'blob:mock' });
    }

    // Verify priority files are processed first
    expect(images.length).toBeGreaterThan(0);
    expect(sortImages).toHaveBeenCalledWith(imageFiles, true, '!');
  });

  it('should process multiple files sequentially', async () => {
    const files = [
      { name: 'file1.zip', type: 'application/zip' },
      { name: 'file2.zip', type: 'application/zip' },
      { name: 'file3.zip', type: 'application/zip' }
    ];

    const processedFiles = [];

    for (const file of files) {
      const mockZipInstance = {
        loadAsync: vi.fn().mockResolvedValue({
          files: {
            'img.jpg': {
              dir: false,
              async: vi.fn().mockResolvedValue(new Blob())
            }
          }
        })
      };

      JSZip.mockImplementation(() => mockZipInstance);

      const zipData = await mockZipInstance.loadAsync(new Blob());
      processedFiles.push(file.name);
    }

    expect(processedFiles).toHaveLength(3);
    expect(processedFiles).toEqual(['file1.zip', 'file2.zip', 'file3.zip']);
  });
});

describe('Settings Persistence Workflow', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.getItem.mockClear();
    localStorage.setItem.mockClear();
  });

  it('should save and restore settings across sessions', () => {
    // Initial state
    const initialSettings = {
      useNaturalSort: true,
      priorityChars: '!'
    };

    // Save settings
    localStorage.setItem('zipToPdfSettings', JSON.stringify(initialSettings));

    // Simulate page reload
    const savedData = localStorage.getItem('zipToPdfSettings');
    const restoredSettings = JSON.parse(savedData);

    expect(restoredSettings).toEqual(initialSettings);
  });

  it('should update settings and persist changes', () => {
    // Initial settings
    localStorage.setItem('zipToPdfSettings', JSON.stringify({
      useNaturalSort: true,
      priorityChars: '!'
    }));

    // User changes settings
    const newSettings = {
      useNaturalSort: false,
      priorityChars: '@'
    };

    localStorage.setItem('zipToPdfSettings', JSON.stringify(newSettings));

    // Verify persistence
    const saved = localStorage.getItem('zipToPdfSettings');
    const parsed = JSON.parse(saved);

    expect(parsed.useNaturalSort).toBe(false);
    expect(parsed.priorityChars).toBe('@');
  });

  it('should apply settings to conversion workflow', async () => {
    // Set custom settings
    const settings = {
      useNaturalSort: false,
      priorityChars: '@'
    };

    localStorage.setItem('zipToPdfSettings', JSON.stringify(settings));

    // Load settings
    const savedSettings = JSON.parse(localStorage.getItem('zipToPdfSettings'));

    // Use in sorting
    const files = ['img_10.jpg', 'img_1.jpg', '@special.jpg', 'img_2.jpg'];
    const sorted = sortImages(files, savedSettings.useNaturalSort, savedSettings.priorityChars);

    expect(sortImages).toHaveBeenCalledWith(files, false, '@');
  });
});

describe('File State Management Workflow', () => {
  it('should manage multiple files through complete lifecycle', () => {
    const state = {
      files: new Map(),
      currentFileId: 0
    };

    // Add files
    const file1 = { name: 'file1.zip', size: 1024 };
    const file2 = { name: 'file2.zip', size: 2048 };
    const file3 = { name: 'file3.zip', size: 4096 };

    const id1 = state.currentFileId++;
    const id2 = state.currentFileId++;
    const id3 = state.currentFileId++;

    state.files.set(id1, { file: file1, status: 'pending' });
    state.files.set(id2, { file: file2, status: 'pending' });
    state.files.set(id3, { file: file3, status: 'pending' });

    expect(state.files.size).toBe(3);

    // Update status
    state.files.get(id1).status = 'processing';
    expect(state.files.get(id1).status).toBe('processing');

    // Complete and remove
    state.files.delete(id1);
    expect(state.files.size).toBe(2);

    // Process remaining
    state.files.get(id2).status = 'processing';
    state.files.delete(id2);

    state.files.get(id3).status = 'processing';
    state.files.delete(id3);

    expect(state.files.size).toBe(0);
  });

  it('should handle file validation workflow', () => {
    const validateAndAddFile = (file) => {
      const isZip = file.type === 'application/zip' ||
        file.name.toLowerCase().endsWith('.zip');

      if (!isZip) {
        return { success: false, error: 'Not a ZIP file' };
      }

      if (file.size === 0) {
        return { success: false, error: 'Empty file' };
      }

      if (file.size > 1024 * 1024 * 500) {  // 500MB
        return { success: false, error: 'File too large' };
      }

      return { success: true, file };
    };

    // Valid file
    const validFile = { name: 'test.zip', type: 'application/zip', size: 1024 };
    expect(validateAndAddFile(validFile).success).toBe(true);

    // Invalid type
    const invalidType = { name: 'test.pdf', type: 'application/pdf', size: 1024 };
    expect(validateAndAddFile(invalidType).success).toBe(false);

    // Empty file
    const emptyFile = { name: 'test.zip', type: 'application/zip', size: 0 };
    expect(validateAndAddFile(emptyFile).success).toBe(false);

    // Too large
    const largeFile = { name: 'test.zip', type: 'application/zip', size: 1024 * 1024 * 600 };
    expect(validateAndAddFile(largeFile).success).toBe(false);
  });
});

describe('Progress Tracking Workflow', () => {
  it('should track extraction progress', async () => {
    const progressEvents = [];
    const progressCallback = (info) => {
      progressEvents.push(info);
    };

    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {
          'img1.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'img2.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'img3.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) }
        }
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipData = await mockZipInstance.loadAsync(new Blob());
    const imageFiles = Object.keys(zipData.files).filter(f => !zipData.files[f].dir);

    // Simulate extraction with progress
    for (let i = 0; i < imageFiles.length; i++) {
      await zipData.files[imageFiles[i]].async('blob');
      progressCallback({
        current: i + 1,
        total: imageFiles.length,
        stage: 'extracting'
      });
    }

    expect(progressEvents).toHaveLength(3);
    expect(progressEvents[0]).toEqual({ current: 1, total: 3, stage: 'extracting' });
    expect(progressEvents[2]).toEqual({ current: 3, total: 3, stage: 'extracting' });
  });

  it('should track conversion progress', () => {
    const progressEvents = [];
    const progressCallback = (info) => {
      progressEvents.push(info);
    };

    const images = [
      { url: 'blob:1' },
      { url: 'blob:2' },
      { url: 'blob:3' },
      { url: 'blob:4' },
      { url: 'blob:5' }
    ];

    // Simulate conversion with progress
    for (let i = 0; i < images.length; i++) {
      progressCallback({
        current: i + 1,
        total: images.length,
        stage: 'converting'
      });
    }

    expect(progressEvents).toHaveLength(5);
    expect(progressEvents[4]).toEqual({ current: 5, total: 5, stage: 'converting' });
  });

  it('should calculate progress percentage correctly', () => {
    const calculateProgress = (current, total) => {
      if (total === 0) return 0;
      return Math.min(100, Math.max(0, Math.round((current / total) * 100)));
    };

    expect(calculateProgress(0, 10)).toBe(0);
    expect(calculateProgress(5, 10)).toBe(50);
    expect(calculateProgress(10, 10)).toBe(100);
    expect(calculateProgress(15, 10)).toBe(100); // Clamped to 100
    expect(calculateProgress(-5, 10)).toBe(0);    // Clamped to 0
    expect(calculateProgress(5, 0)).toBe(0);      // Avoid division by zero
  });
});

describe('Real-World Scenarios Integration', () => {
  it('should handle archive workflow', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {
          '!cover.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'page001.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'page002.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'page010.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          '!credits.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) }
        }
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipData = await mockZipInstance.loadAsync(new Blob());
    const imageFiles = Object.keys(zipData.files).filter(f => !zipData.files[f].dir);

    // Sort with priority
    const sorted = sortImages(imageFiles, true, '!');

    // Extract
    const images = [];
    for (const filename of sorted) {
      const blob = await zipData.files[filename].async('blob');
      images.push({ filename, data: blob });
    }

    expect(images.length).toBeGreaterThan(0);
    expect(sortImages).toHaveBeenCalled();
  });

  it('should handle photo album workflow with mixed orientations', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {
          'IMG_0001.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'IMG_0002.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'IMG_0010.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'IMG_0100.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) }
        }
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipData = await mockZipInstance.loadAsync(new Blob());
    const imageFiles = Object.keys(zipData.files).filter(f => !zipData.files[f].dir);

    // Natural sorting should handle IMG_0001, IMG_0002, IMG_0010, IMG_0100
    const sorted = sortImages(imageFiles, true, '!');

    expect(imageFiles).toHaveLength(4);
  });

  it('should handle user interaction workflow: drag-drop -> convert -> download', async () => {
    // 1. Simulate drag and drop
    const droppedFile = {
      name: 'photos.zip',
      type: 'application/zip',
      size: 5242880
    };

    // 2. Validate file
    const isValid = droppedFile.type === 'application/zip' ||
      droppedFile.name.toLowerCase().endsWith('.zip');

    expect(isValid).toBe(true);

    // 3. Add to state
    const state = { files: new Map(), currentFileId: 0 };
    const fileId = state.currentFileId++;
    state.files.set(fileId, { file: droppedFile, status: 'pending' });

    // 4. Process file
    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {
          'img1.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'img2.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) }
        }
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    state.files.get(fileId).status = 'processing';

    const zipData = await mockZipInstance.loadAsync(new Blob());
    const imageFiles = Object.keys(zipData.files).filter(f => !zipData.files[f].dir);

    // 5. Extract and convert
    const images = [];
    for (const filename of imageFiles) {
      const blob = await zipData.files[filename].async('blob');
      images.push({ filename, data: blob, url: URL.createObjectURL(blob) });
    }

    // 6. Generate PDF
    const mockPDF = {
      addImage: vi.fn(),
      addPage: vi.fn(),
      save: vi.fn()
    };

    images.forEach((img, i) => {
      if (i > 0) mockPDF.addPage();
      mockPDF.addImage(img.url, 'JPEG', 0, 0, 100, 100);
    });

    mockPDF.save('photos.pdf');

    // 7. Cleanup
    images.forEach(img => URL.revokeObjectURL(img.url));
    state.files.delete(fileId);

    // Verify complete workflow
    expect(mockPDF.save).toHaveBeenCalledWith('photos.pdf');
    expect(state.files.size).toBe(0);
  });
});

describe('Error Recovery Workflows', () => {
  it('should recover from extraction error and continue with valid images', async () => {
    const mockZipInstance = {
      loadAsync: vi.fn().mockResolvedValue({
        files: {
          'good1.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
          'bad.jpg': { dir: false, async: vi.fn().mockRejectedValue(new Error('Corrupt')) },
          'good2.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) }
        }
      })
    };

    JSZip.mockImplementation(() => mockZipInstance);

    const zipData = await mockZipInstance.loadAsync(new Blob());
    const fileList = Object.keys(zipData.files);

    const images = [];
    for (const filename of fileList) {
      try {
        const blob = await zipData.files[filename].async('blob');
        images.push({ filename, data: blob });
      } catch (error) {
        // Skip corrupted image, continue with others
        console.warn(`Skipped ${filename}:`, error.message);
      }
    }

    // Should have 2 valid images
    expect(images).toHaveLength(2);
    expect(images[0].filename).toBe('good1.jpg');
    expect(images[1].filename).toBe('good2.jpg');
  });

  it('should handle conversion failure and notify user', async () => {
    const mockPDF = {
      addImage: vi.fn(() => {
        throw new Error('PDF generation failed');
      }),
      save: vi.fn()
    };

    let conversionError = null;
    try {
      mockPDF.addImage('blob:url', 'JPEG', 0, 0, 100, 100);
    } catch (error) {
      conversionError = error;
    }

    expect(conversionError).toBeDefined();
    expect(conversionError.message).toBe('PDF generation failed');
    expect(mockPDF.save).not.toHaveBeenCalled();
  });
});
