/**
 * =====================================================================
 * NEXUS QUANTUM // Vitest Global Setup
 * =====================================================================
 * File:    tests/setup.js
 * Loaded:  automatically by vitest.config.js (`setupFiles`)
 * Runs:    ONCE per test file, BEFORE every test
 *
 * Provides:
 *   1. A functional localStorage mock with real storage semantics
 *   2. URL.createObjectURL / revokeObjectURL mocks (non-destructive)
 *   3. A controllable Image mock (jsdom does not load images)
 *   4. Per-test reset of all mocks + storage
 *
 * The mocks are available to every test file without additional setup.
 * =====================================================================
 */

import { vi, beforeEach, afterEach } from 'vitest';

// =====================================================================
// § 01 — STORAGE BACKING (per test file, reset per test)
// =====================================================================

/**
 * Internal store shared by the localStorage mock. Reset in beforeEach.
 * @type {Record<string, string>}
 */
let _storageBacking = {};

// =====================================================================
// § 02 — localStorage MOCK
// =====================================================================

/**
 * Functional localStorage mock.
 *
 * Unlike a bare `vi.fn()`, this implementation:
 *   - Stores values in `_storageBacking`
 *   - Returns what was stored on `getItem`
 *   - Respects `removeItem` / `clear`
 *   - Is fully spy-compatible (assert with `.toHaveBeenCalledWith`)
 *
 * Helpers (prefixed with `_` so tests can use them without colliding
 * with real localStorage API):
 *   - `_reset()`  — clears backing store (also called by beforeEach)
 *   - `_dump()`   — returns a shallow copy of the store
 *   - `_seed()`   — bulk-load key/value pairs
 */
const localStorageMock = {
    // ---- Real localStorage API ------------------------------------
    getItem: vi.fn((key) => {
        if (typeof key !== 'string') return null;
        return Object.prototype.hasOwnProperty.call(_storageBacking, key)
            ? _storageBacking[key]
            : null;
    }),

    setItem: vi.fn((key, value) => {
        if (typeof key !== 'string') return;
        _storageBacking[key] = String(value);
    }),

    removeItem: vi.fn((key) => {
        if (typeof key !== 'string') return;
        delete _storageBacking[key];
    }),

    clear: vi.fn(() => {
        _storageBacking = {};
    }),

    key: vi.fn((index) => {
        const keys = Object.keys(_storageBacking);
        return index >= 0 && index < keys.length ? keys[index] : null;
    }),

    get length() {
        return Object.keys(_storageBacking).length;
    },

    // ---- Test-only helpers ----------------------------------------
    _reset: () => {
        _storageBacking = {};
    },

    _dump: () => ({ ..._storageBacking }),

    _seed: (entries) => {
        for (const [k, v] of Object.entries(entries || {})) {
            _storageBacking[k] = String(v);
        }
    }
};

// =====================================================================
// § 03 — URL MOCK (non-destructive)
// =====================================================================

/**
 * Counter for deterministic, human-readable blob URLs.
 * Reset in beforeEach so tests get predictable values.
 */
let _blobCounter = 0;

/**
 * Generate the next mock blob URL.
 */
function _nextBlobUrl() {
    _blobCounter += 1;
    return `blob:mock-${_blobCounter}`;
}

const createObjectURLMock = vi.fn(() => _nextBlobUrl());
const revokeObjectURLMock = vi.fn(() => undefined);

// Preserve the real URL constructor (jsdom's URL) so `new URL(...)` keeps
// working. We only override the two static methods that jsdom does not
// implement (or that we want to control in tests).
const OriginalURL = globalThis.URL;

/**
 * A URL-like object that keeps the original constructor semantics but
 * replaces `createObjectURL` and `revokeObjectURL` with mocks.
 */
class MockURL extends OriginalURL {
    static createObjectURL = createObjectURLMock;
    static revokeObjectURL = revokeObjectURLMock;
}

// Expose helpers to tests via the mock itself
MockURL._createObjectURLMock = createObjectURLMock;
MockURL._revokeObjectURLMock = revokeObjectURLMock;
MockURL._resetBlobCounter = () => { _blobCounter = 0; };

vi.stubGlobal('URL', MockURL);

// =====================================================================
// § 04 — IMAGE MOCK (controllable)
// =====================================================================

/**
 * Controllable Image mock — jsdom does not decode images.
 *
 * Usage:
 *   const img = new Image();
 *   img.onload = () => {...};
 *   img.src = 'blob:valid';   // fires onload on next microtask
 *
 *   const img2 = new Image();
 *   img2._autoFail = true;    // forces onerror on src assignment
 *   img2.onerror = () => {...};
 *   img2.src = 'invalid://x';
 *
 * Static fields:
 *   - `_instances`    — array of every constructed instance (reset per test)
 *   - `_resetAll()`   — clears `_instances`
 */
class MockImage {
    constructor() {
        this.width = 800;
        this.height = 600;
        this.onload = null;
        this.onerror = null;
        this._src = '';
        this._autoFail = false;

        // Optional overrides tests can set before assigning src
        this._widthOverride = null;
        this._heightOverride = null;

        MockImage._instances.push(this);
    }

    set src(value) {
        this._src = String(value);

        // Determine dimensions at the moment of "loading"
        const width = this._widthOverride != null ? this._widthOverride : this.width;
        const height = this._heightOverride != null ? this._heightOverride : this.height;

        // Auto-fail if URL looks invalid or _autoFail was pre-set
        const shouldFail = this._autoFail
            || this._src.startsWith('invalid:')
            || this._src.startsWith('blob:corrupted');

        queueMicrotask(() => {
            if (shouldFail) {
                if (typeof this.onerror === 'function') {
                    this.onerror(new Error(`Mock image load failure: ${this._src}`));
                }
                return;
            }
            this.width = width;
            this.height = height;
            if (typeof this.onload === 'function') {
                this.onload();
            }
        });
    }

    get src() {
        return this._src;
    }

    // ---- Static helpers ------------------------------------------
    static _instances = [];
    static _resetAll() {
        MockImage._instances.length = 0;
    }
}

vi.stubGlobal('Image', MockImage);

// =====================================================================
// § 05 — PER-TEST RESET
// =====================================================================

beforeEach(() => {
    // ---- Clear call history + impls ---------------------------------
    vi.clearAllMocks();

    // ---- Re-establish default impls (clearAllMocks wipes them) ------
    localStorageMock.getItem.mockImplementation((key) => {
        if (typeof key !== 'string') return null;
        return Object.prototype.hasOwnProperty.call(_storageBacking, key)
            ? _storageBacking[key]
            : null;
    });

    localStorageMock.setItem.mockImplementation((key, value) => {
        if (typeof key !== 'string') return;
        _storageBacking[key] = String(value);
    });

    localStorageMock.removeItem.mockImplementation((key) => {
        if (typeof key !== 'string') return;
        delete _storageBacking[key];
    });

    localStorageMock.clear.mockImplementation(() => {
        _storageBacking = {};
    });

    createObjectURLMock.mockImplementation(() => _nextBlobUrl());
    revokeObjectURLMock.mockImplementation(() => undefined);

    // ---- Reset backing stores ---------------------------------------
    _storageBacking = {};
    _blobCounter = 0;
    MockImage._resetAll();
});

afterEach(() => {
    // Clear lingering state so the next test file starts clean
    _storageBacking = {};
    _blobCounter = 0;
    MockImage._resetAll();
});

// =====================================================================
// § 06 — OPTIONAL GLOBAL EXPORTS
// =====================================================================
// Expose the mocks on `globalThis` for tests that want direct access
// without re-importing (e.g. for setup-specific assertions).

globalThis.__test__ = {
    localStorageMock,
    createObjectURLMock,
    revokeObjectURLMock,
    MockImage,
    MockURL
};
