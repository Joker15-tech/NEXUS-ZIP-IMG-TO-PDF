/**
 * Shared constants for the zipped-imgs-to-pdf project — JS MIRROR.
 *
 * ⚠️  KEEP IN SYNC with `shared/constants.py`.
 *     Any change here must be reflected there, and vice-versa.
 *
 * UMD wrapper: works in Node (CommonJS), AMD, and browser (global).
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else {
        const api = factory();
        root.NexusConstants = api;
        root.IMAGE_EXTENSIONS          = api.IMAGE_EXTENSIONS;
        root.DEFAULT_PRIORITY_CHARS    = api.DEFAULT_PRIORITY_CHARS;
        root.MAX_FILE_SIZE             = api.MAX_FILE_SIZE_BYTES;
        root.MAX_EXTRACTED_SIZE        = api.MAX_EXTRACTED_SIZE_BYTES;
        root.MAX_FILES_IN_ZIP          = api.MAX_FILES_IN_ZIP;
        root.MAX_COMPRESSION_RATIO     = api.MAX_COMPRESSION_RATIO;
        root.MAX_IMAGE_DIMENSION       = api.MAX_IMAGE_DIMENSION;
        root.IMAGE_SCALE_FACTOR        = api.IMAGE_SCALE_FACTOR;
    }
})(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    const IMAGE_EXTENSIONS = [
        '.jpg',
        '.jpeg',
        '.png',
        '.gif',
        '.bmp',
        '.tiff',
        '.webp'
    ];

    const DEFAULT_PRIORITY_CHARS = '!';

    const MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024;
    const MAX_EXTRACTED_SIZE_BYTES = 500 * 1024 * 1024;
    const MAX_FILES_IN_ZIP = 10000;
    const MAX_COMPRESSION_RATIO = 100;
    const MAX_IMAGE_DIMENSION = 2000;
    const IMAGE_SCALE_FACTOR = 4;

    return {
        IMAGE_EXTENSIONS,
        DEFAULT_PRIORITY_CHARS,
        MAX_FILE_SIZE_BYTES,
        MAX_EXTRACTED_SIZE_BYTES,
        MAX_FILES_IN_ZIP,
        MAX_COMPRESSION_RATIO,
        MAX_IMAGE_DIMENSION,
        IMAGE_SCALE_FACTOR
    };
});
