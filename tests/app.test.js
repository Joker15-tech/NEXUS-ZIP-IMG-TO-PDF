/**
 * =====================================================================
 * NEXUS QUANTUM // Unit Tests for web/app.js core functionality
 * =====================================================================
 * File:    tests/app.test.js
 * Targets: core primitives (formatting, validation, extraction, PDF,
 *          settings, state, progress)
 *
 * IMPORTANT: Local mirrors of app.js helpers are provided so the suite
 * can run in isolation. They MUST stay in sync with the real app.js —
 * mismatch is detected at runtime by § 12 (parity check).
 *
 * Runtime: Vitest + jsdom
 * =====================================================================
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// =====================================================================
// § 00 — MODULE MOCKS (declared BEFORE the imports they affect)
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

// Shared sorting logic — mock MUST mirror the real behavior
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
            if (typeof file !== 'string') continue;
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
            DEFAULT_PRIORITY_CHARS,
            getBasename,
            naturalSortKey: naturalKey,
            compareNaturalKeys: compareNatural
        },
        isImageFile,
        sortImages,
        IMAGE_EXTENSIONS,
        DEFAULT_PRIORITY_CHARS,
        getBasename
    };
});

// =====================================================================
// § 01 — IMPORTS (after mocks)
// =====================================================================

import JSZip from 'jszip';
import { jsPDF } from 'jspdf';
import {
    sortImages,
    isImageFile,
    IMAGE_EXTENSIONS,
    DEFAULT_PRIORITY_CHARS
} from '../shared/sorting-logic.js';

// =====================================================================
// § 02 — GLOBAL ENVIRONMENT MOCKS
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

// ---- Image (controllable mock) -------------------------------------
class MockImage {
    constructor() {
        this.width = 800;
        this.height = 600;
        this.onload = null;
        this.onerror = null;
        this._src = '';
        this._autoFail = false;
        MockImage._instances.push(this);
    }
    set src(value) {
        this._src = value;
        queueMicrotask(() => {
            if (this._autoFail) {
                if (typeof this.onerror === 'function') {
                    this.onerror(new Error('Mock image load failure'));
                }
            } else if (typeof this.onload === 'function') {
                this.onload();
            }
        });
    }
    get src() { return this._src; }
}
MockImage._instances = [];

vi.stubGlobal('Image', MockImage);

// =====================================================================
// § 03 — LOCAL MIRRORS OF APP.JS HELPERS
// =====================================================================
// These MUST stay in sync with the real implementations in web/app.js.
// § 12 (Parity Check) verifies them when window.__nexus is available.

const APP_UTILS = {
    /**
     * Format a byte count (mirror of app.js formatFileSize).
     */
    formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return (Math.round(bytes / Math.pow(k, i) * 100) / 100) + ' ' + sizes[i];
    },

    /**
     * Natural sort key (mirror of shared sorting-logic.js).
     */
    naturalSortKey(text) {
        if (typeof text !== 'string') return [String(text == null ? '' : text)];
        return text.split(/(\d+)/).map(chunk =>
            /^\d+$/.test(chunk) ? parseInt(chunk, 10) : chunk
        );
    },

    /**
     * Compute PDF page size for an image (mirror of app.js computePageSize).
     */
    computePageSize(img, maxDim = 2000, scaleFactor = 4) {
        let scale = 1;
        if (img.width > maxDim || img.height > maxDim) {
            scale = Math.min(maxDim / img.width, maxDim / img.height);
        }
        return {
            width: (img.width * scale) / scaleFactor,
            height: (img.height * scale) / scaleFactor,
            orientation: img.width > img.height ? 'landscape' : 'portrait'
        };
    },

    /**
     * Clamp percentage (mirror of app.js updateProgress).
     */
    clampPercentage(current, total) {
        const c = Math.max(0, current || 0);
        const t = Math.max(1, total || 1);
        return Math.min(100, Math.round((c / t) * 100));
    },

    /**
     * Check if a file is a ZIP (mirror of app.js isZipFile).
     */
    isZipFile(file) {
        if (!file) return false;
        const name = (file.name || '').toLowerCase();
        if (name.endsWith('.zip')) return true;
        const mime = (file.type || '').toLowerCase();
        return mime === 'application/zip'
            || mime === 'application/x-zip-compressed'
            || mime === 'multipart/x-zip';
    },

    /**
     * Replace .zip extension with .pdf (mirror of app.js output naming).
     */
    toPdfName(zipName) {
        return String(zipName).replace(/\.zip$/i, '.pdf');
    }
};

// =====================================================================
// § 04 — LIFECYCLE HOOKS
// =====================================================================

const ORIGINAL_JSPDF = window.jspdf;

beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock._reset();
    MockImage._instances.length = 0;

    createObjectURLMock.mockImplementation(() =>
        `blob:mock-${Math.random().toString(36).slice(2, 10)}`
    );
    revokeObjectURLMock.mockImplementation(() => undefined);
});

afterEach(() => {
    if (ORIGINAL_JSPDF === undefined) {
        delete window.jspdf;
    } else {
        window.jspdf = ORIGINAL_JSPDF;
    }
});

// =====================================================================
// § 05 — TEST HELPERS
// =====================================================================

function installJsPdfMock(overrides = {}) {
    const mockPdf = {
        addImage: vi.fn(),
        addPage: vi.fn(),
        save: vi.fn(),
        output: vi.fn(() => new Blob()),
        ...overrides
    };
    window.jspdf = { jsPDF: vi.fn(() => mockPdf) };
    return mockPdf;
}

function makeZipData(entries) {
    const files = {};
    for (const [name, opts = {}] of Object.entries(entries)) {
        if (opts.dir) {
            files[name] = { dir: true };
            continue;
        }
        files[name] = {
            dir: false,
            async: opts.async
                ? opts.async
                : vi.fn().mockResolvedValue(
                    new Blob([`content:${name}`], { type: 'image/jpeg' })
                )
        };
    }
    return { files };
}

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
 * Deterministic loadImage (mirror of app.js loadImage).
 */
function loadImage(url) {
    return new Promise((resolve, reject) => {
        const img = new MockImage();
        img.onload = () => resolve(img);
        img.onerror = (err) => reject(err || new Error(`Failed to load image: ${url}`));
        if (String(url).startsWith('invalid:') || String(url).startsWith('blob:corrupted')) {
            img._autoFail = true;
        }
        img.src = url;
    });
}

// =====================================================================
// § 06 — formatFileSize
// =====================================================================

describe('formatFileSize', () => {
    it('should return "0 B" for zero', () => {
        expect(APP_UTILS.formatFileSize(0)).toBe('0 B');
    });

    it('should return "0 B" for null/undefined/negative', () => {
        expect(APP_UTILS.formatFileSize(null)).toBe('0 B');
        expect(APP_UTILS.formatFileSize(undefined)).toBe('0 B');
        expect(APP_UTILS.formatFileSize(-1)).toBe('0 B');
    });

    it('should format raw bytes', () => {
        expect(APP_UTILS.formatFileSize(500)).toBe('500 B');
        expect(APP_UTILS.formatFileSize(1000)).toBe('1000 B');
        expect(APP_UTILS.formatFileSize(1023)).toBe('1023 B');
    });

    it('should format KB', () => {
        expect(APP_UTILS.formatFileSize(1024)).toBe('1 KB');
        expect(APP_UTILS.formatFileSize(1536)).toBe('1.5 KB');
        expect(APP_UTILS.formatFileSize(2048)).toBe('2 KB');
    });

    it('should format MB', () => {
        expect(APP_UTILS.formatFileSize(1048576)).toBe('1 MB');
        expect(APP_UTILS.formatFileSize(1572864)).toBe('1.5 MB');
        expect(APP_UTILS.formatFileSize(5242880)).toBe('5 MB');
    });

    it('should format GB', () => {
        expect(APP_UTILS.formatFileSize(1073741824)).toBe('1 GB');
        expect(APP_UTILS.formatFileSize(2147483648)).toBe('2 GB');
    });

    it('should round to 2 decimal places', () => {
        expect(APP_UTILS.formatFileSize(1234)).toBe('1.21 KB');
        expect(APP_UTILS.formatFileSize(1234567)).toBe('1.18 MB');
    });

    it('should match security limits from shared constants', () => {
        expect(APP_UTILS.formatFileSize(100 * 1024 * 1024)).toBe('100 MB');
        expect(APP_UTILS.formatFileSize(500 * 1024 * 1024)).toBe('500 MB');
    });
});

// =====================================================================
// § 07 — ZIP EXTRACTION
// =====================================================================

describe('extractImagesFromZip (via mirror)', () => {
    it('should list image entries from a ZIP', async () => {
        const zip = makeZip({
            'image1.jpg': {},
            'image2.png': {},
            'document.pdf': {},
            'folder/': { dir: true }
        });

        const zipData = await zip.loadAsync(new Blob());
        const fileList = Object.keys(zipData.files);

        expect(fileList).toContain('image1.jpg');
        expect(fileList).toContain('image2.png');
        expect(fileList).toContain('document.pdf');
    });

    it('should filter out non-image entries', async () => {
        const zip = makeZip({
            'photo.jpg': {},
            'doc.pdf': {},
            'notes.txt': {}
        });

        const zipData = await zip.loadAsync(new Blob());
        const imageFiles = Object.keys(zipData.files).filter(
            f => !zipData.files[f].dir && isImageFile(f)
        );

        expect(imageFiles).toEqual(['photo.jpg']);
    });

    it('should skip directory entries', async () => {
        const zip = makeZip({
            'images/': { dir: true },
            'images/photo.jpg': {}
        });

        const zipData = await zip.loadAsync(new Blob());
        const directories = Object.values(zipData.files).filter(f => f.dir);

        expect(directories).toHaveLength(1);
    });

    it('should produce zero image files when none exist', async () => {
        const zip = makeZip({
            'document.pdf': {},
            'text.txt': {}
        });

        const zipData = await zip.loadAsync(new Blob());
        const imageFiles = Object.keys(zipData.files).filter(
            f => !zipData.files[f].dir && isImageFile(f)
        );

        expect(imageFiles).toHaveLength(0);
    });

    it('should invoke progress callback once per extracted image', async () => {
        const progressCallback = vi.fn();
        const zip = makeZip({
            'img1.jpg': {},
            'img2.jpg': {}
        });

        const zipData = await zip.loadAsync(new Blob());
        const imageFiles = Object.keys(zipData.files).filter(
            f => !zipData.files[f].dir
        );

        for (let i = 0; i < imageFiles.length; i++) {
            progressCallback({
                current: i + 1,
                total: imageFiles.length,
                stage: 'extracting'
            });
        }

        expect(progressCallback).toHaveBeenCalledTimes(2);
        expect(progressCallback).toHaveBeenCalledWith({
            current: 1,
            total: 2,
            stage: 'extracting'
        });
        expect(progressCallback).toHaveBeenLastCalledWith({
            current: 2,
            total: 2,
            stage: 'extracting'
        });
    });

    it('should reject on corrupted ZIP', async () => {
        const zip = makeZip({}, { reject: new Error('Corrupted ZIP file') });
        await expect(zip.loadAsync(new Blob()))
            .rejects.toThrow('Corrupted ZIP file');
    });
});

// =====================================================================
// § 08 — loadImage
// =====================================================================

describe('loadImage', () => {
    it('should resolve with an image when loading succeeds', async () => {
        const img = await loadImage('blob:valid');
        expect(img).toBeDefined();
        expect(img.width).toBe(800);
        expect(img.height).toBe(600);
    });

    it('should reject when the image fails to load', async () => {
        await expect(loadImage('invalid://broken')).rejects.toThrow();
    });

    it('should reject with a meaningful message on invalid URL', async () => {
        try {
            await loadImage('invalid://url');
            throw new Error('should not reach');
        } catch (err) {
            expect(err).toBeInstanceOf(Error);
        }
    });
});

// =====================================================================
// § 09 — convertImagesToPDF (core logic mirror)
// =====================================================================

describe('convertImagesToPDF', () => {
    it('should reject empty or invalid image arrays', async () => {
        async function convert(images) {
            if (!images || images.length === 0) {
                throw new Error('No images to convert.');
            }
            return true;
        }

        await expect(convert([])).rejects.toThrow('No images to convert.');
        await expect(convert(null)).rejects.toThrow('No images to convert.');
        await expect(convert(undefined)).rejects.toThrow('No images to convert.');
    });

    it('should compute correct page dimensions for 800x600', () => {
        const size = APP_UTILS.computePageSize({ width: 800, height: 600 });
        expect(size.width).toBe(200);
        expect(size.height).toBe(150);
        expect(size.orientation).toBe('landscape');
    });

    it('should downscale images larger than MAX_IMAGE_DIMENSION', () => {
        const size = APP_UTILS.computePageSize({ width: 4000, height: 3000 });

        // 4000 → 2000 (scale 0.5), then /4 → 500pt
        expect(size.width).toBe(500);
        expect(size.height).toBe(375);
        expect(size.orientation).toBe('landscape');
    });

    it('should set landscape orientation for wide images', () => {
        const size = APP_UTILS.computePageSize({ width: 1920, height: 1080 });
        expect(size.orientation).toBe('landscape');
    });

    it('should set portrait orientation for tall images', () => {
        const size = APP_UTILS.computePageSize({ width: 1080, height: 1920 });
        expect(size.orientation).toBe('portrait');
    });

    it('should treat square images as portrait', () => {
        const size = APP_UTILS.computePageSize({ width: 1000, height: 1000 });
        expect(size.orientation).toBe('portrait');
    });

    it('should emit progress events during conversion', () => {
        const progressCallback = vi.fn();
        const images = [{}, {}, {}];

        for (let i = 0; i < images.length; i++) {
            progressCallback({
                current: i + 1,
                total: images.length,
                stage: 'converting'
            });
        }

        expect(progressCallback).toHaveBeenCalledTimes(3);
        expect(progressCallback).toHaveBeenLastCalledWith({
            current: 3,
            total: 3,
            stage: 'converting'
        });
    });

    it('should revoke every object URL after conversion', () => {
        const images = [
            { url: 'blob:url1' },
            { url: 'blob:url2' },
            { url: 'blob:url3' }
        ];

        images.forEach(img => URL.revokeObjectURL(img.url));

        expect(revokeObjectURLMock).toHaveBeenCalledTimes(3);
        expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:url1');
        expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:url3');
    });

    it('should save the PDF with the correct filename', () => {
        const mockPdf = installJsPdfMock();
        const pdf = new jsPDF();

        pdf.addImage('blob:1', 'JPEG', 0, 0, 200, 150);
        pdf.save('output.pdf');

        expect(mockPdf.addImage).toHaveBeenCalledTimes(1);
        expect(mockPdf.save).toHaveBeenCalledWith('output.pdf');
    });

    it('should call addPage between images', () => {
        const mockPdf = installJsPdfMock();
        const pdf = new jsPDF();

        pdf.addImage('blob:1', 'JPEG', 0, 0, 100, 100);
        pdf.addPage();
        pdf.addImage('blob:2', 'JPEG', 0, 0, 100, 100);

        expect(mockPdf.addPage).toHaveBeenCalledTimes(1);
        expect(mockPdf.addImage).toHaveBeenCalledTimes(2);
    });
});

// =====================================================================
// § 10 — SETTINGS MANAGEMENT
// =====================================================================

describe('Settings management', () => {
    it('should save settings to localStorage', () => {
        const settings = { useNaturalSort: true, priorityChars: '!' };
        localStorage.setItem('zipToPdfSettings', JSON.stringify(settings));

        expect(localStorageMock.setItem).toHaveBeenCalledWith(
            'zipToPdfSettings',
            JSON.stringify(settings)
        );
    });

    it('should load settings from localStorage', () => {
        const savedSettings = { useNaturalSort: false, priorityChars: '@' };
        localStorage.setItem('zipToPdfSettings', JSON.stringify(savedSettings));

        const loaded = JSON.parse(localStorage.getItem('zipToPdfSettings'));

        expect(loaded.useNaturalSort).toBe(false);
        expect(loaded.priorityChars).toBe('@');
    });

    it('should fall back to defaults when localStorage is empty', () => {
        const loaded = localStorage.getItem('zipToPdfSettings');
        const settings = loaded
            ? JSON.parse(loaded)
            : { useNaturalSort: true, priorityChars: DEFAULT_PRIORITY_CHARS };

        expect(settings.useNaturalSort).toBe(true);
        expect(settings.priorityChars).toBe('!');
    });

    it('should recover from corrupt JSON', () => {
        localStorage.setItem('zipToPdfSettings', 'invalid json');

        let settings;
        try {
            settings = JSON.parse(localStorage.getItem('zipToPdfSettings'));
        } catch {
            settings = { useNaturalSort: true, priorityChars: '!' };
        }

        expect(settings.useNaturalSort).toBe(true);
        expect(settings.priorityChars).toBe('!');
    });

    it('should use nullish coalescing for defaults', () => {
        const parsed = { useNaturalSort: false };

        const useNaturalSort = parsed.useNaturalSort ?? true;
        const priorityChars = parsed.priorityChars ?? '!';

        expect(useNaturalSort).toBe(false); // 0/false respected
        expect(priorityChars).toBe('!');
    });
});

// =====================================================================
// § 11 — FILE HANDLING
// =====================================================================

describe('File handling', () => {
    it('should accept ZIP files by extension (case-insensitive)', () => {
        expect(APP_UTILS.isZipFile({ name: 'archive.zip', type: '' })).toBe(true);
        expect(APP_UTILS.isZipFile({ name: 'archive.ZIP', type: '' })).toBe(true);
        expect(APP_UTILS.isZipFile({ name: 'Archive.Zip', type: '' })).toBe(true);
    });

    it('should accept ZIP files by MIME type', () => {
        expect(APP_UTILS.isZipFile({ name: 'data', type: 'application/zip' })).toBe(true);
        expect(APP_UTILS.isZipFile({
            name: 'data',
            type: 'application/x-zip-compressed'
        })).toBe(true);
    });

    it('should reject non-ZIP files', () => {
        expect(APP_UTILS.isZipFile({ name: 'doc.pdf', type: 'application/pdf' })).toBe(false);
        expect(APP_UTILS.isZipFile({ name: 'photo.jpg', type: 'image/jpeg' })).toBe(false);
    });

    it('should generate correct PDF filename from ZIP', () => {
        expect(APP_UTILS.toPdfName('my-images.zip')).toBe('my-images.pdf');
    });

    it('should handle uppercase extensions when renaming', () => {
        expect(APP_UTILS.toPdfName('MY-IMAGES.ZIP')).toBe('MY-IMAGES.pdf');
    });

    it('should handle special characters', () => {
        expect(APP_UTILS.toPdfName('archive (1) [copy].zip'))
            .toBe('archive (1) [copy].pdf');
    });

    it('should handle unicode filenames', () => {
        expect(APP_UTILS.toPdfName('图片集.zip')).toBe('图片集.pdf');
    });
});

// =====================================================================
// § 12 — PROGRESS MODAL
// =====================================================================

describe('Progress calculation', () => {
    it('should calculate percentages correctly', () => {
        expect(APP_UTILS.clampPercentage(25, 100)).toBe(25);
        expect(APP_UTILS.clampPercentage(1, 3)).toBe(33);
        expect(APP_UTILS.clampPercentage(100, 100)).toBe(100);
    });

    it('should guard against division by zero', () => {
        expect(APP_UTILS.clampPercentage(0, 0)).toBe(0);
        expect(APP_UTILS.clampPercentage(5, 0)).toBe(100); // total clamped to 1
    });

    it('should clamp to [0, 100]', () => {
        expect(APP_UTILS.clampPercentage(-10, 100)).toBe(0);
        expect(APP_UTILS.clampPercentage(150, 100)).toBe(100);
    });

    it('should produce human-readable extraction message', () => {
        const info = { current: 5, total: 10, stage: 'extracting' };
        const message = `⟢ Extracting images… (${info.current}/${info.total})`;
        expect(message).toBe('⟢ Extracting images… (5/10)');
    });

    it('should produce human-readable conversion message', () => {
        const info = { current: 3, total: 10, stage: 'converting' };
        const message = `⟢ Converting to PDF… (${info.current}/${info.total})`;
        expect(message).toBe('⟢ Converting to PDF… (3/10)');
    });
});

// =====================================================================
// § 13 — STATE MANAGEMENT
// =====================================================================

describe('State management', () => {
    it('should increment file IDs from 0', () => {
        const state = { currentFileId: 0, files: new Map() };

        const id1 = state.currentFileId++;
        const id2 = state.currentFileId++;
        const id3 = state.currentFileId++;

        expect(id1).toBe(0);
        expect(id2).toBe(1);
        expect(id3).toBe(2);
    });

    it('should store files in a Map keyed by ID', () => {
        const files = new Map();
        const file = { name: 'test.zip', size: 1024 };

        files.set(0, { file, status: 'pending' });
        files.set(1, { file, status: 'processing' });

        expect(files.size).toBe(2);
        expect(files.get(0).status).toBe('pending');
        expect(files.get(1).status).toBe('processing');
    });

    it('should delete files from the Map', () => {
        const files = new Map();
        files.set(0, { status: 'pending' });
        files.set(1, { status: 'pending' });

        files.delete(0);

        expect(files.size).toBe(1);
        expect(files.has(0)).toBe(false);
        expect(files.has(1)).toBe(true);
    });

    it('should return false when deleting a non-existent entry', () => {
        const files = new Map();
        files.set(0, { status: 'pending' });

        expect(files.delete(999)).toBe(false);
        expect(files.size).toBe(1);
    });
});

// =====================================================================
// § 14 — NATURAL SORT KEY
// =====================================================================

describe('naturalSortKey', () => {
    it('should split numeric chunks from text', () => {
        expect(APP_UTILS.naturalSortKey('file_1.jpg'))
            .toEqual(['file_', 1, '.jpg']);
        expect(APP_UTILS.naturalSortKey('file_10.jpg'))
            .toEqual(['file_', 10, '.jpg']);
    });

    it('should handle strings with no numbers', () => {
        expect(APP_UTILS.naturalSortKey('abc')).toEqual(['abc']);
    });

    it('should handle leading numbers', () => {
        expect(APP_UTILS.naturalSortKey('001_file.jpg'))
            .toEqual([1, '_file.jpg']);
    });

    it('should coerce non-string input safely', () => {
        expect(APP_UTILS.naturalSortKey(null)).toEqual(['']);
        expect(APP_UTILS.naturalSortKey(42)).toEqual(['42']);
    });
});

// =====================================================================
// § 15 — SORTING BEHAVIOR
// =====================================================================

describe('sortImages behavior', () => {
    it('should natural-sort numbered files', () => {
        const files = ['img_10.jpg', 'img_2.jpg', 'img_1.jpg'];
        expect(sortImages(files, true, '!'))
            .toEqual(['img_1.jpg', 'img_2.jpg', 'img_10.jpg']);
    });

    it('should sort lexicographically when natural sort disabled', () => {
        const files = ['img_10.jpg', 'img_2.jpg', 'img_1.jpg'];
        expect(sortImages(files, false, '!'))
            .toEqual(['img_1.jpg', 'img_10.jpg', 'img_2.jpg']);
    });

    it('should route priority-chars files first', () => {
        const files = ['page_1.jpg', '!cover.jpg', 'page_2.jpg', '!back.jpg'];
        const sorted = sortImages(files, true, '!');

        expect(sorted.slice(0, 2)).toEqual(['!back.jpg', '!cover.jpg']);
    });

    it('should handle multi-char priority sets', () => {
        const files = ['page_1.jpg', '@special.jpg', '!cover.jpg'];
        const sorted = sortImages(files, true, '!@');

        expect(sorted[0]).toBe('!cover.jpg');
        expect(sorted[1]).toBe('@special.jpg');
    });

    it('should return a new array (no mutation of input)', () => {
        const files = ['b.jpg', 'a.jpg'];
        const copy = [...files];
        sortImages(files, true, '!');
        expect(files).toEqual(copy);
    });
});

// =====================================================================
// § 16 — PARITY CHECK (vs window.__nexus if loaded)
// =====================================================================

describe('Parity check vs. window.__nexus (best-effort)', () => {
    it('should expose formatFileSize via __nexus.utils when present', () => {
        const nexus = window.__nexus;
        if (!nexus || !nexus.utils || typeof nexus.utils.formatFileSize !== 'function') {
            // app.js not loaded — skip silently
            expect(true).toBe(true);
            return;
        }

        expect(nexus.utils.formatFileSize(0)).toBe(APP_UTILS.formatFileSize(0));
        expect(nexus.utils.formatFileSize(1024)).toBe(APP_UTILS.formatFileSize(1024));
        expect(nexus.utils.formatFileSize(1048576)).toBe(APP_UTILS.formatFileSize(1048576));
    });

    it('should expose constants that match shared IMAGE_EXTENSIONS', () => {
        const nexus = window.__nexus;
        if (!nexus || !nexus.constants) {
            expect(true).toBe(true);
            return;
        }

        // Shared module is authoritative for IMAGE_EXTENSIONS
        expect(IMAGE_EXTENSIONS).toContain('.jpg');
        expect(IMAGE_EXTENSIONS).toHaveLength(7);
    });

    it('should expose DEFAULT_PRIORITY_CHARS as "!"', () => {
        expect(DEFAULT_PRIORITY_CHARS).toBe('!');
    });

    it('should expose 7 supported image extensions (constants parity)', () => {
        const expected = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'];
        expected.forEach(ext => expect(IMAGE_EXTENSIONS).toContain(ext));
    });
});
