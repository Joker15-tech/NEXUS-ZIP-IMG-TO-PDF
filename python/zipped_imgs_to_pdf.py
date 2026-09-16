#!/usr/bin/env python3
"""
Zipped Images to PDF Converter
================================
Converts ZIP archives containing images into single-file PDFs.

All security checks are enforced before any extraction happens:
    - Zip-slip / path traversal guard (resolve + containment check)
    - Cumulative uncompressed size limit (ZIP bomb)
    - Compression ratio limit (ZIP bomb heuristic)
    - File count limit
    - Absolute path / Windows drive letter rejection

The CLI consumes shared constants from `shared/constants.py` so it stays
in lockstep with the Web version (`shared/constants.js`).
"""

from __future__ import annotations

__version__ = "2.0.0"

import argparse
import logging
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional, Sequence

# ---------------------------------------------------------------------
# Path bootstrap — allow running as `python python/zipped_imgs_to_pdf.py`
# ---------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared import (  # noqa: E402
    is_image_file,
    sort_images,
    get_basename,
    DEFAULT_PRIORITY_CHARS,
    MAX_FILE_SIZE_BYTES,
    MAX_EXTRACTED_SIZE_BYTES,
    MAX_FILES_IN_ZIP,
    MAX_COMPRESSION_RATIO,
)

# ---------------------------------------------------------------------
# Pillow (optional — checked at runtime)
# ---------------------------------------------------------------------
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    Image = None  # type: ignore

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
logger = logging.getLogger("zip2pdf")

# =====================================================================
# § 01 — UTILITIES
# =====================================================================

def human_size(num_bytes: int) -> str:
    """Format a byte count into a compact human-readable string."""
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(num_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024.0
        i += 1
    if i == 0:
        return f"{int(size)} {units[i]}"
    return f"{size:.1f} {units[i]}"


_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _normalize_zip_entry(name: str) -> str:
    """
    Normalize a ZIP entry name for safe extraction.

    - Convert backslashes to forward slashes
    - Strip leading slashes
    - Strip leading `./`
    """
    if not name:
        return ""
    normalized = name.replace("\\", "/")
    normalized = re.sub(r"^\./+", "", normalized)
    normalized = normalized.lstrip("/")
    return normalized


def _is_safe_entry(entry_name: str) -> bool:
    """
    Reject dangerous ZIP entries BEFORE extraction.

    Rules:
        - Reject Windows drive paths  ("C:...")
        - Reject absolute paths       ("/etc/passwd")
        - Reject traversal markers    ("../" anywhere)
        - Reject NUL bytes / empty names
    """
    if not entry_name or "\x00" in entry_name:
        return False
    if _WIN_DRIVE_RE.match(entry_name):
        return False
    if entry_name.startswith("/") or entry_name.startswith("\\"):
        return False

    normalized = _normalize_zip_entry(entry_name)
    parts = [p for p in normalized.split("/") if p not in ("", ".")]
    if any(part == ".." for part in parts):
        return False
    return True


def _is_contained(base_dir: Path, target: Path) -> bool:
    """
    Verify that `target` resolves inside `base_dir`.
    Uses resolved absolute paths (symlinks followed).
    """
    try:
        base = base_dir.resolve()
        resolved = target.resolve()
    except (OSError, ValueError):
        return False
    try:
        resolved.relative_to(base)
        return True
    except ValueError:
        return False


def _safe_extract_member(
    zip_ref: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    temp_dir: Path,
) -> Optional[Path]:
    """
    Extract a single ZIP member into `temp_dir` with full safety checks.

    Returns the resolved extracted path, or None if skipped.
    """
    if not _is_safe_entry(info.filename):
        logger.warning("Skipping suspicious entry: %s", info.filename)
        return None

    normalized = _normalize_zip_entry(info.filename)
    target_path = (temp_dir / normalized).resolve()

    if not _is_contained(temp_dir, target_path):
        logger.warning("Path escapes temp dir (zip-slip): %s", info.filename)
        return None

    # Ensure parent exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Manual extraction — avoids zipfile.extract() quirks across platforms
    with zip_ref.open(info, "r") as src, open(target_path, "wb") as dst:
        shutil.copyfileobj(src, dst, length=64 * 1024)

    return target_path


# =====================================================================
# § 02 — ZIP EXTRACTION
# =====================================================================

class ZipSecurityError(ValueError):
    """Raised when a ZIP violates the configured security limits."""


def extract_images_from_zip(
    zip_path: Path,
    temp_dir: Path,
    use_natural_sort: bool = True,
    priority_chars: str = DEFAULT_PRIORITY_CHARS,
) -> List[Path]:
    """
    Extract all supported image files from a ZIP archive.

    Security checks (all enforced BEFORE any byte hits disk):
        - Path traversal / zip-slip rejection (per-entry)
        - Windows drive letter rejection
        - Cumulative uncompressed size limit
        - Compression ratio limit (ZIP bomb heuristic)
        - File count limit

    Args:
        zip_path: Path to the ZIP file.
        temp_dir: Directory where members will be extracted.
        use_natural_sort: Enable natural sort of filenames.
        priority_chars: Chars triggering priority placement.

    Returns:
        Sorted list of extracted image file paths (may be empty).

    Raises:
        ZipSecurityError: If any security limit is exceeded.
        zipfile.BadZipFile: If the archive is malformed.
    """
    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP not found: {zip_path}")

    temp_dir.mkdir(parents=True, exist_ok=True)

    # ---- Pass 1: validate --------------------------------------------
    image_infos: List[zipfile.ZipInfo] = []
    total_uncompressed = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Reject archives with encrypted entries early
        for info in zf.infolist():
            if info.is_dir():
                continue

            if info.flag_bits & 0x1:
                logger.warning("Encrypted entry skipped: %s", info.filename)
                continue

            if not _is_safe_entry(info.filename):
                logger.warning("Skipping suspicious entry: %s", info.filename)
                continue

            if not is_image_file(info.filename):
                continue

            # Compression ratio heuristic
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_COMPRESSION_RATIO:
                    raise ZipSecurityError(
                        f"Suspicious compression ratio "
                        f"({ratio:.0f}:1 > {MAX_COMPRESSION_RATIO}:1) "
                        f"in {info.filename}. Possible ZIP bomb."
                    )

            # Cumulative uncompressed size
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_EXTRACTED_SIZE_BYTES:
                raise ZipSecurityError(
                    f"ZIP exceeds maximum extraction size "
                    f"({human_size(MAX_EXTRACTED_SIZE_BYTES)}). "
                    f"Possible ZIP bomb."
                )

            image_infos.append(info)

        total_images = len(image_infos)
        if total_images == 0:
            logger.warning("No image files found in %s", zip_path.name)
            return []

        if total_images > MAX_FILES_IN_ZIP:
            raise ZipSecurityError(
                f"ZIP contains too many images "
                f"({total_images} > {MAX_FILES_IN_ZIP})."
            )

        # ---- Pass 2: extract -----------------------------------------
        extracted: List[str] = []
        for idx, info in enumerate(image_infos, 1):
            display = get_basename(info.filename) or info.filename
            logger.info(
                "Extracting %d/%d: %s", idx, total_images, display
            )
            path = _safe_extract_member(zf, info, temp_dir)
            if path is None:
                continue
            extracted.append(str(path))

    if not extracted:
        return []

    sorted_paths = sort_images(extracted, use_natural_sort, priority_chars)
    return [Path(p) for p in sorted_paths]


# =====================================================================
# § 03 — PDF CONVERSION
# =====================================================================

_WHITE_BG = (255, 255, 255)


def _load_image_safely(path: Path) -> Optional["Image.Image"]:
    """
    Load an image, close the file handle, and return an in-memory copy.

    This pattern prevents "file in use" errors on Windows when the
    temp directory is deleted afterwards.
    """
    try:
        with Image.open(path) as src:
            src.load()  # force decode while the file is still open

            if src.mode in ("RGBA", "LA", "P"):
                if src.mode == "P":
                    src = src.convert("RGBA")
                has_alpha = src.mode in ("RGBA", "LA")
                background = Image.new("RGB", src.size, _WHITE_BG)
                if has_alpha:
                    background.paste(src, mask=src.split()[-1])
                else:
                    background.paste(src)
                return background

            if src.mode != "RGB":
                return src.convert("RGB")

            return src.copy()  # detach from file handle
    except (IOError, OSError, ValueError) as exc:
        logger.warning("Cannot process %s: %s", path.name, exc)
        return None


def convert_images_to_pdf(
    image_paths: Sequence[Path],
    output_pdf: Path,
    *,
    resolution: float = 100.0,
) -> bool:
    """
    Convert a list of images to a single multi-page PDF.

    Args:
        image_paths: Ordered list of image paths.
        output_pdf: Destination PDF path.
        resolution: DPI used by Pillow when writing the PDF.

    Returns:
        True on success, False otherwise.
    """
    if not image_paths:
        logger.error("No images to convert.")
        return False

    total = len(image_paths)
    logger.info("Converting %d image(s) to PDF…", total)

    loaded: List["Image.Image"] = []
    for idx, path in enumerate(image_paths, 1):
        logger.info("  [%d/%d] %s", idx, total, path.name)
        img = _load_image_safely(path)
        if img is not None:
            loaded.append(img)

    if not loaded:
        logger.error("No valid images to convert.")
        return False

    try:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        first, rest = loaded[0], loaded[1:]

        first.save(
            str(output_pdf),
            "PDF",
            save_all=True,
            append_images=rest,
            resolution=resolution,
        )
        logger.info("Successfully created: %s", output_pdf.name)
        logger.info("  Pages: %d", len(loaded))
        return True

    except Exception as exc:  # noqa: BLE001 — surface any Pillow failure
        logger.error("Error creating PDF: %s", exc)
        return False

    finally:
        # Explicitly close in-memory images (frees RAM + releases refs)
        for img in loaded:
            try:
                img.close()
            except Exception:  # noqa: BLE001
                pass


# =====================================================================
# § 04 — SINGLE ZIP WORKFLOW
# =====================================================================

def process_zip_file(
    zip_path: Path,
    output_dir: Optional[Path] = None,
    use_natural_sort: bool = True,
    priority_chars: str = DEFAULT_PRIORITY_CHARS,
) -> bool:
    """
    Process a single ZIP file: extract → sort → convert → save PDF.

    Returns True on success, False otherwise.
    """
    if not zip_path.exists():
        logger.error("File not found: %s", zip_path)
        return False

    if zip_path.suffix.lower() != ".zip":
        logger.error("Not a ZIP file: %s", zip_path)
        return False

    # Pre-check: input file size
    file_size = zip_path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        logger.error(
            "File too large: %s (%s > %s)",
            zip_path.name,
            human_size(file_size),
            human_size(MAX_FILE_SIZE_BYTES),
        )
        return False

    if output_dir is None:
        output_dir = zip_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    output_pdf = output_dir / f"{zip_path.stem}.pdf"

    temp_dir = Path(tempfile.mkdtemp(prefix="zip2pdf_"))
    try:
        try:
            image_paths = extract_images_from_zip(
                zip_path, temp_dir, use_natural_sort, priority_chars
            )
        except zipfile.BadZipFile:
            logger.error("%s is not a valid ZIP file.", zip_path.name)
            return False
        except ZipSecurityError as exc:
            logger.error("Security error: %s", exc)
            return False

        if not image_paths:
            return False

        logger.info("Found %d image(s) in archive", len(image_paths))
        return convert_images_to_pdf(image_paths, output_pdf)

    finally:
        try:
            shutil.rmtree(temp_dir)
        except OSError as exc:
            logger.warning("Could not remove temp dir %s: %s", temp_dir, exc)


# =====================================================================
# § 05 — RECURSIVE ZIP DISCOVERY
# =====================================================================

def find_zip_files_recursive(directory: Path) -> List[Path]:
    """
    Recursively find all `.zip` files (case-insensitive) in a directory.

    Deduplicates via resolved path and returns a case-insensitive sort.
    """
    found: List[Path] = []
    seen: set = set()

    try:
        for entry in directory.rglob("*"):
            if not entry.is_file():
                continue
            if entry.suffix.lower() != ".zip":
                continue
            try:
                key = entry.resolve()
            except OSError:
                key = entry
            if key in seen:
                continue
            seen.add(key)
            found.append(entry)
    except OSError as exc:
        logger.error("Error searching %s: %s", directory, exc)

    return sorted(found, key=lambda p: str(p).lower())


# =====================================================================
# § 06 — CLI
# =====================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zipped-imgs-to-pdf",
        description="Convert ZIP files containing images to PDF files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s images1.zip
  %(prog)s images1.zip images2.zip images3.zip
  %(prog)s *.zip
  %(prog)s images1.zip -o /path/to/output/
  %(prog)s images1.zip --no-natural-sort
  %(prog)s images1.zip --priority-chars "!@"
  %(prog)s /path/to/archives/ -r
  %(prog)s /path/to/archives/ --recursive -o /path/to/output/
""",
    )

    parser.add_argument(
        "zip_files",
        nargs="+",
        type=str,
        help="ZIP file(s) or directory to convert",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output directory for PDF files (default: same as input file)",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively process all ZIP files in specified directories",
    )
    parser.add_argument(
        "--natural-sort",
        dest="natural_sort",
        action="store_true",
        default=True,
        help="Use natural sorting for numbers in filenames (default: enabled)",
    )
    parser.add_argument(
        "--no-natural-sort",
        dest="natural_sort",
        action="store_false",
        help="Disable natural sorting (use standard lexical sorting)",
    )
    parser.add_argument(
        "--priority-chars",
        type=str,
        default=DEFAULT_PRIORITY_CHARS,
        help=(
            "Characters that mark images for priority placement "
            "at the beginning (default: '!')"
        ),
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only show errors",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show debug-level messages",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s version {__version__}",
    )

    return parser


def _setup_logging(quiet: bool, verbose: bool) -> None:
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stdout,
    )


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point. Returns process exit code."""
    if not PILLOW_AVAILABLE:
        print(
            "Error: Pillow library is required. "
            "Install it with: pip install Pillow",
            file=sys.stderr,
        )
        return 1

    args = build_parser().parse_args(argv)
    _setup_logging(args.quiet, args.verbose)

    # ---- Output directory --------------------------------------------
    output_dir: Optional[Path] = None
    if args.output:
        output_dir = Path(args.output)
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                logger.error("Error creating output directory: %s", exc)
                return 1

    # ---- Banner ------------------------------------------------------
    if not args.quiet:
        logger.info("Configuration:")
        logger.info(
            "  Natural sorting     : %s",
            "enabled" if args.natural_sort else "disabled",
        )
        logger.info(
            "  Priority characters : %s",
            repr(args.priority_chars) if args.priority_chars else "none",
        )
        logger.info(
            "  Recursive mode      : %s",
            "enabled" if args.recursive else "disabled",
        )
        logger.info("")

    # ---- Collect targets ---------------------------------------------
    targets: List[Path] = []
    for path_str in args.zip_files:
        path = Path(path_str)
        if path.is_dir():
            if args.recursive:
                found = find_zip_files_recursive(path)
                if found:
                    logger.info(
                        "Found %d ZIP file(s) in %s", len(found), path
                    )
                    targets.extend(found)
                else:
                    logger.warning("No ZIP files found in %s", path)
            else:
                logger.warning(
                    "%s is a directory. Use --recursive to process "
                    "directories.",
                    path,
                )
        elif path.is_file():
            targets.append(path)
        else:
            logger.warning("%s not found", path)

    if not targets:
        logger.error("No ZIP files to process")
        return 1

    # ---- Process -----------------------------------------------------
    logger.info("Processing %d ZIP file(s)…\n", len(targets))

    success_count = 0
    failure_count = 0
    total = len(targets)

    for idx, zip_path in enumerate(targets, 1):
        logger.info("[%d/%d] Processing: %s", idx, total, zip_path.name)
        logger.info("-" * 60)

        ok = process_zip_file(
            zip_path,
            output_dir,
            args.natural_sort,
            args.priority_chars,
        )
        if ok:
            success_count += 1
        else:
            failure_count += 1

        logger.info("")

    # ---- Summary -----------------------------------------------------
    logger.info("=" * 50)
    logger.info(
        "Summary: %d successful, %d failed", success_count, failure_count
    )

    return 0 if failure_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
