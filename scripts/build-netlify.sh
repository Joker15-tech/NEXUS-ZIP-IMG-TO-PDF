#!/usr/bin/env bash
# =====================================================================
# NEXUS QUANTUM // Netlify Build Script
# =====================================================================
# File:    scripts/build-netlify.sh
#
# Purpose:
#   Produce a self-contained `dist/` folder where `../shared/*.js`
#   resolves correctly from `web/index.html`.
#
# Final layout:
#   dist/
#   ├── _redirects            (Netlify routing)
#   ├── _headers              (security headers)
#   ├── index.html            (redirect → /web/)
#   ├── shared/
#   │   ├── constants.js
#   │   └── sorting-logic.js
#   └── web/
#       ├── index.html
#       ├── styles.css
#       └── app.js
# =====================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"

echo "▸ NEXUS QUANTUM — Netlify build"
echo "  root: $ROOT"
echo "  dist: $DIST"

# ---- Clean previous build -------------------------------------------
rm -rf "$DIST"
mkdir -p "$DIST/web" "$DIST/shared"

# ---- Copy web assets ------------------------------------------------
echo "▸ Copying web/ → dist/web/"
cp -R "$ROOT/web/." "$DIST/web/"

# Remove any dev-only files that shouldn't ship
find "$DIST/web" -type f \( -name "*.md" -o -name "*.map" \) -delete || true

# ---- Copy shared JS modules -----------------------------------------
echo "▸ Copying shared/*.js → dist/shared/"
for f in constants.js sorting-logic.js; do
    if [ -f "$ROOT/shared/$f" ]; then
        cp "$ROOT/shared/$f" "$DIST/shared/$f"
    else
        echo "  ⚠ missing shared/$f" >&2
    fi
done

# ---- Root redirect (visitors hitting / land on /web/) ---------------
cat > "$DIST/index.html" <<'HTML'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url=/web/">
    <meta name="robots" content="noindex">
    <title>NEXUS QUANTUM — Redirecting…</title>
    <link rel="canonical" href="/web/">
</head>
<body>
    <p>Redirecting to <a href="/web/">NEXUS QUANTUM</a>…</p>
</body>
</html>
HTML

# ---- Netlify routing ------------------------------------------------
cat > "$DIST/_redirects" <<'REDIRECTS'
# NEXUS QUANTUM — Netlify redirects
/                /web/index.html       200
/app             /web/index.html       200
/app/*           /web/index.html       200
REDIRECTS

# ---- Netlify security headers ---------------------------------------
cat > "$DIST/_headers" <<'HEADERS'
/*
    X-Frame-Options: DENY
    X-Content-Type-Options: nosniff
    Referrer-Policy: strict-origin-when-cross-origin
    Permissions-Policy: geolocation=(), microphone=(), camera=()
    X-XSS-Protection: 1; mode=block

/web/index.html
    Cache-Control: public, max-age=0, must-revalidate

/shared/*
    Cache-Control: public, max-age=31536000, immutable

/web/*.js
    Cache-Control: public, max-age=31536000, immutable

/web/*.css
    Cache-Control: public, max-age=31536000, immutable
HEADERS

# ---- Sanity check ---------------------------------------------------
if [ ! -f "$DIST/web/index.html" ]; then
    echo "  ✗ dist/web/index.html missing — build failed" >&2
    exit 1
fi

if [ ! -f "$DIST/shared/sorting-logic.js" ]; then
    echo "  ✗ dist/shared/sorting-logic.js missing — build failed" >&2
    exit 1
fi

echo "▸ Build complete ✓"
echo "  files in dist/:"
find "$DIST" -type f | sed 's|'"$DIST"'/|    |' | sort
