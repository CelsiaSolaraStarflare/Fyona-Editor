"""
Raster rendering utilities for Fiona layouts.

This module converts layout JSON (same format returned by /api/layout) into a
list of Pillow Image objects. The raster output is used for PNG/JPEG exports
and as intermediate assets for Office formats.
"""

from __future__ import annotations

import base64
import io
import math
import re
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps

from fonts import find_font


@dataclass
class RasterPage:
    index: int
    image: Image.Image
    width: int
    height: int


DEFAULT_TEXT_COLOR = (28, 35, 51, 255)
DEFAULT_BACKGROUND = (255, 255, 255, 255)
TEXT_PADDING = 16
DEFAULT_SCALE = 2
FONT_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def rasterize_layout(
    layout: Dict[str, Any],
    *,
    asset_base: Optional[Path] = None,
    scale: int = DEFAULT_SCALE,
) -> List[RasterPage]:
    pages = _normalize_pages(layout)
    asset_root = Path(asset_base) if asset_base else None
    raster_pages: List[RasterPage] = []

    for page in pages:
        page_width, page_height = _resolve_page_dimensions(layout, page)
        pixel_width = max(1, int(page_width * scale))
        pixel_height = max(1, int(page_height * scale))
        canvas = Image.new("RGBA", (pixel_width, pixel_height), DEFAULT_BACKGROUND)
        draw = ImageDraw.Draw(canvas, "RGBA")

        blocks = _sort_blocks(page.get("blocks", []))
        for block in blocks:
            _draw_block(draw, canvas, block, scale, asset_root)

        raster_pages.append(
            RasterPage(
                index=len(raster_pages),
                image=canvas.convert("RGB"),
                width=int(page_width),
                height=int(page_height),
            )
        )
    return raster_pages


# ---------------------------------------------------------------------------
# block rendering helpers
# ---------------------------------------------------------------------------
def _draw_block(draw: ImageDraw.ImageDraw, canvas: Image.Image, block: Dict[str, Any], scale: int, asset_root: Optional[Path]):
    rect = _resolve_rect(block.get("position"), scale)
    if not rect:
        return

    bg_color = _parse_color(block.get("backgroundColor") or block.get("background"), DEFAULT_BACKGROUND)
    border_radius = max(0, int(_coerce_float(block.get("borderRadius"), 12) * scale))
    margins = _resolve_block_margins(block, scale)
    content_rect = _inset_rect(rect, margins)

    if bg_color[3] > 0:
        draw.rounded_rectangle(
            [rect.x, rect.y, rect.x + rect.width, rect.y + rect.height],
            radius=border_radius,
            fill=bg_color,
            outline=None,
        )

    block_type = str(block.get("type") or "text").lower()
    if block_type == "image":
        target_rect = content_rect or rect
        _draw_image_block(canvas, block, target_rect, border_radius, asset_root)
    else:
        if content_rect:
            _draw_text_block(draw, block, content_rect, scale)


def _draw_image_block(canvas: Image.Image, block: Dict[str, Any], rect, border_radius: int, asset_root: Optional[Path]):
    image = _resolve_block_image(block, asset_root)
    if not image:
        return
    target_size = (rect.width, rect.height)
    fitted = ImageOps.fit(image, target_size, method=LANCZOS)
    mask = None
    if border_radius > 0:
        mask = Image.new("L", target_size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, target_size[0], target_size[1]], radius=border_radius, fill=255)

    canvas.paste(fitted, (rect.x, rect.y), mask)


def _draw_text_block(draw: ImageDraw.ImageDraw, block: Dict[str, Any], rect, scale: int):
    content = _sanitize_text(block.get("content", ""))
    if not content:
        return
    typography = block.get("typography") or {}
    inner_width = max(10, rect.width)
    x = rect.x
    y = rect.y

    font_size = max(8, int(_coerce_float(typography.get("fontSize"), 18) * scale))
    font = _resolve_font(typography.get("fontFamily"), font_size)
    line_height_ratio = typography.get("lineHeight")
    line_height = max(font_size + 2, int(font_size * (line_height_ratio if isinstance(line_height_ratio, (int, float)) and line_height_ratio > 0 else 1.35)))
    color = _parse_color(block.get("textColor") or typography.get("color"), DEFAULT_TEXT_COLOR)
    if typography.get("uppercase"):
        content = content.upper()

    lines = _wrap_text(content, font, inner_width)
    for line in lines:
        draw.text((x, y), line, fill=color, font=font)
        y += line_height
        if y > rect.y + rect.height:
            break


# ---------------------------------------------------------------------------
# layout helpers
# ---------------------------------------------------------------------------
def _normalize_pages(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    pages = layout.get("pages")
    if isinstance(pages, list) and pages:
        return sorted(pages, key=lambda page: page.get("order", 0))
    return [
        {
            "order": 0,
            "blocks": layout.get("blocks") or [],
            "dimensions": layout.get("dimensions"),
        }
    ]


def _resolve_page_dimensions(layout: Dict[str, Any], page: Dict[str, Any]) -> Tuple[float, float]:
    dims = page.get("dimensions") or layout.get("dimensions") or {}
    width = _coerce_float(dims.get("width"), 794)
    height = _coerce_float(dims.get("height"), 1123)
    return width, height


def _sort_blocks(blocks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(block):
        z = _coerce_float(block.get("zIndex"), 0)
        return (z, block.get("id") or "")

    return sorted(blocks, key=key)


# ---------------------------------------------------------------------------
# utilities
# ---------------------------------------------------------------------------
def _coerce_float(value, fallback):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _sanitize_text(content: str) -> str:
    text = unescape(str(content))
    text = text.replace("\r", "")
    text = text.replace("<br/>", "\n").replace("<br>", "\n")
    return text.strip()


def _resolve_rect(position: Dict[str, Any], scale: int):
    if not isinstance(position, dict):
        return None
    left = _coerce_float(position.get("left"), math.nan)
    top = _coerce_float(position.get("top"), math.nan)
    width = _coerce_float(position.get("width"), math.nan)
    height = _coerce_float(position.get("height"), math.nan)
    if any(math.isnan(v) for v in (left, top, width, height)):
        return None
    return Rect(int(left * scale), int(top * scale), int(width * scale), int(height * scale))


def _resolve_block_margins(block: Dict[str, Any], scale: int) -> Tuple[int, int, int, int]:
    margin = block.get("margin")
    block_type = str(block.get("type") or "text").lower()
    fallback = 0.0 if block_type == "image" else float(TEXT_PADDING)
    if isinstance(margin, dict):
        values = (
            max(0.0, _coerce_float(margin.get("top"), fallback)),
            max(0.0, _coerce_float(margin.get("right"), fallback)),
            max(0.0, _coerce_float(margin.get("bottom"), fallback)),
            max(0.0, _coerce_float(margin.get("left"), fallback)),
        )
    elif margin is not None:
        uniform = max(0.0, _coerce_float(margin, fallback))
        values = (uniform, uniform, uniform, uniform)
    else:
        values = (fallback, fallback, fallback, fallback)
    return tuple(int(value * scale) for value in values)


def _inset_rect(rect: Rect, margins: Tuple[int, int, int, int]) -> Optional[Rect]:
    top, right, bottom, left = margins
    width = rect.width - left - right
    height = rect.height - top - bottom
    if width <= 0 or height <= 0:
        return None
    return Rect(rect.x + left, rect.y + top, width, height)


@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int


def _parse_color(raw_color, fallback):
    if not raw_color:
        return fallback
    if isinstance(raw_color, tuple) and len(raw_color) in {3, 4}:
        if len(raw_color) == 3:
            return (*raw_color, 255)
        return raw_color
    value = str(raw_color).strip()
    if not value:
        return fallback
    try:
        color = ImageColor.getcolor(value, "RGBA")
        if len(color) == 3:
            color = (*color, 255)
        return color
    except Exception:
        return fallback


def _resolve_font(font_family: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    family_key = (font_family or "default").lower()
    cache_key = (family_key, size)
    if cache_key in FONT_CACHE:
        return FONT_CACHE[cache_key]

    candidates: List[Path] = []
    font_info = find_font(font_family)
    if font_info:
        candidates.append(font_info.path)
    if font_family:
        normalized = re.sub(r"[^0-9a-zA-Z]+", "", font_family)
        if normalized:
            for base in [
                Path("/System/Library/Fonts/Supplemental"),
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path("/usr/share/fonts/truetype"),
                Path("/usr/share/fonts/truetype/dejavu"),
                Path("/usr/share/fonts/truetype/liberation"),
            ]:
                candidates.append(base / f"{normalized}.ttf")
                candidates.append(base / f"{normalized}.otf")
    candidates.extend(Path(path) for path in FONT_CANDIDATES)

    for path in candidates:
        if not path.exists():
            continue
        try:
            font = ImageFont.truetype(str(path), size=size)
            FONT_CACHE[cache_key] = font
            return font
        except Exception:
            continue
    font = ImageFont.load_default()
    FONT_CACHE[cache_key] = font
    return font


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    lines: List[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split()
        current = ""
        for word in words:
            tentative = f"{current} {word}".strip()
            try:
                width = font.getlength(tentative)
            except AttributeError:
                width = font.getsize(tentative)[0]
            if width <= max_width or not current:
                current = tentative
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def _resolve_block_image(block: Dict[str, Any], asset_root: Optional[Path]) -> Optional[Image.Image]:
    sources = []
    url = block.get("imageUrl")
    if isinstance(url, str):
        sources.append(url)
    content = block.get("content")
    if isinstance(content, str) and content not in sources:
        sources.append(content)
    raw = block.get("rawPath")
    if isinstance(raw, str):
        sources.append(raw)

    for source in sources:
        data_stream = _decode_data_uri(source)
        if data_stream:
            try:
                return Image.open(data_stream).convert("RGB")
            except Exception:
                continue

        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"}:
            continue  # remote fetching not supported

        if asset_root:
            filename = Path(parsed.path or source).name
            candidate = asset_root / "media" / filename
            if candidate.exists():
                try:
                    return Image.open(candidate).convert("RGB")
                except Exception:
                    continue
            fallback = asset_root / filename
            if fallback.exists():
                try:
                    return Image.open(fallback).convert("RGB")
                except Exception:
                    continue
    return None


def _decode_data_uri(value: str) -> Optional[io.BytesIO]:
    if not isinstance(value, str):
        return None
    if not value.startswith("data:image/"):
        return None
    try:
        header, data = value.split(",", 1)
    except ValueError:
        return None
    if ";base64" not in header:
        return None
    try:
        return io.BytesIO(base64.b64decode(data))
    except Exception:
        return None


__all__ = ["RasterPage", "rasterize_layout"]
RESAMPLE = getattr(Image, "Resampling", Image)
LANCZOS = getattr(RESAMPLE, "LANCZOS", Image.LANCZOS if hasattr(Image, "LANCZOS") else Image.BICUBIC)
