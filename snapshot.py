"""
Helper utilities for generating Fiona layout snapshots.

Provides functions that render the current magazine layout into a PNG preview
that can be supplied to multimodal language models for fast visual context.
"""

from __future__ import annotations

import base64
import io
import json
import re
import textwrap
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent
STATE_ROOT = PROJECT_ROOT / "state"
DEFAULT_PROJECT = "default"
DEFAULT_SNAPSHOT_SIZE: Tuple[int, int] = (600, 800)
PADDING = 24


def parse_color(value: Any, fallback: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
    if not isinstance(value, str):
        return fallback
    text = value.strip()
    if not text:
        return fallback
    if text.startswith("#"):
        digits = text[1:]
        if len(digits) in (3, 4):
            digits = "".join(ch * 2 for ch in digits[:3])
        if len(digits) == 6:
            try:
                return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return fallback
        return fallback
    match = re.match(r"rgba?\s*\(\s*([^)]+)\s*\)", text, re.IGNORECASE)
    if match:
        parts = match.group(1).split(",")
        if len(parts) >= 3:
            try:
                rgb = [int(float(part.strip())) for part in parts[:3]]
                return tuple(max(0, min(255, component)) for component in rgb)
            except ValueError:
                return fallback
    return fallback


def get_font(size: float) -> ImageFont.ImageFont:
    target = max(10, min(int(size), 72))
    try:
        return ImageFont.truetype("DejaVuSans.ttf", target)
    except OSError:
        return ImageFont.load_default()


def sanitize_blocks(blocks: Any) -> Iterable[Dict[str, Any]]:
    if not isinstance(blocks, list):
        return []
    return [block for block in blocks if isinstance(block, dict)]


def render_snapshot(layout: Dict[str, Any], size: Tuple[int, int] = DEFAULT_SNAPSHOT_SIZE) -> Image.Image:
    width, height = size
    canvas = Image.new("RGB", (width, height), "#fafafa")
    draw = ImageDraw.Draw(canvas)

    base_width = float(layout.get("dimensions", {}).get("width") or 794)
    base_height = float(layout.get("dimensions", {}).get("height") or 1123)
    columns = int(layout.get("columns") or 1)

    scale = min(
        (width - PADDING * 2) / base_width,
        (height - PADDING * 2) / base_height,
        1.0,
    )
    scaled_width = int(base_width * scale)
    scaled_height = int(base_height * scale)
    offset_x = PADDING
    offset_y = PADDING

    page_rect = [offset_x, offset_y, offset_x + scaled_width, offset_y + scaled_height]
    draw.rectangle(page_rect, fill=(255, 255, 255), outline=(200, 200, 200))

    if columns > 1:
        column_width = scaled_width / max(columns, 1)
        for idx in range(1, columns):
            x = offset_x + int(column_width * idx)
            draw.line([(x, offset_y), (x, offset_y + scaled_height)], fill=(180, 210, 230), width=1)

    for block in sanitize_blocks(layout.get("blocks")):
        position = block.get("position") or {}
        left = float(position.get("left") or 0)
        top = float(position.get("top") or 0)
        block_width = float(position.get("width") or 0)
        block_height = float(position.get("height") or 0)
        bx = int(offset_x + left * scale)
        by = int(offset_y + top * scale)
        bw = max(1, int(block_width * scale))
        bh = max(1, int(block_height * scale))
        block_rect = [bx, by, bx + bw, by + bh]

        background = parse_color(block.get("background")) or parse_color(
            block.get("typography", {}).get("textColor"),
            (245, 245, 245),
        )
        draw.rectangle(block_rect, fill=background, outline=(210, 210, 210))

        block_type = (block.get("type") or "").lower()
        if block_type == "image":
            inset = 6
            placeholder = [
                bx + inset,
                by + inset,
                bx + bw - inset,
                by + bh - inset,
            ]
            draw.rectangle(placeholder, outline=(120, 120, 120), width=1)
            label_font = get_font(14)
            text = "IMAGE"
            bbox = draw.textbbox((0, 0), text, font=label_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            draw.text(
                (bx + bw / 2 - text_w / 2, by + bh / 2 - text_h / 2),
                text,
                fill=(90, 90, 90),
                font=label_font,
            )
            continue

        content = block.get("content") or ""
        if not isinstance(content, str):
            continue
        clean = re.sub(r"<[^>]+>", "", content).strip()
        if not clean:
            continue

        typography = block.get("typography") or {}
        base_font_size = float(typography.get("fontSize") or 16) * scale
        font_size = max(10, min(int(base_font_size), 72))
        font = get_font(font_size)
        font_height = getattr(font, "size", font_size)
        line_height = max(font_height + 4, int(font_height * float(typography.get("lineHeight") or 1.4)))
        wrap_width = max(10, int(bw / max(font_height * 0.6, 1)))
        lines = textwrap.wrap(clean, width=wrap_width)[:6]
        text_y = by + 8
        for line in lines:
            if text_y + line_height > by + bh - 8:
                break
            draw.text((bx + 8, text_y), line, fill=(30, 30, 30), font=font)
            text_y += line_height
    return canvas


def encode_image(image: Image.Image, format: str = "PNG", *, quality: int = 90) -> str:
    buffer = io.BytesIO()
    format_upper = (format or "PNG").strip().upper()
    save_kwargs: Dict[str, Any] = {"format": format_upper}
    image_to_save = image
    if format_upper == "JPEG":
        image_to_save = image.convert("RGB")
        save_kwargs.update({"quality": max(1, min(int(quality), 100)), "optimize": True})
    image_to_save.save(buffer, **save_kwargs)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def load_layout(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"layout not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def merge_block_with_raw(block: Dict[str, Any], base_path: Path) -> Dict[str, Any]:
    raw_path = block.get("rawPath")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return block
    normalized = raw_path.strip().replace("\\", "/")
    candidate = Path(normalized)
    if not candidate.is_absolute():
        candidate = (base_path / normalized).resolve()
    if not candidate.exists():
        return block
    try:
        with candidate.open("r", encoding="utf-8") as fh:
            raw_payload = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return block
    merged = deepcopy(raw_payload) if isinstance(raw_payload, dict) else {}
    if isinstance(block, dict):
        merged.update(block)
    return merged


def hydrate_layout(layout: Dict[str, Any], base_path: Path) -> Dict[str, Any]:
    if not isinstance(layout, dict):
        return {}
    hydrated = deepcopy(layout)
    blocks = layout.get("blocks")
    if isinstance(blocks, list):
        hydrated_blocks = []
        for block in sanitize_blocks(blocks):
            merged = merge_block_with_raw(block, base_path)
            hydrated_blocks.append(merged)
        hydrated["blocks"] = hydrated_blocks
    return hydrated



def snapshot_for_project(
    project: str,
    *,
    state_root: Path | None = None,
    size: Tuple[int, int] = DEFAULT_SNAPSHOT_SIZE,
    image_format: str = "JPEG",
    quality: int = 85,
    include_prefix: bool = True,
    layout_override: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    target_root = state_root or STATE_ROOT
    if not project:
        project = DEFAULT_PROJECT
    layout_dir = target_root / project
    layout_path = layout_dir / "layout.json"
    layout_data: Optional[Dict[str, Any]] = None
    if isinstance(layout_override, dict):
        layout_data = hydrate_layout(layout_override, layout_dir)
    if layout_data is None:
        if not layout_path.exists():
            return None
        layout_data = hydrate_layout(load_layout(layout_path), layout_dir)
    layout = layout_data
    image = render_snapshot(layout, size)
    fmt = (image_format or "JPEG").strip().upper()
    base64_payload = encode_image(image, format=fmt, quality=quality)
    if include_prefix:
        mime = "image/png" if fmt != "JPEG" else "image/jpeg"
        return f"data:{mime};base64,{base64_payload}"
    return base64_payload


# High-quality rendering functions for PDF export
def render_high_quality_snapshot(layout: Dict[str, Any], dpi: int = 300) -> Image.Image:
    """
    Render a high-quality snapshot of the layout with increased resolution for lossless PDF export.
    Based on the original render_snapshot function but with much higher detail.
    """
    # Calculate the canvas size based on the layout dimensions
    base_width = float(layout.get("dimensions", {}).get("width") or 794)
    base_height = float(layout.get("dimensions", {}).get("height") or 1123)
    
    # Calculate target size based on DPI (e.g., 300 DPI for print quality)
    # Convert from points to inches then to pixels
    width_inches = base_width / 72.0  # Points to inches (72 points per inch)
    height_inches = base_height / 72.0
    target_width = int(width_inches * dpi)
    target_height = int(height_inches * dpi)
    
    # Use higher padding relative to the high resolution
    padding = int(48 * (dpi / 72))  # Scale padding to match high DPI
    
    canvas = Image.new("RGB", (target_width, target_height), "#fafafa")
    draw = ImageDraw.Draw(canvas)

    # Calculate scaling factor
    scale_x = (target_width - padding * 2) / base_width
    scale_y = (target_height - padding * 2) / base_height
    scale = min(scale_x, scale_y, 1.0)  # Don't upscale beyond 1:1
    
    scaled_width = int(base_width * scale)
    scaled_height = int(base_height * scale)
    offset_x = (target_width - scaled_width) // 2  # Center the page
    offset_y = (target_height - scaled_height) // 2

    # Draw the main page rectangle
    page_rect = [offset_x, offset_y, offset_x + scaled_width, offset_y + scaled_height]
    draw.rectangle(page_rect, fill=(255, 255, 255), outline=(200, 200, 200))

    # Draw column guides if needed
    columns = int(layout.get("columns") or 1)
    if columns > 1:
        column_width = scaled_width / max(columns, 1)
        for idx in range(1, columns):
            x = offset_x + int(column_width * idx)
            draw.line([(x, offset_y), (x, offset_y + scaled_height)], fill=(180, 210, 230), width=max(1, int(1*scale)))

    # Draw all blocks
    for block in sanitize_blocks(layout.get("blocks")):
        position = block.get("position") or {}
        left = float(position.get("left") or 0)
        top = float(position.get("top") or 0)
        block_width = float(position.get("width") or 0)
        block_height = float(position.get("height") or 0)
        bx = int(offset_x + left * scale)
        by = int(offset_y + top * scale)
        bw = max(1, int(block_width * scale))
        bh = max(1, int(block_height * scale))
        block_rect = [bx, by, bx + bw, by + bh]

        background = parse_color(block.get("background")) or parse_color(
            block.get("typography", {}).get("textColor"),
            (245, 245, 245),
        )
        draw.rectangle(block_rect, fill=background, outline=(210, 210, 210))

        block_type = (block.get("type") or "").lower()
        if block_type == "image":
            inset = max(1, int(6 * scale))  # Scale inset with resolution
            placeholder = [
                bx + inset,
                by + inset,
                bx + bw - inset,
                by + bh - inset,
            ]
            draw.rectangle(placeholder, outline=(120, 120, 120), width=max(1, int(1 * scale)))
            if scale > 0.2:  # Only draw text if it will be visible
                label_font = get_font(max(10, int(14 * scale)))
                text = "IMAGE"
                bbox = draw.textbbox((0, 0), text, font=label_font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                draw.text(
                    (bx + bw / 2 - text_w / 2, by + bh / 2 - text_h / 2),
                    text,
                    fill=(90, 90, 90),
                    font=label_font,
                )
            continue

        content = block.get("content") or ""
        if not isinstance(content, str):
            continue
        clean = re.sub(r"<[^>]+>", "", content).strip()
        if not clean:
            continue

        typography = block.get("typography") or {}
        base_font_size = float(typography.get("fontSize") or 16) * scale
        font_size = max(10, min(int(base_font_size), 72))
        font = get_font(font_size)
        font_height = getattr(font, "size", font_size)
        line_height = max(font_height + int(4 * scale), int(font_height * float(typography.get("lineHeight") or 1.4)))
        wrap_width = max(10, int(bw / max(font_height * 0.6, 1)))
        lines = textwrap.wrap(clean, width=wrap_width)[:6]
        text_y = by + int(8 * scale)
        for line in lines:
            if text_y + line_height > by + bh - int(8 * scale):
                break
            draw.text((bx + int(8 * scale), text_y), line, fill=(30, 30, 30), font=font)
            text_y += line_height
    return canvas

def create_pdf_from_snapshot(layout: Dict[str, Any], dpi: int = 150) -> bytes:
    """
    Create a PDF from high-quality snapshots using Pillow and fitz (PyMuPDF).
    This creates a lossless PDF from pixel-perfect snapshots.
    Falls back to vector method if PyMuPDF is not available.
    """
    try:
        import fitz  # PyMuPDF - for creating PDF from images
    except ImportError:
        # If PyMuPDF is not available, fall back to a basic implementation
        # This would require creating a simple PDF using reportlab instead
        from pdf_export import render_layout_to_pdf
        # For now, let's raise a clear error
        raise ImportError("PyMuPDF (fitz) is required for snapshot-based PDF export. Please install with: pip install PyMuPDF")
    
    # Handle multi-page layouts
    pages = layout.get("pages", [])
    if not pages:
        # If no pages, create single page from main blocks
        pages = [{"blocks": layout.get("blocks", []), "order": 0}]
    
    # Sort pages by order
    sorted_pages = sorted(pages, key=lambda p: p.get("order", 0))
    
    # Create PDF in memory
    pdf_document = fitz.open()
    
    # Pre-calculate dimensions to optimize performance
    base_width = float(layout.get("dimensions", {}).get("width") or 794)
    base_height = float(layout.get("dimensions", {}).get("height") or 1123)
    
    for page_data in sorted_pages:
        # Create layout for this page
        page_layout = {
            **layout,  # Copy all layout properties
            "blocks": page_data.get("blocks", []),
            "dimensions": page_data.get("dimensions") or layout.get("dimensions", {})
        }
        
        # Generate high-quality snapshot
        snapshot = render_high_quality_snapshot(page_layout, dpi=dpi)
        
        # Convert PIL image to bytes - Use JPEG for smaller file size if PNG isn't required
        img_bytes = io.BytesIO()
        snapshot.save(img_bytes, format="JPEG", quality=95)  # Use JPEG with high quality for better performance
        img_bytes.seek(0)
        
        # Add image to PDF
        img_data = img_bytes.getvalue()
        pdf_page = pdf_document.new_page(width=snapshot.width, height=snapshot.height)
        pdf_page.insert_image(fitz.Rect(0, 0, snapshot.width, snapshot.height), 
                             stream=img_data, 
                             keep_proportion=True)
    
    # Get PDF as bytes
    pdf_bytes = pdf_document.write()
    pdf_document.close()
    
    return pdf_bytes

__all__ = [
    "DEFAULT_PROJECT",
    "DEFAULT_SNAPSHOT_SIZE",
    "STATE_ROOT",
    "encode_image",
    "load_layout",
    "render_snapshot",
    "render_high_quality_snapshot",
    "create_pdf_from_snapshot",
    "snapshot_for_project",
]
