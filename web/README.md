# Web Application

A web application for converting images in ZIP files to PDF.

**100% Client-Side** - All processing happens in the browser, and files are not sent to any server.

## File Structure

```
web/
├── index.html    # Main HTML
├── app.js        # Application logic
└── styles.css    # Stylesheet
```

## Usage

### Online Usage

Use directly on GitHub Pages:
https://9bow.github.io/zipped-imgs-to-pdf/web/

### Local Execution

1. Clone the repository
2. Open `web/index.html` in a browser
3. Drag and drop ZIP files or select files
4. Adjust settings (optional)
5. Click "Convert to PDF" button

## Features

### 1. Drag and Drop

You can drag ZIP files to the drop zone to add them.

### 2. Settings

#### Natural Sorting
- Enabled (recommended): `page_1.jpg` < `page_2.jpg` < `page_10.jpg`
- Disabled: `page_1.jpg` < `page_10.jpg` < `page_2.jpg`

#### Priority Characters
Files starting with entered characters will be placed at the beginning.

Example: When `!` is entered, `!cover.jpg` and `!back.jpg` will be placed first

### 3. Multiple File Processing

Multiple ZIP files can be added at once and converted individually.

### 4. Progress Display

Conversion progress is displayed in a modal:
- Image extraction phase
- PDF generation phase
- Progress percentage (%)

## Tech Stack

### External Libraries

```html
<!-- ZIP file processing -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>

<!-- PDF generation -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
```

### Shared Modules

```html
<!-- Sorting logic -->
<script src="../shared/sorting-logic.js"></script>
```

## Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Required features:**
- ES6+ JavaScript
- File API
- Blob API
- Promise/async-await

## How It Works

### 1. File Selection

```javascript
// Drag and drop or file input
handleFiles(files) {
    for (const file of files) {
        if (file.type === 'application/zip' || file.name.endsWith('.zip')) {
            addFile(file);
        }
    }
}
```

### 2. Image Extraction

```javascript
async function extractImagesFromZip(zipFile, progressCallback) {
    const zip = new JSZip();
    const zipData = await zip.loadAsync(zipFile);

    // Filter only image files
    const imageFiles = Object.keys(zipData.files)
        .filter(filename => isImageFile(filename));

    // Sort
    const sortedImages = sortImages(imageFiles, useNaturalSort, priorityChars);

    // Extract image data
    const images = [];
    for (const filename of sortedImages) {
        const imageData = await zipData.file(filename).async('blob');
        images.push({ filename, data: imageData });
    }

    return images;
}
```

### 3. PDF Conversion

```javascript
async function convertImagesToPDF(images, outputFilename) {
    const { jsPDF } = window.jspdf;

    // Create PDF with first image size
    const firstImg = await loadImage(images[0].url);
    const pdf = new jsPDF({
        orientation: firstImg.width > firstImg.height ? 'landscape' : 'portrait',
        unit: 'pt',
        format: [pdfWidth, pdfHeight]
    });

    // Add images
    for (const image of images) {
        pdf.addImage(image.url, 'JPEG', 0, 0, pdfWidth, pdfHeight);
    }

    // Download
    pdf.save(outputFilename);
}
```

## State Management

```javascript
const state = {
    files: new Map(),      // List of uploaded files
    currentFileId: 0,      // File ID counter
    settings: {
        useNaturalSort: true,        // Whether to use natural sorting
        priorityChars: '!'           // Priority characters
    }
};
```

## UI Components

### 1. Settings Section

```html
<div class="settings-section">
    <label>
        <input type="checkbox" id="naturalSortEnabled" checked>
        Use Natural Sorting
    </label>
    <input type="text" id="priorityChars" value="!">
</div>
```

### 2. Drop Zone

```html
<div class="drop-zone" id="dropZone">
    <p>Drag ZIP files or click to select</p>
    <input type="file" id="fileInput" accept=".zip" multiple hidden>
</div>
```

### 3. File List

```html
<div class="file-list" id="fileList">
    <!-- Dynamically generated -->
</div>
```

### 4. Progress Modal

```html
<div class="modal" id="progressModal">
    <div class="progress-bar">
        <div class="progress-fill" id="progressFill"></div>
    </div>
    <div class="progress-text" id="progressText">0%</div>
</div>
```

## Performance Optimization

### 1. Image Size Limits

Images larger than 2000px are automatically scaled down:

```javascript
const maxDimension = 2000;
if (imgWidth > maxDimension || imgHeight > maxDimension) {
    scale = Math.min(maxDimension / imgWidth, maxDimension / imgHeight);
}
```

### 2. Memory Management

Object URLs are released immediately after use:

```javascript
images.forEach(img => URL.revokeObjectURL(img.url));
```

### 3. Asynchronous Processing

All file I/O is handled with async/await to prevent UI blocking

## Security

- All processing is performed client-side
- Files are not sent to any server
- No external API calls
- HTTPS recommended (GitHub Pages uses HTTPS automatically)

## Development

### Local Testing

Run a simple HTTP server:

```bash
# Python 3
python -m http.server 8000

# Node.js
npx http-server
```

Access http://localhost:8000/web/ in browser

### Debugging

In Chrome DevTools console:

```javascript
// Check current state
console.log(state);

// Test specific file conversion
convertZipToPDF(0);
```

## Deployment

### GitHub Pages

1. Settings > Pages
2. Source: Deploy from a branch
3. Branch: main, Folder: /web
4. Save

### Other Hosting

Upload static files as-is:
- `index.html`
- `app.js`
- `styles.css`
- `../shared/sorting-logic.js`

## License

MIT License - See LICENSE file in parent directory
