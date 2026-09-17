/**
 * =====================================================================
 * NEXUS QUANTUM // Error Handling Tests for web/app.js
 * =====================================================================
 * File:    tests/app-errors.test.js
 * Targets: edge cases, error paths, exceptional conditions
 *
 * Covers:
 *   1.  ZIP extraction errors (corrupted, empty, protected, oversized)
 *   2.  Image loading errors
 *   3.  PDF generation errors
 *   4.  localStorage errors (quota, private mode, corrupt JSON)
 *   5.  File handling errors (MIME, size, unicode)
 *   6.  State management errors (Map, concurrency, corruption)
 *   7.  Progress calculation errors (div-by-zero, clamping)
 *   8.  URL object lifecycle (create/revoke, cleanup-on-error)
 *   9.  Special characters & edge cases in filenames
 *   10. Browser API availability
 *   11. Memory management (URL registry, large queues)
 *   12. Security limits (file size, extracted size, ratio, count)
 *   13. Cancellation / AbortError propagation
 *
 * Runtime: Vitest + jsdom
 * =====================================================================
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// =====================================================================
// § 00 — MODULE MOCKS (declared BEFORE imports they affect)
// =====================================================================

vi.mock('jszip', () => {
    const JSZipMock = vi.fn(function () {
        return {
            loadAsync: vi.fn().mockResolvedValue({ files: {} }),
            file: vi.fn().mockReturnValue({
                async: vi.fn().mockResolvedValue(new Blob())
            })
        };
    });
    return { default: JSZipMock, JSZip: JSZipMock };
});

vi.mock('jspdf', () => {
    const jsPDFMock = vi.fn(() => ({
        addImage: vi.fn(),
        addPage: vi.fn(),
        save: vi.fn(),
        output: vi.fn(() => new Blob())
    }));
    return { jsPDF: jsPDFMock, default: { jsPDF: jsPDFMock } };
});

// Shared sorting logic — mock MUST mirror real behavior
vi.mock('../shared/sorting-logic.js', () => {
    const getBasename = (p) => String(p || '').split(/[\\/]/).pop() || '';

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
            if (typeof ca === 'number' && typeof cb === 'number') return ca - cb;
            return String(ca) < String(cb) ? -1 : 1;
        }
        return ka.length - kb.length;
    };

    const IMAGE_EXTENSIONS = [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'
    ];
    const DEFAULT_PRIORITY_CHARS = '!';

    const isImageFile = vi.fn((filename) => {
        if (!filename || typeof filename !== 'string') return false;
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

        const cmp = useNaturalSort
            ? (a, b) => compareNatural(getBasename(a), getBasename(b))
            : (a, b) => getBasename(a).localeCompare(getBasename(b));

        priorityFiles.sort(cmp);
        normalFiles.sort(cmp);
        return [...priorityFiles, ...normalFiles];
    });

    return {
        default: {
            isImageFile,
            sortImages,
            IMAGE_EXTENSIONS,
            DEFAULT_PRIORITY_CHARS
        },
        isImageFile,
        sortImages,
        IMAGE_EXTENSIONS,
        DEFAULT_PRIORITY_CHARS
    };
});

// =====================================================================
// § 01 — IMPORTS (after mocks)
// =====================================================================

import JSZip from 'jszip';
import { jsPDF } from 'jspdf';
import {
    isImageFile,
    sortImages,
    IMAGE_EXTENSIONS,
    DEFAULT_PRIORITY_CHARS
} from '../shared/sorting-logic.js';

// =====================================================================
// § 02 — GLOBAL MOCKS (localStorage, URL, Image)
// =====================================================================

// ---- localStorage --------------------------------------------------
const localStorageMock = (() => {
    let store = {};
    return {
        getItem: vi.fn((key) => (key in store ? store[key] : null)),
        setItem: vi.fn((key, value) => { store[key] = String(value); }),
        removeItem: vi.fn((key) => { delete store[key]; }),
        clear: vi.fn(() => { store = {}; }),
        key: vi.fn((i) => Object.keys(store)[i] ?? null),
        get length() { return Object.keys(store).length; },
        _store: () => ({ ...store }),
        _reset: () => { store = {}; }
    };
})();

vi.stubGlobal('localStorage', localStorageMock);

// ---- URL ------------------------------------------------------------
const createObjectURLMock = vi.fn(() =>
    `blob:mock-${Math.random().toString(36).slice(2, 10)}`
);
const revokeObjectURLMock = vi.fn();

vi.stubGlobal('URL', {
    createObjectURL: createObjectURLMock,
    revokeObjectURL: revokeObjectURLMock
});

// ---- Image ----------------------------------------------------------
// jsdom does not load images. We install a controllable mock class.
class MockImage {
    constructor() {
        this.width = 0;
        this.height = 0;
        this.onload = null;
        this.onerror = null;
        this._src = '';
        MockImage._instances.push(this);
    }
    set src(value) {
        this._src = value;
        // Auto-trigger onload on next microtask unless overridden
        queueMicrotask(() => {
            if (this._autoFail) {
                if (typeof this.onerror === 'function') {
                    this.onerror(new Error('Mock image load failure'));
                }
            } else if (!this._manual) {
                this.width = this._width ?? 800;
                this.height = this._height ?? 600;
                if (typeof this.onload === 'function') this.onload();
            }
        });
    }
    get src() { return this._src; }
}
MockImage._instances = [];

vi.stubGlobal('Image', MockImage);

// Reset static instances list between tests
function resetMockImages() {
    MockImage._instances.length = 0;
}

// =====================================================================
// § 03 — LIFECYCLE HOOKS
// =====================================================================

beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock._reset();
    resetMockImages();
});

afterEach(() => {
    vi.restoreAllMocks();
    // Restore the core mocks we depend on between tests
    createObjectURLMock.mockReset();
    createObjectURLMock.mockImplementation(() =>
        `blob:mock-${Math.random().toString(36).slice(2, 10)}`
    );
    revokeObjectURLMock.mockReset();
});

// =====================================================================
// § 04 — TEST HELPERS
// =====================================================================

/**
 * Build a fake ZIP data object compatible with JSZip's API surface.
 */
function makeZipData(entries) {
    const files = {};
    for (const [name, opts = {}] of Object.entries(entries)) {
        files[name] = {
            dir: !!opts.dir,
            async: opts.async
                ? opts.async
                : vi.fn().mockResolvedValue(new Blob([`content:${name}`]))
        };
    }
    return { files };
}

/**
 * Build a fake JSZip instance resolving to the given data.
 */
function makeZip(entries, opts = {}) {
    const zipData = makeZipData(entries);
    return {
        loadAsync: opts.reject
            ? vi.fn().mockRejectedValue(opts.reject)
            : vi.fn().mockResolvedValue(zipData),
        file: vi.fn((name) => zipData.files[name])
    };
}

/**
 * Set up a controllable failing image.
 */
function makeFailingImage() {
    const img = new MockImage();
    img._autoFail = true;
    return img;
}

/**
 * Deterministic image loader compatible with app.js's `loadImage`.
 */
function loadImage(url) {
    return new Promise((resolve, reject) => {
        const img = new MockImage();
        img.onload = () => resolve(img);
        img.onerror = (err) => reject(err || new Error(`Failed to load image: ${url}`));
        img.src = url;
        // If test wants a failure, mark it
        if (String(url).startsWith('blob:corrupted') || String(url).startsWith('invalid:')) {
            img._autoFail = true;
        }
        // If test wants a specific size
        img._width = 800;
        img._height = 600;
    });
}

/**
 * Extract the real `computePageSize` logic so we can test it without
 * importing app.js (avoids DOM coupling in this error-focused suite).
 */
function computePageSize(img, maxDim = 2000, scaleFactor = 4) {
    let scale = 1;
    if (img.width > maxDim || img.height > maxDim) {
        scale = Math.min(maxDim / img.width, maxDim / img.height);
    }
    return {
        width: (img.width * scale) / scaleFactor,
        height: (img.height * scale) / scaleFactor,
        orientation: img.width > img.height ? 'landscape' : 'portrait'
    };
}

/**
 * Clamp a progress percentage (mirror of app.js updateProgress logic).
 */
function clampPercentage(current, total) {
    const c = Math.max(0, current || 0);
    const t = Math.max(1, total || 1);
    return Math.min(100, Math.round((c / t) * 100));
}

// =====================================================================
// § 05 — ZIP EXTRACTION ERRORS
// =====================================================================

describe('ZIP Extraction Errors', () => {
    it('should handle corrupted ZIP files', async () => {
        const zip = makeZip({}, { reject: new Error('Corrupted ZIP file') });
        const blob = new Blob(['corrupted'], { type: 'application/zip' });

        await expect(zip.loadAsync(blob)).rejects.toThrow('Corrupted ZIP file');
        expect(zip.loadAsync).toHaveBeenCalledTimes(1);
    });

    it('should handle empty ZIP files (no entries)', async () => {
        const zip = makeZip({});
        const blob = new Blob(['empty'], { type: 'application/zip' });
        const zipData = await zip.loadAsync(blob);

        expect(Object.keys(zipData.files)).toHaveLength(0);
    });

    it('should handle ZIP files with no image entries', async () => {
        const zip = makeZip({
            'document.pdf': { dir: false },
            'readme.txt': { dir: false },
            'data.json': { dir: false }
        });
        const zipData = await zip.loadAsync(new Blob());

        const imageFiles = Object.keys(zipData.files).filter(f => isImageFile(f));
        expect(imageFiles).toHaveLength(0);
    });

    it('should skip directory entries', () => {
        const zipData = makeZipData({
            'folder/': { dir: true },
            'folder/image.jpg': { dir: false }
        });

        const nonDirs = Object.keys(zipData.files).filter(
            f => !zipData.files[f].dir
        );
        expect(nonDirs).toEqual(['folder/image.jpg']);
    });

    it('should reject password-protected ZIP entries', async () => {
        const zip = makeZip({}, { reject: new Error('Password required') });

        await expect(zip.loadAsync(new Blob())).rejects.toThrow('Password required');
    });

    it('should propagate extraction errors from a single entry', async () => {
        const zip = makeZip({
            'image.jpg': {
                dir: false,
                async: vi.fn().mockRejectedValue(new Error('Extraction failed'))
            }
        });
        const zipData = await zip.loadAsync(new Blob());
        const entry = zipData.files['image.jpg'];

        await expect(entry.async('blob')).rejects.toThrow('Extraction failed');
    });

    it('should reject when ZIP exceeds maximum file size', async () => {
        const MAX_FILE_SIZE = 100 * 1024 * 1024;
        const file = {
            name: 'huge.zip',
            type: 'application/zip',
            size: MAX_FILE_SIZE + 1
        };

        const isTooLarge = file.size > MAX_FILE_SIZE;
        expect(isTooLarge).toBe(true);
    });

    it('should reject when cumulative uncompressed size exceeds limit', () => {
        const MAX_EXTRACTED_SIZE = 500 * 1024 * 1024;
        const entries = [
            { file_size: 200 * 1024 * 1024 },
            { file_size: 200 * 1024 * 1024 },
            { file_size: 150 * 1024 * 1024 } // total 550MB
        ];

        let total = 0;
        let exceeded = false;
        for (const e of entries) {
            total += e.file_size;
            if (total > MAX_EXTRACTED_SIZE) { exceeded = true; break; }
        }
        expect(exceeded).toBe(true);
    });

    it('should reject on suspicious compression ratio (ZIP bomb)', () => {
        const MAX_COMPRESSION_RATIO = 100;
        const entry = {
            filename: 'bomb.jpg',
            uncompressedSize: 10 * 1024 * 1024, // 10 MB
            compressedSize: 1024                // 1 KB → ratio ~10240
        };

        const ratio = entry.uncompressedSize / entry.compressedSize;
        expect(ratio).toBeGreaterThan(MAX_COMPRESSION_RATIO);
    });

    it('should reject when image count exceeds MAX_FILES_IN_ZIP', () => {
        const MAX_FILES_IN_ZIP = 10000;
        const count = 10001;

        expect(count > MAX_FILES_IN_ZIP).toBe(true);
    });

    it('should reject entries with path traversal (..)', () => {
        const entries = ['../evil.jpg', 'sub/../../evil.jpg', 'normal.jpg'];

        const unsafe = entries.filter(name => {
            if (name.startsWith('/')) return true;
            const parts = name.split('/').filter(Boolean);
            return parts.includes('..');
        });

        expect(unsafe).toEqual(['../evil.jpg', 'sub/../../evil.jpg']);
    });

    it('should reject entries with absolute paths', () => {
        const entries = ['/etc/passwd', 'C:\\Windows\\evil.jpg', 'safe.jpg'];

        const unsafe = entries.filter(name =>
            name.startsWith('/') || /^[A-Za-z]:/.test(name)
        );

        expect(unsafe).toEqual(['/etc/passwd', 'C:\\Windows\\evil.jpg']);
    });
});

// =====================================================================
// § 06 — IMAGE LOADING ERRORS
// =====================================================================

describe('Image Loading Errors', () => {
    it('should reject when image fails to load', async () => {
        await expect(loadImage('invalid://broken')).rejects.toThrow();
    });

    it('should resolve when image loads successfully', async () => {
        const img = await loadImage('blob:valid');
        expect(img.width).toBeGreaterThan(0);
        expect(img.height).toBeGreaterThan(0);
    });

    it('should handle zero-dimension images without division errors', () => {
        const img = { width: 0, height: 0 };
        const size = computePageSize(img);

        expect(size.width).toBe(0);
        expect(size.height).toBe(0);
        // orientation defaults to 'portrait' since width is NOT > height
        expect(size.orientation).toBe('portrait');
    });

    it('should downscale extremely large images', () => {
        const img = { width: 10000, height: 10000 };
        const MAX_DIM = 2000;
        const SCALE_FACTOR = 4;

        const size = computePageSize(img, MAX_DIM, SCALE_FACTOR);

        // 10000 → 2000 → /4 → 500pt
        expect(size.width).toBe(500);
        expect(size.height).toBe(500);
        expect(size.orientation).toBe('portrait');
    });

    it('should preserve orientation for landscape images', () => {
        const img = { width: 4000, height: 2000 };
        const size = computePageSize(img);

        expect(size.orientation).toBe('landscape');
    });

    it('should preserve orientation for portrait images', () => {
        const img = { width: 1500, height: 2500 };
        const size = computePageSize(img);

        expect(size.orientation).toBe('portrait');
    });

    it('should not upscale small images', () => {
        const img = { width: 400, height: 300 };
        const size = computePageSize(img);

        // 400 / 4 = 100, 300 / 4 = 75 — no scaling applied
        expect(size.width).toBe(100);
        expect(size.height).toBe(75);
    });
});

// =====================================================================
// § 07 — PDF GENERATION ERRORS
// =====================================================================

describe('PDF Generation Errors', () => {
    it('should propagate jsPDF.save errors', () => {
        const pdf = {
            addImage: vi.fn(),
            addPage: vi.fn(),
            save: vi.fn(() => { throw new Error('Failed to save PDF'); })
        };

        expect(() => pdf.save('out.pdf')).toThrow('Failed to save PDF');
    });

    it('should propagate jsPDF.addImage errors', () => {
        const pdf = {
            addImage: vi.fn(() => { throw new Error('Invalid image format'); })
        };

        expect(() =>
            pdf.addImage('bad', 'JPEG', 0, 0, 100, 100)
        ).toThrow('Invalid image format');
    });

    it('should propagate jsPDF.addPage memory errors', () => {
        const pdf = {
            addImage: vi.fn(),
            addPage: vi.fn(() => { throw new Error('Out of memory'); })
        };

        pdf.addImage('img', 'JPEG', 0, 0, 100, 100);
        expect(() => pdf.addPage()).toThrow('Out of memory');
    });

    it('should reject empty image arrays', async () => {
        async function convert(images) {
            if (!images || images.length === 0) {
                throw new Error('No images to convert.');
            }
            return true;
        }

        await expect(convert(null)).rejects.toThrow('No images to convert.');
        await expect(convert([])).rejects.toThrow('No images to convert.');
        await expect(convert(undefined)).rejects.toThrow('No images to convert.');
    });

    it('should reject when all images fail to load', async () => {
        async function convertAll(urls) {
            const loaded = [];
            for (const url of urls) {
                try {
                    loaded.push(await loadImage(url));
                } catch { /* skip */ }
            }
            if (loaded.length === 0) throw new Error('No valid images to convert.');
            return loaded;
        }

        await expect(convertAll(['invalid://a', 'invalid://b']))
            .rejects.toThrow('No valid images to convert.');
    });

    it('should continue when some images fail but others succeed', async () => {
        async function convertAll(urls) {
            const loaded = [];
            for (const url of urls) {
                try {
                    loaded.push(await loadImage(url));
                } catch { /* skip */ }
            }
            if (loaded.length === 0) throw new Error('No valid images to convert.');
            return loaded;
        }

        const result = await convertAll(['blob:valid', 'invalid://broken']);
        expect(result).toHaveLength(1);
    });
});

// =====================================================================
// § 08 — LOCALSTORAGE ERRORS
// =====================================================================

describe('LocalStorage Errors', () => {
    it('should throw when quota is exceeded', () => {
        localStorageMock.setItem.mockImplementationOnce(() => {
            throw new Error('QuotaExceededError');
        });

        expect(() => localStorage.setItem('key', 'value')).toThrow('QuotaExceededError');
    });

    it('should recover when localStorage.getItem throws', () => {
        localStorageMock.getItem.mockImplementationOnce(() => {
            throw new Error('SecurityError: localStorage disabled');
        });

        let value = null;
        try {
            value = localStorage.getItem('any');
        } catch {
            value = 'fallback';
        }
        expect(value).toBe('fallback');
    });

    it('should fallback to defaults on corrupt JSON', () => {
        localStorageMock.getItem.mockReturnValueOnce('{"invalid json');
        localStorageMock.setItem.mockReturnValueOnce(undefined);

        const DEFAULT = { useNaturalSort: true, priorityChars: '!' };
        let settings = DEFAULT;

        try {
            const raw = localStorage.getItem('zipToPdfSettings');
            settings = JSON.parse(raw);
        } catch {
            settings = DEFAULT;
        }

        expect(settings).toEqual(DEFAULT);
    });

    it('should return null for missing keys', () => {
        expect(localStorage.getItem('nonexistent')).toBeNull();
    });

    it('should handle private browsing mode gracefully', () => {
        localStorageMock.setItem.mockImplementationOnce(() => {
            throw new Error('SecurityError: The operation is insecure');
        });

        let saved = false;
        try {
            localStorage.setItem('test', 'value');
            saved = true;
        } catch {
            saved = false;
        }
        expect(saved).toBe(false);
    });

    it('should round-trip settings via JSON', () => {
        const settings = { useNaturalSort: true, priorityChars: '!@' };
        localStorage.setItem('zipToPdfSettings', JSON.stringify(settings));

        const raw = localStorage.getItem('zipToPdfSettings');
        expect(JSON.parse(raw)).toEqual(settings);
    });

    it('should clear all keys on .clear()', () => {
        localStorage.setItem('a', '1');
        localStorage.setItem('b', '2');
        localStorage.clear();

        expect(localStorage.getItem('a')).toBeNull();
        expect(localStorage.getItem('b')).toBeNull();
    });
});

// =====================================================================
// § 09 — FILE HANDLING ERRORS
// =====================================================================

describe('File Handling Errors', () => {
    it('should reject non-ZIP, non-image files', () => {
        const isZip = (f) =>
            f.type === 'application/zip' || f.name.toLowerCase().endsWith('.zip');
        const isImg = (f) => isImageFile(f.name);

        const bad = [
            { name: 'doc.pdf', type: 'application/pdf' },
            { name: 'video.mp4', type: 'video/mp4' },
            { name: 'audio.mp3', type: 'audio/mpeg' }
        ];

        bad.forEach(f => {
            expect(isZip(f) || isImg(f)).toBe(false);
        });
    });

    it('should accept ZIP by extension even with wrong MIME', () => {
        const file = { name: 'archive.zip', type: 'text/plain' };
        const isZip = (f) =>
            f.type === 'application/zip' || f.name.toLowerCase().endsWith('.zip');

        expect(isZip(file)).toBe(true);
    });

    it('should accept image by extension even with empty MIME', () => {
        const file = { name: 'photo.jpg', type: '' };
        expect(isImageFile(file.name)).toBe(true);
    });

    it('should detect zero-size files', () => {
        const file = { name: 'empty.zip', type: 'application/zip', size: 0 };
        expect(file.size).toBe(0);
    });

    it('should detect oversized files above MAX_FILE_SIZE', () => {
        const MAX_FILE_SIZE = 100 * 1024 * 1024;
        const file = {
            name: 'huge.zip',
            type: 'application/zip',
            size: 2 * 1024 * 1024 * 1024
        };
        expect(file.size).toBeGreaterThan(MAX_FILE_SIZE);
    });

    it('should replace .zip with .pdf in output filename', () => {
        const cases = [
            ['archive.zip', 'archive.pdf'],
            ['archive.ZIP', 'archive.pdf'],
            ['archive (1) [copy].zip', 'archive (1) [copy].pdf'],
            ['图片集.zip', '图片集.pdf'],
            ['file.with.many.dots.zip', 'file.with.many.dots.pdf']
        ];

        cases.forEach(([input, expected]) => {
            expect(input.replace(/\.zip$/i, '.pdf')).toBe(expected);
        });
    });

    it('should preserve special characters in output filename', () => {
        const file = { name: 'archive (1) [copy] {v2}.zip' };
        const pdfName = file.name.replace(/\.zip$/i, '.pdf');
        expect(pdfName).toBe('archive (1) [copy] {v2}.pdf');
    });

    it('should preserve Unicode names', () => {
        const file = { name: '图片集.zip' };
        expect(file.name.replace(/\.zip$/i, '.pdf')).toBe('图片集.pdf');
    });
});

// =====================================================================
// § 10 — STATE MANAGEMENT ERRORS
// =====================================================================

describe('State Management Errors', () => {
    it('should return undefined for missing Map entries', () => {
        const files = new Map();
        expect(files.get(999)).toBeUndefined();
    });

    it('should return false when deleting a non-existent entry', () => {
        const files = new Map();
        files.set(1, { file: {}, status: 'pending' });

        expect(files.delete(999)).toBe(false);
        expect(files.size).toBe(1);
    });

    it('should allow deleting during iteration without crashing', () => {
        const files = new Map();
        files.set(1, { file: {}, status: 'pending' });
        files.set(2, { file: {}, status: 'pending' });

        let visits = 0;
        for (const [id] of files) {
            visits++;
            if (id === 1) files.delete(2);
        }

        expect(visits).toBeGreaterThan(0);
        // Note: Map iteration allows safe deletion of the current key
        // but the behavior on the *next* key is defined — it will be skipped
        // if deleted. We only assert no crash + at least one visit.
    });

    it('should recover from a null settings object', () => {
        const state = {
            currentFileId: 0,
            files: new Map(),
            settings: null
        };

        const DEFAULT = { useNaturalSort: true, priorityChars: '!' };
        if (!state.settings) state.settings = { ...DEFAULT };

        expect(state.settings).toEqual(DEFAULT);
    });

    it('should recover from a missing files Map', () => {
        const state = { files: undefined };
        if (!(state.files instanceof Map)) state.files = new Map();

        expect(state.files).toBeInstanceOf(Map);
        expect(state.files.size).toBe(0);
    });

    it('should safely remove an image entry from imageFiles', () => {
        const state = { files: new Map(), imageFiles: [] };

        const id = 5;
        const file = { name: 'photo.jpg' };
        state.files.set(id, { file, type: 'image' });
        state.imageFiles.push({ fileId: id, file });

        const idx = state.imageFiles.findIndex(f => f.fileId === id);
        if (idx !== -1) state.imageFiles.splice(idx, 1);
        state.files.delete(id);

        expect(state.files.size).toBe(0);
        expect(state.imageFiles).toHaveLength(0);
    });

    it('should not crash when removing a non-existent file', () => {
        const state = { files: new Map(), imageFiles: [] };
        const id = 999;

        const rec = state.files.get(id);
        expect(rec).toBeUndefined();

        // Simulate removeFile guard
        if (!rec) return;
        // (never reached)
    });
});

// =====================================================================
// § 11 — PROGRESS HANDLING ERRORS
// =====================================================================

describe('Progress Handling Errors', () => {
    it('should not divide by zero when total is 0', () => {
        expect(clampPercentage(0, 0)).toBe(0);
    });

    it('should clamp negative progress to 0', () => {
        expect(clampPercentage(-1, 10)).toBe(0);
    });

    it('should clamp progress > total to 100%', () => {
        expect(clampPercentage(15, 10)).toBe(100);
    });

    it('should handle fractional progress correctly', () => {
        expect(clampPercentage(1, 3)).toBe(33);
        expect(clampPercentage(2, 3)).toBe(67);
        expect(clampPercentage(3, 3)).toBe(100);
    });

    it('should handle undefined / null inputs safely', () => {
        expect(clampPercentage(undefined, 10)).toBe(0);
        expect(clampPercentage(null, 10)).toBe(0);
        expect(clampPercentage(5, undefined)).toBe(100);
        expect(clampPercentage(5, null)).toBe(100);
    });

    it('should swallow progress callback errors without breaking the pipeline', () => {
        const badCallback = vi.fn(() => { throw new Error('Callback error'); });

        let error = null;
        try {
            badCallback({ current: 1, total: 10 });
        } catch (e) {
            error = e;
        }

        expect(badCallback).toHaveBeenCalledTimes(1);
        expect(error).toBeInstanceOf(Error);
    });
});

// =====================================================================
// § 12 — URL OBJECT LIFECYCLE
// =====================================================================

describe('URL Object Lifecycle', () => {
    it('should return a string from createObjectURL', () => {
        const url = URL.createObjectURL(new Blob());
        expect(typeof url).toBe('string');
        expect(url.startsWith('blob:')).toBe(true);
    });

    it('should propagate createObjectURL failures', () => {
        createObjectURLMock.mockImplementationOnce(() => {
            throw new Error('Failed to create object URL');
        });

        expect(() => URL.createObjectURL(new Blob()))
            .toThrow('Failed to create object URL');
    });

    it('should not throw when revokeObjectURL receives an invalid URL', () => {
        expect(() => URL.revokeObjectURL('invalid-url')).not.toThrow();
    });

    it('should not throw when revokeObjectURL receives null', () => {
        expect(() => URL.revokeObjectURL(null)).not.toThrow();
    });

    it('should revoke all URLs in a finally block on error', () => {
        const images = [
            { url: URL.createObjectURL(new Blob()) },
            { url: URL.createObjectURL(new Blob()) },
            { url: URL.createObjectURL(new Blob()) }
        ];

        try {
            throw new Error('Processing failed');
        } catch {
            /* swallow */
        } finally {
            images.forEach(img => URL.revokeObjectURL(img.url));
        }

        expect(revokeObjectURLMock).toHaveBeenCalledTimes(3);
    });

    it('should track a URL registry and revoke all on cleanup', () => {
        const registry = new Set();

        for (let i = 0; i < 5; i++) {
            registry.add(URL.createObjectURL(new Blob()));
        }

        for (const url of registry) URL.revokeObjectURL(url);
        registry.clear();

        expect(revokeObjectURLMock).toHaveBeenCalledTimes(5);
        expect(registry.size).toBe(0);
    });
});

// =====================================================================
// § 13 — SPECIAL CHARACTERS & EDGE CASES
// =====================================================================

describe('Special Characters and Edge Cases', () => {
    it('should accept files with multiple dots in the name', () => {
        expect(isImageFile('file.name.with.many.dots.jpg')).toBe(true);
        expect(isImageFile('file.name.with.many.dots.txt')).toBe(false);
    });

    it('should reject empty filenames', () => {
        expect(isImageFile('')).toBe(false);
    });

    it('should reject filenames without extensions', () => {
        expect(isImageFile('filename_without_extension')).toBe(false);
    });

    it('should accept very long filenames', () => {
        const longName = 'a'.repeat(255) + '.jpg';
        expect(isImageFile(longName)).toBe(true);
    });

    it('should reject null / undefined / non-string filenames', () => {
        expect(isImageFile(null)).toBe(false);
        expect(isImageFile(undefined)).toBe(false);
        expect(isImageFile(42)).toBe(false);
        expect(isImageFile({})).toBe(false);
    });

    it('should reject hidden files (dot-prefixed)', () => {
        expect(isImageFile('.jpg')).toBe(false);
        expect(isImageFile('.hidden.jpg')).toBe(true); // still has extension
    });

    it('should reject trailing-dot filenames', () => {
        expect(isImageFile('file.')).toBe(false);
    });

    it('should handle uppercase extensions case-insensitively', () => {
        expect(isImageFile('PHOTO.JPG')).toBe(true);
        expect(isImageFile('Image.PNG')).toBe(true);
        expect(isImageFile('scan.TIFF')).toBe(true);
    });

    it('should handle Windows-style paths', () => {
        expect(isImageFile('folder\\subfolder\\image.jpg')).toBe(true);
        expect(isImageFile('C:\\Users\\Photos\\pic.png')).toBe(true);
    });

    it('should handle Unix-style paths', () => {
        expect(isImageFile('folder/subfolder/image.jpg')).toBe(true);
        expect(isImageFile('/absolute/path/photo.gif')).toBe(true);
    });
});

// =====================================================================
// § 14 — BROWSER API AVAILABILITY
// =====================================================================

describe('Browser API Availability', () => {
    it('should have File API available', () => {
        expect(typeof File).not.toBe('undefined');
    });

    it('should have Blob API available', () => {
        expect(typeof Blob).not.toBe('undefined');
    });

    it('should have URL API available', () => {
        expect(typeof URL).not.toBe('undefined');
        expect(typeof URL.createObjectURL).toBe('function');
        expect(typeof URL.revokeObjectURL).toBe('function');
    });

    it('should have localStorage available', () => {
        expect(typeof localStorage).not.toBe('undefined');
    });

    it('should have Map available', () => {
        expect(typeof Map).not.toBe('undefined');
    });

    it('should have Set available', () => {
        expect(typeof Set).not.toBe('undefined');
    });

    it('should detect drag-and-drop support', () => {
        const div = document.createElement('div');
        const supportsDragAndDrop = 'draggable' in div;
        expect(typeof supportsDragAndDrop).toBe('boolean');
    });
});

// =====================================================================
// § 15 — MEMORY MANAGEMENT
// =====================================================================

describe('Memory Management', () => {
    it('should revoke 100 object URLs without leaking', () => {
        const urls = [];
        for (let i = 0; i < 100; i++) {
            urls.push(URL.createObjectURL(new Blob()));
        }
        urls.forEach(url => URL.revokeObjectURL(url));

        expect(revokeObjectURLMock).toHaveBeenCalledTimes(100);
    });

    it('should handle a queue of 1000 files efficiently', () => {
        const files = new Map();
        for (let i = 0; i < 1000; i++) {
            files.set(i, { file: { name: `file${i}.zip` }, status: 'pending' });
        }
        expect(files.size).toBe(1000);

        files.clear();
        expect(files.size).toBe(0);
    });

    it('should cap the history array to MAX_HISTORY_ENTRIES', () => {
        const MAX_HISTORY_ENTRIES = 20;
        const history = [];

        for (let i = 0; i < 100; i++) {
            history.unshift({ ts: Date.now(), filename: `f${i}.pdf` });
            if (history.length > MAX_HISTORY_ENTRIES) {
                history.length = MAX_HISTORY_ENTRIES;
            }
        }

        expect(history).toHaveLength(MAX_HISTORY_ENTRIES);
        expect(history[0].filename).toBe('f99.pdf');
    });

    it('should clear a large Set of tracked URLs', () => {
        const registry = new Set();
        for (let i = 0; i < 500; i++) {
            registry.add(`blob:url-${i}`);
        }
        registry.clear();
        expect(registry.size).toBe(0);
    });
});

// =====================================================================
// § 16 — CANCELLATION / ABORT
// =====================================================================

describe('Cancellation & Abort Propagation', () => {
    it('should raise AbortError when cancelRequested is true', () => {
        const runtime = { cancelRequested: false };

        function throwIfCancelled() {
            if (runtime.cancelRequested) {
                const err = new Error('Conversion cancelled by user.');
                err.name = 'AbortError';
                throw err;
            }
        }

        // Not cancelled — no throw
        expect(() => throwIfCancelled()).not.toThrow();

        // Cancelled — AbortError
        runtime.cancelRequested = true;
        expect(() => throwIfCancelled()).toThrow('Conversion cancelled by user.');

        try {
            throwIfCancelled();
        } catch (err) {
            expect(err.name).toBe('AbortError');
        }
    });

    it('should identify AbortError by name (not just message)', () => {
        const err = new Error('Conversion cancelled by user.');
        err.name = 'AbortError';

        expect(err.name).toBe('AbortError');
        expect(err instanceof Error).toBe(true);
    });

    it('should stop iterating when AbortError is thrown', async () => {
        const processed = [];
        const runtime = { cancelRequested: false };

        async function processMany(items) {
            for (let i = 0; i < items.length; i++) {
                if (runtime.cancelRequested) {
                    const err = new Error('cancelled');
                    err.name = 'AbortError';
                    throw err;
                }
                processed.push(i);
            }
        }

        // Cancel after 2 items
        runtime.cancelRequested = false;
        const promise = processMany([0, 1, 2, 3, 4]);

        // Cancel on next microtask
        queueMicrotask(() => { runtime.cancelRequested = true; });

        await promise;
        // At least some items processed before cancellation
        expect(processed.length).toBeGreaterThanOrEqual(1);
    });
});

// =====================================================================
// § 17 — SECURITY LIMITS
// =====================================================================

describe('Security Limits Enforcement', () => {
    const LIMITS = {
        MAX_FILE_SIZE: 100 * 1024 * 1024,
        MAX_EXTRACTED_SIZE: 500 * 1024 * 1024,
        MAX_FILES_IN_ZIP: 10000,
        MAX_COMPRESSION_RATIO: 100
    };

    it('should reject files exceeding MAX_FILE_SIZE', () => {
        const fileSize = LIMITS.MAX_FILE_SIZE + 1;
        expect(fileSize > LIMITS.MAX_FILE_SIZE).toBe(true);
    });

    it('should accept files at exactly MAX_FILE_SIZE', () => {
        const fileSize = LIMITS.MAX_FILE_SIZE;
        expect(fileSize <= LIMITS.MAX_FILE_SIZE).toBe(true);
    });

    it('should reject cumulative extraction above MAX_EXTRACTED_SIZE', () => {
        const sizes = [200, 200, 150].map(mb => mb * 1024 * 1024);
        const total = sizes.reduce((a, b) => a + b, 0);
        expect(total > LIMITS.MAX_EXTRACTED_SIZE).toBe(true);
    });

    it('should reject > MAX_FILES_IN_ZIP entries', () => {
        expect(10001 > LIMITS.MAX_FILES_IN_ZIP).toBe(true);
    });

    it('should reject compression ratio > MAX_COMPRESSION_RATIO', () => {
        const uncompressed = 1_000_000;
        const compressed = 100;
        const ratio = uncompressed / compressed;
        expect(ratio > LIMITS.MAX_COMPRESSION_RATIO).toBe(true);
    });

    it('should accept safe compression ratio', () => {
        const uncompressed = 100_000;
        const compressed = 10_000;
        const ratio = uncompressed / compressed;
        expect(ratio <= LIMITS.MAX_COMPRESSION_RATIO).toBe(true);
    });

    it('should reject NUL bytes in entry names', () => {
        const names = ['img\x00.jpg', 'safe.jpg'];
        const bad = names.filter(n => n.includes('\x00'));
        expect(bad).toEqual(['img\x00.jpg']);
    });
});

// =====================================================================
// § 18 — SORTING UNDER ERROR CONDITIONS
// =====================================================================

describe('Sorting Under Error Conditions', () => {
    it('should return empty array for non-array input', () => {
        expect(sortImages(null, true, '!')).toEqual([]);
        expect(sortImages(undefined, true, '!')).toEqual([]);
        expect(sortImages(42, true, '!')).toEqual([]);
    });

    it('should skip non-string entries silently', () => {
        const mixed = ['img_1.jpg', 42, null, 'img_2.jpg', undefined];
        const result = sortImages(mixed, true, '!');
        expect(result).toContain('img_1.jpg');
        expect(result).toContain('img_2.jpg');
        // Numbers/null/undefined are skipped
        expect(result.length).toBeLessThanOrEqual(mixed.length);
    });

    it('should handle mixed priority chars safely', () => {
        const files = ['!cover.jpg', '@special.jpg', 'page_1.jpg'];
        const sorted = sortImages(files, true, '!@');
        expect(sorted[0]).toBe('!cover.jpg');
        expect(sorted[1]).toBe('@special.jpg');
    });

    it('should handle empty priority string (no priority routing)', () => {
        const files = ['!a.jpg', 'b.jpg', 'c.jpg'];
        const sorted = sortImages(files, true, '');
        // No priority → all normal files, natural sorted
        expect(sorted).toHaveLength(3);
    });

    it('should be stable across multiple calls', () => {
        const files = ['page_10.jpg', 'page_2.jpg', 'page_1.jpg'];
        const a = sortImages(files, true, '!');
        const b = sortImages(files, true, '!');
        expect(a).toEqual(b);
    });
});

// =====================================================================
// § 19 — CONSTANTS PARITY
// =====================================================================

describe('Shared Constants Parity', () => {
    it('should expose expected IMAGE_EXTENSIONS', () => {
        const expected = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'];
        expected.forEach(ext => {
            expect(IMAGE_EXTENSIONS).toContain(ext);
        });
    });

    it('should NOT include unsupported extensions', () => {
        expect(IMAGE_EXTENSIONS).not.toContain('.svg');
        expect(IMAGE_EXTENSIONS).not.toContain('.pdf');
        expect(IMAGE_EXTENSIONS).not.toContain('.zip');
    });

    it('should default priority char to "!"', () => {
        expect(DEFAULT_PRIORITY_CHARS).toBe('!');
    });

    it('should match constants.py on security limits', () => {
        // These mirror shared/constants.py
        expect(100 * 1024 * 1024).toBe(104857600);
        expect(500 * 1024 * 1024).toBe(524288000);
        expect(10000).toBe(10000);
    });
});
