"""
Font discovery utilities shared across the Fyona backend.

This module scans common font directories (system fonts plus the
`static/fonts` folder used for manually installed faces) and exposes a
registry so the API, PDF exporter, and raster renderer can resolve font
IDs into actual files on disk.
"""

from __future__ import annotations

import functools
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

BASE_DIR = Path(__file__).resolve().parent
MANUAL_FONT_DIR = (BASE_DIR / "static" / "fonts").resolve()
FONT_EXTENSIONS = {".ttf", ".otf"}
SEARCH_DIRECTORIES: List[Path] = [
    MANUAL_FONT_DIR,
    Path("/System/Library/Fonts/Supplemental"),
    Path("/System/Library/Fonts"),
    Path("/Library/Fonts"),
    Path("/usr/share/fonts"),
    Path("/usr/share/fonts/truetype"),
    Path("/usr/share/fonts/opentype"),
    Path("/usr/local/share/fonts"),
]


@dataclass(frozen=True)
class FontInfo:
    id: str
    name: str
    path: Path
    category: str  # "manual" (custom) or "system"
    slug: str


_FONT_CACHE: Dict[str, FontInfo] = {}
_FONT_SLUG_CACHE: Dict[str, str] = {}
_CACHE_LOCK = threading.Lock()


def list_fonts() -> List[FontInfo]:
    """Return all discovered fonts sorted by display name."""
    registry = _ensure_registry()
    return sorted(registry.values(), key=lambda info: info.name.lower())


def get_font(font_id: str) -> Optional[FontInfo]:
    """Resolve an exact font ID."""
    if not font_id:
        return None
    registry = _ensure_registry()
    return registry.get(font_id)


def find_font(value: Optional[str]) -> Optional[FontInfo]:
    """Resolve a font by ID or slugified name."""
    if not value:
        return None
    registry = _ensure_registry()
    direct = registry.get(value)
    if direct:
        return direct
    slug = _slugify(value)
    font_id = _FONT_SLUG_CACHE.get(slug)
    if font_id:
        return registry.get(font_id)
    return None


def refresh_fonts() -> None:
    """Force a rescan of the filesystem."""
    with _CACHE_LOCK:
        _FONT_CACHE.clear()
        _FONT_SLUG_CACHE.clear()
        _scan_font_directories()


def _ensure_registry() -> Dict[str, FontInfo]:
    if _FONT_CACHE:
        return _FONT_CACHE
    with _CACHE_LOCK:
        if not _FONT_CACHE:
            _scan_font_directories()
    return _FONT_CACHE


def _scan_font_directories() -> None:
    for directory in SEARCH_DIRECTORIES:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.suffix.lower() not in FONT_EXTENSIONS:
                continue
            try:
                resolved = path.resolve()
            except Exception:
                continue
            name = _derive_display_name(resolved)
            slug = _slugify(name)
            if not slug:
                continue
            font_id = _deduplicate_id(slug)
            category = "manual" if _is_relative_to(resolved, MANUAL_FONT_DIR) else "system"
            info = FontInfo(id=font_id, name=name, path=resolved, category=category, slug=slug)
            _FONT_CACHE[font_id] = info
            _FONT_SLUG_CACHE.setdefault(slug, font_id)


def _deduplicate_id(base_slug: str) -> str:
    candidate = base_slug
    counter = 2
    while candidate in _FONT_CACHE:
        candidate = f"{base_slug}-{counter}"
        counter += 1
    return candidate


def _derive_display_name(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    if stem:
        return re.sub(r"\s+", " ", stem).title()
    return "Untitled Font"


def _slugify(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "-", value.lower()).strip("-")


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False
