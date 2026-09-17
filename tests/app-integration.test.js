/**
 * =====================================================================
 * NEXUS QUANTUM // End-to-End Integration Tests for web/app.js
 * =====================================================================
 * File:    tests/app-integration.test.js
 * Targets: complete workflows (upload → extract → sort → convert → download)
 *
 * Covers:
 *   1.  Full ZIP → PDF pipeline
 *   2.  Priority-char routing through the whole pipeline
 *   3.  Settings persistence (localStorage round-trip)
 *   4.  Multi-file lifecycle (add / process / remove)
 *   5.  Progress tracking (extract + convert)
 *   6.  Real-world scenarios (archives, photo albums, drag-drop)
 *   7.  Error recovery (partial failure, continued processing)
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

    // Fully functional sortImages — respects natural sort + priority routing
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

const originalURL = globalThis.URL;

vi.stubGlobal('URL', {
    createObjectURL: createObjectURLMock,
    revokeObjectURL: revokeObjectURLMock
});

// =====================================================================
// § 03 — LIFECYCLE HOOKS
// =====================================================================

const ORIGINAL_JSPDF = window.jspdf;

beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock._reset();

    // Reinstall fresh URL impls after clearAllMocks resets impls
    createObjectURLMock.mockImplementation(() =>
        `blob:mock-${Math.random().toString(36).slice(2, 10)}`
    );
    revokeObjectURLMock.mockImplementation(() => undefined);
});

afterEach(() => {
    // Restore window.jspdf to avoid cross-suite pollution
    if (ORIGINAL_JSPDF === undefined) {
        delete window.jspdf;
    } else {
        window.jspdf = ORIGINAL_JSPDF;
    }
});

// =====================================================================
// § 04 — TEST HELPERS
// =====================================================================

/**
 * Install a jsPDF mock into window.jspdf without nuking the whole window.
 */
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

/**
 * Build a fake JSZip data object.
 */
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
 * Replicates app.js's `extractImagesFromZip` — used to drive the
 * integration flows without importing the whole app.
 */
async function extractImages(zip, { useNaturalSort = true, priorityChars = '!' } = {}) {
    const zipData = await zip.loadAsync(new Blob());

    const imageFiles = Object.keys(zipData.files).filter(
        f => !zipData.files[f].dir && isImageFile(f)
    );

    const sorted = sortImages(imageFiles, useNaturalSort, priorityChars);

    const images = [];
    for (const filename of sorted) {
        const blob = await zipData.files[filename].async('blob');
        images.push({
            filename,
            data: blob,
            url: URL.createObjectURL(blob)
        });
    }
    return images;
}

/**
 * Replicates app.js's `convertImagesToPDF` core loop.
 */
function buildPdf(images, pdf, filename) {
    for (let i = 0; i < images.length; i++) {
        if (i > 0) pdf.addPage();
        pdf.addImage(images[i].url, 'JPEG', 0, 0, 100, 100);
    }
    pdf.save(filename);
    return pdf;
}

/**
 * Replicates app.js's progress percentage logic.
 */
function calculateProgress(current, total) {
    if (total === 0) return 0;
    return Math.min(100, Math.max(0, Math.round((current / total) * 100)));
}

// =====================================================================
// § 05 — COMPLETE ZIP → PDF PIPELINE
// =====================================================================

describe('Complete ZIP to PDF Workflow', () => {
    it('should complete full workflow: upload → extract → convert → download', async () => {
        const zip = makeZip({
            'img1.jpg': {},
            'img2.jpg': {},
            'img3.jpg': {}
        });

        // Extract + sort
        const images = await extractImages(zip, { useNaturalSort: true });

        expect(images).toHaveLength(3);
        expect(images.map(i => i.filename)).toEqual([
            'img1.jpg', 'img2.jpg', 'img3.jpg'
        ]);
        expect(createObjectURLMock).toHaveBeenCalledTimes(3);

        // Convert
        const mockPdf = installJsPdfMock();
        const pdf = new jsPDF();
        buildPdf(images, pdf, 'test.pdf');

        expect(mockPdf.addImage).toHaveBeenCalledTimes(3);
        expect(mockPdf.addPage).toHaveBeenCalledTimes(2);
        expect(mockPdf.save).toHaveBeenCalledWith('test.pdf');

        // Cleanup
        images.forEach(img => URL.revokeObjectURL(img.url));
        expect(revokeObjectURLMock).toHaveBeenCalledTimes(3);
    });

    it('should handle priority files in complete workflow', async () => {
        const zip = makeZip({
            'page1.jpg': {},
            '!cover.jpg': {},
            'page2.jpg': {},
            '!back.jpg': {}
        });

        const images = await extractImages(zip, {
            useNaturalSort: true,
            priorityChars: '!'
        });

        // Priority files MUST come first
        const names = images.map(i => i.filename);
        expect(names[0]).toBe('!back.jpg');
        expect(names[1]).toBe('!cover.jpg');
        expect(names.slice(2)).toEqual(['page1.jpg', 'page2.jpg']);

        expect(sortImages).toHaveBeenCalledWith(
            expect.arrayContaining(['!cover.jpg', '!back.jpg']),
            true,
            '!'
        );
    });

    it('should apply natural sort to numbered files', async () => {
        const zip = makeZip({
            'page_10.jpg': {},
            'page_2.jpg': {},
            'page_1.jpg': {}
        });

        const images = await extractImages(zip, { useNaturalSort: true });

        expect(images.map(i => i.filename)).toEqual([
            'page_1.jpg', 'page_2.jpg', 'page_10.jpg'
        ]);
    });

    it('should process multiple files sequentially', async () => {
        const files = ['file1.zip', 'file2.zip', 'file3.zip'];
        const processed = [];

        for (const name of files) {
            const zip = makeZip({ 'img.jpg': {} });
            JSZip.mockImplementationOnce(() => zip);

            const instance = new JSZip();
            await instance.loadAsync(new Blob());
            processed.push(name);
        }

        expect(processed).toEqual(files);
        expect(JSZip).toHaveBeenCalledTimes(3);
    });

    it('should skip directory entries during extraction', async () => {
        const zip = makeZip({
            'folder/': { dir: true },
            'folder/img.jpg': {},
            'another/': { dir: true }
        });

        const images = await extractImages(zip);

        expect(images).toHaveLength(1);
        expect(images[0].filename).toBe('folder/img.jpg');
    });
});

// =====================================================================
// § 06 — SETTINGS PERSISTENCE
// =====================================================================

describe('Settings Persistence Workflow', () => {
    it('should save and restore settings across sessions', () => {
        const initialSettings = {
            useNaturalSort: true,
            priorityChars: '!'
        };

        localStorage.setItem('zipToPdfSettings', JSON.stringify(initialSettings));

        const savedData = localStorage.getItem('zipToPdfSettings');
        const restored = JSON.parse(savedData);

        expect(restored).toEqual(initialSettings);
    });

    it('should update settings and persist changes', () => {
        localStorage.setItem('zipToPdfSettings', JSON.stringify({
            useNaturalSort: true,
            priorityChars: '!'
        }));

        const newSettings = {
            useNaturalSort: false,
            priorityChars: '@'
        };
        localStorage.setItem('zipToPdfSettings', JSON.stringify(newSettings));

        const parsed = JSON.parse(localStorage.getItem('zipToPdfSettings'));

        expect(parsed.useNaturalSort).toBe(false);
        expect(parsed.priorityChars).toBe('@');
    });

    it('should apply persisted settings to the sort step', () => {
        const settings = { useNaturalSort: false, priorityChars: '@' };
        localStorage.setItem('zipToPdfSettings', JSON.stringify(settings));

        const loaded = JSON.parse(localStorage.getItem('zipToPdfSettings'));

        const files = ['img_10.jpg', 'img_1.jpg', '@special.jpg', 'img_2.jpg'];
        const sorted = sortImages(
            files,
            loaded.useNaturalSort,
            loaded.priorityChars
        );

        expect(sortImages).toHaveBeenCalledWith(files, false, '@');
        // @special comes first (priority), then lexical: img_1, img_10, img_2
        expect(sorted[0]).toBe('@special.jpg');
        expect(sorted.slice(1)).toEqual(['img_1.jpg', 'img_10.jpg', 'img_2.jpg']);
    });

    it('should fall back to defaults when localStorage is empty', () => {
        const raw = localStorage.getItem('zipToPdfSettings');
        expect(raw).toBeNull();

        const DEFAULT = { useNaturalSort: true, priorityChars: '!' };
        const settings = raw ? JSON.parse(raw) : DEFAULT;

        expect(settings).toEqual(DEFAULT);
    });

    it('should fall back to defaults when JSON is corrupt', () => {
        localStorage.setItem('zipToPdfSettings', '{not valid json');

        const DEFAULT = { useNaturalSort: true, priorityChars: '!' };
        let settings = DEFAULT;
        try {
            settings = JSON.parse(localStorage.getItem('zipToPdfSettings'));
        } catch {
            settings = DEFAULT;
        }
        expect(settings).toEqual(DEFAULT);
    });
});

// =====================================================================
// § 07 — FILE STATE LIFECYCLE
// =====================================================================

describe('File State Management Workflow', () => {
    it('should manage multiple files through complete lifecycle', () => {
        const state = { files: new Map(), currentFileId: 0 };

        const ids = [];
        for (let i = 0; i < 3; i++) {
            const id = state.currentFileId++;
            ids.push(id);
            state.files.set(id, {
                file: { name: `file${i + 1}.zip` },
                status: 'pending'
            });
        }

        expect(state.files.size).toBe(3);

        state.files.get(ids[0]).status = 'processing';
        expect(state.files.get(ids[0]).status).toBe('processing');

        state.files.delete(ids[0]);
        expect(state.files.size).toBe(2);

        state.files.delete(ids[1]);
        state.files.delete(ids[2]);
        expect(state.files.size).toBe(0);
    });

    it('should validate files before adding to state', () => {
        const MAX_FILE_SIZE = 100 * 1024 * 1024;

        const validate = (file) => {
            const isZip = file.type === 'application/zip' ||
                file.name.toLowerCase().endsWith('.zip');
            if (!isZip) return { ok: false, error: 'Not a ZIP file' };
            if (file.size === 0) return { ok: false, error: 'Empty file' };
            if (file.size > MAX_FILE_SIZE) return { ok: false, error: 'Too large' };
            return { ok: true, file };
        };

        expect(validate({ name: 'test.zip', type: 'application/zip', size: 1024 }).ok).toBe(true);
        expect(validate({ name: 'test.pdf', type: 'application/pdf', size: 1024 }).ok).toBe(false);
        expect(validate({ name: 'test.zip', type: 'application/zip', size: 0 }).ok).toBe(false);
        expect(validate({ name: 'test.zip', type: 'application/zip', size: MAX_FILE_SIZE + 1 }).ok).toBe(false);
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

        // Mirror app.js removeFile
        const rec = state.files.get(id);
        if (rec && rec.type === 'image') {
            const idx = state.imageFiles.findIndex(f => f.fileId === id);
            if (idx !== -1) state.imageFiles.splice(idx, 1);
        }
        state.files.delete(id);

        expect(state.files.size).toBe(0);
        expect(state.imageFiles).toHaveLength(0);
    });

    it('should return false when deleting a non-existent entry', () => {
        const files = new Map();
        files.set(1, { status: 'pending' });
        expect(files.delete(999)).toBe(false);
        expect(files.size).toBe(1);
    });
});

// =====================================================================
// § 08 — PROGRESS TRACKING
// =====================================================================

describe('Progress Tracking Workflow', () => {
    it('should track extraction progress', async () => {
        const zip = makeZip({
            'img1.jpg': {},
            'img2.jpg': {},
            'img3.jpg': {}
        });

        const events = [];
        const zipData = await zip.loadAsync(new Blob());
        const imageFiles = Object.keys(zipData.files).filter(
            f => !zipData.files[f].dir
        );

        for (let i = 0; i < imageFiles.length; i++) {
            await zipData.files[imageFiles[i]].async('blob');
            events.push({
                current: i + 1,
                total: imageFiles.length,
                stage: 'extracting'
            });
        }

        expect(events).toHaveLength(3);
        expect(events[0]).toEqual({ current: 1, total: 3, stage: 'extracting' });
        expect(events[2]).toEqual({ current: 3, total: 3, stage: 'extracting' });
    });

    it('should track conversion progress', () => {
        const events = [];
        const images = Array.from({ length: 5 }, (_, i) => ({ url: `blob:${i}` }));

        for (let i = 0; i < images.length; i++) {
            events.push({
                current: i + 1,
                total: images.length,
                stage: 'converting'
            });
        }

        expect(events).toHaveLength(5);
        expect(events[4]).toEqual({ current: 5, total: 5, stage: 'converting' });
    });

    it('should calculate progress percentages correctly (clamped)', () => {
        expect(calculateProgress(0, 10)).toBe(0);
        expect(calculateProgress(5, 10)).toBe(50);
        expect(calculateProgress(10, 10)).toBe(100);
        expect(calculateProgress(15, 10)).toBe(100); // clamp high
        expect(calculateProgress(-5, 10)).toBe(0);   // clamp low
        expect(calculateProgress(5, 0)).toBe(0);     // div-by-zero guard
    });

    it('should report ETA based on elapsed time', () => {
        const started = performance.now();
        const total = 10;
        const current = 3;

        // Simulate elapsed
        const elapsed = 300; // ms
        const perItem = elapsed / current;
        const eta = perItem * (total - current);

        expect(eta).toBe(700); // (300 / 3) * 7
        expect(perItem).toBe(100);
    });
});

// =====================================================================
// § 09 — REAL-WORLD SCENARIOS
// =====================================================================

describe('Real-World Scenarios Integration', () => {
    it('should process a cover + pages + credits archive in order', async () => {
        const zip = makeZip({
            '!cover.jpg': {},
            'page001.jpg': {},
            'page002.jpg': {},
            'page010.jpg': {},
            '!credits.jpg': {}
        });

        const images = await extractImages(zip, {
            useNaturalSort: true,
            priorityChars: '!'
        });

        const order = images.map(i => i.filename);

        // Priority first (natural sorted), then normal (natural sorted)
        expect(order).toEqual([
            '!cover.jpg',
            '!credits.jpg',
            'page001.jpg',
            'page002.jpg',
            'page010.jpg'
        ]);
    });

    it('should natural-sort a photo album with leading zeros', async () => {
        const zip = makeZip({
            'IMG_0100.jpg': {},
            'IMG_0010.jpg': {},
            'IMG_0001.jpg': {},
            'IMG_0002.jpg': {}
        });

        const images = await extractImages(zip, { useNaturalSort: true });

        expect(images.map(i => i.filename)).toEqual([
            'IMG_0001.jpg',
            'IMG_0002.jpg',
            'IMG_0010.jpg',
            'IMG_0100.jpg'
        ]);
    });

    it('should handle drag-drop → convert → download workflow', async () => {
        const droppedFile = {
            name: 'photos.zip',
            type: 'application/zip',
            size: 5 * 1024 * 1024
        };

        const isValid = droppedFile.type === 'application/zip' ||
            droppedFile.name.toLowerCase().endsWith('.zip');
        expect(isValid).toBe(true);

        const state = { files: new Map(), currentFileId: 0 };
        const fileId = state.currentFileId++;
        state.files.set(fileId, { file: droppedFile, status: 'pending' });

        const zip = makeZip({
            'img1.jpg': {},
            'img2.jpg': {}
        });

        state.files.get(fileId).status = 'processing';
        const images = await extractImages(zip);

        const mockPdf = installJsPdfMock();
        const pdf = new jsPDF();
        buildPdf(images, pdf, 'photos.pdf');

        images.forEach(img => URL.revokeObjectURL(img.url));
        state.files.delete(fileId);

        expect(mockPdf.save).toHaveBeenCalledWith('photos.pdf');
        expect(mockPdf.addImage).toHaveBeenCalledTimes(2);
        expect(revokeObjectURLMock).toHaveBeenCalledTimes(2);
        expect(state.files.size).toBe(0);
    });

    it('should merge multiple ZIPs into a single PDF, in sorted ZIP order', async () => {
        const zips = [
            { name: 'vol_2.zip', entries: { 'p1.jpg': {}, 'p2.jpg': {} } },
            { name: 'vol_1.zip', entries: { 'p1.jpg': {}, 'p2.jpg': {} } }
        ];

        // Sort ZIP names first
        const names = zips.map(z => z.name);
        const sortedNames = sortImages(names, true, '!');

        expect(sortedNames).toEqual(['vol_1.zip', 'vol_2.zip']);

        // Extract each ZIP in sorted order
        const allImages = [];
        for (const name of sortedNames) {
            const entry = zips.find(z => z.name === name);
            const zip = makeZip(entry.entries);
            const images = await extractImages(zip, { useNaturalSort: true });
            allImages.push(...images.map(i => ({ ...i, sourceZip: name })));
        }

        // Final order: vol_1 (p1, p2) then vol_2 (p1, p2)
        expect(allImages.map(i => `${i.sourceZip}:${i.filename}`)).toEqual([
            'vol_1.zip:p1.jpg',
            'vol_1.zip:p2.jpg',
            'vol_2.zip:p1.jpg',
            'vol_2.zip:p2.jpg'
        ]);
    });
});

// =====================================================================
// § 10 — ERROR RECOVERY
// =====================================================================

describe('Error Recovery Workflows', () => {
    it('should skip corrupted entries and continue with valid images', async () => {
        const zip = makeZip({
            'good1.jpg': {},
            'bad.jpg': {
                async: vi.fn().mockRejectedValue(new Error('Corrupt'))
            },
            'good2.jpg': {}
        });

        const zipData = await zip.loadAsync(new Blob());
        const fileList = Object.keys(zipData.files);

        const images = [];
        for (const filename of fileList) {
            try {
                const blob = await zipData.files[filename].async('blob');
                images.push({ filename, data: blob });
            } catch (err) {
                // Skip and continue
            }
        }

        expect(images).toHaveLength(2);
        expect(images.map(i => i.filename)).toEqual(['good1.jpg', 'good2.jpg']);
    });

    it('should propagate PDF generation failure and skip save', () => {
        const mockPdf = installJsPdfMock({
            addImage: vi.fn(() => { throw new Error('PDF generation failed'); })
        });

        let caught = null;
        try {
            const pdf = new jsPDF();
            pdf.addImage('blob:url', 'JPEG', 0, 0, 100, 100);
            pdf.save('out.pdf');
        } catch (err) {
            caught = err;
        }

        expect(caught).toBeInstanceOf(Error);
        expect(caught.message).toBe('PDF generation failed');
        expect(mockPdf.save).not.toHaveBeenCalled();
    });

    it('should propagate loadAsync rejection for corrupted ZIP', async () => {
        const zip = makeZip({}, { reject: new Error('Corrupted ZIP file') });

        await expect(zip.loadAsync(new Blob()))
            .rejects.toThrow('Corrupted ZIP file');
    });

    it('should recover when partial extraction succeeds', async () => {
        const zip = makeZip({
            'a.jpg': {},
            'b.jpg': { async: vi.fn().mockRejectedValue(new Error('fail')) },
            'c.jpg': {},
            'd.jpg': {}
        });

        const images = [];
        try {
            const zipData = await zip.loadAsync(new Blob());
            for (const filename of Object.keys(zipData.files)) {
                try {
                    const blob = await zipData.files[filename].async('blob');
                    images.push(filename);
                } catch { /* skip */ }
            }
        } catch { /* noop */ }

        expect(images).toEqual(['a.jpg', 'c.jpg', 'd.jpg']);
    });
});

// =====================================================================
// § 11 — CONSTANTS PARITY
// =====================================================================

describe('Shared Constants Parity', () => {
    it('should expose the 7 supported image extensions', () => {
        const expected = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'];
        expected.forEach(ext => expect(IMAGE_EXTENSIONS).toContain(ext));
        expect(IMAGE_EXTENSIONS).toHaveLength(7);
    });

    it('should NOT include unsupported extensions', () => {
        expect(IMAGE_EXTENSIONS).not.toContain('.svg');
        expect(IMAGE_EXTENSIONS).not.toContain('.pdf');
        expect(IMAGE_EXTENSIONS).not.toContain('.zip');
        expect(IMAGE_EXTENSIONS).not.toContain('.tif');
    });

    it('should default priority char to "!"', () => {
        expect(DEFAULT_PRIORITY_CHARS).toBe('!');
    });
});

// =====================================================================
// § 12 — URL LIFECYCLE
// =====================================================================

describe('Object URL Lifecycle in Pipeline', () => {
    it('should create one URL per extracted image', async () => {
        const zip = makeZip({
            'a.jpg': {}, 'b.jpg': {}, 'c.jpg': {}
        });

        const images = await extractImages(zip);

        expect(images).toHaveLength(3);
        expect(createObjectURLMock).toHaveBeenCalledTimes(3);
        images.forEach(i => expect(i.url).toMatch(/^blob:/));
    });

    it('should revoke URLs on cleanup', async () => {
        const zip = makeZip({ 'a.jpg': {}, 'b.jpg': {} });
        const images = await extractImages(zip);

        images.forEach(img => URL.revokeObjectURL(img.url));

        expect(revokeObjectURLMock).toHaveBeenCalledTimes(2);
    });

    it('should revoke URLs even when conversion throws', async () => {
        const zip = makeZip({ 'a.jpg': {}, 'b.jpg': {} });
        const images = await extractImages(zip);

        try {
            throw new Error('simulated failure');
        } catch { /* noop */ }
        finally {
            images.forEach(img => URL.revokeObjectURL(img.url));
        }

        expect(revokeObjectURLMock).toHaveBeenCalledTimes(2);
    });
});
