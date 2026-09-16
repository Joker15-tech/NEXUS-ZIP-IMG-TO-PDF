/**
 * Zipped Images to PDF Converter - Web Application
 * Converts ZIP files containing images to PDF files.
 * All processing is done client-side - no files are uploaded to any server.
 *
 * Note: This application uses shared sorting logic from ../shared/sorting-logic.js
 * The following functions are imported from the shared module:
 * - isImageFile()
 * - sortImages()
 * - IMAGE_EXTENSIONS
 * - DEFAULT_PRIORITY_CHARS
 */

// LocalStorage key for settings
const SETTINGS_STORAGE_KEY = 'zipToPdfSettings';

// Security limits - should match shared/constants.py
const MAX_FILE_SIZE = 200 * 1024 * 1024; // 200MB in bytes
const MAX_EXTRACTED_SIZE = 500 * 1024 * 1024; // 500MB (ZIP bomb protection)
const MAX_FILES_IN_ZIP = 10000; // Maximum number of files to extract

// Image processing constants
const MAX_IMAGE_DIMENSION = 2000; // Maximum dimension in pixels
const IMAGE_SCALE_FACTOR = 4; // Scale factor for PDF conversion

// State management
const state = {
    files: new Map(), // Map<fileId, {file, type: 'zip'|'image', status}>
    imageFiles: [], // Array of {fileId, file} for batch image conversion
    currentFileId: 0,
    settings: {
        useNaturalSort: true,
        priorityChars: DEFAULT_PRIORITY_CHARS
    }
};

/**
 * Format file size in human-readable format
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Show notification modal
 * @param {string} type - Type of notification: 'success', 'error', 'warning', 'info'
 * @param {string} title - Title of the notification
 * @param {string} message - Message to display
 */
function showNotification(type, title, message) {
    const modal = document.getElementById('notificationModal');
    const iconContainer = document.getElementById('notificationIcon');
    const titleElement = document.getElementById('notificationTitle');
    const messageElement = document.getElementById('notificationMessage');

    // Define SVG icons for different notification types
    const icons = {
        success: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>`,
        error: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>`,
        warning: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>`,
        info: `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>`
    };

    // Set icon and class
    iconContainer.innerHTML = icons[type] || icons.info;
    iconContainer.className = 'notification-icon ' + type;

    // Set title and message
    titleElement.textContent = title;
    messageElement.textContent = message;

    // Show modal
    modal.classList.add('active');
}

/**
 * Hide notification modal
 */
function hideNotification() {
    const modal = document.getElementById('notificationModal');
    modal.classList.remove('active');
}

/**
 * Extract images from ZIP file with security checks
 * @param {File} zipFile - The ZIP file to extract
 * @param {Function} progressCallback - Progress callback function
 * @returns {Promise<Array>} Array of extracted images
 * @throws {Error} If security limits are exceeded
 */
async function extractImagesFromZip(zipFile, progressCallback) {
    const zip = new JSZip();
    const zipData = await zip.loadAsync(zipFile);

    const imageFiles = [];
    const fileList = Object.keys(zipData.files);
    let totalExtractedSize = 0;

    // First pass: validate files and check security limits
    for (const filename of fileList) {
        const file = zipData.files[filename];

        // Skip directories
        if (file.dir) {
            continue;
        }

        // Security: Check for path traversal
        if (filename.includes('..') || filename.startsWith('/')) {
            console.warn(`Skipping suspicious path: ${filename}`);
            continue;
        }

        // Check if it's an image file
        if (!isImageFile(filename)) {
            continue;
        }

        // Check if format is supported in Web App
        if (!isSupportedWebFormat(filename)) {
            console.warn(`Skipping unsupported format: ${filename}`);
            continue;
        }

        // Security: Check extracted size (ZIP bomb protection)
        const uncompressedSize = file._data?.uncompressedSize || 0;
        totalExtractedSize += uncompressedSize;
        if (totalExtractedSize > MAX_EXTRACTED_SIZE) {
            throw new Error(
                `ZIP file exceeds maximum extraction size ` +
                `(${MAX_EXTRACTED_SIZE / (1024 * 1024)}MB). ` +
                `Possible ZIP bomb attack.`
            );
        }

        imageFiles.push(filename);
    }

    // Security: Check file count
    if (imageFiles.length > MAX_FILES_IN_ZIP) {
        throw new Error(
            `ZIP file contains too many files ` +
            `(${imageFiles.length} > ${MAX_FILES_IN_ZIP})`
        );
    }

    if (imageFiles.length === 0) {
        throw new Error('No image files found in ZIP archive.');
    }

    // Sort images using current settings
    const sortedImages = sortImages(
        imageFiles,
        state.settings.useNaturalSort,
        state.settings.priorityChars
    );

    // Extract image data
    const images = [];
    for (let i = 0; i < sortedImages.length; i++) {
        const filename = sortedImages[i];
        const imageData = await zipData.file(filename).async('blob');

        images.push({
            filename,
            data: imageData,
            url: URL.createObjectURL(imageData)
        });

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

/**
 * Load image and get dimensions
 */
function loadImage(imageUrl) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = imageUrl;
    });
}

/**
 * Detect image format from filename for PDF generation
 * jsPDF supports: JPEG, PNG, WEBP, GIF
 */
function getImageFormat(filename) {
    const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
    const formatMap = {
        '.jpg': 'JPEG',
        '.jpeg': 'JPEG',
        '.png': 'PNG',
        '.gif': 'GIF',
        '.webp': 'WEBP'
    };
    return formatMap[ext] || 'JPEG';  // Default to JPEG for unknown formats
}

/**
 * Check if image format is supported by Web App
 */
function isSupportedWebFormat(filename) {
    const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
    return ['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(ext);
}

/**
 * Convert images to PDF
 */
async function convertImagesToPDF(images, outputFilename, progressCallback) {
    const { jsPDF } = window.jspdf;

    if (!images || images.length === 0) {
        throw new Error('No images to convert.');
    }

    // Load first image to determine page size
    const firstImg = await loadImage(images[0].url);
    const imgWidth = firstImg.width;
    const imgHeight = firstImg.height;

    // Create PDF with custom page size matching the image dimensions
    // jsPDF uses points (1 pt = 1/72 inch)
    // We'll scale down large images to a reasonable size
    let scale = 1;

    if (imgWidth > MAX_IMAGE_DIMENSION || imgHeight > MAX_IMAGE_DIMENSION) {
        scale = Math.min(
            MAX_IMAGE_DIMENSION / imgWidth,
            MAX_IMAGE_DIMENSION / imgHeight
        );
    }

    // Convert to points (rough approximation)
    const pdfWidth = (imgWidth * scale) / IMAGE_SCALE_FACTOR;
    const pdfHeight = (imgHeight * scale) / IMAGE_SCALE_FACTOR;

    const pdf = new jsPDF({
        orientation: imgWidth > imgHeight ? 'landscape' : 'portrait',
        unit: 'pt',
        format: [pdfWidth, pdfHeight]
    });

    // Add first image
    const firstImageFormat = getImageFormat(images[0].filename);
    pdf.addImage(images[0].url, firstImageFormat, 0, 0, pdfWidth, pdfHeight);

    if (progressCallback) {
        progressCallback({
            current: 1,
            total: images.length,
            stage: 'converting'
        });
    }

    // Add remaining images
    for (let i = 1; i < images.length; i++) {
        const img = await loadImage(images[i].url);
        const currentImgWidth = img.width;
        const currentImgHeight = img.height;

        // Calculate page size for current image
        let currentScale = 1;
        if (currentImgWidth > MAX_IMAGE_DIMENSION ||
            currentImgHeight > MAX_IMAGE_DIMENSION) {
            currentScale = Math.min(
                MAX_IMAGE_DIMENSION / currentImgWidth,
                MAX_IMAGE_DIMENSION / currentImgHeight
            );
        }

        const currentPdfWidth = (currentImgWidth * currentScale) /
            IMAGE_SCALE_FACTOR;
        const currentPdfHeight = (currentImgHeight * currentScale) /
            IMAGE_SCALE_FACTOR;

        // Add new page with appropriate size
        pdf.addPage([currentPdfWidth, currentPdfHeight], currentImgWidth > currentImgHeight ? 'landscape' : 'portrait');
        const imageFormat = getImageFormat(images[i].filename);
        pdf.addImage(images[i].url, imageFormat, 0, 0, currentPdfWidth, currentPdfHeight);

        if (progressCallback) {
            progressCallback({
                current: i + 1,
                total: images.length,
                stage: 'converting'
            });
        }
    }

    // Save PDF
    pdf.save(outputFilename);

    // Clean up object URLs
    images.forEach(img => URL.revokeObjectURL(img.url));

    return true;
}

/**
 * Show/hide progress modal
 */
function showProgressModal(show = true) {
    const modal = document.getElementById('progressModal');
    if (show) {
        modal.classList.add('active');
    } else {
        modal.classList.remove('active');
    }
}

/**
 * Update progress modal
 */
function updateProgress(info) {
    const progressInfo = document.getElementById('progressInfo');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');

    const percentage = Math.round((info.current / info.total) * 100);

    let message = '';
    if (info.stage === 'extracting') {
        message = `Extracting images... (${info.current}/${info.total})`;
    } else if (info.stage === 'converting') {
        message = `Converting to PDF... (${info.current}/${info.total})`;
    }

    progressInfo.textContent = message;
    progressFill.style.width = percentage + '%';
    progressText.textContent = percentage + '%';
}

/**
 * Process and convert a ZIP file to PDF
 */
async function convertZipToPDF(fileId) {
    const fileData = state.files.get(fileId);
    if (!fileData) return;

    try {
        showProgressModal(true);

        // Extract images from ZIP
        updateProgress({ current: 0, total: 100, stage: 'extracting' });
        const images = await extractImagesFromZip(fileData.file, updateProgress);

        if (images.length === 0) {
            throw new Error('No images found in ZIP file.');
        }

        // Convert to PDF
        const outputFilename = fileData.file.name.replace(/\.zip$/i, '.pdf');
        await convertImagesToPDF(images, outputFilename, updateProgress);

        showProgressModal(false);
        showNotification(
            'success',
            'Conversion Complete',
            `Successfully converted!\nFile: ${outputFilename}\nPages: ${images.length}`
        );

        // Remove file from list after successful conversion
        removeFile(fileId);

    } catch (error) {
        showProgressModal(false);
        showNotification('error', 'Error Occurred', error.message);
        console.error('Conversion error:', error);
    }
}

/**
 * Convert all image files to a single PDF
 */
async function convertAllToPDF() {
    if (state.imageFiles.length === 0) {
        showNotification('warning', 'No Images', 'No image files to convert.');
        return;
    }

    try {
        showProgressModal(true);

        // Load all images
        updateProgress({ current: 0, total: state.imageFiles.length, stage: 'extracting' });

        const images = [];
        for (let i = 0; i < state.imageFiles.length; i++) {
            const { file } = state.imageFiles[i];
            const blob = file;
            const url = URL.createObjectURL(blob);

            images.push({
                filename: file.name,
                data: blob,
                url: url
            });

            updateProgress({
                current: i + 1,
                total: state.imageFiles.length,
                stage: 'extracting'
            });
        }

        // Sort images using current settings
        const filenames = images.map(img => img.filename);
        const sortedFilenames = sortImages(
            filenames,
            state.settings.useNaturalSort,
            state.settings.priorityChars
        );

        // Reorder images based on sorted filenames
        const sortedImages = sortedFilenames.map(filename =>
            images.find(img => img.filename === filename)
        );

        // Convert to PDF
        const outputFilename = 'converted_images.pdf';
        await convertImagesToPDF(sortedImages, outputFilename, updateProgress);

        showProgressModal(false);
        showNotification(
            'success',
            'Conversion Complete',
            `Successfully converted ${images.length} image(s) to PDF!\\nFile: ${outputFilename}`
        );

        // Clear all image files after successful conversion
        state.imageFiles.forEach(({ fileId }) => removeFile(fileId));

    } catch (error) {
        showProgressModal(false);
        showNotification('error', 'Error Occurred', error.message);
        console.error('Batch conversion error:', error);
    }
}

/**
 * Convert all ZIP files individually (each ZIP to its own PDF)
 */
async function convertAllZipsIndividually() {
    const zipFiles = Array.from(state.files.entries())
        .filter(([_, fileData]) => fileData.type === 'zip')
        .map(([fileId, fileData]) => ({ fileId, fileData }));

    if (zipFiles.length === 0) {
        showNotification('warning', 'No ZIP Files', 'No ZIP files to convert.');
        return;
    }

    try {
        showProgressModal(true);
        let successCount = 0;
        let failCount = 0;

        for (let i = 0; i < zipFiles.length; i++) {
            const { fileId, fileData } = zipFiles[i];

            try {
                updateProgress({
                    current: i + 1,
                    total: zipFiles.length,
                    stage: 'extracting'
                });

                // Extract images from ZIP
                const images = await extractImagesFromZip(fileData.file, (progress) => {
                    // Update with file-specific progress
                    updateProgress({
                        current: i + 1,
                        total: zipFiles.length,
                        stage: progress.stage
                    });
                });

                if (images.length === 0) {
                    failCount++;
                    continue;
                }

                // Convert to PDF
                const outputFilename = fileData.file.name.replace(/\.zip$/i, '.pdf');
                await convertImagesToPDF(images, outputFilename, (progress) => {
                    updateProgress({
                        current: i + 1,
                        total: zipFiles.length,
                        stage: progress.stage
                    });
                });

                successCount++;

                // Add small delay to ensure browser processes each download separately
                // This prevents filename conflicts when multiple files are downloaded rapidly
                await new Promise(resolve => setTimeout(resolve, 100));

                // Remove the processed file
                removeFile(fileId);

            } catch (error) {
                console.error(`Error processing ${fileData.file.name}:`, error);
                failCount++;
            }
        }

        showProgressModal(false);

        if (successCount > 0) {
            showNotification(
                failCount === 0 ? 'success' : 'warning',
                'Batch Conversion Complete',
                `Successfully converted ${successCount} ZIP file(s) to PDF.${failCount > 0 ? `\n${failCount} file(s) failed.` : ''}`
            );
        } else {
            showNotification('error', 'Conversion Failed', 'All conversions failed.');
        }

    } catch (error) {
        showProgressModal(false);
        showNotification('error', 'Error Occurred', error.message);
        console.error('Batch conversion error:', error);
    }
}

/**
 * Convert all ZIP files to a single merged PDF
 */
async function convertAllZipsToSinglePDF() {
    const zipFiles = Array.from(state.files.entries())
        .filter(([_, fileData]) => fileData.type === 'zip')
        .map(([fileId, fileData]) => ({ fileId, fileData }));

    if (zipFiles.length === 0) {
        showNotification('warning', 'No ZIP Files', 'No ZIP files to convert.');
        return;
    }

    try {
        showProgressModal(true);

        // Sort ZIP files by their filenames first (using natural sort settings)
        const zipFilenames = zipFiles.map(({ fileData }) => fileData.file.name);
        const sortedZipFilenames = sortImages(
            zipFilenames,
            state.settings.useNaturalSort,
            state.settings.priorityChars
        );

        // Reorder zipFiles array based on sorted filenames
        const sortedZipFiles = sortedZipFilenames.map(filename =>
            zipFiles.find(({ fileData }) => fileData.file.name === filename)
        );

        // Extract images from all ZIPs in sorted order
        // Each ZIP's images are already sorted internally by extractImagesFromZip
        const allImages = [];
        for (let i = 0; i < sortedZipFiles.length; i++) {
            const { fileData } = sortedZipFiles[i];

            updateProgress({
                current: i + 1,
                total: sortedZipFiles.length,
                stage: 'extracting'
            });

            const images = await extractImagesFromZip(fileData.file, () => { });

            // Images from extractImagesFromZip are already sorted
            // Add them in order to maintain ZIP file sequence
            if (images.length > 0) {
                allImages.push(...images);
            }
        }

        if (allImages.length === 0) {
            throw new Error('No images found in any ZIP file.');
        }
        // Convert to PDF
        const outputFilename = 'merged_archives.pdf';
        await convertImagesToPDF(allImages, outputFilename, updateProgress);

        showProgressModal(false);
        showNotification(
            'success',
            'Merge Complete',
            `Successfully merged ${zipFiles.length} ZIP file(s) into one PDF!\nFile: ${outputFilename} \nTotal pages: ${allImages.length} `
        );

        // Clear all ZIP files after successful conversion
        sortedZipFiles.forEach(({ fileId }) => removeFile(fileId));

    } catch (error) {
        showProgressModal(false);
        showNotification('error', 'Error Occurred', error.message);
        console.error('Merge conversion error:', error);
    }
}

/**
 * Add a file to the list
 */
function addFile(file, type = 'zip') {
    const fileId = state.currentFileId++;
    state.files.set(fileId, {
        file,
        type,
        status: 'pending'
    });

    // If it's an image file, add to imageFiles array
    if (type === 'image') {
        state.imageFiles.push({ fileId, file });
    }

    renderFileList();
}

/**
 * Remove a file from the list
 */
function removeFile(fileId) {
    const fileData = state.files.get(fileId);

    // Remove from imageFiles array if it's an image
    if (fileData?.type === 'image') {
        const index = state.imageFiles.findIndex(f => f.fileId === fileId);
        if (index !== -1) {
            state.imageFiles.splice(index, 1);
        }
    }

    state.files.delete(fileId);
    renderFileList();
}

/**
 * Render the file list
 */
function renderFileList() {
    const fileList = document.getElementById('fileList');
    const convertAllSection = document.getElementById('convertAllSection');
    const buttonGroup = document.getElementById('convertButtonGroup');

    if (state.files.size === 0) {
        fileList.innerHTML = '';
        convertAllSection.style.display = 'none';
        return;
    }

    // Count file types
    const zipCount = Array.from(state.files.values()).filter(f => f.type === 'zip').length;
    const imageCount = state.imageFiles.length;

    // Determine which buttons to show
    let buttonsHTML = '';

    if (zipCount > 1) {
        // Multiple ZIP files - show both ZIP options
        buttonsHTML += `
            <button class="btn btn-primary btn-convert-all" onclick="convertAllZipsIndividually()">
                Convert Each to PDF
            </button>
            <button class="btn btn-primary btn-convert-all" onclick="convertAllZipsToSinglePDF()">
                Merge All to Single PDF
            </button>
        `;
    }

    if (imageCount > 1) {
        // Multiple image files - show image convert all option
        buttonsHTML += `
            <button class="btn btn-primary btn-convert-all" onclick="convertAllToPDF()">
                Convert Images to PDF
            </button>
        `;
    }

    // Show/hide convert all section
    if (buttonsHTML) {
        buttonGroup.innerHTML = buttonsHTML;
        convertAllSection.style.display = 'block';
    } else {
        convertAllSection.style.display = 'none';
    }

    // Render file list
    let html = '';
    state.files.forEach((fileData, fileId) => {
        const isZip = fileData.type === 'zip';

        html += `
            <div class="file-item" data-file-id="${fileId}">
                <div class="file-info">
                    <div class="file-name">${fileData.file.name}</div>
                    <div class="file-size">${formatFileSize(fileData.file.size)}</div>
                </div>
                <div class="file-actions">
                    ${isZip ? `<button class="btn btn-convert" onclick="convertZipToPDF(${fileId})">Convert to PDF</button>` : ''}
                    <button class="btn btn-remove" onclick="removeFile(${fileId})">Remove</button>
                </div>
            </div>
        `;
    });

    fileList.innerHTML = html;
}

/**
 * Handle file selection
 */
function handleFiles(files) {
    for (const file of files) {
        const isZipFile = file.type === 'application/zip' || file.name.toLowerCase().endsWith('.zip');
        const isImageFile = isSupportedWebFormat(file.name);

        // Check if file is valid type (ZIP or supported image)
        if (!isZipFile && !isImageFile) {
            showNotification(
                'warning',
                'Invalid File Type',
                `${file.name} is not a supported file type.\nSupported: ZIP, JPG, JPEG, PNG, GIF, WebP`
            );
            continue;
        }

        // Check file size
        if (file.size > MAX_FILE_SIZE) {
            showNotification(
                'warning',
                'File Size Exceeded',
                `${file.name} is too large.\nMaximum: ${formatFileSize(MAX_FILE_SIZE)} \nCurrent: ${formatFileSize(file.size)} `
            );
            continue;
        }

        // Add file with appropriate type
        const fileType = isZipFile ? 'zip' : 'image';
        addFile(file, fileType);
    }
}

/**
 * Save settings to localStorage
 */
function saveSettings() {
    try {
        localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(state.settings));
    } catch (error) {
        console.warn('Failed to save settings to localStorage:', error);
    }
}

/**
 * Load settings from localStorage
 */
function loadSettings() {
    try {
        const savedSettings = localStorage.getItem(SETTINGS_STORAGE_KEY);
        if (savedSettings) {
            const parsed = JSON.parse(savedSettings);
            state.settings.useNaturalSort = parsed.useNaturalSort ?? true;
            state.settings.priorityChars = parsed.priorityChars ?? '!';
        }
    } catch (error) {
        console.warn('Failed to load settings from localStorage:', error);
    }
}

/**
 * Update settings from UI
 */
function updateSettings() {
    const naturalSortEnabled = document.getElementById('naturalSortEnabled');
    const priorityChars = document.getElementById('priorityChars');

    state.settings.useNaturalSort = naturalSortEnabled.checked;
    state.settings.priorityChars = priorityChars.value;

    // Save settings to localStorage
    saveSettings();
}

/**
 * Apply settings to UI
 */
function applySettingsToUI() {
    const naturalSortEnabled = document.getElementById('naturalSortEnabled');
    const priorityChars = document.getElementById('priorityChars');

    naturalSortEnabled.checked = state.settings.useNaturalSort;
    priorityChars.value = state.settings.priorityChars;
}

/**
 * Reset settings to default values
 */
function resetSettings() {
    // Reset to default values
    state.settings.useNaturalSort = true;
    state.settings.priorityChars = DEFAULT_PRIORITY_CHARS;

    // Apply to UI
    applySettingsToUI();

    // Save to localStorage
    saveSettings();

    // Show notification
    showNotification(
        'info',
        'Settings Reset',
        'Settings have been reset to default values.'
    );
}

/**
 * Initialize the application
 */
function init() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const naturalSortEnabled = document.getElementById('naturalSortEnabled');
    const priorityChars = document.getElementById('priorityChars');
    const resetSettingsBtn = document.getElementById('resetSettingsBtn');
    const notificationCloseBtn = document.getElementById('notificationCloseBtn');

    // Load saved settings from localStorage
    loadSettings();

    // Apply loaded settings to UI
    applySettingsToUI();

    // Settings change handlers
    naturalSortEnabled.addEventListener('change', updateSettings);
    priorityChars.addEventListener('input', updateSettings);

    // Reset settings button handler
    resetSettingsBtn.addEventListener('click', resetSettings);

    // Notification modal close button handler
    notificationCloseBtn.addEventListener('click', hideNotification);

    // Close notification modal when clicking outside
    const notificationModal = document.getElementById('notificationModal');
    notificationModal.addEventListener('click', (e) => {
        if (e.target === notificationModal) {
            hideNotification();
        }
    });

    // File input change handler
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
        fileInput.value = ''; // Reset input
    });

    // Drop zone click handler
    dropZone.addEventListener('click', (e) => {
        if (e.target.tagName !== 'BUTTON') {
            fileInput.click();
        }
    });

    // Drag and drop handlers
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');

        const files = Array.from(e.dataTransfer.files);
        handleFiles(files);
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Make functions globally accessible for inline event handlers
window.convertZipToPDF = convertZipToPDF;
window.convertAllToPDF = convertAllToPDF;
window.convertAllZipsIndividually = convertAllZipsIndividually;
window.convertAllZipsToSinglePDF = convertAllZipsToSinglePDF;
window.removeFile = removeFile;
