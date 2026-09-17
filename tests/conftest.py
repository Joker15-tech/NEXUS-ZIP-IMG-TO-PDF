#!/usr/bin/env python3
"""
=====================================================================
NEXUS QUANTUM // Pytest Shared Fixtures (conftest.py)
=====================================================================
File:    tests/conftest.py

STRICTLY ADDITIVE — this file only ADDS helpers. It never:
    - overrides existing fixtures in test files,
    - changes the working directory,
    - auto-adds markers,
    - modifies sys.argv,
    - alters logging handlers outside a controlled scope.

Pytest gives LOCAL fixtures priority over conftest ones, so any test
that already defines `temp_dir`, `create_test_zip`, `run_main`, etc.
keeps its own version untouched.

Provides (all optional — use only what you need):
    • Path bootstrap (so `from shared import ...` works)
    • Env values:  pillow_available, is_windows, is_posix, project_root
    • Logging reset (autouse, safe)
    • Directories: temp_dir, extract_dir, output_dir
    • ZIP factories: make_zip, create_test_zip, create_image_zip
    • Image factories: make_real_image, make_test_image
    • PDF helpers: assert_valid_pdf, count_pdf_pages
    • CLI helpers: run_main, run_main_with_argv
    • Parity helper: node_available
=====================================================================
"""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple, Union

import pytest

# =====================================================================
// § 01 — PATH BOOTSTRAP (idempotent, harmless if already on path)
// =====================================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# =====================================================================
// § 02 — ENVIRONMENT CONSTANTS (module-level, read-only)
// =====================================================================

IS_WINDOWS = os.name == "nt"
IS_POSIX = not IS_WINDOWS

try:
    from PIL import Image  # type: ignore
    _PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    _PILLOW_AVAILABLE = False


# =====================================================================
// § 03 — AUTouse FIXTURE (safe)
// =====================================================================
# We ONLY reset the root logger. We do NOT touch cwd, argv, or env vars.


@pytest.fixture(autouse=True)
def reset_root_logger():
    """
    Reset the root logger around each test.

    Safe and additive: preserves the caller's handlers/level across
    the test, and only clears them for the duration. If a test file
    does not touch logging, this fixture has no visible effect.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level

    root.handlers = []
    root.setLevel(logging.NOTSET)

    yield

    root.handlers = saved_handlers
    root.setLevel(saved_level)


# =====================================================================
// § 04 — ENVIRONMENT VALUE FIXTURES (read-only)
// =====================================================================


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the project root."""
    return _PROJECT_ROOT


@pytest.fixture(scope="session")
def pillow_available() -> bool:
    """True if Pillow is importable in the current environment."""
    return _PILLOW_AVAILABLE


@pytest.fixture(scope="session")
def is_windows() -> bool:
    """True if running on Windows."""
    return IS_WINDOWS


@pytest.fixture(scope="session")
def is_posix() -> bool:
    """True if running on POSIX (Linux / macOS)."""
    return IS_POSIX


# =====================================================================
// § 05 — DIRECTORY FIXTURES
// =====================================================================
# NOTE: If a test file already defines `temp_dir`, pytest uses the
# local one. These are pure fallbacks.


@pytest.fixture
def temp_dir() -> Path:
    """Fresh temporary directory with explicit cleanup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def extract_dir(temp_dir: Path) -> Path:
    """Pre-created extraction directory inside `temp_dir`."""
    d = temp_dir / "extract"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def output_dir(temp_dir: Path) -> Path:
    """Pre-created output directory inside `temp_dir`."""
    d = temp_dir / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


# =====================================================================
// § 06 — ZIP FACTORY FIXTURES
// =====================================================================


@pytest.fixture
def make_zip():
    """
    Factory: build a ZIP from ``{name: bytes}``.

        make_zip(path, {"a.jpg": b"..."}) -> Path
    """
    def _make(zip_path, entries: Dict[str, bytes]) -> Path:
        zip_path = Path(zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, data in entries.items():
                zf.writestr(name, data)
        return zip_path
    return _make


@pytest.fixture
def create_test_zip():
    """
    Factory: build a ZIP from a dict OR a list of filenames.

        create_test_zip(path, ["a.jpg", "b.png"])   # fake bytes
        create_test_zip(path, {"a.jpg": b"..."})    # custom bytes
    """
    def _create(zip_path, files) -> Path:
        zip_path = Path(zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if isinstance(files, dict):
                for name, content in files.items():
                    zf.writestr(name, content)
            else:
                for name in files:
                    zf.writestr(name, f"fake image content:{name}".encode())
        return zip_path
    return _create


@pytest.fixture
def create_image_zip(pillow_available: bool):
    """
    Factory: build a ZIP containing real Pillow images.

        create_image_zip(path, [
            "cover.jpg",                                 # RGB 100x100 red
            ("p.png", "RGBA", (50, 50), (0, 255, 0, 128)),
            ("p.gif", "P",    (50, 50), None),
        ]) -> Path
    """
    if not pillow_available:
        pytest.skip("Pillow not available")

    def _build(mode, size, color):
        if mode == "P":
            img = Image.new("P", size)
            img.putpalette([i % 256 for i in range(768)])
            return img
        if mode == "LA":
            return Image.new("LA", size, (128, 255) if color is None else color)
        if mode == "CMYK":
            return Image.new("CMYK", size, (0, 100, 100, 0))
        if mode == "RGBA":
            return Image.new("RGBA", size, color or (0, 255, 0, 128))
        return Image.new(mode, size, color if color is not None else (255, 0, 0))

    def _encode(img, filename):
        name = filename.lower()
        buf = io.BytesIO()
        if name.endswith(".png"):
            img.save(buf, "PNG")
        elif name.endswith(".gif"):
            if img.mode not in ("P", "L", "RGB"):
                img = img.convert("RGB")
            img.save(buf, "GIF")
        elif name.endswith(".bmp"):
            img.save(buf, "BMP")
        elif name.endswith(".webp"):
            img.save(buf, "WEBP")
        else:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(buf, "JPEG")
        return buf.getvalue()

    def _create(zip_path, images_config) -> Path:
        zip_path = Path(zip_path)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for cfg in images_config:
                if isinstance(cfg, str):
                    name, mode, size, color = cfg, "RGB", (100, 100), (255, 0, 0)
                else:
                    name, mode, size, color = cfg
                img = _build(mode, size, color)
                zf.writestr(name, _encode(img, name))
        return zip_path
    return _create


# =====================================================================
// § 07 — IMAGE FACTORY FIXTURES
// =====================================================================


@pytest.fixture
def make_real_image(pillow_available: bool):
    """
    Factory: write a single Pillow image to disk.

        make_real_image(path, mode="RGB", size=(50,50), color=(255,0,0))
    """
    if not pillow_available:
        pytest.skip("Pillow not available")

    def _make(path, mode="RGB", size=(50, 50), color=(255, 0, 0)) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode == "P":
            img = Image.new("P", size)
            img.putpalette([i % 256 for i in range(768)])
        elif mode == "LA":
            img = Image.new("LA", size, (128, 255))
        elif mode == "CMYK":
            img = Image.new("CMYK", size, (0, 100, 100, 0))
        else:
            img = Image.new(mode, size, color)
        img.save(path)
        return path
    return _make


@pytest.fixture
def make_test_image(make_real_image):
    """Alias with the historical signature used in existing tests."""
    def _make(path, mode="RGB", size=(100, 100), color=(255, 0, 0)):
        return make_real_image(path, mode=mode, size=size, color=color)
    return _make


# =====================================================================
// § 08 — PDF ASSERTION HELPERS
// =====================================================================


@pytest.fixture(scope="session")
def assert_valid_pdf():
    """
    Callable: asserts a file is a well-formed PDF.

        assert_valid_pdf(path)  # raises AssertionError on failure
    """
    def _assert(path) -> None:
        p = Path(path)
        assert p.exists(), f"PDF not found: {p}"
        assert p.stat().st_size > 0, f"PDF is empty: {p}"
        with open(p, "rb") as fh:
            header = fh.read(5)
        assert header.startswith(b"%PDF"), f"Not a PDF: {p} (header={header!r})"
    return _assert


@pytest.fixture(scope="session")
def count_pdf_pages():
    """
    Callable: counts pages by scanning raw PDF bytes.

        count_pdf_pages(path) -> int
    """
    _re = re.compile(rb"/Type\s*/Page(?![s])")
    def _count(path) -> int:
        return len(_re.findall(Path(path).read_bytes()))
    return _count


# =====================================================================
// § 09 — CLI HELPERS
// =====================================================================


@pytest.fixture
def run_main():
    """
    Callable: run the CLI main() and return the exit code.

        rc = run_main("file.zip", "--quiet")
        assert rc == 0
    """
    def _run(*args: str) -> int:
        from python.zipped_imgs_to_pdf import main
        return main(list(args))
    return _run


@pytest.fixture
def run_main_with_argv(monkeypatch):
    """
    Callable: run main() with a mocked sys.argv (legacy pattern).

        rc = run_main_with_argv(["prog.py", "file.zip", "--quiet"])
    """
    def _run(argv: List[str]) -> int:
        from python.zipped_imgs_to_pdf import main
        monkeypatch.setattr(sys, "argv", list(argv))
        return main()
    return _run


# =====================================================================
// § 10 — CROSS-RUNTIME PARITY
// =====================================================================


@pytest.fixture(scope="session")
def node_available() -> bool:
    """True if the `node` binary is on PATH."""
    return shutil.which("node") is not None


@pytest.fixture
def run_node_sorting_logic(node_available):
    """
    Callable: run a method from shared/sorting-logic.js via Node.

        out = run_node_sorting_logic("sortImages", [["p_10.jpg","p_1.jpg"], True, "!"])
    """
    if not node_available:
        pytest.skip("node binary not available")

    import json
    import subprocess

    script_path = _PROJECT_ROOT / "shared" / "sorting-logic.js"

    def _run(method: str, args: List) -> object:
        js = (
            f"const m = require({json.dumps(str(script_path))});"
            f"const out = m.{method}.apply(null, {json.dumps(args)});"
            f"process.stdout.write(JSON.stringify(out));"
        )
        proc = subprocess.run(
            ["node", "-e", js],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            pytest.fail(
                f"Node failed (rc={proc.returncode}):\n"
                f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
            )
        return json.loads(proc.stdout)

    return _run


# =====================================================================
// § 11 — SAFE HOOKS (registration only)
// =====================================================================


def pytest_configure(config):
    """
    Register the extra markers used by conftest.py fixtures so that
    ``--strict-markers`` never fails. Idempotent — safe to call even
    if pytest.ini already registers them.
    """
    for line in (
        "requires_pillow: test requires Pillow to be installed",
        "requires_no_pillow: test requires Pillow to be ABSENT",
        "posix_only: test runs only on POSIX (Linux/macOS)",
        "windows_only: test runs only on Windows",
        "parity: test verifies JS <-> Python behavior parity",
    ):
        config.addinivalue_line("markers", line)
