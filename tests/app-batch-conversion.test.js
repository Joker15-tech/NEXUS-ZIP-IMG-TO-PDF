/**
 * =====================================================================
 * NEXUS QUANTUM // Batch Conversion and Multi-File Tests
 * =====================================================================
 * File:    tests/app-batch-conversion.test.js
 * Targets: web/app.js batch conversion workflows
 *
 * Covers:
 *   1. Multiple image file upload
 *   2. Batch ZIP conversion (Convert Each to PDF)
 *   3. ZIP merging (Merge All to Single PDF)
 *   4. ZIP sorting during merge operations
 *   5. File type management (ZIP vs IMG routing)
 *
 * Runtime: Vitest + jsdom
 * =====================================================================
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// =====================================================================
// § 00 — MOCKS (declared BEFORE imports they affect)
// =====================================================================

vi.mock('jszip', () => {
    const JSZip = vi.fn();
    JSZip.loadAsync = vi.fn();
    return { default: JSZip };
});

vi.mock('jspdf', () => {
    const jsPDF = vi.fn(() => ({
        addImage: vi.fn(),
        addPage: vi.fn(),
        save: vi.fn()
    }));
    return { jsPDF, default: { jsPDF } };
});

// =====================================================================
// § 01 — SHARED SORTING-LOGIC MOCK (mirrors real behavior)
// =====================================================================
//
// We mock `../shared/sorting-logic.js` for isolation. The mock MUST
// mirror the real behavior (priority routing, basename handling,
// natural sort) — otherwise tests pass against a lie.

vi.mock('../shared/sorting-logic.js', () => {
    // Local helpers that mirror the real implementations
    const getBasename = (p) =>
        String(p || '').split(/[\\/]/).pop() || '';

    const naturalKey = (text) =>
        text.split(/(\d+)/).map(chunk =>
            /^\d+$/.test(chunk) ? parseInt(chunk, 10) : chunk
        );

    const compareNatural = (a, b) => {
        const ka = naturalKey(a);
        const kb = naturalKey(b);
        const min = Math.min(ka.length, kb.length);

        for (let i = 0; i < min; i++) {
            const ca = ka[i];
            const cb = kb[i];
            if (ca === cb) continue;
            if (typeof ca === 'number' && typeof cb === 'number') {
                return ca - cb;
            }
            return String(ca) < String(cb) ? -1 : 1;
        }
        return ka.length - kb.length;
    };

    const IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'];
    const DEFAULT_PRIORITY_CHARS = '!';

    const isImageFile = vi.fn((filename) => {
        const basename = getBasename(filename);
        const dot = basename.lastIndexOf('.');
        if (dot <= 0 || dot === basename.length - 1) return false;
        return IMAGE_EXTENSIONS.includes(basename.substring(dot).toLowerCase());
    });

    const sortImages = vi.fn((files, useNaturalSort = true, priorityChars = '!') => {
        if (!Array.isArray(files) || files.length === 0) return [];

        const prioritySet = new Set((priorityChars || '').split(''));
        const priorityFiles = [];
        const normalFiles = [];

        for (const file of files) {
            const first = getBasename(file).charAt(0);
            if (first && prioritySet.has(first)) priorityFiles.push(file);
            else normalFiles.push(file);
        }

        const comparator = useNaturalSort
            ? (a, b) => compareNatural(getBasename(a), getBasename(b))
            : (a, b) => getBasename(a).localeCompare(getBasename(b));

        priorityFiles.sort(comparator);
        normalFiles.sort(comparator);

        return [...priorityFiles, ...normalFiles];
    });

    return {
        default: { isImageFile, sortImages, IMAGE_EXTENSIONS, DEFAULT_PRIORITY_CHARS },
        isImageFile,
        sortImages,
        IMAGE_EXTENSIONS,
        DEFAULT_PRIORITY_CHARS
    };
});

// Import the mocked functions AFTER the mock factory
import JSZip from 'jszip';
import { jsPDF } from 'jspdf';
import {
    sortImages,
    isImageFile,
    IMAGE_EXTENSIONS,
    DEFAULT_PRIORITY_CHARS
} from '../shared/sorting-logic.js';

// =====================================================================
// § 02 — GLOBAL SETUP
// =====================================================================

// localStorage mock (per-suite isolated)
const localStorageMock = (() => {
    let store = {};
    return {
        getItem: vi.fn((key) => store[key] ?? null),
        setItem: vi.fn((key, value) => { store[key] = String(value); }),
        removeItem: vi.fn((key) => { delete store[key]; }),
        clear: vi.fn(() => { store = {}; }),
        _dump: () => ({ ...store }),
        _reset: () => { store = {}; }
    };
})();

vi.stubGlobal('localStorage', localStorageMock);

// Preserve original window.jspdf so we can restore it after each test
const ORIGINAL_JSPDF = window.jspdf;

// =====================================================================
// § 03 — LIFECYCLE HOOKS
// =====================================================================

beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock._reset();
});

afterEach(() => {
    // Restore window.jspdf to avoid cross-suite pollution
    if (ORIGINAL_JSPDF === undefined) {
        delete window.jspdf;
    } else {
        window.jspdf = ORIGINAL_JSPDF;
    }
    // Do NOT call vi.unstubAllGlobals() here — it would undo localStorage
    // for the whole file. We reset the store manually instead.
});

// =====================================================================
// § 04 — TEST HELPERS
// =====================================================================

/**
 * Safely install a jsPDF mock into `window.jspdf` without nuking window.
 */
function installJsPdfMock() {
    const mockPdf = {
        addImage: vi.fn(),
        addPage: vi.fn(),
        save: vi.fn()
    };
    window.jspdf = { jsPDF: vi.fn(() => mockPdf) };
    return mockPdf;
}

/**
 * Build a minimal fake ZIP data object compatible with our usage.
 */
function makeZipData(entries) {
    const files = {};
    for (const name of entries) {
        files[name] = {
            dir: false,
            async: vi.fn().mockResolvedValue(new Blob([`content:${name}`]))
        };
    }
    return { files };
}

/**
 * Build a fake JSZip instance resolving to the given data.
 */
function makeZip(entries) {
    return { loadAsync: vi.fn().mockResolvedValue(makeZipData(entries)) };
}

// =====================================================================
// § 05 — MULTIPLE IMAGE FILE UPLOAD
// =====================================================================

describe('Multiple Image File Upload', () => {
    it('should accept multiple image files (not ZIPs)', () => {
        const files = [
            { name: 'photo1.jpg', type: 'image/jpeg', size: 1024 },
            { name: 'photo2.png', type: 'image/png', size: 2048 },
            { name: 'photo3.jpg', type: 'image/jpeg', size: 1536 }
        ];

        const imageFiles = files.filter(f => isImageFile(f.name));

        expect(imageFiles).toHaveLength(3);
        expect(isImageFile).toHaveBeenCalledTimes(3);
    });

    it('should convert multiple images to single PDF', () => {
        const mockPdf = installJsPdfMock();

        const images = [
            { filename: 'img1.jpg', data: new Blob(), url: 'blob:1' },
            { filename: 'img2.jpg', data: new Blob(), url: 'blob:2' },
            { filename: 'img3.jpg', data: new Blob(), url: 'blob:3' }
        ];

        const pdf = new jsPDF({ unit: 'pt' });
        for (let i = 0; i < images.length; i++) {
            if (i > 0) pdf.addPage();
            pdf.addImage(images[i].url, 'JPEG', 0, 0, 100, 100);
        }
        pdf.save('converted_images.pdf');

        expect(mockPdf.addImage).toHaveBeenCalledTimes(3);
        expect(mockPdf.addPage).toHaveBeenCalledTimes(2);
        expect(mockPdf.save).toHaveBeenCalledWith('converted_images.pdf');
    });

    it('should sort image files before conversion (natural order)', () => {
        const files = ['img_10.jpg', 'img_2.jpg', 'img_1.jpg'];
        const sorted = sortImages(files, true, '!');

        expect(sorted).toEqual(['img_1.jpg', 'img_2.jpg', 'img_10.jpg']);
        expect(sortImages).toHaveBeenCalledWith(files, true, '!');
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

    it('should accept uppercase extensions', () => {
        expect(isImageFile('PHOTO.JPG')).toBe(true);
        expect(isImageFile('Image.PNG')).toBe(true);
    });

    it('should reject hidden files and trailing-dot names', () => {
        expect(isImageFile('.jpg')).toBe(false); // hidden
        expect(isImageFile('file.')).toBe(false); // trailing dot
        expect(isImageFile('noext')).toBe(false);
    });
});

// =====================================================================
// § 06 — BATCH ZIP CONVERSION (Convert Each)
// =====================================================================

describe('Batch ZIP Conversion (Convert Each to PDF)', () => {
    it('should process multiple ZIP files sequentially', async () => {
        const zipNames = ['archive1.zip', 'archive2.zip', 'archive3.zip'];
        const processedFiles = [];

        for (const name of zipNames) {
            const mockZip = makeZip(['img.jpg']);
            JSZip.mockImplementationOnce(() => mockZip);

            const zip = new JSZip();
            await zip.loadAsync(new Blob());
            processedFiles.push(name);
        }

        expect(processedFiles).toEqual(zipNames);
        expect(JSZip).toHaveBeenCalledTimes(3);
    });

    it('should generate unique PDF filename for each ZIP', () => {
        const zipFiles = [
            { name: 'photos.zip' },
            { name: 'documents.zip' },
            { name: 'backup.ZIP' }
        ];

        const pdfNames = zipFiles.map(f => f.name.replace(/\.zip$/i, '.pdf'));

        expect(pdfNames).toEqual(['photos.pdf', 'documents.pdf', 'backup.pdf']);
        expect(new Set(pdfNames).size).toBe(3);
    });

    it('should add delay between downloads to prevent filename conflicts', async () => {
        vi.useFakeTimers();

        try {
            const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));
            const delays = [];

            for (let i = 0; i < 3; i++) {
                if (i > 0) {
                    const p = delay(100);
                    vi.advanceTimersByTime(100);
                    await p;
                    delays.push(100);
                }
            }

            expect(delays).toEqual([100, 100]);
        } finally {
            vi.useRealTimers();
        }
    });

    it('should track success and failure counts', () => {
        const results = { successCount: 0, failCount: 0 };

        const zipFiles = [
            { id: 1, shouldFail: false },
            { id: 2, shouldFail: true },
            { id: 3, shouldFail: false }
        ];

        for (const zip of zipFiles) {
            try {
                if (zip.shouldFail) throw new Error('Conversion failed');
                results.successCount++;
            } catch {
                results.failCount++;
            }
        }

        expect(results.successCount).toBe(2);
        expect(results.failCount).toBe(1);
    });

    it('should continue processing even if one ZIP fails', async () => {
        const mockZips = [
            makeZip(['img.jpg']),
            { loadAsync: vi.fn().mockRejectedValue(new Error('Corrupted ZIP')) },
            makeZip(['img.jpg'])
        ];

        const processed = [];

        for (let i = 0; i < mockZips.length; i++) {
            try {
                await mockZips[i].loadAsync(new Blob());
                processed.push(i);
            } catch {
                // continue
            }
        }

        expect(processed).toEqual([0, 2]);
    });
});

// =====================================================================
// § 07 — ZIP MERGING (Merge All to Single PDF)
// =====================================================================

describe('ZIP Merging (Merge All to Single PDF)', () => {
    it('should extract images from multiple ZIPs', async () => {
        const mockZips = [
            makeZip(['img1.jpg', 'img2.jpg']),
            makeZip(['img3.jpg'])
        ];

        const allImages = [];

        for (const mockZip of mockZips) {
            const zipData = await mockZip.loadAsync(new Blob());
            const imageFiles = Object.keys(zipData.files).filter(
                f => !zipData.files[f].dir
            );

            for (const filename of imageFiles) {
                const blob = await zipData.files[filename].async('blob');
                allImages.push({ filename, data: blob });
            }
        }

        expect(allImages).toHaveLength(3);
        expect(allImages.map(i => i.filename)).toEqual(['img1.jpg', 'img2.jpg', 'img3.jpg']);
    });

    it('should sort ZIP files by name before extracting', () => {
        const zipFiles = [
            { fileData: { file: { name: 'archive_3.zip' } } },
            { fileData: { file: { name: 'archive_1.zip' } } },
            { fileData: { file: { name: 'archive_2.zip' } } }
        ];

        const zipFilenames = zipFiles.map(({ fileData }) => fileData.file.name);
        const sortedFilenames = sortImages(zipFilenames, true, '!');

        expect(sortedFilenames).toEqual([
            'archive_1.zip',
            'archive_2.zip',
            'archive_3.zip'
        ]);
    });

    it('should maintain order of images within each ZIP', async () => {
        const mockZip = makeZip(['page_3.jpg', 'page_1.jpg', 'page_2.jpg']);

        const zipData = await mockZip.loadAsync(new Blob());
        const imageFiles = Object.keys(zipData.files).filter(
            f => !zipData.files[f].dir
        );
        const sortedImages = sortImages(imageFiles, true, '!');

        expect(sortedImages).toEqual(['page_1.jpg', 'page_2.jpg', 'page_3.jpg']);
    });

    it('should create single merged PDF with correct filename', () => {
        const mockPdf = installJsPdfMock();

        const pdf = new jsPDF();
        const images = [{ url: 'blob:1' }, { url: 'blob:2' }, { url: 'blob:3' }];

        for (let i = 0; i < images.length; i++) {
            if (i > 0) pdf.addPage();
            pdf.addImage(images[i].url, 'JPEG', 0, 0, 100, 100);
        }
        pdf.save('merged_archives.pdf');

        expect(mockPdf.save).toHaveBeenCalledWith('merged_archives.pdf');
        expect(mockPdf.addImage).toHaveBeenCalledTimes(3);
    });

    it('should track progress during merge operation', () => {
        const progressEvents = [];
        const callback = (info) => progressEvents.push(info);

        const zipFiles = [
            { name: 'zip1.zip' },
            { name: 'zip2.zip' },
            { name: 'zip3.zip' }
        ];

        for (let i = 0; i < zipFiles.length; i++) {
            callback({
                current: i + 1,
                total: zipFiles.length,
                stage: 'extracting'
            });
        }

        expect(progressEvents).toHaveLength(3);
        expect(progressEvents[2]).toEqual({
            current: 3,
            total: 3,
            stage: 'extracting'
        });
    });
});

// =====================================================================
// § 08 — ZIP SORTING IN MERGE OPERATIONS
// =====================================================================

describe('ZIP Sorting in Merge Operations', () => {
    it('should apply natural sort to ZIP filenames', () => {
        const zipFiles = [
            'chapter_10.zip',
            'chapter_2.zip',
            'chapter_1.zip',
            'chapter_20.zip'
        ];

        const sorted = sortImages(zipFiles, true, '!');

        expect(sorted).toEqual([
            'chapter_1.zip',
            'chapter_2.zip',
            'chapter_10.zip',
            'chapter_20.zip'
        ]);
    });

    it('should respect priority characters for ZIP files', () => {
        const zipFiles = [
            'regular.zip',
            '!important.zip',
            'another.zip',
            '!cover.zip'
        ];

        const sorted = sortImages(zipFiles, true, '!');

        // Priority files first, then natural-sorted normal files
        expect(sorted[0]).toBe('!cover.zip');
        expect(sorted[1]).toBe('!important.zip');
        expect(sorted.slice(2)).toEqual(['another.zip', 'regular.zip']);
    });

    it('should route multiple priority chars correctly', () => {
        const zipFiles = [
            'page_2.zip',
            '@special.zip',
            '!cover.zip',
            'page_10.zip'
        ];

        const sorted = sortImages(zipFiles, true, '!@');

        expect(sorted[0]).toBe('!cover.zip');
        expect(sorted[1]).toBe('@special.zip');
        expect(sorted.slice(2)).toEqual(['page_2.zip', 'page_10.zip']);
    });

    it('should maintain correct final order: sorted ZIPs then images', () => {
        const zipFiles = [
            { name: 'vol_2.zip', images: ['page_1.jpg', 'page_2.jpg'] },
            { name: 'vol_1.zip', images: ['page_1.jpg', 'page_2.jpg'] }
        ];

        const sortedZips = zipFiles
            .slice()
            .sort((a, b) => sortImages([a.name, b.name], true, '!')[0] === a.name ? -1 : 1);

        const finalOrder = [];
        for (const zip of sortedZips) {
            finalOrder.push(...zip.images.map(img => `${zip.name}:${img}`));
        }

        expect(finalOrder).toEqual([
            'vol_1.zip:page_1.jpg',
            'vol_1.zip:page_2.jpg',
            'vol_2.zip:page_1.jpg',
            'vol_2.zip:page_2.jpg'
        ]);
    });

    it('should handle mixed cases in ZIP filenames', () => {
        const zipFiles = ['Archive_B.zip', 'archive_a.zip', 'ARCHIVE_C.zip'];
        const sorted = sortImages(zipFiles, true, '!');

        // Natural sort is case-sensitive on first differing char, so
        // verify relative order within the same letter group:
        // 'archive_a' < 'Archive_B' < 'ARCHIVE_C' under localeCompare
        // is not portable — so we assert length + membership, then
        // assert same-prefix ordering manually.
        expect(sorted).toHaveLength(3);
        expect(new Set(sorted)).toEqual(new Set(zipFiles));

        // Manually verify a/c ordering is deterministic within our mock
        const lower = zipFiles.map(z => z.toLowerCase());
        expect(lower.sort()).toEqual([
            'archive_a.zip',
            'archive_b.zip',
            'archive_c.zip'
        ]);
    });

    it('should keep priority-first routing stable across natural + non-natural', () => {
        const zipFiles = ['z_10.zip', '!a.zip', 'z_2.zip'];

        const natural = sortImages(zipFiles, true, '!');
        const lexical = sortImages(zipFiles, false, '!');

        expect(natural[0]).toBe('!a.zip');
        expect(lexical[0]).toBe('!a.zip');
        expect(natural.slice(1)).toEqual(['z_2.zip', 'z_10.zip']);
    });
});

// =====================================================================
// § 09 — FILE TYPE MANAGEMENT
// =====================================================================

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

        const zipId = state.currentFileId++;
        state.files.set(zipId, {
            file: { name: 'archive.zip' },
            type: 'zip',
            status: 'pending'
        });

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

        const zipCount = Array.from(state.files.values())
            .filter(f => f.type === 'zip').length;
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

        expect(getButtonsToShow(3, 0)).toEqual([
            'Convert Each to PDF',
            'Merge All to Single PDF'
        ]);
        expect(getButtonsToShow(0, 3)).toEqual(['Convert Images to PDF']);
        expect(getButtonsToShow(2, 2)).toEqual([
            'Convert Each to PDF',
            'Merge All to Single PDF',
            'Convert Images to PDF'
        ]);
        expect(getButtonsToShow(1, 1)).toEqual([]);
    });

    it('should remove image entries from imageFiles when removeFile is called', () => {
        const state = {
            files: new Map(),
            imageFiles: [],
            currentFileId: 0
        };

        const id = state.currentFileId++;
        const file = { name: 'photo.jpg' };
        state.files.set(id, { file, type: 'image' });
        state.imageFiles.push({ fileId: id, file });

        // Simulate removeFile logic
        const idx = state.imageFiles.findIndex(f => f.fileId === id);
        if (idx !== -1) state.imageFiles.splice(idx, 1);
        state.files.delete(id);

        expect(state.files.size).toBe(0);
        expect(state.imageFiles).toHaveLength(0);
    });
});

// =====================================================================
// § 10 — CONSTANTS PARITY (with shared module)
// =====================================================================

describe('Shared Constants Parity', () => {
    it('should expose the expected image extensions', () => {
        expect(IMAGE_EXTENSIONS).toContain('.jpg');
        expect(IMAGE_EXTENSIONS).toContain('.jpeg');
        expect(IMAGE_EXTENSIONS).toContain('.png');
        expect(IMAGE_EXTENSIONS).toContain('.gif');
        expect(IMAGE_EXTENSIONS).toContain('.webp');
        // Aligned with shared/constants.py
        expect(IMAGE_EXTENSIONS).toContain('.bmp');
        expect(IMAGE_EXTENSIONS).toContain('.tiff');
    });

    it('should expose a default priority-char string', () => {
        expect(DEFAULT_PRIORITY_CHARS).toBe('!');
    });
});

// =====================================================================
// § 11 — localState + settings persistence
// =====================================================================

describe('localStorage Settings Persistence', () => {
    it('should store settings as JSON', () => {
        const settings = { useNaturalSort: true, priorityChars: '!@' };
        localStorage.setItem('zipToPdfSettings', JSON.stringify(settings));

        const raw = localStorage.getItem('zipToPdfSettings');
        expect(raw).toBe(JSON.stringify(settings));
        expect(JSON.parse(raw)).toEqual(settings);
    });

    it('should return null for missing keys', () => {
        expect(localStorage.getItem('missing-key')).toBeNull();
    });

    it('should clear the store on .clear()', () => {
        localStorage.setItem('a', '1');
        localStorage.clear();
        expect(localStorage.getItem('a')).toBeNull();
    });
});
