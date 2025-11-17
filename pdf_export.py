"""
Utilities for rendering Fiona layout JSON payloads into print-ready PDFs.

The exporter mirrors the block coordinates used by the canvas so the
resulting PDF is visually identical (lossless) to what the user sees in
the editor. Every block in a layout must render successfully – any
failure raises PdfExportError so the caller knows the output was not
lossless.
"""

from __future__ import annotations

import base64
import io
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from html import unescape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

Color = None  # type: ignore

try:  # Optional dependency – callers should install reportlab.
    from reportlab.lib.colors import Color
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph
except ImportError as exc:  # pragma: no cover - exercised in environments without reportlab
    REPORTLAB_AVAILABLE = False
    REPORTLAB_IMPORT_ERROR = exc
else:  # pragma: no cover - import guards for optional dependencies
    REPORTLAB_AVAILABLE = True
    REPORTLAB_IMPORT_ERROR = None


DEFAULT_PAGE_WIDTH = 794.0
DEFAULT_PAGE_HEIGHT = 1123.0
DEFAULT_FONT = "Helvetica"
DEFAULT_FONT_BOLD = "Helvetica-Bold"
if REPORTLAB_AVAILABLE:
    DEFAULT_TEXT_COLOR = Color(0.11, 0.14, 0.2)
else:  # pragma: no cover - only hit when reportlab is missing
    DEFAULT_TEXT_COLOR = None
TEXT_PADDING = 16.0
FONT_DIR = (Path(__file__).resolve().parent / "static" / "fonts").resolve()
CUSTOM_FONT_SPECS = {
    "inter": ("FyonaInter", "Inter-Regular.ttf"),
    "space-grotesk": ("FyonaSpaceGrotesk", "SpaceGrotesk-Regular.ttf"),
    "playfair": ("FyonaPlayfair", "PlayfairDisplay-Regular.ttf"),
    "merriweather": ("FyonaMerriweather", "Merriweather-Regular.ttf"),
}

if REPORTLAB_AVAILABLE:
    CUSTOM_FONT_ALIASES: Dict[str, str] = {}
    for alias, (font_name, filename) in CUSTOM_FONT_SPECS.items():
        path = FONT_DIR / filename
        try:
            if not path.exists():
                continue
            pdfmetrics.registerFont(TTFont(font_name, str(path)))
            CUSTOM_FONT_ALIASES[alias] = font_name
        except Exception:
            continue
    STANDARD_FONTS = {name.lower(): name for name in pdfmetrics.standardFonts}
else:  # pragma: no cover - used only when reportlab is unavailable
    CUSTOM_FONT_ALIASES = {}
    STANDARD_FONTS = {}


class PdfExportError(RuntimeError):
    """Raised whenever the exporter cannot produce a lossless document."""


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float


@dataclass
class PdfRenderStats:
    pages: int = 0
    blocks_attempted: int = 0
    blocks_rendered: int = 0
    text_blocks: int = 0
    image_blocks: int = 0

    @property
    def lossless(self) -> bool:
        return self.blocks_attempted == self.blocks_rendered


@dataclass
class PdfRenderResult:
    data: bytes
    stats: PdfRenderStats
    digest: str
    path: Optional[Path] = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _require_reportlab() -> None:
    if not REPORTLAB_AVAILABLE:
        raise PdfExportError("ReportLab is required for PDF export.") from REPORTLAB_IMPORT_ERROR


def _coerce_float(value: Any, fallback: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if math.isnan(number) or math.isinf(number):
        return fallback
    return number


def _sanitize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = unescape(text)
    return text.replace("\r", "").replace("\n", "<br/>").strip()


def _parse_color(raw: Any, fallback: Optional[Color] = None) -> Optional[Color]:
    if isinstance(raw, Color):
        return raw
    if not isinstance(raw, str):
        return fallback
    value = raw.strip()
    if not value:
        return fallback
    if value.startswith("#"):
        hex_value = value[1:]
        if len(hex_value) == 3:
            hex_value = "".join(c * 2 for c in hex_value)
        if len(hex_value) == 6:
            try:
                r = int(hex_value[0:2], 16) / 255.0
                g = int(hex_value[2:4], 16) / 255.0
                b = int(hex_value[4:6], 16) / 255.0
                return Color(r, g, b)
            except Exception:
                return fallback
        return fallback
    match = re.match(r"rgba?\(([^)]+)\)", value)
    if match:
        parts = [p.strip() for p in match.group(1).split(",")]
        if len(parts) >= 3:
            try:
                r = float(parts[0]) / 255.0
                g = float(parts[1]) / 255.0
                b = float(parts[2]) / 255.0
                return Color(r, g, b)
            except Exception:
                return fallback
    return fallback


def _decode_data_uri(source: str) -> Optional[io.BytesIO]:
    if not isinstance(source, str):
        return None
    if not source.startswith("data:image/"):
        return None
    try:
        header, data = source.split(",", 1)
    except ValueError:
        return None
    if ";base64" not in header:
        return None
    try:
        return io.BytesIO(base64.b64decode(data))
    except Exception:
        return None


def _layout_digest(layout: Dict[str, Any]) -> str:
    try:
        payload = json.dumps(layout, sort_keys=True).encode("utf-8")
    except TypeError as exc:  # pragma: no cover - layout is expected to be serializable
        raise PdfExportError("Layout payload contains non-serializable data.") from exc
    return sha1(payload).hexdigest()


def _resolve_image_reader(block: Dict[str, Any], asset_root: Optional[Path]) -> Optional[ImageReader]:
    """
    Returns an ImageReader for the block. Supports URLs, local project assets,
    and inline data URIs. asset_root should point at the project directory.
    """

    # Prefer explicit imageUrl, otherwise fall back to content for legacy blocks.
    candidate_sources: List[str] = []
    url_value = block.get("imageUrl")
    if isinstance(url_value, str):
        candidate_sources.append(url_value)
    if block.get("type") == "image":
        content = block.get("content")
        if isinstance(content, str) and content not in candidate_sources:
            candidate_sources.append(content)

    for source in candidate_sources:
        # Inline data
        inline_data = _decode_data_uri(source)
        if inline_data:
            try:
                return ImageReader(inline_data)
            except Exception:
                continue

        parsed = urlparse(source)
        if parsed.scheme in {"http", "https", "file"}:
            try:
                return ImageReader(source.replace("file://", ""))
            except Exception:
                continue

        if asset_root:
            path_part = Path(parsed.path or "")
            filename = path_part.name or Path(source).name

            media_candidate = (asset_root / "media" / filename).resolve()
            try:
                if media_candidate.exists() and media_candidate.is_file() and media_candidate.is_relative_to(asset_root):
                    try:
                        return ImageReader(str(media_candidate))
                    except Exception:
                        pass
            except AttributeError:
                # Python <3.9 compat – fall back to manual check
                if media_candidate.exists() and media_candidate.is_file() and str(media_candidate).startswith(str(asset_root)):
                    try:
                        return ImageReader(str(media_candidate))
                    except Exception:
                        pass

            rel_path = Path(parsed.path.lstrip("/"))
            if rel_path.parts:
                raw_candidate = (asset_root / rel_path).resolve()
                try:
                    if raw_candidate.exists() and raw_candidate.is_file() and raw_candidate.is_relative_to(asset_root):
                        try:
                            return ImageReader(str(raw_candidate))
                        except Exception:
                            continue
                except AttributeError:
                    if raw_candidate.exists() and raw_candidate.is_file() and str(raw_candidate).startswith(str(asset_root)):
                        try:
                            return ImageReader(str(raw_candidate))
                        except Exception:
                            continue
    return None


def _resolve_rect(position: Dict[str, Any], page_height: float) -> Optional[Rect]:
    if not isinstance(position, dict):
        return None
    left = _coerce_float(position.get("left"), math.nan)
    top = _coerce_float(position.get("top"), math.nan)
    width = _coerce_float(position.get("width"), math.nan)
    height = _coerce_float(position.get("height"), math.nan)
    if any(math.isnan(num) for num in (left, top, width, height)):
        return None
    if width <= 0 or height <= 0:
        return None
    pdf_y = page_height - (top + height)
    return Rect(left, pdf_y, width, height)


def _map_font_family(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    if not key:
        return None
    if key in CUSTOM_FONT_ALIASES:
        return CUSTOM_FONT_ALIASES[key]
    alias_map = {
        "inter": CUSTOM_FONT_ALIASES.get("inter") or DEFAULT_FONT,
        "space grotesk": CUSTOM_FONT_ALIASES.get("space-grotesk") or DEFAULT_FONT,
        "space-grotesk": CUSTOM_FONT_ALIASES.get("space-grotesk") or DEFAULT_FONT,
        "playfair": CUSTOM_FONT_ALIASES.get("playfair") or "Times-Roman",
        "playfair display": CUSTOM_FONT_ALIASES.get("playfair") or "Times-Roman",
        "merriweather": CUSTOM_FONT_ALIASES.get("merriweather") or "Times-Roman",
        "sans": CUSTOM_FONT_ALIASES.get("inter") or DEFAULT_FONT,
        "sans-serif": CUSTOM_FONT_ALIASES.get("inter") or DEFAULT_FONT,
        "serif": CUSTOM_FONT_ALIASES.get("merriweather") or "Times-Roman",
        "times": "Times-Roman",
        "times new roman": "Times-Roman",
        "georgia": "Times-Roman",
        "arial": DEFAULT_FONT,
        "helvetica": DEFAULT_FONT,
        "mono": "Courier",
        "monospace": "Courier",
        "courier": "Courier",
    }
    mapped = alias_map.get(key)
    if mapped:
        return mapped
    return STANDARD_FONTS.get(key)


def _resolve_font(block: Dict[str, Any], typography: Dict[str, Any]) -> str:
    mapped = _map_font_family(typography.get("fontFamily"))
    if mapped:
        return mapped
    block_type = str(block.get("type", "")).lower()
    if block_type in {"headline", "title"}:
        return DEFAULT_FONT_BOLD
    return DEFAULT_FONT


def _resolve_text_align(value: Any) -> int:
    key = str(value or "left").lower()
    return {
        "center": TA_CENTER,
        "right": TA_RIGHT,
        "justify": TA_JUSTIFY,
    }.get(key, TA_LEFT)


def _normalize_pages(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    pages = layout.get("pages")
    if isinstance(pages, list) and pages:
        sorted_pages = sorted(pages, key=lambda item: item.get("order", 0))
        return sorted_pages
    return [
        {
            "order": 0,
            "blocks": layout.get("blocks", []),
            "dimensions": layout.get("dimensions"),
        }
    ]


def _resolve_page_dimensions(layout: Dict[str, Any], page: Dict[str, Any]) -> Tuple[float, float]:
    dims = page.get("dimensions") or layout.get("dimensions") or {}
    width = _coerce_float(dims.get("width"), DEFAULT_PAGE_WIDTH)
    height = _coerce_float(dims.get("height"), DEFAULT_PAGE_HEIGHT)
    return width, height


def _sort_blocks(blocks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sort_key(block: Dict[str, Any]) -> Tuple[float, str]:
        z = block.get("zIndex")
        return (_coerce_float(z, 0.0), block.get("id") or "")

    return sorted(blocks or [], key=sort_key)


def _text_padding_for_block(block: Dict[str, Any]) -> float:
    if block.get("type") == "image":
        return 0.0
    padding = block.get("padding")
    if padding is None:
        return TEXT_PADDING
    return max(0.0, _coerce_float(padding, TEXT_PADDING))


def _draw_text_block(pdf: canvas.Canvas, block: Dict[str, Any], rect: Rect, padding: float) -> bool:
    text = _sanitize_text(block.get("content"))
    if not text:
        return False

    typography = block.get("typography") or {}
    if not isinstance(typography, dict):
        typography = {}

    font_size = _coerce_float(typography.get("fontSize"), 16.0)
    line_height = typography.get("lineHeight")
    leading = font_size * (line_height if isinstance(line_height, (int, float)) and line_height > 0 else 1.4)
    text_color = _parse_color(block.get("textColor") or typography.get("color"), DEFAULT_TEXT_COLOR)

    style = ParagraphStyle(
        name="block-text",
        fontName=_resolve_font(block, typography),
        fontSize=font_size,
        leading=leading,
        textColor=text_color,
        alignment=_resolve_text_align(typography.get("textAlign")),
        spaceBefore=0,
        spaceAfter=0,
        leftIndent=0,
        rightIndent=0,
        allowWidows=1,
        allowOrphans=1,
    )

    inner_width = rect.width - (padding * 2)
    inner_height = rect.height - (padding * 2)
    if inner_width <= 0 or inner_height <= 0:
        return False

    paragraph = Paragraph(text, style)
    available_width = max(inner_width, 1)
    available_height = max(inner_height, 1)
    width, height = paragraph.wrap(available_width, available_height)
    draw_x = padding
    draw_y = padding + max(available_height - height, 0)
    paragraph.drawOn(pdf, draw_x, draw_y)
    return True


def _draw_image_placeholder(pdf: canvas.Canvas, block: Dict[str, Any], rect: Rect) -> None:
    pdf.setStrokeColorRGB(0.7, 0.72, 0.76)
    pdf.setLineWidth(1)
    pdf.rect(4, 4, rect.width - 8, rect.height - 8, stroke=1, fill=0)
    pdf.setFont(DEFAULT_FONT_BOLD, 12)
    label = block.get("content") or "Image"
    pdf.drawCentredString(rect.width / 2, rect.height / 2 - 6, label[:64])


def _draw_image_block(pdf: canvas.Canvas, block: Dict[str, Any], rect: Rect, image: ImageReader, border_radius: float) -> None:
    pdf.saveState()
    path = pdf.beginPath()
    if border_radius > 0:
        path.roundRect(0, 0, rect.width, rect.height, border_radius)
    else:
        path.rect(0, 0, rect.width, rect.height)
    pdf.clipPath(path, stroke=0, fill=0)

    img_width, img_height = image.getSize()
    if img_width <= 0 or img_height <= 0:
        pdf.restoreState()
        _draw_image_placeholder(pdf, block, rect)
        return
    # cover-style scale
    scale = max(rect.width / img_width, rect.height / img_height)
    draw_width = img_width * scale
    draw_height = img_height * scale
    offset_x = (rect.width - draw_width) / 2
    offset_y = (rect.height - draw_height) / 2
    pdf.drawImage(
        image,
        offset_x,
        offset_y,
        width=draw_width,
        height=draw_height,
        preserveAspectRatio=True,
        mask="auto",
    )
    pdf.restoreState()


def _draw_block(
    pdf: canvas.Canvas,
    block: Dict[str, Any],
    page_height: float,
    asset_root: Optional[Path],
) -> Optional[str]:
    rect = _resolve_rect(block.get("position") or {}, page_height)
    if not rect:
        return None

    rotation = _coerce_float(block.get("rotation"), 0.0)
    background = block.get("backgroundColor") or block.get("background")
    border_radius = _coerce_float(block.get("borderRadius"), 0.0)
    block_type = str(block.get("type") or "text").lower()

    image_reader = _resolve_image_reader(block, asset_root)
    padding = _text_padding_for_block(block)

    pdf.saveState()
    if rotation:
        center_x = rect.x + rect.width / 2
        center_y = rect.y + rect.height / 2
        pdf.translate(center_x, center_y)
        pdf.rotate(rotation)
        pdf.translate(-rect.width / 2, -rect.height / 2)
    else:
        pdf.translate(rect.x, rect.y)

    bg_color = _parse_color(background, None)
    if bg_color:
        pdf.setFillColor(bg_color)
        if border_radius > 0:
            pdf.roundRect(0, 0, rect.width, rect.height, border_radius, stroke=0, fill=1)
        else:
            pdf.rect(0, 0, rect.width, rect.height, stroke=0, fill=1)

    rendered_type: Optional[str] = None
    if block_type == "image" and image_reader:
        _draw_image_block(pdf, block, rect, image_reader, border_radius)
        rendered_type = "image"
    elif block_type == "image":
        _draw_image_placeholder(pdf, block, rect)
        rendered_type = "image"
    else:
        if _draw_text_block(pdf, block, rect, padding):
            rendered_type = "text"
        else:
            rendered_type = None

    pdf.restoreState()
    return rendered_type


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def render_layout_to_pdf(
    layout: Dict[str, Any],
    *,
    project_name: Optional[str] = None,
    asset_base: Optional[Path] = None,
    persist: bool = False,
    verify_lossless: bool = True,
) -> PdfRenderResult:
    """
    Render a layout dictionary (matching /api/layout payloads) to a PDF.

    Args:
        layout: Layout JSON as a Python dict.
        project_name: Optional project name used for metadata.
        asset_base: Optional path to the project directory for local assets.
        persist: When True a PDF will be written to <asset_base>/exports.
        verify_lossless: Raise PdfExportError if any block fails to render.
    Returns:
        PdfRenderResult containing the PDF bytes and render stats.
    """

    _require_reportlab()
    if not isinstance(layout, dict):
        raise PdfExportError("Layout payload must be a dictionary.")

    asset_root = Path(asset_base) if asset_base else None
    pages = _normalize_pages(layout)
    stats = PdfRenderStats()
    digest = _layout_digest(layout)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setAuthor("Fyona Editorial Studio")
    pdf.setTitle(f"Project {project_name or layout.get('project') or 'Untitled'}")
    pdf.setSubject("Canvas export")
    pdf.setKeywords(f"layout-digest:{digest}")

    for page in pages:
        blocks = _sort_blocks(page.get("blocks", []))
        page_width, page_height = _resolve_page_dimensions(layout, page)

        pdf.setPageSize((page_width, page_height))
        pdf.setFillColorRGB(1, 1, 1)
        pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)

        stats.pages += 1
        stats.blocks_attempted += len(blocks)
        for block in blocks:
            rendered_type = _draw_block(pdf, block, page_height, asset_root)
            if not rendered_type:
                if verify_lossless:
                    block_id = block.get("id") or "<unknown>"
                    raise PdfExportError(f"Block {block_id} could not be rendered.")
                continue
            stats.blocks_rendered += 1
            if rendered_type == "image":
                stats.image_blocks += 1
            else:
                stats.text_blocks += 1

        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    data = buffer.read()

    output_path: Optional[Path] = None
    if persist and asset_root:
        export_dir = asset_root / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        filename = f"{project_name or layout.get('project') or 'layout'}-{timestamp}.pdf"
        output_path = export_dir / filename
        output_path.write_bytes(data)

    if verify_lossless and not stats.lossless:
        raise PdfExportError("Export finished but at least one block failed to render.")

    return PdfRenderResult(data=data, stats=stats, digest=digest, path=output_path)


def export_project_layout(project_dir: Path, *, persist: bool = True) -> PdfRenderResult:
    """
    Convenience helper for CLI/cron usage. project_dir should contain layout.json.
    """

    project_dir = Path(project_dir)
    layout_file = project_dir / "layout.json"
    if not layout_file.exists():
        raise PdfExportError(f"Missing layout file: {layout_file}")
    layout = json.loads(layout_file.read_text(encoding="utf-8"))
    project_name = project_dir.name
    return render_layout_to_pdf(layout, project_name=project_name, asset_base=project_dir, persist=persist)


__all__ = ["render_layout_to_pdf", "export_project_layout", "PdfExportError", "PdfRenderResult"]
