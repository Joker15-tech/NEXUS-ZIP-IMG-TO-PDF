/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  NEXUS QUANTUM // Zipped Images → PDF Converter                  ║
 * ║  ──────────────────────────────────────────────────────────────── ║
 * ║  Application:  web/app.js                                        ║
 * ║  Version  :    2.0.0-nexus                                       ║
 * ║  Author   :    @NEXUS_QUANTUM                                    ║
 * ║  Contact  :    drxenon487@gmail.com                              ║
 * ║  License  :    MIT                                               ║
 * ║  ──────────────────────────────────────────────────────────────── ║
 * ║  Dependencies (must be loaded BEFORE this file):                 ║
 * ║    1. JSZip                 (CDN)                                ║
 * ║    2. jsPDF UMD             (CDN)                                ║
 * ║    3. shared/constants.js   (window.NexusConstants)              ║
 * ║    4. shared/sorting-logic.js (window.NexusSorting)              ║
 * ║  ──────────────────────────────────────────────────────────────── ║
 * ║  100% client-side · zero uploads · zero telemetry                ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

'use strict';

// =====================================================================
// § 00 — BOOTSTRAP / CONSTANTS
// =====================================================================

const APP_VERSION  = '2.0.0-nexus';
const APP_CODENAME = 'QUANTUM';

// -- Shared constants (from NexusConstants or fallback) ---------------
const _C = (typeof window.NexusConstants !== 'undefined' && window.NexusConstants)
    ? window.NexusConstants
    : null;

const _FALLBACK_CONSTANTS = {
    IMAGE_EXTENSIONS:          ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'],
    DEFAULT_PRIORITY_CHARS:    '!',
    MAX_FILE_SIZE_BYTES:       100 * 1024 * 1024, // 100 MB
    MAX_EXTRACTED_SIZE_BYTES:  500 * 1024 * 1024, // 500 MB
    MAX_FILES_IN_ZIP:          10000,
    MAX_COMPRESSION_RATIO:     100,
    MAX_IMAGE_DIMENSION:       2000,
    IMAGE_SCALE_FACTOR:        4
};

const C = _C || _FALLBACK_CONSTANTS;

const MAX_FILE_SIZE         = C.MAX_FILE_SIZE_BYTES;
const MAX_EXTRACTED_SIZE    = C.MAX_EXTRACTED_SIZE_BYTES;
const MAX_FILES_IN_ZIP      = C.MAX_FILES_IN_ZIP;
const MAX_COMPRESSION_RATIO = C.MAX_COMPRESSION_RATIO || 100;
const MAX_IMAGE_DIMENSION   = C.MAX_IMAGE_DIMENSION;
const IMAGE_SCALE_FACTOR    = C.IMAGE_SCALE_FACTOR;
const DEFAULT_PRIORITY_CHARS = C.DEFAULT_PRIORITY_CHARS || '!';

// -- Storage keys -----------------------------------------------------
const SETTINGS_STORAGE_KEY = 'zipToPdfSettings';
const HISTORY_STORAGE_KEY  = 'zipToPdfHistory';
const THEME_STORAGE_KEY    = 'zipToPdfTheme';

// -- Web-specific constants -------------------------------------------
const WEB_SUPPORTED_FORMATS = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];
const MAX_HISTORY_ENTRIES   = 20;
const CONVERSION_THROTTLE_MS = 500;

// -- MIME whitelist for consistency validation ------------------------
const MIME_WHITELIST = {
    '.jpg':  ['image/jpeg'],
    '.jpeg': ['image/jpeg'],
    '.png':  ['image/png'],
    '.gif':  ['image/gif'],
    '.webp': ['image/webp'],
    '.zip':  ['application/zip', 'application/x-zip-compressed', 'multipart/x-zip', '']
};

// =====================================================================
// § 01 — SHARED LOGIC ALIASES (with graceful fallback)
// =====================================================================

const _S = (typeof window.NexusSorting !== 'undefined' && window.NexusSorting)
    ? window.NexusSorting
    : null;

const sharedIsImageFile = (_S && typeof _S.isImageFile === 'function')
    ? _S.isImageFile
    : function fallbackIsImageFile(name) {
        if (!name) return false;
        const ext = String(name).toLowerCase().match(/\.[a-z0-9]+$/);
        return !!ext && C.IMAGE_EXTENSIONS.includes(ext[0]);
    };

const sharedSortImages = (_S && typeof _S.sortImages === 'function')
    ? _S.sortImages
    : function fallbackSortImages(files) {
        return Array.isArray(files) ? files.slice().sort() : [];
    };

const sharedGetBasename = (_S && typeof _S.getBasename === 'function')
    ? _S.getBasename
    : function fallbackGetBasename(p) {
        return String(p || '').split(/[\\/]/).pop() || '';
    };

// =====================================================================
// § 02 — STATE
// =====================================================================

/**
 * Global application state. Kept in a single object for easy
 * introspection via `window.__nexus.state` in tests / DevTools.
 */
const state = {
    files: new Map(),        // Map<fileId, FileRecord>
    imageFiles: [],          // Array<{fileId, file}>
    currentFileId: 0,
    dragSrcId: null,         // For reorder-by-drag

    settings: {
        useNaturalSort: true,
        priorityChars: DEFAULT_PRIORITY_CHARS,
        theme: 'nexus',
        showPreviews: true,
        autoRetry: true
    },

    runtime: {
        isConverting: false,
        cancelRequested: false,
        lastConversionAt: 0,
        stats: {
            totalConverted: 0,
            totalPages: 0,
            totalBytesProcessed: 0
        }
    },

    history: [] // Array<{ts, filename, pages, duration, bytes}>
};

// -- URL registry (for cleanup) ---------------------------------------
const urlRegistry = new Set();

// -- Abort controller for in-flight conversions -----------------------
let currentAbort = null;

// =====================================================================
// § 03 — UTILITIES
// =====================================================================

/**
 * Escape a string for safe HTML interpolation (XSS prevention).
 */
function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Format a byte count into a human-readable string.
 */
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (Math.round(bytes / Math.pow(k, i) * 100) / 100) + ' ' + sizes[i];
}

/**
 * Format a duration (ms) into a compact human-readable string.
 */
function formatDuration(ms) {
    if (!ms || ms < 1000) return `${Math.round(ms || 0)}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    const min = Math.floor(ms / 60000);
    const sec = Math.round((ms % 60000) / 1000);
    return `${min}m ${sec}s`;
}

/**
 * Get lowercase extension including the dot, or '' if none.
 */
function getExtension(filename) {
    const base = String(filename).split(/[\\/]/).pop() || '';
    const idx = base.lastIndexOf('.');
    return idx > 0 ? base.substring(idx).toLowerCase() : '';
}

/**
 * Get basename from a path with any separator (delegates to shared).
 */
function getBasename(filepath) {
    return sharedGetBasename(filepath);
}

/**
 * Check if a filename is a Web-app-supported image format.
 */
function isSupportedWebFormat(filename) {
    return WEB_SUPPORTED_FORMATS.includes(getExtension(filename));
}

/**
 * Map filename extension to a jsPDF image format string.
 */
function getImageFormat(filename) {
    const map = {
        '.jpg':  'JPEG',
        '.jpeg': 'JPEG',
        '.png':  'PNG',
        '.gif':  'GIF',
        '.webp': 'WEBP'
    };
    return map[getExtension(filename)] || 'JPEG';
}

/**
 * Check whether a file is a ZIP based on extension or MIME.
 */
function isZipFile(file) {
    if (!file) return false;
    const name = (file.name || '').toLowerCase();
    if (name.endsWith('.zip')) return true;
    const mime = (file.type || '').toLowerCase();
    return mime === 'application/zip'
        || mime === 'application/x-zip-compressed'
        || mime === 'multipart/x-zip';
}

/**
 * Cross-validate extension vs MIME for a given file.
 */
function isMimeConsistent(file) {
    const ext = getExtension(file.name);
    const mime = (file.type || '').toLowerCase();
    const allowed = MIME_WHITELIST[ext];
    if (!allowed) return true;
    if (!mime) return true;
    return allowed.includes(mime);
}

/**
 * Compute a SHA-256 hash of a File for deduplication.
 */
async function hashFile(file) {
    try {
        if (window.crypto && window.crypto.subtle && file.arrayBuffer) {
            const buf = await file.arrayBuffer();
            const digest = await crypto.subtle.digest('SHA-256', buf);
            return Array.from(new Uint8Array(digest))
                .map(b => b.toString(16).padStart(2, '0'))
                .join('');
        }
    } catch (_) { /* fall through */ }
    return `fp:${file.name}:${file.size}:${file.lastModified}`;
}

/**
 * Debounce helper.
 */
function debounce(fn, wait) {
    let t = null;
    return function debounced(...args) {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(this, args), wait);
    };
}

/**
 * Unique ID generator.
 */
function uid(prefix = 'id') {
    return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Register an object URL for later cleanup.
 */
function registerUrl(url) {
    if (url) urlRegistry.add(url);
    return url;
}

/**
 * Revoke a single tracked URL.
 */
function revokeUrl(url) {
    if (!url) return;
    try { URL.revokeObjectURL(url); } catch (_) { /* noop */ }
    urlRegistry.delete(url);
}

/**
 * Revoke all tracked object URLs.
 */
function revokeAllUrls() {
    for (const url of urlRegistry) {
        try { URL.revokeObjectURL(url); } catch (_) { /* noop */ }
    }
    urlRegistry.clear();
}

// =====================================================================
// § 04 — TOAST SYSTEM
// =====================================================================

/**
 * Ensure the toast container exists in the DOM.
 */
function ensureToastContainer() {
    let c = document.getElementById('nexus-toasts');
    if (!c) {
        c = document.createElement('div');
        c.id = 'nexus-toasts';
        c.className = 'toast-stack';
        c.setAttribute('aria-live', 'polite');
        document.body.appendChild(c);
    }
    return c;
}

/**
 * Push a toast notification.
 */
function pushToast(type, title, message = '', timeout = 4500) {
    const container = ensureToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'status');
    toast.innerHTML = `
        <div class="toast-bar" aria-hidden="true"></div>
        <div class="toast-body">
            <div class="toast-title">${escapeHtml(title)}</div>
            ${message ? `<div class="toast-msg">${escapeHtml(message)}</div>` : ''}
        </div>
        <button type="button" class="toast-close" aria-label="Dismiss">✕</button>
    `;

    const dismiss = () => {
        toast.classList.add('toast-out');
        setTimeout(() => toast.remove(), 300);
    };

    const closeBtn = toast.querySelector('.toast-close');
    if (closeBtn) closeBtn.addEventListener('click', dismiss);

    container.appendChild(toast);
    if (timeout > 0) setTimeout(dismiss, timeout);
    return toast;
}

// =====================================================================
// § 05 — NOTIFICATION MODAL
// =====================================================================

function showNotification(type, title, message) {
    const modal          = document.getElementById('notificationModal');
    const iconContainer  = document.getElementById('notificationIcon');
    const titleElement   = document.getElementById('notificationTitle');
    const messageElement = document.getElementById('notificationMessage');

    if (!modal || !iconContainer || !titleElement || !messageElement) return;

    const icons = {
        success: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>`,
        error:   `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>`,
        warning: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>`,
        info:    `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`
    };

    iconContainer.innerHTML = icons[type] || icons.info;
    iconContainer.className = 'notification-icon ' + (type || 'info');

    titleElement.textContent   = title;
    messageElement.textContent = message;

    modal.classList.add('active');
}

function hideNotification() {
    const modal = document.getElementById('notificationModal');
    if (modal) modal.classList.remove('active');
}

// =====================================================================
// § 06 — PROGRESS MODAL
// =====================================================================

function showProgressModal(show = true) {
    const modal = document.getElementById('progressModal');
    if (!modal) return;
    modal.classList.toggle('active', !!show);
}

/**
 * Update progress modal.
 */
function updateProgress(info) {
    const progressInfo = document.getElementById('progressInfo');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');

    if (!progressInfo || !progressFill || !progressText) return;

    const current = Math.max(0, info.current || 0);
    const total   = Math.max(1, info.total   || 1);
    const percentage = Math.min(100, Math.round((current / total) * 100));

    let message = info.detail || 'Processing…';
    if (info.stage === 'extracting') {
        message = `⟢ Extracting images… (${current}/${total})`;
    } else if (info.stage === 'converting') {
        message = `⟢ Converting to PDF… (${current}/${total})`;
    } else if (info.stage === 'hashing') {
        message = `⟢ Hashing file… (${current}/${total})`;
    } else if (info.stage === 'inspecting') {
        message = `⟢ Inspecting archive…`;
    }

    if (info.eta && info.eta > 0) {
        message += ` · ETA ${formatDuration(info.eta)}`;
    }

    progressInfo.textContent = message;
    progressFill.style.width = percentage + '%';
    progressText.textContent = percentage + '%';
}

/**
 * Request cancellation of the current conversion.
 */
function requestCancel() {
    if (!state.runtime.isConverting) return;
    state.runtime.cancelRequested = true;
    if (currentAbort) currentAbort.abort();
    pushToast('warning', 'Cancellation requested', 'The current operation will stop shortly.');
}

/**
 * Throw if cancellation was requested.
 */
function throwIfCancelled() {
    if (state.runtime.cancelRequested) {
        const err = new Error('Conversion cancelled by user.');
        err.name = 'AbortError';
        throw err;
    }
}

// =====================================================================
// § 07 — IMAGE HELPERS
// =====================================================================

/**
 * Load an <img> from a URL, resolving with the loaded HTMLImageElement.
 */
function loadImage(imageUrl) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload  = () => resolve(img);
        img.onerror = () => reject(new Error(`Failed to load image: ${imageUrl}`));
        img.src = imageUrl;
    });
}

/**
 * Generate a small thumbnail data URL from a File/Blob.
 */
async function makeThumbnail(file, maxSide = 96) {
    try {
        const url = registerUrl(URL.createObjectURL(file));
        const img = await loadImage(url);
        const scale = Math.min(maxSide / img.width, maxSide / img.height, 1);
        const w = Math.max(1, Math.round(img.width  * scale));
        const h = Math.max(1, Math.round(img.height * scale));

        const canvas = document.createElement('canvas');
        canvas.width  = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, w, h);

        const dataUrl = canvas.toDataURL('image/jpeg', 0.72);
        revokeUrl(url);
        return { dataUrl, width: img.width, height: img.height };
    } catch (err) {
        console.warn('Thumbnail generation failed:', err);
        return null;
    }
}

/**
 * Compute PDF page size in points for an image.
 */
function computePageSize(img) {
    let scale = 1;
    if (img.width > MAX_IMAGE_DIMENSION || img.height > MAX_IMAGE_DIMENSION) {
        scale = Math.min(
            MAX_IMAGE_DIMENSION / img.width,
            MAX_IMAGE_DIMENSION / img.height
        );
    }
    return {
        width:  (img.width  * scale) / IMAGE_SCALE_FACTOR,
        height: (img.height * scale) / IMAGE_SCALE_FACTOR,
        orientation: img.width > img.height ? 'landscape' : 'portrait'
    };
}

// =====================================================================
// § 08 — ZIP INSPECTION & EXTRACTION
// =====================================================================

/**
 * Inspect a ZIP file — returns metadata without extracting image data.
 */
async function inspectZip(zipFile) {
    const zip = new JSZip();
    const zipData = await zip.loadAsync(zipFile);

    const names = [];
    let images = 0;
    let dirs = 0;
    let totalSize = 0;

    Object.keys(zipData.files).forEach(filename => {
        const entry = zipData.files[filename];
        if (entry.dir) { dirs++; return; }
        if (filename.includes('..') || filename.startsWith('/')) return;
        if (!sharedIsImageFile(filename)) return;
        if (!isSupportedWebFormat(filename)) return;

        images++;
        totalSize += entry._data && entry._data.uncompressedSize
            ? entry._data.uncompressedSize
            : 0;
        if (names.length < 50) names.push(filename);
    });

    return {
        total: Object.keys(zipData.files).length,
        images,
        dirs,
        size: totalSize,
        names
    };
}

/**
 * Extract all supported images from a ZIP with full security checks.
 */
async function extractImagesFromZip(zipFile, progressCallback) {
    const zip = new JSZip();
    const zipData = await zip.loadAsync(zipFile);

    const imageFiles = [];
    const fileList = Object.keys(zipData.files);
    let totalExtractedSize = 0;

    // ---- Pass 1: security & filtering ----
    for (const filename of fileList) {
        throwIfCancelled();
        const entry = zipData.files[filename];
        if (entry.dir) continue;

        // Path traversal
        if (filename.includes('..') || filename.startsWith('/')) {
            console.warn(`Skipping suspicious path: ${filename}`);
            continue;
        }

        // Must be shared-image AND web-supported
        if (!sharedIsImageFile(filename)) continue;
        if (!isSupportedWebFormat(filename)) {
            console.warn(`Skipping unsupported format: ${filename}`);
            continue;
        }

        const uncompressed = entry._data && entry._data.uncompressedSize
            ? entry._data.uncompressedSize
            : 0;
        const compressed = entry._data && entry._data.compressedSize
            ? entry._data.compressedSize
            : 0;

        totalExtractedSize += uncompressed;

        if (totalExtractedSize > MAX_EXTRACTED_SIZE) {
            throw new Error(
                `ZIP file exceeds maximum extraction size ` +
                `(${MAX_EXTRACTED_SIZE / (1024 * 1024)} MB). Possible ZIP bomb.`
            );
        }

        if (compressed > 0 && uncompressed / compressed > MAX_COMPRESSION_RATIO) {
            throw new Error(
                `Suspicious compression ratio ` +
                `(${Math.round(uncompressed / compressed)}:1). Possible ZIP bomb.`
            );
        }

        imageFiles.push(filename);
    }

    if (imageFiles.length > MAX_FILES_IN_ZIP) {
        throw new Error(
            `ZIP contains too many images (${imageFiles.length} > ${MAX_FILES_IN_ZIP}).`
        );
    }

    if (imageFiles.length === 0) {
        throw new Error('No image files found in ZIP archive.');
    }

    // ---- Sort via shared logic ----
    const sortedImages = sharedSortImages(
        imageFiles,
        state.settings.useNaturalSort,
        state.settings.priorityChars
    );

    // ---- Pass 2: extract ----
    const images = [];
    for (let i = 0; i < sortedImages.length; i++) {
        throwIfCancelled();
        const filename = sortedImages[i];
        const blob = await zipData.file(filename).async('blob');
        const url = registerUrl(URL.createObjectURL(blob));

        images.push({ filename, data: blob, url });

        if (progressCallback) {
            progressCallback({
                current: i + 1,
                total: sortedImages.length,
                stage: 'extracting'
            });
        }
    }

    return images;
}

// =====================================================================
// § 09 — PDF CONVERSION
// =====================================================================

/**
 * Convert a list of images into a single PDF and trigger a download.
 */
async function convertImagesToPDF(images, outputFilename, progressCallback) {
    const { jsPDF } = window.jspdf;

    if (!images || images.length === 0) {
        throw new Error('No images to convert.');
    }

    const started = performance.now();

    try {
        const firstImg = await loadImage(images[0].url);
        const firstSize = computePageSize(firstImg);

        const pdf = new jsPDF({
            orientation: firstSize.orientation,
            unit: 'pt',
            format: [firstSize.width, firstSize.height],
            compress: true
        });

        pdf.addImage(
            images[0].url,
            getImageFormat(images[0].filename),
            0, 0,
            firstSize.width,
            firstSize.height,
            undefined,
            'FAST'
        );

        if (progressCallback) {
            progressCallback({ current: 1, total: images.length, stage: 'converting' });
        }

        for (let i = 1; i < images.length; i++) {
            throwIfCancelled();
            const img = await loadImage(images[i].url);
            const size = computePageSize(img);

            pdf.addPage([size.width, size.height], size.orientation);
            pdf.addImage(
                images[i].url,
                getImageFormat(images[i].filename),
                0, 0,
                size.width,
                size.height,
                undefined,
                'FAST'
            );

            if (progressCallback) {
                const elapsed = performance.now() - started;
                const perPage = elapsed / (i + 1);
                const remaining = perPage * (images.length - i - 1);

                progressCallback({
                    current: i + 1,
                    total: images.length,
                    stage: 'converting',
                    eta: remaining
                });
            }
        }

        pdf.save(outputFilename);

        const duration = performance.now() - started;
        recordConversion({
            filename: outputFilename,
            pages: images.length,
            duration,
            bytes: images.reduce((s, im) => s + ((im.data && im.data.size) || 0), 0)
        });

        return { success: true, duration };
    } finally {
        images.forEach(i => revokeUrl(i.url));
    }
}

// =====================================================================
// § 10 — HISTORY + STATS
// =====================================================================

function recordConversion({ filename, pages, duration, bytes }) {
    state.runtime.stats.totalConverted++;
    state.runtime.stats.totalPages += pages;
    state.runtime.stats.totalBytesProcessed += (bytes || 0);

    state.history.unshift({
        ts: Date.now(),
        filename,
        pages,
        duration: Math.round(duration),
        bytes
    });
    state.history = state.history.slice(0, MAX_HISTORY_ENTRIES);

    try {
        localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(state.history));
    } catch (_) { /* quota */ }
}

function loadHistory() {
    try {
        const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
        if (raw) state.history = JSON.parse(raw) || [];
    } catch (_) {
        state.history = [];
    }
}

function clearHistory() {
    state.history = [];
    try { localStorage.removeItem(HISTORY_STORAGE_KEY); } catch (_) {}
    renderHistory();
    pushToast('info', 'History cleared');
}

function renderHistory() {
    const host = document.getElementById('nexus-history');
    if (!host) return;

    if (state.history.length === 0) {
        host.innerHTML = `<div class="history-empty">No conversions yet.</div>`;
        return;
    }

    host.innerHTML = state.history.map(h => `
        <div class="history-row">
            <span class="history-time">${new Date(h.ts).toLocaleTimeString()}</span>
            <span class="history-name">${escapeHtml(h.filename)}</span>
            <span class="history-pages">${h.pages}p</span>
            <span class="history-dur">${formatDuration(h.duration)}</span>
        </div>
    `).join('');
}

// =====================================================================
// § 11 — CONVERSION LOCK (anti-overlap + throttle)
// =====================================================================

function acquireConversionLock() {
    const now = Date.now();
    if (state.runtime.isConverting) {
        pushToast('warning', 'Conversion in progress', 'Please wait for it to finish.');
        return false;
    }
    if (now - state.runtime.lastConversionAt < CONVERSION_THROTTLE_MS) {
        return false;
    }
    state.runtime.isConverting = true;
    state.runtime.cancelRequested = false;
    state.runtime.lastConversionAt = now;
    currentAbort = new AbortController();
    return true;
}

function releaseConversionLock() {
    state.runtime.isConverting = false;
    state.runtime.cancelRequested = false;
    currentAbort = null;
}

// =====================================================================
// § 12 — CONVERSION WORKFLOWS
// =====================================================================

/**
 * Convert a single ZIP to PDF.
 */
async function convertZipToPDF(fileId) {
    const rec = state.files.get(fileId);
    if (!rec) return;
    if (!acquireConversionLock()) return;

    try {
        showProgressModal(true);
        updateProgress({ current: 0, total: 100, stage: 'extracting' });

        const images = await extractImagesFromZip(rec.file, updateProgress);
        if (images.length === 0) throw new Error('No images found in ZIP file.');

        const out = rec.file.name.replace(/\.zip$/i, '.pdf');
        await convertImagesToPDF(images, out, updateProgress);

        showProgressModal(false);
        pushToast('success', 'Conversion complete', `${out} · ${images.length} pages`);
        showNotification(
            'success',
            'Conversion Complete',
            `Successfully converted!\nFile: ${out}\nPages: ${images.length}`
        );

        removeFile(fileId);
    } catch (err) {
        showProgressModal(false);
        if (err.name === 'AbortError') {
            pushToast('warning', 'Conversion cancelled');
        } else {
            pushToast('error', 'Conversion failed', err.message);
            showNotification('error', 'Error Occurred', err.message);
        }
        console.error('Conversion error:', err);
    } finally {
        releaseConversionLock();
    }
}

/**
 * Convert all loaded image files to a single PDF.
 */
async function convertAllToPDF() {
    if (state.imageFiles.length === 0) {
        showNotification('warning', 'No Images', 'No image files to convert.');
        return;
    }
    if (!acquireConversionLock()) return;

    try {
        showProgressModal(true);
        updateProgress({ current: 0, total: state.imageFiles.length, stage: 'extracting' });

        const images = [];
        for (let i = 0; i < state.imageFiles.length; i++) {
            throwIfCancelled();
            const entry = state.imageFiles[i];
            const file = entry && entry.file;
            if (!file) continue;

            const url = registerUrl(URL.createObjectURL(file));
            images.push({ filename: file.name, data: file, url });

            updateProgress({
                current: i + 1,
                total: state.imageFiles.length,
                stage: 'extracting'
            });
        }

        if (images.length === 0) throw new Error('No valid images to convert.');

        const sortedFilenames = sharedSortImages(
            images.map(i => i.filename),
            state.settings.useNaturalSort,
            state.settings.priorityChars
        );
        const sortedImages = sortedFilenames
            .map(name => images.find(i => i.filename === name))
            .filter(Boolean);

        const out = 'converted_images.pdf';
        await convertImagesToPDF(sortedImages, out, updateProgress);

        showProgressModal(false);
        pushToast('success', 'Conversion complete', `${out} · ${images.length} pages`);
        showNotification(
            'success',
            'Conversion Complete',
            `Successfully converted ${images.length} image(s) to PDF!\nFile: ${out}`
        );

        state.imageFiles.slice().forEach(({ fileId }) => removeFile(fileId));
    } catch (err) {
        showProgressModal(false);
        if (err.name === 'AbortError') {
            pushToast('warning', 'Conversion cancelled');
        } else {
            pushToast('error', 'Conversion failed', err.message);
            showNotification('error', 'Error Occurred', err.message);
        }
        console.error('Batch conversion error:', err);
    } finally {
        releaseConversionLock();
    }
}

/**
 * Convert each ZIP file to its own PDF, individually.
 */
async function convertAllZipsIndividually() {
    const zipFiles = Array.from(state.files.entries())
        .filter(([_, d]) => d.type === 'zip')
        .map(([fileId, fileData]) => ({ fileId, fileData }));

    if (zipFiles.length === 0) {
        showNotification('warning', 'No ZIP Files', 'No ZIP files to convert.');
        return;
    }
    if (!acquireConversionLock()) return;

    try {
        showProgressModal(true);
        let ok = 0, fail = 0;

        for (let i = 0; i < zipFiles.length; i++) {
            throwIfCancelled();
            const { fileId, fileData } = zipFiles[i];

            try {
                updateProgress({
                    current: i + 1,
                    total: zipFiles.length,
                    stage: 'extracting',
                    detail: `⟢ ${fileData.file.name}`
                });

                const images = await extractImagesFromZip(fileData.file, () => {});
                if (images.length === 0) { fail++; continue; }

                const out = fileData.file.name.replace(/\.zip$/i, '.pdf');
                await convertImagesToPDF(images, out, () => {});

                ok++;
                await new Promise(r => setTimeout(r, 150));
                removeFile(fileId);
            } catch (err) {
                if (err.name === 'AbortError') throw err;
                console.error(`Error processing ${fileData.file.name}:`, err);
                fail++;
            }
        }

        showProgressModal(false);

        if (ok > 0) {
            pushToast(
                fail === 0 ? 'success' : 'warning',
                `Converted ${ok} ZIP file(s)`,
                fail > 0 ? `${fail} failed` : ''
            );
            showNotification(
                fail === 0 ? 'success' : 'warning',
                'Batch Conversion Complete',
                `Successfully converted ${ok} ZIP file(s) to PDF.` +
                (fail > 0 ? `\n${fail} file(s) failed.` : '')
            );
        } else {
            showNotification('error', 'Conversion Failed', 'All conversions failed.');
        }
    } catch (err) {
        showProgressModal(false);
        if (err.name === 'AbortError') {
            pushToast('warning', 'Batch cancelled');
        } else {
            showNotification('error', 'Error Occurred', err.message);
            pushToast('error', 'Batch failed', err.message);
        }
        console.error('Batch conversion error:', err);
    } finally {
        releaseConversionLock();
    }
}

/**
 * Merge all ZIPs into a single PDF.
 */
async function convertAllZipsToSinglePDF() {
    const zipFiles = Array.from(state.files.entries())
        .filter(([_, d]) => d.type === 'zip')
        .map(([fileId, fileData]) => ({ fileId, fileData }));

    if (zipFiles.length === 0) {
        showNotification('warning', 'No ZIP Files', 'No ZIP files to convert.');
        return;
    }
    if (!acquireConversionLock()) return;

    try {
        showProgressModal(true);

        const sortedNames = sharedSortImages(
            zipFiles.map(({ fileData }) => fileData.file.name),
            state.settings.useNaturalSort,
            state.settings.priorityChars
        );
        const sortedZips = sortedNames
            .map(name => zipFiles.find(({ fileData }) => fileData.file.name === name))
            .filter(Boolean);

        const allImages = [];
        for (let i = 0; i < sortedZips.length; i++) {
            throwIfCancelled();
            const { fileData } = sortedZips[i];

            updateProgress({
                current: i + 1,
                total: sortedZips.length,
                stage: 'extracting',
                detail: `⟢ ${fileData.file.name}`
            });

            const images = await extractImagesFromZip(fileData.file, () => {});
            if (images.length > 0) allImages.push(...images);
        }

        if (allImages.length === 0) throw new Error('No images found in any ZIP file.');

        const out = 'merged_archives.pdf';
        await convertImagesToPDF(allImages, out, updateProgress);

        showProgressModal(false);
        pushToast('success', 'Merge complete', `${out} · ${allImages.length} pages`);
        showNotification(
            'success',
            'Merge Complete',
            `Successfully merged ${zipFiles.length} ZIP file(s) into one PDF!\n` +
            `File: ${out}\nTotal pages: ${allImages.length}`
        );

        sortedZips.forEach(({ fileId }) => removeFile(fileId));
    } catch (err) {
        showProgressModal(false);
        if (err.name === 'AbortError') {
            pushToast('warning', 'Merge cancelled');
        } else {
            showNotification('error', 'Error Occurred', err.message);
            pushToast('error', 'Merge failed', err.message);
        }
        console.error('Merge conversion error:', err);
    } finally {
        releaseConversionLock();
    }
}

// =====================================================================
// § 13 — FILE MANAGEMENT
// =====================================================================

function addFile(file, type = 'zip', meta = {}) {
    const fileId = state.currentFileId++;
    state.files.set(fileId, {
        file,
        type,
        status: 'pending',
        hash: meta.hash || null,
        thumbnail: meta.thumbnail || null,
        zipMeta: meta.zipMeta || null,
        addedAt: Date.now()
    });

    if (type === 'image') {
        state.imageFiles.push({ fileId, file });
    }

    renderFileList();
    renderStats();
    return fileId;
}

function removeFile(fileId) {
    const rec = state.files.get(fileId);
    if (!rec) return;

    if (rec.thumbnail && rec.thumbnail.dataUrl && rec.thumbnail.dataUrl.startsWith('blob:')) {
        revokeUrl(rec.thumbnail.dataUrl);
    }

    if (rec.type === 'image') {
        const idx = state.imageFiles.findIndex(f => f.fileId === fileId);
        if (idx !== -1) state.imageFiles.splice(idx, 1);
    }

    state.files.delete(fileId);
    renderFileList();
    renderStats();
}

function reorderFiles(srcId, dstId) {
    if (srcId === dstId) return;

    const entries = Array.from(state.files.entries());
    const srcIdx = entries.findIndex(([id]) => id === srcId);
    const dstIdx = entries.findIndex(([id]) => id === dstId);
    if (srcIdx === -1 || dstIdx === -1) return;

    const [moved] = entries.splice(srcIdx, 1);
    entries.splice(dstIdx, 0, moved);

    state.files = new Map(entries);

    state.imageFiles = Array.from(state.files.entries())
        .filter(([_, d]) => d.type === 'image')
        .map(([fileId, d]) => ({ fileId, file: d.file }));

    renderFileList();
}

function clearAllFiles() {
    if (state.files.size === 0) return;

    const run = async () => {
        let confirmed = true;
        if (typeof window.nexusConfirm === 'function') {
            confirmed = await window.nexusConfirm('Remove all files from the queue?');
        }
        if (!confirmed) return;

        state.files.clear();
        state.imageFiles = [];
        revokeAllUrls();
        renderFileList();
        renderStats();
        pushToast('info', 'Queue cleared');
    };

    run();
}

// =====================================================================
// § 14 — RENDER
// =====================================================================

function renderBulkActions(zipCount, imageCount) {
    let html = '';

    if (zipCount > 1) {
        html += `
            <button type="button" class="btn btn-primary btn-convert-all" onclick="convertAllZipsIndividually()">
                <span class="btn-glow" aria-hidden="true"></span>
                <svg class="btn-icon" aria-hidden="true"><use href="#i-zap"/></svg>
                CONVERT EACH
            </button>
            <button type="button" class="btn btn-primary btn-convert-all btn-merge" onclick="convertAllZipsToSinglePDF()">
                <span class="btn-glow" aria-hidden="true"></span>
                <svg class="btn-icon" aria-hidden="true"><use href="#i-merge"/></svg>
                MERGE ALL
            </button>`;
    }

    if (imageCount > 1) {
        html += `
            <button type="button" class="btn btn-primary btn-convert-all" onclick="convertAllToPDF()">
                <span class="btn-glow" aria-hidden="true"></span>
                <svg class="btn-icon" aria-hidden="true"><use href="#i-zap"/></svg>
                CONVERT IMAGES
            </button>`;
    }

    return html;
}

function renderFileCard(fileId, fileData) {
    const isZip = fileData.type === 'zip';
    const badge = isZip ? 'ZIP' : 'IMG';
    const badgeCls = isZip ? 'badge-zip' : 'badge-img';
    const safeName = escapeHtml(fileData.file.name);
    const size = formatFileSize(fileData.file.size);
    const status = fileData.status || 'pending';

    const thumb = (fileData.thumbnail && fileData.thumbnail.dataUrl)
        ? `<div class="file-thumb"><img src="${fileData.thumbnail.dataUrl}" alt=""></div>`
        : `<div class="file-thumb file-thumb-placeholder">${badge}</div>`;

    return `
        <div class="file-item"
             data-file-id="${fileId}"
             data-type="${fileData.type}"
             draggable="true">
            <div class="drag-handle" title="Drag to reorder" aria-hidden="true">⋮⋮</div>
            ${thumb}
            <div class="file-info">
                <div class="file-name" title="${safeName}">${safeName}</div>
                <div class="file-meta">
                    <span class="file-size">${size}</span>
                    <span class="meta-sep">//</span>
                    <span class="file-status status-${status}">
                        <span class="status-dot-mini" aria-hidden="true"></span>
                        ${status.toUpperCase()}
                    </span>
                </div>
            </div>
            <div class="file-actions">
                ${isZip ? `
                    <button type="button" class="btn btn-convert" onclick="convertZipToPDF(${fileId})" title="Convert to PDF">
                        <span class="btn-glow" aria-hidden="true"></span>
                        ⚡ CONVERT
                    </button>` : ''}
                <button type="button" class="btn btn-remove" onclick="removeFile(${fileId})" aria-label="Remove file" title="Remove">✕</button>
            </div>
        </div>`;
}

function renderFileList() {
    const fileList          = document.getElementById('fileList');
    const convertAllSection = document.getElementById('convertAllSection');
    const buttonGroup       = document.getElementById('convertButtonGroup');

    if (!fileList) return;

    if (state.files.size === 0) {
        fileList.innerHTML = '';
        if (convertAllSection) convertAllSection.style.display = 'none';
        return;
    }

    const zipCount = Array.from(state.files.values()).filter(f => f.type === 'zip').length;
    const imageCount = state.imageFiles.length;

    if (buttonGroup && convertAllSection) {
        const html = renderBulkActions(zipCount, imageCount);
        if (html) {
            buttonGroup.innerHTML = html;
            convertAllSection.style.display = 'block';
        } else {
            convertAllSection.style.display = 'none';
        }
    }

    const cards = [];
    state.files.forEach((fileData, fileId) => {
        cards.push(renderFileCard(fileId, fileData));
    });

    fileList.innerHTML = `<div class="file-list-inner">${cards.join('')}</div>`;

    wireDragAndDrop();
}

function wireDragAndDrop() {
    const items = document.querySelectorAll('.file-item');

    items.forEach(item => {
        item.addEventListener('dragstart', (e) => {
            state.dragSrcId = Number(item.dataset.fileId);
            item.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', item.dataset.fileId);
        });

        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            document.querySelectorAll('.file-item').forEach(i => i.classList.remove('drag-over-item'));
            state.dragSrcId = null;
        });

        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            item.classList.add('drag-over-item');
        });

        item.addEventListener('dragleave', () => {
            item.classList.remove('drag-over-item');
        });

        item.addEventListener('drop', (e) => {
            e.preventDefault();
            item.classList.remove('drag-over-item');
            const dstId = Number(item.dataset.fileId);
            if (state.dragSrcId != null && state.dragSrcId !== dstId) {
                reorderFiles(state.dragSrcId, dstId);
            }
        });
    });
}

function renderStats() {
    const host = document.getElementById('nexus-stats');
    if (!host) return;

    const zipCount = Array.from(state.files.values()).filter(f => f.type === 'zip').length;
    const imgCount = state.imageFiles.length;
    const totalSize = Array.from(state.files.values())
        .reduce((s, f) => s + (f.file.size || 0), 0);

    host.innerHTML = `
        <div class="stat-cell">
            <span class="stat-label">FILES</span>
            <span class="stat-value">${state.files.size}</span>
        </div>
        <div class="stat-cell">
            <span class="stat-label">ZIP</span>
            <span class="stat-value">${zipCount}</span>
        </div>
        <div class="stat-cell">
            <span class="stat-label">IMG</span>
            <span class="stat-value">${imgCount}</span>
        </div>
        <div class="stat-cell">
            <span class="stat-label">LOAD</span>
            <span class="stat-value">${formatFileSize(totalSize)}</span>
        </div>
        <div class="stat-cell">
            <span class="stat-label">DONE</span>
            <span class="stat-value">${state.runtime.stats.totalConverted}</span>
        </div>
    `;
}

// =====================================================================
// § 15 — FILE INPUT HANDLING
// =====================================================================

async function handleFiles(files) {
    const list = Array.from(files || []);
    if (list.length === 0) return;

    for (const file of list) {
        const zip = isZipFile(file);
        const img = isSupportedWebFormat(file.name);

        if (!zip && !img) {
            pushToast('warning', 'Unsupported file', file.name);
            showNotification(
                'warning',
                'Invalid File Type',
                `${file.name} is not a supported file type.\nSupported: ZIP, JPG, JPEG, PNG, GIF, WebP`
            );
            continue;
        }

        if (!isMimeConsistent(file)) {
            pushToast('warning', 'MIME mismatch', file.name);
            continue;
        }

        if (file.size > MAX_FILE_SIZE) {
            showNotification(
                'warning',
                'File Size Exceeded',
                `${file.name} is too large.\nMaximum: ${formatFileSize(MAX_FILE_SIZE)}\nCurrent: ${formatFileSize(file.size)}`
            );
            continue;
        }

        const hash = await hashFile(file);
        const dup = Array.from(state.files.values()).some(r => r.hash === hash);
        if (dup) {
            pushToast('info', 'Duplicate skipped', file.name);
            continue;
        }

        let thumbnail = null;
        if (img && state.settings.showPreviews) {
            thumbnail = await makeThumbnail(file, 96);
        }

        let zipMeta = null;
        if (zip) {
            try { zipMeta = await inspectZip(file); }
            catch (err) { console.warn('ZIP inspect failed:', err); }
        }

        addFile(file, zip ? 'zip' : 'image', { hash, thumbnail, zipMeta });

        if (zipMeta) {
            pushToast(
                'info',
                `ZIP loaded · ${zipMeta.images} images`,
                file.name
            );
        } else {
            pushToast('success', 'File added', file.name);
        }
    }
}

// =====================================================================
// § 16 — SETTINGS
// =====================================================================

function saveSettings() {
    try {
        localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(state.settings));
    } catch (err) {
        console.warn('Failed to save settings:', err);
    }
}

function loadSettings() {
    try {
        const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        state.settings.useNaturalSort = parsed.useNaturalSort ?? true;
        state.settings.priorityChars   = parsed.priorityChars ?? DEFAULT_PRIORITY_CHARS;
        state.settings.theme           = parsed.theme ?? 'nexus';
        state.settings.showPreviews    = parsed.showPreviews ?? true;
        state.settings.autoRetry       = parsed.autoRetry ?? true;
    } catch (err) {
        console.warn('Failed to load settings:', err);
    }
}

function updateSettings() {
    const ns = document.getElementById('naturalSortEnabled');
    const pc = document.getElementById('priorityChars');
    if (ns) state.settings.useNaturalSort = ns.checked;
    if (pc) state.settings.priorityChars = pc.value;
    saveSettings();
}

function applySettingsToUI() {
    const ns = document.getElementById('naturalSortEnabled');
    const pc = document.getElementById('priorityChars');
    if (ns) ns.checked = state.settings.useNaturalSort;
    if (pc) pc.value = state.settings.priorityChars;
}

function resetSettings() {
    state.settings.useNaturalSort = true;
    state.settings.priorityChars = DEFAULT_PRIORITY_CHARS;

    applySettingsToUI();
    saveSettings();
    pushToast('info', 'Settings reset');
    showNotification('info', 'Settings Reset', 'Settings have been reset to default values.');
}

// =====================================================================
// § 17 — KEYBOARD SHORTCUTS (business logic side)
// =====================================================================

function wireKeyboard() {
    document.addEventListener('keydown', (e) => {
        const tag = (e.target.tagName || '').toLowerCase();
        const typing = tag === 'input' || tag === 'textarea' || e.target.isContentEditable;

        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') {
            e.preventDefault();
            const fi = document.getElementById('fileInput');
            if (fi) fi.click();
            return;
        }

        if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'x') {
            e.preventDefault();
            clearAllFiles();
            return;
        }

        if (e.key === 'Escape') {
            if (state.runtime.isConverting) requestCancel();
            return;
        }

        if (e.key === 'Delete' && !typing) {
            /* Reserved for future selection model */
        }
    });
}

// =====================================================================
// § 18 — INITIALIZATION
// =====================================================================

function init() {
    const dropZone             = document.getElementById('dropZone');
    const fileInput            = document.getElementById('fileInput');
    const naturalSortEnabled   = document.getElementById('naturalSortEnabled');
    const priorityChars        = document.getElementById('priorityChars');
    const resetSettingsBtn     = document.getElementById('resetSettingsBtn');
    const notificationCloseBtn = document.getElementById('notificationCloseBtn');
    const notificationModal    = document.getElementById('notificationModal');
    const clearHistoryBtn      = document.getElementById('clearHistoryBtn');
    const progressCancelBtn    = document.getElementById('progressCancelBtn');

    loadSettings();
    loadHistory();
    applySettingsToUI();

    if (naturalSortEnabled) {
        naturalSortEnabled.addEventListener('change', updateSettings);
    }
    if (priorityChars) {
        priorityChars.addEventListener('input', debounce(updateSettings, 250));
    }
    if (resetSettingsBtn) {
        resetSettingsBtn.addEventListener('click', resetSettings);
    }
    if (notificationCloseBtn) {
        notificationCloseBtn.addEventListener('click', hideNotification);
    }
    if (notificationModal) {
        notificationModal.addEventListener('click', (e) => {
            if (e.target === notificationModal) hideNotification();
        });
    }
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', clearHistory);
    }
    if (progressCancelBtn) {
        progressCancelBtn.addEventListener('click', requestCancel);
    }

    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
            fileInput.value = '';
        });
    }

    if (dropZone) {
        dropZone.addEventListener('click', (e) => {
            if (e.target.tagName !== 'BUTTON') {
                if (fileInput) fileInput.click();
            }
        });

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });

        dropZone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });
    }

    wireKeyboard();

    renderFileList();
    renderStats();
    renderHistory();

    pushToast('info', `NEXUS ${APP_CODENAME} v${APP_VERSION}`, 'Drop ZIPs or images to begin.', 4000);

    window.addEventListener('beforeunload', () => {
        revokeAllUrls();
    });

    console.info(
        `%c NEXUS ${APP_CODENAME} v${APP_VERSION} `,
        'background:#00f0ff;color:#000;font-weight:bold;padding:2px 6px;border-radius:2px;',
        'Ready · @NEXUS_QUANTUM'
    );
}

// =====================================================================
// § 19 — BOOTSTRAP
// =====================================================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// =====================================================================
// § 20 — GLOBAL EXPORTS
// =====================================================================

// -- For inline onclick handlers in index.html -------------------------
window.convertZipToPDF            = convertZipToPDF;
window.convertAllToPDF            = convertAllToPDF;
window.convertAllZipsIndividually = convertAllZipsIndividually;
window.convertAllZipsToSinglePDF  = convertAllZipsToSinglePDF;
window.removeFile                 = removeFile;
window.reorderFiles               = reorderFiles;
window.clearAllFiles              = clearAllFiles;
window.requestCancel              = requestCancel;
window.clearHistory               = clearHistory;

// -- For tests / DevTools introspection --------------------------------
window.__nexus = {
    version: APP_VERSION,
    codename: APP_CODENAME,

    state,

    constants: {
        MAX_FILE_SIZE,
        MAX_EXTRACTED_SIZE,
        MAX_FILES_IN_ZIP,
        MAX_COMPRESSION_RATIO,
        MAX_IMAGE_DIMENSION,
        IMAGE_SCALE_FACTOR,
        WEB_SUPPORTED_FORMATS,
        MAX_HISTORY_ENTRIES,
        CONVERSION_THROTTLE_MS,
        DEFAULT_PRIORITY_CHARS
    },

    utils: {
        escapeHtml,
        formatFileSize,
        formatDuration,
        getExtension,
        getBasename,
        isSupportedWebFormat,
        getImageFormat,
        isZipFile,
        isMimeConsistent,
        hashFile,
        debounce,
        uid
    },

    actions: {
        handleFiles,
        renderFileList,
        renderStats,
        renderHistory,
        reorderFiles,
        clearAllFiles,
        requestCancel,
        clearHistory,
        addFile,
        removeFile,
        updateSettings,
        resetSettings
    },

    internals: {
        extractImagesFromZip,
        convertImagesToPDF,
        inspectZip,
        makeThumbnail,
        loadImage,
        computePageSize,
        acquireConversionLock,
        releaseConversionLock,
        pushToast,
        showNotification,
        hideNotification,
        showProgressModal,
        updateProgress
    }
};

// -- Diagnostics -------------------------------------------------------
(function diagnostics() {
    const missing = [];

    if (!_C) missing.push('NexusConstants (using fallback)');
    if (!_S) missing.push('NexusSorting (using fallback)');
    if (typeof window.JSZip === 'undefined') missing.push('JSZip');
    if (typeof window.jspdf === 'undefined') missing.push('jsPDF');

    if (missing.length > 0) {
        console.warn('[NEXUS] Load order issues:', missing);
    }
})();
