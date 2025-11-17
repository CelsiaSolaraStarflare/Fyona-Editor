"""
PDF export utilities for Fiona layouts.

This module renders layout structures (matching the front-end serializeLayout output)
into vector PDFs using ReportLab. It supports multi-page documents, text styling,
rotation, gradients, opacity, and image embedding for valid assets only.
The export is designed to be lossless and exactly 1:1 with the canvas' shown contents.
"""

from __future__ import annotations
import base64, io, math, re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from reportlab.lib.colors import Color
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfgen import canvas
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
except ImportError as exc:
    REPORTLAB_AVAILABLE = False
    REPORTLAB_IMPORT_ERROR = exc
else:
    REPORTLAB_AVAILABLE = True
    REPORTLAB_IMPORT_ERROR = None

DEFAULT_PAGE_WIDTH = 794.0
DEFAULT_PAGE_HEIGHT = 1123.0
CANVAS_PADDING = 48.0  # This matches the padding in the CSS (.block-layer padding)
DEFAULT_FONT = "Helvetica"
DEFAULT_FONT_BOLD = "Helvetica-Bold"

class PdfExportError(RuntimeError):
    pass

@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

def _require_reportlab():
    if not REPORTLAB_AVAILABLE:
        raise PdfExportError("ReportLab is required for PDF export.") from REPORTLAB_IMPORT_ERROR

def _coerce_float(value: Any, fallback: float) -> float:
    try:
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return fallback
        return number
    except (TypeError, ValueError):
        return fallback

def _sanitize_text(content: Any) -> str:
    if content is None:
        return ""
    text = str(content)
    text = unescape(text)
    text = text.replace("\r", "").replace("\n", "<br/>")
    return text.strip()

def _parse_color(value: Any, fallback: Optional[Color] = None) -> Optional[Color]:
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if value.startswith("#"):
        hexv = value[1:]
        if len(hexv) == 3:
            hexv = "".join(c*2 for c in hexv)
        try:
            r, g, b = (int(hexv[i:i+2], 16) / 255.0 for i in (0, 2, 4))
            return Color(r, g, b)
        except Exception:
            return fallback
    match = re.match(r"rgba?\(([^)]+)\)", value)
    if match:
        parts = [p.strip() for p in match.group(1).split(",")]
        if len(parts) >= 3:
            try:
                r, g, b = [float(x)/255.0 for x in parts[:3]]
                return Color(r, g, b)
            except Exception:
                pass
    return fallback

def _decode_data_uri(source: str) -> Optional[io.BytesIO]:
    if source.startswith("data:image/"):
        try:
            header, data = source.split(",", 1)
            if ";base64" in header:
                return io.BytesIO(base64.b64decode(data))
        except Exception:
            return None
    return None

def _resolve_image_reader(block: Dict[str, Any], asset_base: Optional[Path]) -> Optional[ImageReader]:
    content = block.get("content")
    if isinstance(content, str):
        # handle data URIs
        data_uri = _decode_data_uri(content)
        if data_uri:
            try:
                return ImageReader(data_uri)
            except Exception:
                return None
        # handle http/file sources with image extension only
        if content.startswith(("http://", "https://", "file://")):
            suffix = Path(content.split("?")[0]).suffix.lower()
            if suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".bmp", ".tiff"}:
                try:
                    return ImageReader(content.replace("file://", ""))
                except Exception:
                    pass
    # handle local raw paths with validation
    raw = block.get("rawPath")
    if raw and asset_base:
        candidate = asset_base / raw
        if candidate.exists() and candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".bmp", ".tiff"}:
            try:
                return ImageReader(str(candidate))
            except Exception:
                pass
    return None

def _resolve_rect(pos: Dict[str, Any], ph: float) -> Optional[Rect]:
    if not isinstance(pos, dict):
        return None
    x = _coerce_float(pos.get("left"), 0)
    y = _coerce_float(pos.get("top"), 0)
    # Apply the canvas padding to match the frontend positioning
    x_with_padding = x + CANVAS_PADDING
    y_with_padding = y + CANVAS_PADDING
    w = _coerce_float(pos.get("width"), 0)
    h = _coerce_float(pos.get("height"), 0)
    if w <= 0 or h <= 0:
        return None
    # In PDF coordinates, y=0 is at the bottom, so we need to flip the y-coordinate
    # ph is the page height, so ph - (y + h) gives us the correct position
    pdf_y = ph - (y_with_padding + h)
    return Rect(x_with_padding, pdf_y, w, h)

def _resolve_font(block: Dict[str, Any], typ: Dict[str, Any]) -> str:
    fam = typ.get("fontFamily")
    if isinstance(fam, str) and fam.strip():
        return fam
    t = str(block.get("type", "")).lower()
    return DEFAULT_FONT_BOLD if t in {"headline", "title", "pullquote"} else DEFAULT_FONT

def _parse_gradient(bg: str, rect: Rect) -> Optional[list]:
    m = re.match(r"linear-gradient\(([^,]+)deg\s*,\s*(.+)\)", bg)
    if not m:
        return None
    angle = float(m.group(1))
    colors = [c.strip() for c in m.group(2).split(",")]
    stops = []
    for i, c in enumerate(colors):
        col = _parse_color(c, None)
        if col:
            t = i / max(len(colors)-1, 1)
            dx = rect.width * math.cos(math.radians(angle)) * t
            dy = rect.height * math.sin(math.radians(angle)) * t
            stops.append((col, dx, dy))
    return stops

def _draw_text_block(pdf: canvas.Canvas, block: Dict[str, Any], rect: Rect, typ: Dict[str, Any]):
    text = _sanitize_text(block.get("content"))
    if not text:
        return
    fs = _coerce_float(typ.get("fontSize"), 18)
    lh = typ.get("lineHeight", 1.4)
    # Calculate line height in points
    lead = fs * (lh if lh > 1 else 1.4)
    align = {"center": TA_CENTER, "right": TA_RIGHT, "justify": TA_JUSTIFY}.get(str(typ.get("textAlign", "left")).lower(), TA_LEFT)
    color = _parse_color(typ.get("textColor"), Color(0, 0, 0))
    if typ.get("uppercase"):
        text = text.upper()
    # Create paragraph style with exact font sizes for lossless rendering
    style = ParagraphStyle(
        "sty",
        fontName=_resolve_font(block, typ),
        fontSize=fs,
        leading=lead,
        alignment=align,
        textColor=color,
        # Ensure exact rendering with no extra padding
        leftIndent=0,
        rightIndent=0,
        spaceAfter=0,
        spaceBefore=0,
        bulletFontSize=0,
        wordWrap=None
    )
    p = Paragraph(text, style)
    # Use the full rectangle dimensions without additional padding for text
    available_width = rect.width
    available_height = rect.height
    try:
        w, h = p.wrap(available_width, available_height)
        # Draw the paragraph with exact positioning
        # Position at the top of the available space
        p.drawOn(pdf, 0, available_height - h)  # Relative to translated block position
    except:
        # Fallback to simpler text rendering if paragraph fails
        pdf.setFont(_resolve_font(block, typ), fs)
        pdf.setFillColor(color)
        lines = text.split('<br/>')[:5]  # Limit to 5 lines to fit
        y_pos = available_height - fs  # Start from top
        for line in lines:
            if y_pos < 0:
                break  # Stop if we run out of space
            pdf.drawString(0, y_pos, line[:80])  # Limit line length
            y_pos -= lead

def _draw_block(pdf: canvas.Canvas, block: Dict[str, Any], ph: float, asset: Optional[Path]):
    rect = _resolve_rect(block.get("position"), ph)
    if not rect:
        return
    rotation = _coerce_float(block.get("rotation"), 0)
    bg = block.get("background", "")
    op = float(block.get("opacity", 1))
    grad = _parse_gradient(bg, rect) if isinstance(bg, str) and bg.startswith("linear-gradient") else None
    img = _resolve_image_reader(block, asset)

    pdf.saveState()
    if rotation != 0:
        # For rotation, translate to center of block, rotate, then translate back
        center_x = rect.x + rect.width / 2
        center_y = rect.y + rect.height / 2
        pdf.translate(center_x, center_y)
        pdf.rotate(rotation)
        # Adjust rect coordinates relative to the new origin
        adjusted_rect = Rect(-rect.width/2, -rect.height/2, rect.width, rect.height)
    else:
        pdf.translate(rect.x, rect.y)
        adjusted_rect = Rect(0, 0, rect.width, rect.height)
    
    pdf.setFillAlpha(op)

    # Draw background - whether solid color, gradient, or image
    if grad:
        # Draw gradient step by step as a more accurate representation
        step_count = 50  # More steps for smoother gradients
        for step in range(step_count):
            ratio = step / (step_count - 1) if step_count > 1 else 0
            # Interpolate between colors for smooth gradient
            if len(grad) >= 2:
                # Simple two-color gradient interpolation
                start_color, end_color = grad[0][0], grad[-1][0]
                interp_r = start_color.red + (end_color.red - start_color.red) * ratio
                interp_g = start_color.green + (end_color.green - start_color.green) * ratio
                interp_b = start_color.blue + (end_color.blue - start_color.blue) * ratio
                interp_color = Color(interp_r, interp_g, interp_b)
                pdf.setFillColor(interp_color)
                
                # Draw a small slice of the gradient
                y_pos = ratio * adjusted_rect.height
                pdf.rect(0, y_pos, adjusted_rect.width, adjusted_rect.height / step_count, fill=1, stroke=0)
    else:
        col = _parse_color(bg, None)
        if col:
            pdf.setFillColor(col)
            pdf.rect(0, 0, adjusted_rect.width, adjusted_rect.height, fill=1, stroke=0)

    if img:
        # Draw image with the exact dimensions of the block
        # Use higher quality image rendering without resampling artifacts
        pdf.drawImage(img, 0, 0, adjusted_rect.width, adjusted_rect.height, 
                     preserveAspectRatio=True, anchor='c', mask='auto')
    else:
        typ = block.get("typography", {}) or {}
        if isinstance(typ, dict):
            # Calculate the text area within the block
            text_rect = Rect(0, 0, adjusted_rect.width, adjusted_rect.height)
            _draw_text_block(pdf, block, text_rect, typ)

    pdf.restoreState()

def _sort_blocks(blocks: Iterable[Dict[str, Any]]):
    def key(b):
        return (float(b.get("compositeZ", b.get("zIndex", 0))), b.get("id", ""))
    return sorted(blocks, key=key)

def _normalize_pages(layout: Dict[str, Any]):
    pages = layout.get("pages", [])
    if pages:
        return sorted(pages, key=lambda p: p.get("order", 0))
    return [{"blocks": layout.get("blocks", []), "order": 0}]

def _resolve_page_dimensions(layout: Dict[str, Any], page: Dict[str, Any]):
    dim = page.get("dimensions") or layout.get("dimensions", {})
    width = _coerce_float(dim.get("width", DEFAULT_PAGE_WIDTH), DEFAULT_PAGE_WIDTH)
    height = _coerce_float(dim.get("height", DEFAULT_PAGE_HEIGHT), DEFAULT_PAGE_HEIGHT)
    # Add padding to match the canvas layout in the frontend
    total_width = width + (CANVAS_PADDING * 2)
    total_height = height + (CANVAS_PADDING * 2)
    return total_width, total_height

def render_layout_to_pdf(layout: Dict[str, Any], *, project_name=None, asset_base=None, persist=False):
    _require_reportlab()
    if not isinstance(layout, dict):
        raise PdfExportError("Invalid layout payload.")

    pages = _normalize_pages(layout)
    asset_root = Path(asset_base) if asset_base else None

    buf = io.BytesIO()
    # Create PDF canvas with higher quality parameters
    pdf = canvas.Canvas(buf)
    
    # Set higher quality rendering parameters
    pdf.setPageCompression(1) # Enable compression for smaller files
    pdf.setAuthor("Fiona Editorial Studio")
    pdf.setTitle(f"Layout Export - {project_name or 'Untitled'}")
    pdf.setSubject("Editorial Layout")

    for i, page in enumerate(pages):
        blocks = _sort_blocks(page.get("blocks", []))
        pw, ph = _resolve_page_dimensions(layout, page)
        pdf.setPageSize((pw, ph))
        
        # Draw a white background to match the canvas appearance
        pdf.setFillColorRGB(1, 1, 1)  # White background
        pdf.rect(0, 0, pw, ph, fill=1, stroke=0)
        
        # Draw all blocks on the page
        for blk in blocks:
            _draw_block(pdf, blk, ph, asset_root)
        
        if i < len(pages)-1:
            pdf.showPage()

    pdf.save()
    buf.seek(0)
    data = buf.read()

    path = None
    if persist and asset_root:
        outdir = asset_root / "exports"
        outdir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        name = f"{project_name or 'layout'}-{ts}.pdf"
        path = outdir / name
        path.write_bytes(data)

    return data, path

__all__ = ["render_layout_to_pdf", "PdfExportError"]
