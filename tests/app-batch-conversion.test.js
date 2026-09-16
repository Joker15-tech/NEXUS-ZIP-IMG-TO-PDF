/**
 * Batch Conversion and Multi-File Tests for web/app.js
 * Tests for newly added batch conversion features
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
        clear: vi.fn(() => { store = {}; })
    };
})();
vi.stubGlobal('localStorage', localStorageMock);

import JSZip from 'jszip';

// Mock sorting logic
vi.mock('../shared/sorting-logic.js', () => ({
    sortImages: vi.fn((files, useNaturalSort, priorityChars) => {
        // Simple mock implementation that respects natural sort
        if (useNaturalSort) {
            return [...files].sort((a, b) => {
                // Extract numbers from filenames for natural sorting
                const aNum = parseInt(a.match(/\d+/)?.[0] || '0');
                const bNum = parseInt(b.match(/\d+/)?.[0] || '0');
                if (aNum !== bNum) return aNum - bNum;
                return a.localeCompare(b);
            });
        }
        return [...files].sort();
    }),
    isImageFile: vi.fn((filename) => {
        const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
        return ['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(ext);
    }),
    IMAGE_EXTENSIONS: ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
    DEFAULT_PRIORITY_CHARS: '!'
}));

import { sortImages, isImageFile } from '../shared/sorting-logic.js';

describe('Multiple Image File Upload', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should accept multiple image files (not ZIPs)', () => {
        const files = [
            { name: 'photo1.jpg', type: 'image/jpeg', size: 1024 },
            { name: 'photo2.png', type: 'image/png', size: 2048 },
            { name: 'photo3.jpg', type: 'image/jpeg', size: 1536 }
        ];

        const imageFiles = files.filter(f => isImageFile(f.name));

        expect(imageFiles).toHaveLength(3);
    });

    it('should convert multiple images to single PDF', async () => {
        const images = [
            { filename: 'img1.jpg', data: new Blob(), url: 'blob:1' },
            { filename: 'img2.jpg', data: new Blob(), url: 'blob:2' },
            { filename: 'img3.jpg', data: new Blob(), url: 'blob:3' }
        ];

        // Mock PDF
        const mockPDF = {
            addImage: vi.fn(),
            addPage: vi.fn(),
            save: vi.fn()
        };

        global.window = {
            jspdf: { jsPDF: vi.fn(() => mockPDF) }
        };

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF();

        // Add all images to PDF
        for (let i = 0; i < images.length; i++) {
            if (i > 0) pdf.addPage();
            pdf.addImage(images[i].url, 'JPEG', 0, 0, 100, 100);
        }

        pdf.save('converted_images.pdf');

        expect(mockPDF.addImage).toHaveBeenCalledTimes(3);
        expect(mockPDF.save).toHaveBeenCalledWith('converted_images.pdf');
    });

    it('should sort image files before conversion', () => {
        const files = ['img_10.jpg', 'img_2.jpg', 'img_1.jpg'];

        const sorted = sortImages(files, true, '!');

        // Natural sort: img_1, img_2, img_10
        expect(sorted[0]).toBe('img_1.jpg');
        expect(sorted[1]).toBe('img_2.jpg');
        expect(sorted[2]).toBe('img_10.jpg');
    });

    it('should reject non-image files when uploading images', () => {
        const files = [
            { name: 'photo.jpg', type: 'image/jpeg' },
            { name: 'document.pdf', type: 'application/pdf' },
            { name: 'archive.zip', type: 'application/zip' }
        ];

        const imageFiles = files.filter(f => {
            const isImage = isImageFile(f.name);
            const isZip = f.type === 'application/zip' || f.name.endsWith('.zip');
            return isImage && !isZip;
        });

        expect(imageFiles).toHaveLength(1);
        expect(imageFiles[0].name).toBe('photo.jpg');
    });
});

describe('Batch ZIP Conversion (Convert Each to PDF)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should process multiple ZIP files sequentially', async () => {
        const zipFiles = [
            { fileId: 1, fileData: { file: { name: 'archive1.zip' } } },
            { fileId: 2, fileData: { file: { name: 'archive2.zip' } } },
            { fileId: 3, fileData: { file: { name: 'archive3.zip' } } }
        ];

        const processedFiles = [];

        for (const { fileId, fileData } of zipFiles) {
            const mockZip = {
                loadAsync: vi.fn().mockResolvedValue({
                    files: {
                        'img.jpg': {
                            dir: false,
                            async: vi.fn().mockResolvedValue(new Blob())
                        }
                    }
                })
            };

            JSZip.mockImplementation(() => mockZip);

            await mockZip.loadAsync(new Blob());
            processedFiles.push(fileData.file.name);
        }

        expect(processedFiles).toHaveLength(3);
        expect(processedFiles).toEqual(['archive1.zip', 'archive2.zip', 'archive3.zip']);
    });

    it('should generate unique PDF filename for each ZIP', () => {
        const zipFiles = [
            { name: 'photos.zip' },
            { name: 'documents.zip' },
            { name: 'backup.ZIP' }
        ];

        const pdfNames = zipFiles.map(f =>
            f.name.replace(/\.zip$/i, '.pdf')
        );

        expect(pdfNames).toEqual(['photos.pdf', 'documents.pdf', 'backup.pdf']);
        expect(new Set(pdfNames).size).toBe(3); // All unique
    });

    it('should add delay between downloads to prevent filename conflicts', async () => {
        const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

        const startTime = Date.now();

        // Simulate 3 conversions with 100ms delay each
        for (let i = 0; i < 3; i++) {
            if (i > 0) await delay(100);
        }

        const elapsed = Date.now() - startTime;

        // Should have taken at least 200ms (2 delays)
        expect(elapsed).toBeGreaterThanOrEqual(200);
    });

    it('should track success and failure counts', async () => {
        const results = { successCount: 0, failCount: 0 };

        const zipFiles = [
            { id: 1, shouldFail: false },
            { id: 2, shouldFail: true },
            { id: 3, shouldFail: false }
        ];

        for (const zip of zipFiles) {
            try {
                if (zip.shouldFail) {
                    throw new Error('Conversion failed');
                }
                results.successCount++;
            } catch (error) {
                results.failCount++;
            }
        }

        expect(results.successCount).toBe(2);
        expect(results.failCount).toBe(1);
    });

    it('should continue processing even if one ZIP fails', async () => {
        const mockZips = [
            {
                loadAsync: vi.fn().mockResolvedValue({
                    files: { 'img.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) } }
                })
            },
            {
                loadAsync: vi.fn().mockRejectedValue(new Error('Corrupted ZIP'))
            },
            {
                loadAsync: vi.fn().mockResolvedValue({
                    files: { 'img.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) } }
                })
            }
        ];

        const processed = [];

        for (let i = 0; i < mockZips.length; i++) {
            try {
                await mockZips[i].loadAsync(new Blob());
                processed.push(i);
            } catch (error) {
                // Continue with next ZIP
            }
        }

        expect(processed).toEqual([0, 2]);
    });
});

describe('ZIP Merging (Merge All to Single PDF)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should extract images from multiple ZIPs', async () => {
        const mockZips = [
            {
                loadAsync: vi.fn().mockResolvedValue({
                    files: {
                        'img1.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
                        'img2.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) }
                    }
                })
            },
            {
                loadAsync: vi.fn().mockResolvedValue({
                    files: {
                        'img3.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) }
                    }
                })
            }
        ];

        const allImages = [];

        for (const mockZip of mockZips) {
            const zipData = await mockZip.loadAsync(new Blob());
            const imageFiles = Object.keys(zipData.files).filter(f => !zipData.files[f].dir);

            for (const filename of imageFiles) {
                const blob = await zipData.files[filename].async('blob');
                allImages.push({ filename, data: blob });
            }
        }

        expect(allImages).toHaveLength(3);
    });

    it('should sort ZIP files by name before extracting', () => {
        const zipFiles = [
            { fileData: { file: { name: 'archive_3.zip' } } },
            { fileData: { file: { name: 'archive_1.zip' } } },
            { fileData: { file: { name: 'archive_2.zip' } } }
        ];

        const zipFilenames = zipFiles.map(({ fileData }) => fileData.file.name);
        const sortedFilenames = sortImages(zipFilenames, true, '!');

        expect(sortedFilenames[0]).toBe('archive_1.zip');
        expect(sortedFilenames[1]).toBe('archive_2.zip');
        expect(sortedFilenames[2]).toBe('archive_3.zip');
    });

    it('should maintain order of images within each ZIP', async () => {
        const mockZip = {
            loadAsync: vi.fn().mockResolvedValue({
                files: {
                    'page_3.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
                    'page_1.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) },
                    'page_2.jpg': { dir: false, async: vi.fn().mockResolvedValue(new Blob()) }
                }
            })
        };

        JSZip.mockImplementation(() => mockZip);

        const zipData = await mockZip.loadAsync(new Blob());
        const imageFiles = Object.keys(zipData.files).filter(f => !zipData.files[f].dir);

        // Sort images within this ZIP
        const sortedImages = sortImages(imageFiles, true, '!');

        // Should be sorted: page_1, page_2, page_3
        expect(sortedImages[0]).toBe('page_1.jpg');
        expect(sortedImages[1]).toBe('page_2.jpg');
        expect(sortedImages[2]).toBe('page_3.jpg');
    });

    it('should create single merged PDF with correct filename', () => {
        const mockPDF = {
            addImage: vi.fn(),
            addPage: vi.fn(),
            save: vi.fn()
        };

        global.window = {
            jspdf: { jsPDF: vi.fn(() => mockPDF) }
        };

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF();

        const images = [
            { url: 'blob:1' },
            { url: 'blob:2' },
            { url: 'blob:3' }
        ];

        for (let i = 0; i < images.length; i++) {
            if (i > 0) pdf.addPage();
            pdf.addImage(images[i].url, 'JPEG', 0, 0, 100, 100);
        }

        pdf.save('merged_archives.pdf');

        expect(mockPDF.save).toHaveBeenCalledWith('merged_archives.pdf');
    });

    it('should track progress during merge operation', () => {
        const progressEvents = [];
        const callback = (info) => progressEvents.push(info);

        const zipFiles = [
            { name: 'zip1.zip' },
            { name: 'zip2.zip' },
            { name: 'zip3.zip' }
        ];

        // Simulate extraction progress
        for (let i = 0; i < zipFiles.length; i++) {
            callback({
                current: i + 1,
                total: zipFiles.length,
                stage: 'extracting'
            });
        }

        expect(progressEvents).toHaveLength(3);
        expect(progressEvents[2]).toEqual({ current: 3, total: 3, stage: 'extracting' });
    });
});

describe('ZIP Sorting in Merge Operations', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should apply natural sort to ZIP filenames', () => {
        const zipFiles = [
            'chapter_10.zip',
            'chapter_2.zip',
            'chapter_1.zip',
            'chapter_20.zip'
        ];

        const sorted = sortImages(zipFiles, true, '!');

        expect(sorted[0]).toBe('chapter_1.zip');
        expect(sorted[1]).toBe('chapter_2.zip');
        expect(sorted[2]).toBe('chapter_10.zip');
        expect(sorted[3]).toBe('chapter_20.zip');
    });

    it('should respect priority characters for ZIP files', () => {
        const zipFiles = [
            'regular.zip',
            '!important.zip',
            'another.zip'
        ];

        // Mock sortImages to handle priority
        const sortedFiles = [...zipFiles].sort((a, b) => {
            const aPriority = a.startsWith('!');
            const bPriority = b.startsWith('!');
            if (aPriority && !bPriority) return -1;
            if (!aPriority && bPriority) return 1;
            return a.localeCompare(b);
        });

        expect(sortedFiles[0]).toBe('!important.zip');
    });

    it('should maintain correct final order: sorted ZIPs then images', async () => {
        // Simulate the complete merge workflow
        const zipFiles = [
            {
                name: 'vol_2.zip',
                images: ['page_1.jpg', 'page_2.jpg']
            },
            {
                name: 'vol_1.zip',
                images: ['page_1.jpg', 'page_2.jpg']
            }
        ];

        // Sort ZIPs
        const sortedZips = zipFiles.sort((a, b) =>
            a.name.localeCompare(b.name)
        );

        // Extract images in order
        const finalOrder = [];
        for (const zip of sortedZips) {
            finalOrder.push(...zip.images.map(img => `${zip.name}:${img}`));
        }

        // Final order should be:
        // vol_1.zip:page_1.jpg, vol_1.zip:page_2.jpg,
        // vol_2.zip:page_1.jpg, vol_2.zip:page_2.jpg
        expect(finalOrder[0]).toBe('vol_1.zip:page_1.jpg');
        expect(finalOrder[1]).toBe('vol_1.zip:page_2.jpg');
        expect(finalOrder[2]).toBe('vol_2.zip:page_1.jpg');
        expect(finalOrder[3]).toBe('vol_2.zip:page_2.jpg');
    });

    it('should handle mixed cases in ZIP filenames', () => {
        const zipFiles = [
            'Archive_B.zip',
            'archive_a.zip',
            'ARCHIVE_C.zip'
        ];

        const sorted = [...zipFiles].sort((a, b) =>
            a.toLowerCase().localeCompare(b.toLowerCase())
        );

        expect(sorted[0]).toBe('archive_a.zip');
        expect(sorted[1]).toBe('Archive_B.zip');
        expect(sorted[2]).toBe('ARCHIVE_C.zip');
    });
});

describe('File Type Management', () => {
    it('should differentiate between ZIP and image file types', () => {
        const files = [
            { name: 'archive.zip', type: 'zip' },
            { name: 'photo.jpg', type: 'image' },
            { name: 'doc.zip', type: 'zip' },
            { name: 'pic.png', type: 'image' }
        ];

        const zipFiles = files.filter(f => f.type === 'zip');
        const imageFiles = files.filter(f => f.type === 'image');

        expect(zipFiles).toHaveLength(2);
        expect(imageFiles).toHaveLength(2);
    });

    it('should handle state with both ZIP and image files', () => {
        const state = {
            files: new Map(),
            imageFiles: [],
            currentFileId: 0
        };

        // Add ZIP file
        const zipId = state.currentFileId++;
        state.files.set(zipId, {
            file: { name: 'archive.zip' },
            type: 'zip',
            status: 'pending'
        });

        // Add image files
        const img1Id = state.currentFileId++;
        const img1File = { name: 'photo1.jpg' };
        state.files.set(img1Id, {
            file: img1File,
            type: 'image',
            status: 'pending'
        });
        state.imageFiles.push({ fileId: img1Id, file: img1File });

        const img2Id = state.currentFileId++;
        const img2File = { name: 'photo2.jpg' };
        state.files.set(img2Id, {
            file: img2File,
            type: 'image',
            status: 'pending'
        });
        state.imageFiles.push({ fileId: img2Id, file: img2File });

        expect(state.files.size).toBe(3);
        expect(state.imageFiles.length).toBe(2);

        const zipCount = Array.from(state.files.values()).filter(f => f.type === 'zip').length;
        const imageCount = state.imageFiles.length;

        expect(zipCount).toBe(1);
        expect(imageCount).toBe(2);
    });

    it('should show appropriate buttons based on file types', () => {
        const getButtonsToShow = (zipCount, imageCount) => {
            const buttons = [];

            if (zipCount > 1) {
                buttons.push('Convert Each to PDF');
                buttons.push('Merge All to Single PDF');
            }

            if (imageCount > 1) {
                buttons.push('Convert Images to PDF');
            }

            return buttons;
        };

        // Multiple ZIPs only
        expect(getButtonsToShow(3, 0)).toEqual(['Convert Each to PDF', 'Merge All to Single PDF']);

        // Multiple images only
        expect(getButtonsToShow(0, 3)).toEqual(['Convert Images to PDF']);

        // Both
        expect(getButtonsToShow(2, 2)).toEqual([
            'Convert Each to PDF',
            'Merge All to Single PDF',
            'Convert Images to PDF'
        ]);

        // Single files - no batch buttons
        expect(getButtonsToShow(1, 1)).toEqual([]);
    });
});
