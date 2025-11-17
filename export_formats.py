"""
High-level export helpers that convert layout payloads into various formats.

PDF output is delegated to pdf_export.render_layout_to_pdf. Raster formats
use raster_export.rasterize_layout to draw the canvas into Pillow images,
which are then encoded as PNG/JPEG or embedded into DOCX/PPTX containers.
"""

from __future__ import annotations

import base64
import io
import math
import re
import zipfile
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from PIL import Image

from fonts import find_font
from pdf_export import PdfExportError, PdfRenderResult, PdfRenderStats, render_layout_to_pdf
from raster_export import RasterPage, rasterize_layout

try:  # Optional dependency for Word exports
    from docx import Document  # type: ignore
    from docx.enum.section import WD_SECTION  # type: ignore
    from docx.shared import Inches, Pt, RGBColor  # type: ignore
    from docx.oxml import OxmlElement  # type: ignore
    from docx.oxml.ns import qn  # type: ignore
except ImportError as exc:  # pragma: no cover
    DOCX_AVAILABLE = False
    DOCX_IMPORT_ERROR = exc
else:  # pragma: no cover
    DOCX_AVAILABLE = True
    DOCX_IMPORT_ERROR = None

try:  # Optional dependency for PowerPoint exports
    from pptx import Presentation  # type: ignore
except ImportError as exc:  # pragma: no cover
    PPTX_AVAILABLE = False
    PPTX_IMPORT_ERROR = exc
else:  # pragma: no cover
    PPTX_AVAILABLE = True
    PPTX_IMPORT_ERROR = None


class ExportFormatError(PdfExportError):
    """Raised when a requested export format cannot be produced."""


@dataclass
class ExportPayload:
    data: bytes
    mimetype: str
    filename: str
    digest: str
    stats: PdfRenderStats
    meta: Dict[str, str]


IMAGE_FORMATS = {"png", "jpeg", "jpg"}
DOC_FORMATS = {"doc", "docx", "word"}
PPT_FORMATS = {"ppt", "pptx", "powerpoint"}
FONT_NAME_ALIASES = {
    "inter": "Inter",
    "space-grotesk": "Space Grotesk",
    "space grotesk": "Space Grotesk",
    "playfair": "Playfair Display",
    "playfair display": "Playfair Display",
    "merriweather": "Merriweather",
    "sans": "Inter",
    "sans-serif": "Inter",
    "serif": "Merriweather",
    "times": "Times New Roman",
    "times new roman": "Times New Roman",
    "georgia": "Georgia",
    "arial": "Arial",
    "helvetica": "Helvetica",
    "mono": "Space Grotesk",
    "monospace": "Space Grotesk",
    "courier": "Courier New",
}

DOCX_IMAGE_SIGNATURES = [
    (0, b"\x89PNG\r\n\x1a\n"),
    (6, b"JFIF"),
    (6, b"Exif"),
    (0, b"GIF87a"),
    (0, b"GIF89a"),
    (0, b"MM\x00*"),
    (0, b"II*\x00"),
    (0, b"BM"),
]


def export_layout(
    layout: Dict[str, Any],
    *,
    project_name: Optional[str] = None,
    asset_base: Optional[Path] = None,
    export_format: str = "pdf",
) -> ExportPayload:
    fmt = (export_format or "pdf").lower()
    pdf_result = render_layout_to_pdf(layout, project_name=project_name, asset_base=asset_base, persist=False, verify_lossless=True)

    if fmt == "pdf":
        return ExportPayload(
            data=pdf_result.data,
            mimetype="application/pdf",
            filename=_build_filename(project_name, "pdf"),
            digest=pdf_result.digest,
            stats=pdf_result.stats,
            meta={"format": "pdf"},
        )

    rasters: Optional[List[RasterPage]] = None

    if fmt in IMAGE_FORMATS:
        rasters = _ensure_rasters(rasters, layout, asset_base)
        return _package_images(rasters, fmt, project_name, pdf_result)

    if fmt in DOC_FORMATS:
        data = _layout_to_docx(layout, asset_base)
        return ExportPayload(
            data=data,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=_build_filename(project_name, "docx"),
            digest=pdf_result.digest,
            stats=pdf_result.stats,
            meta={"format": "docx"},
        )

    if fmt in PPT_FORMATS:
        rasters = _ensure_rasters(rasters, layout, asset_base)
        data = _rasters_to_pptx(rasters)
        return ExportPayload(
            data=data,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=_build_filename(project_name, "pptx"),
            digest=pdf_result.digest,
            stats=pdf_result.stats,
            meta={"format": "pptx"},
        )

    raise ExportFormatError(f"Unsupported export format '{fmt}'.")


def _build_filename(project: Optional[str], extension: str) -> str:
    base = project or "layout"
    return f"{base}-layout.{extension}"


def _ensure_rasters(
    cached: Optional[List[RasterPage]],
    layout: Dict[str, Any],
    asset_base: Optional[Path],
) -> List[RasterPage]:
    if cached is not None:
        return cached
    return rasterize_layout(layout, asset_base=asset_base)


def _package_images(
    rasters: List[RasterPage],
    fmt: str,
    project_name: Optional[str],
    pdf_result: PdfRenderResult,
) -> ExportPayload:
    ext = "png" if fmt == "png" else "jpg"
    mimetype = "image/png" if fmt == "png" else "image/jpeg"

    if len(rasters) == 1:
        binary = _encode_raster(rasters[0], fmt)
        return ExportPayload(
            data=binary,
            mimetype=mimetype,
            filename=_build_filename(project_name, ext),
            digest=pdf_result.digest,
            stats=pdf_result.stats,
            meta={"format": ext},
        )

    archive_name = _build_filename(project_name, f"{ext}-pages")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for page in rasters:
            page_name = f"{(project_name or 'layout')}-page-{page.index + 1:02d}.{ext}"
            bundle.writestr(page_name, _encode_raster(page, fmt))
    buffer.seek(0)
    return ExportPayload(
        data=buffer.read(),
        mimetype="application/zip",
        filename=f"{archive_name}.zip",
        digest=pdf_result.digest,
        stats=pdf_result.stats,
        meta={"format": f"{ext}-zip"},
    )


def _encode_raster(page: RasterPage, fmt: str) -> bytes:
    buffer = io.BytesIO()
    image = page.image.convert("RGB")
    fmt_key = "png" if fmt == "png" else "jpeg"
    if fmt_key == "png":
        image.save(buffer, format="PNG", optimize=True)
    else:
        image.save(buffer, format="JPEG", quality=95, optimize=True)
    buffer.seek(0)
    return buffer.read()


def _require_docx():
    if not DOCX_AVAILABLE:
        raise ExportFormatError("DOCX export requires python-docx.") from DOCX_IMPORT_ERROR


def _require_pptx():
    if not PPTX_AVAILABLE:
        raise ExportFormatError("PowerPoint export requires python-pptx.") from PPTX_IMPORT_ERROR


def _layout_to_docx(layout: Dict[str, Any], asset_base: Optional[Path]) -> bytes:
    _require_docx()
    document = Document()
    asset_root = Path(asset_base) if asset_base else None
    pages = _normalize_docx_pages(layout)
    for page_index, page in enumerate(pages):
        if page_index > 0:
            document.add_page_break()
        page_width = _resolve_docx_page_width(layout, page)
        blocks = _sort_docx_blocks(page.get("blocks", []))
        for block in blocks:
            block_type = str(block.get("type") or "text").lower()
            if block_type == "image":
                if not _add_docx_image(document, block, asset_root, page_width):
                    _add_docx_placeholder(document, block)
            else:
                _add_docx_text(document, block)
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer.read()


def _normalize_docx_pages(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    pages = layout.get("pages")
    if isinstance(pages, list) and pages:
        return sorted(pages, key=lambda item: item.get("order", 0))
    return [
        {
            "order": 0,
            "blocks": layout.get("blocks") or [],
            "dimensions": layout.get("dimensions"),
        }
    ]


def _sort_docx_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sort_key(block: Dict[str, Any]):
        position = block.get("position") or {}
        top = _coerce_float(position.get("top"), 0.0)
        left = _coerce_float(position.get("left"), 0.0)
        z_index = _coerce_float(block.get("zIndex"), 0.0)
        return (top, left, z_index, block.get("id") or "")

    return sorted(blocks or [], key=sort_key)


def _resolve_docx_page_width(layout: Dict[str, Any], page: Dict[str, Any]) -> float:
    dims = page.get("dimensions") or layout.get("dimensions") or {}
    return _coerce_float(dims.get("width"), 794.0)


def _add_docx_text(document: Document, block: Dict[str, Any]) -> None:
    text = _sanitize_docx_text(block.get("content"))
    if not text:
        return
    typography = block.get("typography") or {}
    if not isinstance(typography, dict):
        typography = {}
    if typography.get("uppercase"):
        text = text.upper()

    paragraph = document.add_paragraph()
    alignment = _resolve_docx_alignment(typography.get("textAlign"))
    if alignment is not None:
        paragraph.alignment = alignment

    lines = text.split("\n")
    for index, line in enumerate(lines):
        run = paragraph.add_run(line)
        _apply_font_properties(run.font, typography, block)
        if index < len(lines) - 1:
            run.add_break()


def _apply_font_properties(font, typography: Dict[str, Any], block: Dict[str, Any]) -> None:
    font_family = typography.get("fontFamily")
    resolved_family = _resolve_font_name(font_family)
    if resolved_family:
        font.name = resolved_family

    point_size = _points_from_px(typography.get("fontSize"))
    if point_size:
        font.size = Pt(point_size)

    color_value = block.get("textColor") or typography.get("color")
    rgb_color = _parse_rgb_color(color_value)
    if rgb_color:
        font.color.rgb = rgb_color


def _resolve_font_name(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    if not key:
        return None
    if key in FONT_NAME_ALIASES:
        return FONT_NAME_ALIASES[key]
    return value.strip()


def _add_docx_image(document: Document, block: Dict[str, Any], asset_root: Optional[Path], page_width: float) -> bool:
    stream = _resolve_docx_image_stream(block, asset_root)
    if not stream:
        return False
    try:
        width_inches = _block_width_inches(block, page_width)
        document.add_picture(stream, width=Inches(width_inches))
    finally:
        stream.close()
    caption = block.get("caption")
    if isinstance(caption, str) and caption.strip():
        paragraph = document.add_paragraph()
        run = paragraph.add_run(caption.strip())
        run.italic = True
    return True


def _block_width_inches(block: Dict[str, Any], page_width: float) -> float:
    position = block.get("position") or {}
    block_width = _coerce_float(position.get("width"), page_width)
    page_width_inches = max(_px_to_inches(page_width), 1.0)
    width_inches = max(_px_to_inches(block_width), 0.5)
    return min(width_inches, page_width_inches)


def _add_docx_placeholder(document: Document, block: Dict[str, Any]) -> None:
    label = block.get("content") or block.get("id") or "image"
    paragraph = document.add_paragraph()
    run = paragraph.add_run(f"[Missing image: {label}]")
    run.italic = True


def _resolve_docx_image_stream(block: Dict[str, Any], asset_root: Optional[Path]) -> Optional[io.BytesIO]:
    sources: List[str] = []
    for key in ("imageUrl", "rawPath", "content"):
        value = block.get(key)
        if isinstance(value, str) and value and value not in sources:
            sources.append(value)

    for source in sources:
        inline = _decode_image_data_uri(source)
        if inline:
            stream = _prepare_docx_image_stream(inline)
            if stream:
                return stream

        parsed = urlparse(source)
        if parsed.scheme in {"http", "https"}:
            continue
        if not asset_root:
            continue
        filename = Path(parsed.path or source).name
        for candidate in (asset_root / "media" / filename, asset_root / filename):
            if candidate.exists():
                try:
                    raw_bytes = candidate.read_bytes()
                except Exception:
                    continue
                stream = _prepare_docx_image_stream(raw_bytes)
                if stream:
                    return stream
    return None


def _decode_image_data_uri(value: Any) -> Optional[bytes]:
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
        return base64.b64decode(data)
    except Exception:
        return None


def _prepare_docx_image_stream(raw_bytes: bytes) -> Optional[io.BytesIO]:
    if not raw_bytes:
        return None
    if _is_docx_compatible_image(raw_bytes):
        stream = io.BytesIO(raw_bytes)
        stream.seek(0)
        stream.name = "fyona-image.bin"
        return stream
    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            needs_alpha = "A" in image.getbands()
            converted = image.convert("RGBA" if needs_alpha else "RGB")
            buffer = io.BytesIO()
            converted.save(buffer, format="PNG")
    except Exception:
        return None
    buffer.seek(0)
    buffer.name = "fyona-image.png"
    return buffer


def _is_docx_compatible_image(raw_bytes: bytes) -> bool:
    header = raw_bytes[:32]
    for offset, signature in DOCX_IMAGE_SIGNATURES:
        end = offset + len(signature)
        if len(header) < end:
            continue
        if header[offset:end] == signature:
            return True
    return False


def _sanitize_docx_text(content: Any) -> str:
    if content is None:
        return ""
    text = unescape(str(content))
    text = text.replace("\r", "")
    text = text.replace("<br/>", "\n").replace("<br>", "\n")
    return text.strip()


def _points_from_px(value: Any, fallback: float = 16.0) -> float:
    px = _coerce_float(value, fallback)
    if px <= 0:
        return fallback
    return max(px * 0.75, 8.0)


def _px_to_inches(value: Any) -> float:
    pixels = _coerce_float(value, 0.0)
    if pixels <= 0:
        return 0.0
    return pixels / 96.0


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number


def _resolve_docx_alignment(value: Any):
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    if key == "center":
        return WD_ALIGN_PARAGRAPH.CENTER
    if key == "right":
        return WD_ALIGN_PARAGRAPH.RIGHT
    if key == "justify":
        return WD_ALIGN_PARAGRAPH.JUSTIFY
    if key == "left":
        return WD_ALIGN_PARAGRAPH.LEFT
    return None


def _parse_rgb_color(raw: Any) -> Optional[RGBColor]:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value:
        return None
    if value.startswith("#"):
        hex_value = value[1:]
        if len(hex_value) == 3:
            hex_value = "".join(ch * 2 for ch in hex_value)
        if len(hex_value) == 6:
            try:
                r = int(hex_value[0:2], 16)
                g = int(hex_value[2:4], 16)
                b = int(hex_value[4:6], 16)
                return RGBColor(r, g, b)
            except Exception:
                return None
        return None
    match = re.match(r"rgba?\(([^)]+)\)", value)
    if match:
        parts = [p.strip() for p in match.group(1).split(",")]
        if len(parts) >= 3:
            try:
                r = max(0, min(255, int(float(parts[0]))))
                g = max(0, min(255, int(float(parts[1]))))
                b = max(0, min(255, int(float(parts[2]))))
                return RGBColor(r, g, b)
            except Exception:
                return None
    return None


def _rasters_to_pptx(rasters: List[RasterPage]) -> bytes:
    _require_pptx()
    presentation = Presentation()
    blank_layout = presentation.slide_layouts[6]
    for page in rasters:
        slide = presentation.slides.add_slide(blank_layout)
        stream = io.BytesIO(_encode_raster(page, "png"))
        slide.shapes.add_picture(stream, 0, 0, width=presentation.slide_width, height=presentation.slide_height)
    buffer = io.BytesIO()
    presentation.save(buffer)
    buffer.seek(0)
    return buffer.read()


__all__ = ["ExportFormatError", "ExportPayload", "export_layout"]
