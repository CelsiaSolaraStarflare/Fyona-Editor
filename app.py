import base64
import html
import io
import json
import os
import re
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, TYPE_CHECKING
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory, url_for
from werkzeug.utils import secure_filename

from agent_tools import AgentToolContext, AgentToolError, AgentToolset
from export_formats import ExportFormatError, export_layout
from fonts import get_font, list_fonts
from pdf_export import PdfExportError
from raster_export import rasterize_layout
from terminal import TerminalCommandError, TerminalProcessor

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

app = Flask(__name__, template_folder="templates", static_folder="static")

BASE_DIR = Path(app.root_path)
ENV_FILE = BASE_DIR / ".env"


def _load_env_file() -> None:
    path = ENV_FILE
    if not path.exists():
        return
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_env_file()

PROJECTS_ROOT = BASE_DIR / "projects"
DEFAULT_PROJECT = "default"
ASSET_ROUTE = "serve_project_asset"
CHAT_ATTACHMENT_LIMIT = 6
MAX_AGENT_FILES = 24
MAX_AGENT_BYTES = 8_192
MAX_AGENT_TOOL_CALLS = 0  # zero or negative removes the cap
DEFAULT_AGENT_TOOL_MODE = "unbounded"
AGENT_TOOL_BUDGET_PRESETS = {
    "quick": None,
    "balanced": None,
    "deep": None,
    "unbounded": None,
}
AGENT_TOOL_BUDGET_MIN = 2
AGENT_TOOL_BUDGET_MAX = 64
DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", DEFAULT_DASHSCOPE_BASE_URL)
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
FIONA_AGENT_MODEL = (os.getenv("FIONA_AGENT_MODEL") or "qwen3-vl-plus").strip()
_thinking_flag = os.getenv("FIONA_AGENT_ENABLE_THINKING")
FIONA_AGENT_ENABLE_THINKING = (_thinking_flag or "").strip().lower() in {"1", "true", "yes", "on"}
try:
    FIONA_AGENT_THINKING_BUDGET = int(os.getenv("FIONA_AGENT_THINKING_BUDGET", "81920") or "81920")
except ValueError:
    FIONA_AGENT_THINKING_BUDGET = 81920
MAX_LAYOUT_CONTEXT_CHARS = 18_000
MAX_TREE_CONTEXT_CHARS = 6_000
MAX_FILE_PREVIEW_CHARS = 2_000
MAX_FILE_CONTEXT = 6
DEFAULT_FONT_SIZE_PX = 16
FONT_SIZE_MIN = 8
FONT_SIZE_MAX = 200
MARGIN_MIN = 0
MARGIN_MAX = 480
DEFAULT_BLOCK_MARGIN = {"top": 16, "right": 16, "bottom": 16, "left": 16}
DEFAULT_IMAGE_MARGIN = {"top": 0, "right": 0, "bottom": 0, "left": 0}
DEFAULT_LINE_HEIGHT_RATIO = 1.4
TEXT_CHAR_WIDTH_RATIO = 0.55
LAYOUT_WARNING_LIMIT = 12
AGENT_PROGRESS_TTL_SECONDS = 120
AGENT_SYSTEM_PROMPT = (
    "You are Fyona, an editorial design assistant that helps plan and refine magazine layouts. Use the user's "
    "message plus any attachments, the project directory listing, and the current layout JSON to reason about "
    "grid, typography, and composition. When you propose changes, reference block IDs, page names, or coordinates "
    "so the developer can implement them. If context is missing, ask clarifying questions. Respond in Markdown."
)
_openai_client: Optional["OpenAI"] = None

PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
AGENT_PROGRESS: Dict[str, Dict[str, Any]] = {}
AGENT_PROGRESS_LOCK = threading.Lock()
TOKEN_USAGE_DIR = BASE_DIR / "logs"
TOKEN_USAGE_FILE = TOKEN_USAGE_DIR / "token_usage.json"
TOKEN_USAGE_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_USAGE_LOCK = threading.Lock()
TOKEN_USAGE_STATE: Dict[str, float] = {
    "session_tokens": 0,
    "session_image_bytes": 0,
    "lifetime_tokens": 0,
    "lifetime_image_bytes": 0,
}
DEFAULT_BING_SEARCH_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"
BING_SEARCH_ENDPOINT = os.getenv("BING_SEARCH_ENDPOINT", DEFAULT_BING_SEARCH_ENDPOINT)
BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY")
BING_SEARCH_MARKET = os.getenv("BING_SEARCH_MARKET", "en-US")
DEFAULT_BING_IMAGE_ENDPOINT = "https://api.bing.microsoft.com/v7.0/images/search"
BING_IMAGE_ENDPOINT = os.getenv("BING_IMAGE_ENDPOINT", DEFAULT_BING_IMAGE_ENDPOINT)
BING_HTML_FALLBACK_ALLOWED = (os.getenv("BING_HTML_FALLBACK_ALLOWED") or "true").lower() in {"1", "true", "yes", "on"}

DEFAULT_LAYOUT: Dict[str, Any] = {
    "columns": 3,
    "baseline": 24,
    "gutter": 32,
    "snap": True,
    "zoom": 1.0,
    "orientation": "portrait",
    "format": "A4",
    "dimensions": {"width": 794, "height": 1123},
    "blocks": [],
    "pages": [],
    "layers": [
        {
            "id": "layer-main",
            "name": "Layer 1",
            "order": 0,
        }
    ],
    "activeLayer": "layer-main",
    "activePageId": None,
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def sanitize_project(name: str) -> str:
    text = (name or "").strip().lower()
    if not text:
        return DEFAULT_PROJECT
    text = re.sub(r"[^0-9a-z._-]+", "-", text)
    return text.strip(".-_") or DEFAULT_PROJECT


def project_dir(name: str) -> Path:
    folder = PROJECTS_ROOT / sanitize_project(name)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _project_path(name: str) -> Path:
    return PROJECTS_ROOT / sanitize_project(name)


def _list_project_names() -> List[str]:
    projects = {DEFAULT_PROJECT}
    projects.update({p.name for p in PROJECTS_ROOT.iterdir() if p.is_dir()})
    return sorted(projects)


def layout_path(name: str) -> Path:
    return project_dir(name) / "layout.json"


def media_dir(name: str) -> Path:
    folder = project_dir(name) / "media"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _bing_search_available() -> bool:
    return bool((BING_SEARCH_API_KEY and BING_SEARCH_ENDPOINT) or BING_HTML_FALLBACK_ALLOWED)


def _perform_bing_web_search(query: str, *, count: int = 5) -> List[Dict[str, str]]:
    clean_query = (query or "").strip()
    if not clean_query:
        return []
    safe_count = max(1, min(int(count or 5), 10))
    if BING_SEARCH_API_KEY and BING_SEARCH_ENDPOINT:
        params = {
            "q": clean_query,
            "count": safe_count,
            "mkt": BING_SEARCH_MARKET or "en-US",
            "textDecorations": "false",
            "textFormat": "Raw",
            "safeSearch": "Moderate",
        }
        url = f"{BING_SEARCH_ENDPOINT}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url)
        request.add_header("Ocp-Apim-Subscription-Key", BING_SEARCH_API_KEY or "")
        request.add_header("User-Agent", "FyonaEditor/1.0")
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = response.read().decode("utf-8")
                data = json.loads(payload)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")
            except Exception:  # pragma: no cover - best effort diagnostics
                detail = ""
            message = detail.strip()[:200] or exc.reason
            raise RuntimeError(f"Bing search HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Bing search connection failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Bing search returned invalid JSON: {exc}") from exc
        web_pages = data.get("webPages", {}).get("value", []) or []
        results: List[Dict[str, str]] = []
        for item in web_pages[:safe_count]:
            results.append(
                {
                    "title": item.get("name") or "",
                    "url": item.get("url") or "",
                    "snippet": item.get("snippet") or "",
                }
            )
        return results

    # Fallback: scrape HTML results directly from bing.com when API key is unavailable.
    params = {
        "q": clean_query,
        "mkt": BING_SEARCH_MARKET or "en-US",
        "setlang": "en",
    }
    url = f"https://www.bing.com/search?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "FyonaEditor/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            html_body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # pragma: no cover - network guard
        raise RuntimeError(f"Bing HTML search HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network guard
        raise RuntimeError(f"Bing HTML search failed: {exc.reason}") from exc

    results: List[Dict[str, str]] = []
    pattern = re.compile(r'<li class="b_algo".*?<h2><a href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.S)
    for match in pattern.finditer(html_body):
        href = match.group("href")
        title_html = match.group("title")
        title_text = re.sub("<.*?>", "", title_html or "")
        title = html.unescape(title_text).strip()
        snippet = ""
        snippet_match = re.search(r"<p>(.*?)</p>", html_body[match.start(): match.end()], re.S)
        if snippet_match:
            snippet = html.unescape(re.sub("<.*?>", "", snippet_match.group(1) or "").strip())
        if title or href:
            results.append({"title": title or href, "url": href, "snippet": snippet})
        if len(results) >= safe_count:
            break
    return results


def _perform_bing_image_search(query: str, *, count: int = 6) -> List[Dict[str, Any]]:
    if not _bing_search_available():
        raise RuntimeError("Bing search is not configured on this server.")
    clean_query = (query or "").strip()
    if not clean_query:
        return []
    safe_count = max(1, min(int(count or 6), 10))
    if BING_SEARCH_API_KEY and BING_IMAGE_ENDPOINT:
        params = {
            "q": clean_query,
            "count": safe_count,
            "mkt": BING_SEARCH_MARKET or "en-US",
            "safeSearch": "Moderate",
        }
        url = f"{BING_IMAGE_ENDPOINT}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url)
        request.add_header("Ocp-Apim-Subscription-Key", BING_SEARCH_API_KEY or "")
        request.add_header("User-Agent", "FyonaEditor/1.0")
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = response.read().decode("utf-8")
                data = json.loads(payload)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                detail = ""
            message = detail.strip()[:200] or exc.reason
            raise RuntimeError(f"Bing image search HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Bing image search connection failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Bing image search returned invalid JSON: {exc}") from exc
        entries = data.get("value") or []
        results: List[Dict[str, Any]] = []
        for item in entries[:safe_count]:
            results.append(
                {
                    "title": item.get("name") or "",
                    "url": item.get("contentUrl") or "",
                    "thumbnail": item.get("thumbnailUrl") or "",
                    "width": item.get("width"),
                    "height": item.get("height"),
                }
            )
        return results

    # Fallback HTML scrape for images.
    params = {"q": clean_query, "form": "HDRSC2", "mkt": BING_SEARCH_MARKET or "en-US"}
    url = f"https://www.bing.com/images/search?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "FyonaEditor/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            html_body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # pragma: no cover - network guard
        raise RuntimeError(f"Bing image HTML search HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network guard
        raise RuntimeError(f"Bing image HTML search failed: {exc.reason}") from exc

    # Extract direct image URLs from inline metadata (murl) and thumbnails (turl).
    results: List[Dict[str, Any]] = []
    direct_urls = re.finditer(r'"murl"\s*:\s*"(?P<url>[^"]+)"', html_body)
    thumbs = list(re.finditer(r'"turl"\s*:\s*"(?P<thumb>[^"]+)"', html_body))
    thumbs_iter = iter(thumbs)
    for match in direct_urls:
        image_url = html.unescape(match.group("url"))
        thumb_match = next(thumbs_iter, None)
        thumb_url = html.unescape(thumb_match.group("thumb")) if thumb_match else ""
        if not image_url:
            continue
        results.append({"title": Path(urllib.parse.urlparse(image_url).path).name, "url": image_url, "thumbnail": thumb_url})
        if len(results) >= safe_count:
            break
    return results


def _normalize_tool_budget(raw_limit: Any) -> Optional[int]:
    if raw_limit is None:
        return None
    try:
        value = int(raw_limit)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value < AGENT_TOOL_BUDGET_MIN:
        return AGENT_TOOL_BUDGET_MIN
    if value > AGENT_TOOL_BUDGET_MAX:
        return AGENT_TOOL_BUDGET_MAX
    return value


def _resolve_agent_tool_budget(mode: Optional[str], requested_limit: Any) -> Tuple[str, Optional[int]]:
    raw_mode = mode if isinstance(mode, str) else DEFAULT_AGENT_TOOL_MODE if mode is None else str(mode)
    mode_key = (raw_mode or DEFAULT_AGENT_TOOL_MODE).strip().lower() or DEFAULT_AGENT_TOOL_MODE
    if mode_key not in AGENT_TOOL_BUDGET_PRESETS:
        mode_key = DEFAULT_AGENT_TOOL_MODE
    limit = AGENT_TOOL_BUDGET_PRESETS.get(mode_key)
    if requested_limit is not None:
        normalized = _normalize_tool_budget(requested_limit)
        limit = normalized
    return mode_key, limit


def deep_merge(target: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = value
    return target


def normalize_block(block: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "id": block.get("id") or _generate_block_id(),
        "type": block.get("type") or "text",
        "content": block.get("content") or "",
        "position": {
            "left": int(_coerce_number(block.get("position", {}).get("left"), 0)),
            "top": int(_coerce_number(block.get("position", {}).get("top"), 0)),
            "width": int(_coerce_number(block.get("position", {}).get("width"), 240)),
            "height": int(_coerce_number(block.get("position", {}).get("height"), 120)),
        },
    }

    if "backgroundColor" in block:
        result["backgroundColor"] = block["backgroundColor"]
    if "textColor" in block:
        result["textColor"] = block["textColor"]
    if "borderRadius" in block:
        result["borderRadius"] = block["borderRadius"]
    if "imageUrl" in block:
        result["imageUrl"] = block["imageUrl"]
    typography = block.get("typography")
    if isinstance(typography, dict):
        normalized_typography = dict(typography)
        normalized_typography["fontSize"] = _normalize_font_size(normalized_typography.get("fontSize"))
        result["typography"] = normalized_typography
    margin_source = block.get("margin")
    if margin_source is None and "padding" in block:
        margin_source = block.get("padding")
    result["margin"] = _normalize_block_margin(margin_source, result["type"])

    extra_keys = set(block.keys()) - {
        "id",
        "type",
        "content",
        "position",
        "backgroundColor",
        "textColor",
        "borderRadius",
        "imageUrl",
        "typography",
        "margin",
        "padding",
    }
    for key in extra_keys:
        result[key] = block[key]

    return result


def _coerce_number(value: Any, fallback: float) -> float:
    try:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _default_margin_for_type(block_type: str) -> Dict[str, int]:
    key = (block_type or "").strip().lower()
    if key == "image":
        return dict(DEFAULT_IMAGE_MARGIN)
    return dict(DEFAULT_BLOCK_MARGIN)


def _normalize_margin_value(value: Any, fallback: int) -> int:
    number = int(_coerce_number(value, fallback))
    if number < MARGIN_MIN:
        return MARGIN_MIN
    if number > MARGIN_MAX:
        return MARGIN_MAX
    return number


def _normalize_block_margin(raw_margin: Any, block_type: str) -> Dict[str, int]:
    base = _default_margin_for_type(block_type)
    if raw_margin is None:
        return base
    if isinstance(raw_margin, (int, float)):
        uniform = _normalize_margin_value(raw_margin, base["top"])
        return {side: uniform for side in base}
    if isinstance(raw_margin, dict):
        margin = dict(base)
        for side in ("top", "right", "bottom", "left"):
            if side in raw_margin:
                margin[side] = _normalize_margin_value(raw_margin.get(side), margin[side])
        return margin
    if isinstance(raw_margin, str) and raw_margin.strip():
        uniform = _normalize_margin_value(raw_margin, base["top"])
        return {side: uniform for side in base}
    return base


def _normalize_font_size(raw_value: Any) -> int:
    size = int(round(_coerce_number(raw_value, DEFAULT_FONT_SIZE_PX)))
    if size <= 0:
        size = DEFAULT_FONT_SIZE_PX
    if size < FONT_SIZE_MIN:
        return FONT_SIZE_MIN
    if size > FONT_SIZE_MAX:
        return FONT_SIZE_MAX
    return size


def _estimate_text_line_count(text: str, max_chars_per_line: int) -> int:
    if max_chars_per_line <= 0:
        max_chars_per_line = 1
    normalized = (text or "").replace("\r", "")
    if not normalized:
        return 0
    total_lines = 0
    for paragraph in normalized.split("\n"):
        stripped = paragraph.strip()
        if not stripped:
            total_lines += 1
            continue
        words = stripped.split()
        line_length = 0
        for word in words:
            word_len = len(word)
            if word_len >= max_chars_per_line:
                if line_length > 0:
                    total_lines += 1
                    line_length = 0
                full_lines, remainder = divmod(word_len, max_chars_per_line)
                total_lines += full_lines
                line_length = remainder
                continue
            if line_length == 0:
                line_length = word_len
                continue
            if line_length + 1 + word_len <= max_chars_per_line:
                line_length += 1 + word_len
            else:
                total_lines += 1
                line_length = word_len
        if line_length > 0:
            total_lines += 1
    return total_lines


def _collect_layout_warnings(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    warnings: List[Dict[str, Any]] = []
    pages = layout.get("pages") or []
    if not pages and layout.get("blocks"):
        pages = [
            {
                "id": layout.get("activePageId"),
                "name": "Page 1",
                "order": 0,
                "blocks": layout.get("blocks") or [],
            }
        ]
    for index, page in enumerate(pages):
        page_name = page.get("name") or f"Page {index + 1}"
        page_id = page.get("id") or f"page-{index + 1}"
        for block in page.get("blocks") or []:
            warning = _evaluate_text_visibility(block, page_name, page_id)
            if warning:
                warnings.append(warning)
    return warnings


def _evaluate_text_visibility(block: Dict[str, Any], page_name: str, page_id: str) -> Optional[Dict[str, Any]]:
    block_type = str(block.get("type") or "text").lower()
    if block_type == "image":
        return None
    content = (block.get("content") or "").strip()
    if not content:
        return None
    position = block.get("position") or {}
    width = max(0.0, _coerce_number(position.get("width"), 0))
    height = max(0.0, _coerce_number(position.get("height"), 0))
    margin = _normalize_block_margin(block.get("margin") or block.get("padding"), block_type)
    inner_width = width - margin["left"] - margin["right"]
    inner_height = height - margin["top"] - margin["bottom"]
    block_id = block.get("id")
    typography = block.get("typography") if isinstance(block.get("typography"), dict) else {}
    font_size = _normalize_font_size((typography or {}).get("fontSize"))
    line_height_ratio = typography.get("lineHeight")
    if isinstance(line_height_ratio, (int, float)) and line_height_ratio > 0:
        line_height = font_size * line_height_ratio
    else:
        line_height = font_size * DEFAULT_LINE_HEIGHT_RATIO
    char_width = max(font_size * TEXT_CHAR_WIDTH_RATIO, 1.0)
    if inner_width <= 0 or inner_height <= 0:
        return {
            "type": "textOverflow",
            "pageId": page_id,
            "pageName": page_name,
            "blockId": block_id,
            "reason": f"No readable area remains inside the block after applying margins "
            f"({margin['left'] + margin['right']}px horizontal, {margin['top'] + margin['bottom']}px vertical).",
        }
    max_chars_per_line = max(int(inner_width / char_width), 1)
    lines = _estimate_text_line_count(content, max_chars_per_line)
    if lines <= 0:
        return None
    required_height = lines * line_height
    if required_height <= inner_height + 0.5:
        return None
    max_visible_lines = max(int(inner_height / max(line_height, 1) + 0.0001), 0)
    reason = (
        f"Estimated {lines} lines of {font_size}px text inside {int(inner_width)}×{int(inner_height)}px content area, "
        f"but only {max_visible_lines} lines fit before clipping."
    )
    return {
        "type": "textOverflow",
        "pageId": page_id,
        "pageName": page_name,
        "blockId": block_id,
        "reason": reason,
        "stats": {
            "requiredHeight": round(required_height, 2),
            "availableHeight": round(inner_height, 2),
            "lines": lines,
            "visibleLines": max_visible_lines,
            "fontSize": font_size,
            "lineHeight": round(line_height, 2),
        },
    }


def _init_agent_progress(progress_id: Optional[str], status: str = "starting", detail: str = "") -> None:
    if not progress_id:
        return
    payload = {
        "status": status,
        "detail": detail or "Preparing assistant request…",
        "updated": time.time(),
        "done": False,
        "error": None,
        "events": [],
    }
    with AGENT_PROGRESS_LOCK:
        AGENT_PROGRESS[progress_id] = payload
        _append_agent_progress_event(payload, status, payload["detail"])


def _update_agent_progress(
    progress_id: Optional[str],
    *,
    status: Optional[str] = None,
    detail: Optional[str] = None,
    error: Optional[str] = None,
    done: Optional[bool] = None,
) -> None:
    if not progress_id:
        return
    with AGENT_PROGRESS_LOCK:
        entry = AGENT_PROGRESS.get(progress_id)
        if not entry:
            entry = {
                "status": "starting",
                "detail": "",
                "updated": time.time(),
                "done": False,
                "error": None,
                "events": [],
            }
            AGENT_PROGRESS[progress_id] = entry
        if status:
            entry["status"] = status
        if detail:
            entry["detail"] = detail
        if status or detail:
            _append_agent_progress_event(entry, status, detail or status)
        if error:
            entry["error"] = error
            _append_agent_progress_event(entry, "error", error)
        if done is not None:
            entry["done"] = done
            if done:
                entry["expires"] = time.time() + AGENT_PROGRESS_TTL_SECONDS
                if detail:
                    _append_agent_progress_event(entry, status or "complete", detail)
        entry["updated"] = time.time()


def _get_agent_progress(progress_id: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    with AGENT_PROGRESS_LOCK:
        expired = [
            key
            for key, value in AGENT_PROGRESS.items()
            if value.get("done") and value.get("expires", 0) <= now
        ]
        for key in expired:
            AGENT_PROGRESS.pop(key, None)
        entry = AGENT_PROGRESS.get(progress_id)
        if not entry:
            return None
        return dict(entry)


def _append_agent_progress_event(entry: Dict[str, Any], status: Optional[str], detail: Optional[str]) -> None:
    events = entry.setdefault("events", [])
    label = detail or status
    if not label:
        return
    events.append(
        {
            "timestamp": time.time(),
            "status": status,
            "detail": label,
        }
    )
    if len(events) > 80:
        entry["events"] = events[-80:]




def _generate_page_id() -> str:
    return f"page-{uuid4().hex[:12]}"


def _normalize_page(page: Dict[str, Any], index: int = 0) -> Dict[str, Any]:
    page_id = page.get("id") or _generate_page_id()
    raw_name = page.get("name") or page.get("title") or f"Page {index + 1}"
    name = str(raw_name).strip()
    order = int(_coerce_number(page.get("order"), float(index)))
    incoming_blocks: Iterable[Dict[str, Any]] = page.get("blocks") or []
    normalized_blocks = [normalize_block(block) for block in incoming_blocks if isinstance(block, dict)]
    normalized: Dict[str, Any] = {
        "id": page_id,
        "name": name or f"Page {index + 1}",
        "order": order,
        "blocks": normalized_blocks,
    }
    dimensions = page.get("dimensions")
    if isinstance(dimensions, dict):
        normalized["dimensions"] = dict(dimensions)
    return normalized


def _select_active_page(pages: List[Dict[str, Any]], desired_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not pages:
        return None
    if desired_id:
        for page in pages:
            if page.get("id") == desired_id:
                return page
    return pages[0]


def locate_page(pages: Iterable[Dict[str, Any]], page_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not page_id:
        return None
    for page in pages or []:
        if page.get("id") == page_id:
            return page
    return None


def locate_block_in_pages(
    pages: Iterable[Dict[str, Any]], block_id: str
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    for page in pages or []:
        blocks = page.get("blocks", [])
        block = locate_block(blocks, block_id)
        if block:
            return page, block
    return None, None


def _sync_layout_active_page(layout: Dict[str, Any], page: Optional[Dict[str, Any]]) -> None:
    pages = layout.get("pages") or []
    target = page or _select_active_page(pages, layout.get("activePageId"))
    if not target:
        layout["blocks"] = []
        layout["activePageId"] = None
        return
    layout["activePageId"] = target.get("id")
    layout["blocks"] = target.get("blocks", [])


def normalize_layout(data: Dict[str, Any], project_name: str) -> Dict[str, Any]:
    layout = deepcopy(DEFAULT_LAYOUT)
    layout.update({k: v for k, v in data.items() if k not in {"blocks", "pages"}})
    layout["project"] = project_name

    pages_payload = data.get("pages")
    normalized_pages: List[Dict[str, Any]] = []
    if isinstance(pages_payload, list):
        for index, page in enumerate(pages_payload):
            if isinstance(page, dict):
                normalized_pages.append(_normalize_page(page, index))

    if not normalized_pages:
        fallback_page = {
            "id": data.get("activePageId"),
            "name": "Page 1",
            "order": 0,
            "blocks": data.get("blocks") or [],
            "dimensions": data.get("dimensions"),
        }
        normalized_pages.append(_normalize_page(fallback_page, 0))

    normalized_pages.sort(key=lambda item: item.get("order", 0))
    layout["pages"] = normalized_pages

    requested_active = layout.get("activePageId") or data.get("activePageId")
    active_page = _select_active_page(normalized_pages, requested_active)
    if active_page:
        layout["activePageId"] = active_page.get("id")
        layout["blocks"] = active_page.get("blocks", [])
    else:
        layout["activePageId"] = None
        layout["blocks"] = []
    return layout


def load_layout(project: str) -> Dict[str, Any]:
    path = layout_path(project)
    if not path.exists():
        return normalize_layout({"blocks": []}, sanitize_project(project))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {"blocks": []}
    return normalize_layout(payload, sanitize_project(project))


def save_layout(project: str, layout: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_layout(layout, sanitize_project(project))
    path = layout_path(project)
    path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")
    return normalized


def locate_block(blocks: Iterable[Dict[str, Any]], block_id: str) -> Optional[Dict[str, Any]]:
    for block in blocks:
        if block.get("id") == block_id:
            return block
    return None


def _generate_block_id() -> str:
    return f"block-{uuid4().hex[:12]}"


def _sanitize_block_after_update(block: Dict[str, Any]) -> None:
    position = block.get("position") or {}
    block["position"] = {
        "left": int(_coerce_number(position.get("left"), 0)),
        "top": int(_coerce_number(position.get("top"), 0)),
        "width": int(_coerce_number(position.get("width"), 240)),
        "height": int(_coerce_number(position.get("height"), 120)),
    }
    typography = block.get("typography")
    if isinstance(typography, dict):
        typography["fontSize"] = _normalize_font_size(typography.get("fontSize"))
    elif typography is not None:
        block.pop("typography", None)
    block_type = block.get("type") or "text"
    block["margin"] = _normalize_block_margin(block.get("margin") or block.get("padding"), block_type)


def _render_canvas_preview(project: str) -> Dict[str, Any]:
    layout = load_layout(project)
    pages = rasterize_layout(layout, asset_base=project_dir(project))
    if not pages:
        raise ValueError("No pages were generated for this layout.")
    first = pages[0]
    buffer = io.BytesIO()
    first.image.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("ascii")
    return {
        "type": "image/png",
        "label": f"{project}-page-{first.index + 1}.png",
        "width": first.width,
        "height": first.height,
        "dataUrl": f"data:image/png;base64,{encoded}",
    }


def _format_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%b %d, %Y · %I:%M %p")


def _project_created_timestamp(folder: Path) -> float:
    timestamps: List[float] = []
    layout_file = folder / "layout.json"
    try:
        if layout_file.exists():
            timestamps.append(layout_file.stat().st_ctime)
    except OSError:
        pass
    try:
        if folder.exists():
            timestamps.append(folder.stat().st_ctime)
    except OSError:
        pass
    return min(timestamps) if timestamps else time.time()


def _project_preview_thumbnail(project: str) -> Optional[Dict[str, Any]]:
    try:
        preview = _render_canvas_preview(project)
    except Exception:
        return None
    return {
        "url": preview.get("dataUrl"),
        "width": preview.get("width"),
        "height": preview.get("height"),
        "label": preview.get("label"),
    }


def _collect_project_cards() -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for project in _list_project_names():
        folder = _project_path(project)
        created_ts = _project_created_timestamp(folder)
        cards.append(
            {
                "name": project,
                "created_ts": created_ts,
                "created_label": _format_timestamp(created_ts),
                "created_iso": datetime.fromtimestamp(created_ts).isoformat(),
                "preview": _project_preview_thumbnail(project),
            }
        )
    cards.sort(key=lambda item: item["created_ts"], reverse=True)
    return cards


def _build_directory_tree(root: Path, *, max_entries: int = 240, max_depth: int = 6) -> Tuple[str, Dict[str, int]]:
    lines: List[str] = [f"{root.name}/"]
    stats = {"dirs": 0, "files": 0}
    entries_seen = 0

    def walk(current: Path, prefix: str = "", depth: int = 0):
        nonlocal entries_seen
        if depth >= max_depth:
            lines.append(f"{prefix}└── …")
            return
        children = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for idx, child in enumerate(children):
            if entries_seen >= max_entries:
                lines.append(f"{prefix}└── …")
                return
            connector = "└── " if idx == len(children) - 1 else "├── "
            display_name = f"{child.name}/" if child.is_dir() else child.name
            lines.append(f"{prefix}{connector}{display_name}")
            entries_seen += 1
            if child.is_dir():
                stats["dirs"] += 1
                extension = "    " if idx == len(children) - 1 else "│   "
                walk(child, prefix + extension, depth + 1)
            else:
                stats["files"] += 1

    walk(root)
    return "\n".join(lines), stats


def _gather_agent_files(root: Path) -> List[Dict[str, Any]]:
    collected: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = str(path.relative_to(root))
        try:
            size = path.stat().st_size
        except OSError:
            continue
        entry: Dict[str, Any] = {"path": rel_path, "size": size}
        if path.suffix.lower() in {".json", ".txt", ".md", ".py", ".js", ".css"} or rel_path.endswith(".layout"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            entry["preview"] = text[:MAX_AGENT_BYTES]
        collected.append(entry)
        if len(collected) >= MAX_AGENT_FILES:
            break
    return collected


def _build_project_snapshot(project: str) -> Dict[str, Any]:
    root = project_dir(project)
    tree_text, stats = _build_directory_tree(root)
    layout = load_layout(project)
    warnings = _collect_layout_warnings(layout)
    files = _gather_agent_files(root)
    return {
        "project": project,
        "tree": tree_text,
        "filesIndexed": stats["files"],
        "directoriesIndexed": stats["dirs"],
        "files": files,
        "layout": layout,
        "warnings": warnings,
    }


def _dashscope_configured() -> bool:
    return bool(DASHSCOPE_API_KEY and FIONA_AGENT_MODEL)


def _get_openai_client() -> "OpenAI":
    global _openai_client
    if _openai_client is not None:
        return _openai_client
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("DASHSCOPE_API_KEY is not configured.")
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError("Install the 'openai' package to enable the Qwen assistant.") from exc
    _openai_client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
    return _openai_client


def _truncate_context(text: str, limit: int) -> str:
    snippet = (text or "").strip()
    if not snippet:
        return ""
    if len(snippet) <= limit:
        return snippet
    return f"{snippet[:limit]}… (truncated)"


def _build_qwen_messages(
    message: str, attachments: List[Dict[str, Any]], agent_snapshot: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    user_content: List[Dict[str, Any]] = []
    trimmed = message.strip()
    if trimmed:
        user_content.append({"type": "text", "text": trimmed})
    else:
        user_content.append(
            {
                "type": "text",
                "text": "No explicit instructions were provided. Offer actionable layout suggestions using the attached context.",
            }
        )

    for attachment in attachments:
        label = (attachment.get("label") or attachment.get("type") or "Attachment").strip()
        att_type = (attachment.get("type") or "").lower()
        meta = attachment.get("meta") or {}
        meta_desc = []
        if isinstance(meta, dict):
            for key in ("page", "width", "height"):
                if key in meta:
                    meta_desc.append(f"{key}={meta[key]}")
        if meta_desc:
            label = f"{label} ({', '.join(meta_desc)})"
        data_url = attachment.get("dataUrl")
        if data_url and att_type.startswith("image"):
            user_content.append({"type": "text", "text": f"{label} – latest canvas capture."})
            user_content.append({"type": "image_url", "image_url": {"url": data_url}})
        elif data_url:
            user_content.append(
                {"type": "text", "text": f"{label} – data URL provided but not rendered (type: {att_type or 'unknown'})."}
            )
        else:
            user_content.append({"type": "text", "text": f"{label} – metadata only (type: {att_type or 'unknown'})."})

    if agent_snapshot:
        project_name = agent_snapshot.get("project") or DEFAULT_PROJECT
        files_indexed = agent_snapshot.get("filesIndexed", 0)
        directories_indexed = agent_snapshot.get("directoriesIndexed", 0)
        snapshot_header = (
            f"Agent snapshot for project “{project_name}”. "
            f"Indexed {files_indexed} files across {directories_indexed} directories."
        )
        user_content.append({"type": "text", "text": snapshot_header})
        tree = agent_snapshot.get("tree")
        if tree:
            user_content.append(
                {
                    "type": "text",
                    "text": f"Project tree:\n{_truncate_context(tree, MAX_TREE_CONTEXT_CHARS)}",
                }
            )
        layout = agent_snapshot.get("layout")
        if layout:
            layout_text = json.dumps(layout, indent=2, ensure_ascii=False)
            user_content.append(
                {
                    "type": "text",
                    "text": f"Layout JSON:\n{_truncate_context(layout_text, MAX_LAYOUT_CONTEXT_CHARS)}",
                }
            )
        warnings = agent_snapshot.get("warnings") or []
        if warnings:
            entries = warnings[:LAYOUT_WARNING_LIMIT]
            summary_lines = [
                f"- Page “{item.get('pageName') or item.get('pageId') or '?'}”, block {item.get('blockId') or 'unknown'}: {item.get('reason')}"
                for item in entries
            ]
            if len(warnings) > len(entries):
                summary_lines.append(f"...{len(warnings) - len(entries)} additional block(s) with potential clipping.")
            user_content.append(
                {
                    "type": "text",
                    "text": "Layout warnings:\n" + "\n".join(summary_lines),
                }
            )
        files = agent_snapshot.get("files") or []
        if files:
            summary_lines: List[str] = []
            for file_info in files[:MAX_FILE_CONTEXT]:
                path = file_info.get("path") or "unknown file"
                size = file_info.get("size")
                size_label = f"{size} bytes" if isinstance(size, int) else "unknown size"
                summary_lines.append(f"- {path} ({size_label})")
                preview = file_info.get("preview")
                if preview:
                    summary_lines.append(f"  Preview: {_truncate_context(preview, MAX_FILE_PREVIEW_CHARS)}")
            if summary_lines:
                user_content.append(
                    {
                        "type": "text",
                        "text": "File previews:\n" + "\n".join(summary_lines),
                    }
                )

    return [
        {"role": "system", "content": [{"type": "text", "text": AGENT_SYSTEM_PROMPT}]},
        {"role": "user", "content": user_content},
    ]


def _request_qwen_message(
    messages: List[Dict[str, Any]], *, tools: Optional[List[Dict[str, Any]]] = None
) -> Optional[Any]:
    client = _get_openai_client()
    payload: Dict[str, Any] = {"model": FIONA_AGENT_MODEL, "messages": messages}
    extra_body: Dict[str, Any] = {}
    if FIONA_AGENT_ENABLE_THINKING:
        extra_body["enable_thinking"] = True
        if FIONA_AGENT_THINKING_BUDGET > 0:
            extra_body["thinking_budget"] = FIONA_AGENT_THINKING_BUDGET
    if extra_body:
        payload["extra_body"] = extra_body
    if tools:
        payload["tools"] = tools
    response = client.chat.completions.create(**payload)
    choice = (response.choices or [None])[0]
    return choice.message if choice else None


def _message_content_to_text(content: Any) -> str:
    if not content:
        return ""
    if isinstance(content, list):
        parts: List[str] = []
        for entry in content:
            if hasattr(entry, "model_dump"):
                entry_data = entry.model_dump()
            elif isinstance(entry, dict):
                entry_data = entry
            else:
                entry_data = {"type": "text", "text": str(entry)}
            if entry_data.get("type") == "text" and entry_data.get("text"):
                parts.append(str(entry_data["text"]))
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def _serialize_message_content(content: Any) -> Any:
    if isinstance(content, list):
        serialized: List[Any] = []
        for entry in content:
            if hasattr(entry, "model_dump"):
                serialized.append(entry.model_dump())
            elif isinstance(entry, dict):
                serialized.append(entry)
            else:
                serialized.append({"type": "text", "text": str(entry)})
        return serialized
    return content or ""


def _serialize_tool_calls(raw_calls: Any) -> List[Dict[str, Any]]:
    calls = raw_calls or []
    serialized: List[Dict[str, Any]] = []
    for call in calls:
        if hasattr(call, "model_dump"):
            serialized.append(call.model_dump())
        else:
            function = getattr(call, "function", None)
            serialized.append(
                {
                    "id": getattr(call, "id", ""),
                    "type": getattr(call, "type", "function"),
                    "function": {
                        "name": getattr(function, "name", ""),
                        "arguments": getattr(function, "arguments", "{}"),
                    },
                }
            )
    return serialized


def _call_qwen_completion(messages: List[Dict[str, Any]]) -> str:
    message = _request_qwen_message(messages)
    if not message:
        return "I could not generate a response. Please try again."
    content = _message_content_to_text(getattr(message, "content", ""))
    return content or "I could not find anything helpful to share. Try rephrasing your request."


def _build_agent_toolset(project: str, permissions: Optional[Dict[str, bool]] = None) -> AgentToolset:
    def _terminal_factory(layout: Dict[str, Any]) -> TerminalProcessor:
        return TerminalProcessor(project=project, layout=layout, block_id_factory=_generate_block_id)

    perm_payload = permissions or {}
    allow_layout_edits = bool(perm_payload.get("allow_layout_edits"))
    allow_web_search = bool(perm_payload.get("allow_web_search") and _bing_search_available())

    web_search_callable: Optional[Callable[[str, int], List[Dict[str, str]]]] = None
    web_image_search_callable: Optional[Callable[[str, int], List[Dict[str, Any]]]] = None
    if allow_web_search:
        def _web_search_adapter(query: str, count: int) -> List[Dict[str, str]]:
            return _perform_bing_web_search(query, count=count)

        web_search_callable = _web_search_adapter
        def _web_image_search_adapter(query: str, count: int) -> List[Dict[str, Any]]:
            return _perform_bing_image_search(query, count=count)

        web_image_search_callable = _web_image_search_adapter

    context = AgentToolContext(
        project=project,
        load_layout=load_layout,
        save_layout=save_layout,
        terminal_factory=_terminal_factory,
        project_root=project_dir(project),
        project_media_dir=media_dir(project),
        allow_layout_edits=allow_layout_edits,
        allow_web_search=allow_web_search,
        web_search=web_search_callable,
        web_image_search=web_image_search_callable,
    )
    return AgentToolset(context)


def _run_agent_with_tools(
    messages: List[Dict[str, Any]],
    project: str,
    *,
    progress_callback: Optional[Callable[[str, Optional[str]], None]] = None,
    permissions: Optional[Dict[str, bool]] = None,
    tool_limit: Optional[int] = None,
    agent_mode: Optional[str] = None,
) -> Tuple[str, bool, List[Dict[str, Any]]]:
    toolkit = _build_agent_toolset(project, permissions=permissions)
    conversation = list(messages)
    layout_changed = False
    trace: List[Dict[str, Any]] = []
    global_cap: Optional[int] = MAX_AGENT_TOOL_CALLS if MAX_AGENT_TOOL_CALLS > 0 else None
    if tool_limit is None:
        effective_limit = global_cap
    elif global_cap is None:
        effective_limit = tool_limit
    else:
        effective_limit = min(tool_limit, global_cap)
    remaining_calls: Optional[int] = effective_limit
    last_progress_detail: Optional[str] = None
    mode_label = (agent_mode or "standard").strip() or "standard"

    def emit_progress(status: str, detail: Optional[str]) -> None:
        nonlocal last_progress_detail
        if not progress_callback:
            return
        text = (detail or status or "").strip()
        if not text:
            text = status or "working"
        if text == last_progress_detail:
            return
        last_progress_detail = text
        progress_callback(status, text)

    if remaining_calls is None:
        start_detail = f"{mode_label} mode · no tool cap"
    else:
        start_detail = f"{mode_label} mode · up to {remaining_calls} tool call(s)"
    trace.append({"kind": "thought", "message": f"Starting in {start_detail}."})
    emit_progress("starting", start_detail)

    while True:
        if remaining_calls is not None and remaining_calls <= 0:
            limit_message = (
                f"Reached the agent tool budget of {effective_limit} call(s)."
                if effective_limit is not None
                else "Reached the configured agent tool budget."
            )
            trace.append({"kind": "limit", "message": limit_message})
            if progress_callback:
                progress_callback("limit", limit_message)
            return (
                "I hit the configured tool budget before finishing. Summarize what remains or re-run with a higher limit.",
                layout_changed,
                trace,
            )

        if remaining_calls is None:
            emit_progress("thinking", "Analyzing next step (unlimited tool calls)…")
        else:
            emit_progress("thinking", f"Analyzing next step ({remaining_calls} tool call(s) remaining)…")
        response_message = _request_qwen_message(conversation, tools=toolkit.specs)
        if not response_message:
            trace.append({"kind": "error", "message": "Assistant response was empty."})
            emit_progress("error", "Assistant returned an empty response.")
            return (
                "I could not contact the assistant to keep running tools. Please try again.",
                layout_changed,
                trace,
            )

        payload: Dict[str, Any] = {
            "role": getattr(response_message, "role", "assistant"),
            "content": _serialize_message_content(getattr(response_message, "content", "")),
        }
        tool_calls = _serialize_tool_calls(getattr(response_message, "tool_calls", None))
        if tool_calls:
            payload["tool_calls"] = tool_calls
        conversation.append(payload)

        message_text = _message_content_to_text(getattr(response_message, "content", ""))
        if tool_calls:
            if message_text:
                detail = message_text.strip()
                trace.append({"kind": "thought", "message": detail})
                emit_progress("thinking", detail[:280])
            for call in tool_calls:
                function = call.get("function") or {}
                name = function.get("name") or ""
                arguments = function.get("arguments") or "{}"
                entry: Dict[str, Any] = {
                    "kind": "tool",
                    "name": name or "unknown_tool",
                    "arguments": arguments,
                }
                try:
                    arg_preview = (arguments or "{}")[:200]
                    emit_progress("tool", f"Running {name or 'tool'} with args {arg_preview or '{}'}")
                    result = toolkit.invoke(name, arguments)
                    tool_output = result.content
                    layout_changed = layout_changed or result.layout_changed
                    entry["status"] = "ok"
                    entry["result"] = tool_output
                    emit_progress("tool", f"Finished {name or 'tool'}.")
                except AgentToolError as exc:
                    tool_output = f"Tool error: {exc}"
                    entry["status"] = "error"
                    entry["result"] = tool_output
                    emit_progress("error", tool_output[:240])
                except Exception:  # pragma: no cover - defensive guard
                    app.logger.exception("agent tool invocation failed")
                    tool_output = "Tool error: unexpected failure while running this command."
                    entry["status"] = "error"
                    entry["result"] = tool_output
                    emit_progress("error", tool_output[:240])
                trace.append(entry)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or "",
                        "name": name,
                        "content": tool_output,
                    }
                )
                if remaining_calls is not None:
                    remaining_calls -= 1
            continue

        if message_text:
            trace.append({"kind": "final", "message": message_text})
            emit_progress("complete", "Agent finished composing the reply.")
            return message_text, layout_changed, trace

        trace.append({"kind": "thought", "message": "Assistant replied without content, continuing…"})
        if remaining_calls is not None:
            remaining_calls -= 1


def _fallback_chat_reply(message: str, attachments: List[Dict[str, Any]], agent_snapshot: Optional[Dict[str, Any]]) -> str:
    sections: List[str] = []
    if message:
        sections.append(f"You said: {message}")
    if attachments:
        labels = ", ".join(att.get("label") or att.get("type", "attachment") for att in attachments)
        sections.append(f"I received {len(attachments)} attachment(s): {labels}.")
    if agent_snapshot:
        sections.append(
            f"I can read {agent_snapshot.get('filesIndexed', 0)} files inside project '{agent_snapshot.get('project')}'."
        )
    if not sections:
        return "Hi! How can I help with your layout?"
    sections.append("The AI assistant is offline, so this is only an acknowledgement.")
    return " ".join(sections)


def _generate_chat_reply(
    message: str,
    attachments: List[Dict[str, Any]],
    agent_snapshot: Optional[Dict[str, Any]],
    *,
    project: str,
    allow_tools: bool = False,
    tool_permissions: Optional[Dict[str, bool]] = None,
    tool_limit: Optional[int] = None,
    agent_mode: Optional[str] = None,
    progress_callback: Optional[Callable[[str, Optional[str]], None]] = None,
) -> Tuple[str, bool, List[Dict[str, Any]]]:
    if not _dashscope_configured():
        return _fallback_chat_reply(message, attachments, agent_snapshot), False, []

    messages = _build_qwen_messages(message or "", attachments, agent_snapshot)
    if allow_tools:
        reply, layout_changed, trace = _run_agent_with_tools(
            messages,
            project,
            progress_callback=progress_callback,
            permissions=tool_permissions,
            tool_limit=tool_limit,
            agent_mode=agent_mode,
        )
        return reply, layout_changed, trace

    try:
        if progress_callback:
            progress_callback("responding", "Assistant is composing a reply…")
        reply = _call_qwen_completion(messages)
        return reply, False, []
    except Exception as exc:  # pragma: no cover - network and SDK failures
        app.logger.exception("Qwen chat request failed: {error}".format(error=exc))
        fallback = _fallback_chat_reply(message, attachments, agent_snapshot)
        return f"{fallback} Assistant error: {exc.__class__.__name__}.", False, []


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@app.route("/")
def index() -> str:
    return render_template("index.html", bing_search_enabled=_bing_search_available())


@app.route("/welcome", methods=["GET"])
def welcome() -> str:
    projects = _collect_project_cards()
    return render_template("welcome.html", projects=projects)


@app.route("/api/projects", methods=["GET", "POST"])
def projects_api():
    if request.method == "GET":
        return jsonify({"projects": _list_project_names()})

    payload = request.get_json(silent=True) or {}
    requested_name = (payload.get("project") or payload.get("name") or "").strip()
    if not requested_name:
        return jsonify({"success": False, "error": "project name is required"}), 400

    project = sanitize_project(requested_name)
    if not project:
        return jsonify({"success": False, "error": "invalid project name"}), 400

    folder = _project_path(project)
    layout_file = folder / "layout.json"
    if layout_file.exists():
        return jsonify({"success": False, "error": "project already exists"}), 409

    layout_data = payload.get("layout")
    if not isinstance(layout_data, dict):
        layout_data = {"blocks": []}

    saved = save_layout(project, layout_data)
    return jsonify({"success": True, "project": project, "layout": saved})


@app.route("/api/layout", methods=["GET", "POST"])
def layout_api():
    if request.method == "GET":
        project = sanitize_project(request.args.get("project") or DEFAULT_PROJECT)
        layout = load_layout(project)
        return jsonify(layout)

    payload = request.get_json(silent=True) or {}
    project = sanitize_project(payload.get("project") or DEFAULT_PROJECT)
    layout_data = payload.get("layout")
    if not isinstance(layout_data, dict):
        return jsonify({"success": False, "error": "layout must be an object"}), 400

    save_layout(project, layout_data)
    return jsonify({"success": True, "project": project})


@app.route("/api/block", methods=["POST"])
def block_api():
    payload = request.get_json(silent=True) or {}
    project = sanitize_project(payload.get("project") or DEFAULT_PROJECT)
    operation = payload.get("operation")

    if operation not in {"add", "update", "delete"}:
        return jsonify({"success": False, "error": "invalid operation"}), 400

    layout = load_layout(project)
    pages = layout.setdefault("pages", [])
    page_id = payload.get("page_id")
    target_page = locate_page(pages, page_id) or (pages[0] if pages else None)
    if target_page is None:
        target_page = _normalize_page({"name": "Page 1", "order": 0, "blocks": []}, 0)
        pages.append(target_page)

    if operation == "add":
        block_data = payload.get("block")
        if not isinstance(block_data, dict):
            return jsonify({"success": False, "error": "block must be an object"}), 400

        new_block = normalize_block(block_data)
        blocks = target_page.setdefault("blocks", [])
        while locate_block(blocks, new_block["id"]):
            new_block["id"] = _generate_block_id()
        blocks.append(new_block)
        _sync_layout_active_page(layout, target_page)
        save_layout(project, layout)
        return jsonify({"success": True, "block": new_block, "page_id": target_page.get("id")})

    block_id = payload.get("block_id")
    if not isinstance(block_id, str) or not block_id.strip():
        return jsonify({"success": False, "error": "block_id is required"}), 400

    owning_page, block = locate_block_in_pages(pages, block_id)
    if not block:
        return jsonify({"success": False, "error": "block not found"}), 404

    if operation == "delete":
        owning_page["blocks"] = [b for b in owning_page.get("blocks", []) if b.get("id") != block_id]
        _sync_layout_active_page(layout, owning_page)
        save_layout(project, layout)
        return jsonify({"success": True})

    updates = payload.get("updates")
    if not isinstance(updates, dict):
        return jsonify({"success": False, "error": "updates must be an object"}), 400

    deep_merge(block, updates)
    _sanitize_block_after_update(block)
    _sync_layout_active_page(layout, owning_page)
    save_layout(project, layout)
    return jsonify({"success": True, "block": block})


@app.route("/api/upload", methods=["POST"])
def upload_media():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "missing file"}), 400
    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"success": False, "error": "empty filename"}), 400

    project = sanitize_project(request.form.get("project") or DEFAULT_PROJECT)
    block_id = request.form.get("block_id")
    layout = None
    block = None
    owning_page: Optional[Dict[str, Any]] = None
    if block_id:
        layout = load_layout(project)
        owning_page, block = locate_block_in_pages(layout.get("pages", []), block_id)
        if not block:
            return jsonify({"success": False, "error": "block not found"}), 404
        if block.get("type") != "image":
            return jsonify({"success": False, "error": "image uploads only allowed for image blocks"}), 400

    filename_hint = request.form.get("filename") or file.filename
    safe_name = secure_filename(filename_hint) or "upload"
    ext = Path(safe_name).suffix or ".bin"
    unique_name = f"{Path(safe_name).stem}-{uuid4().hex[:10]}{ext}"

    target_path = media_dir(project) / unique_name
    file.save(target_path)

    url = url_for(ASSET_ROUTE, project=project, filename=unique_name)
    if block is not None:
        block["imageUrl"] = url
        if not block.get("content"):
            block["content"] = Path(filename_hint).stem or "Image"
        _sync_layout_active_page(layout, owning_page)
        save_layout(project, layout)
    response_payload: Dict[str, Any] = {"success": True, "url": url, "filename": unique_name}
    if block is not None:
        response_payload["block"] = block
    return jsonify(response_payload)


@app.route("/api/export/<string:export_format>", methods=["GET"])
def export_project(export_format: str):
    return _stream_project_export(export_format)


@app.route("/api/export", methods=["GET"])
def export_project_default():
    export_format = request.args.get("format") or "pdf"
    return _stream_project_export(export_format)


def _stream_project_export(export_format: str):
    project = sanitize_project(request.args.get("project") or DEFAULT_PROJECT)
    layout = load_layout(project)
    assets = project_dir(project)
    try:
        payload = export_layout(layout, project_name=project, asset_base=assets, export_format=export_format)
    except (ExportFormatError, PdfExportError) as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception:  # pragma: no cover - defensive catch to avoid exposing tracebacks
        return jsonify({"success": False, "error": "Unexpected error during export."}), 500

    buffer = io.BytesIO(payload.data)
    buffer.seek(0)
    response = send_file(buffer, mimetype=payload.mimetype, as_attachment=True, download_name=payload.filename)
    response.headers["X-Layout-Digest"] = payload.digest
    response.headers["X-Blocks-Rendered"] = str(payload.stats.blocks_rendered)
    response.headers["X-Blocks-Expected"] = str(payload.stats.blocks_attempted)
    response.headers["X-Export-Format"] = payload.meta.get("format", export_format)
    response.headers["X-Download-Filename"] = payload.filename
    return response


@app.route("/project-assets/<project>/<path:filename>")
def serve_project_asset(project: str, filename: str):
    project_name = sanitize_project(project)
    directory = media_dir(project_name)
    return send_from_directory(directory, filename)


@app.route("/api/fonts", methods=["GET"])
def list_available_fonts():
    fonts = [
        {
            "id": font.id,
            "name": font.name,
            "category": "manual" if font.category == "manual" else "system",
            "url": url_for("serve_font_file", font_id=font.id),
        }
        for font in list_fonts()
    ]
    return jsonify({"fonts": fonts})


@app.route("/fonts/<font_id>", methods=["GET"])
def serve_font_file(font_id: str):
    font = get_font(font_id)
    if not font:
        return jsonify({"success": False, "error": "font not found"}), 404
    mimetype = "font/ttf" if font.path.suffix.lower() == ".ttf" else "font/otf"
    return send_file(font.path, mimetype=mimetype, conditional=True)


@app.route("/api/projects/import", methods=["POST"])
def import_project():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "missing file"}), 400

    upload = request.files["file"]
    if not upload or upload.filename == "":
        return jsonify({"success": False, "error": "select a layout file to import"}), 400

    requested_name = (request.form.get("project_name") or Path(upload.filename).stem or "").strip()
    if not requested_name:
        return jsonify({"success": False, "error": "project name is required"}), 400

    project = sanitize_project(requested_name)
    folder = _project_path(project)
    layout_file = folder / "layout.json"
    if layout_file.exists():
        return jsonify({"success": False, "error": "a project with that name already exists"}), 409

    raw_payload = upload.read()
    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except UnicodeDecodeError:
        return jsonify({"success": False, "error": "layout file must be UTF-8 encoded JSON"}), 400
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "layout file is not valid JSON"}), 400

    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "layout file must contain a JSON object"}), 400

    saved = save_layout(project, payload)
    return jsonify({"success": True, "project": project, "layout": saved})


@app.route("/api/chat", methods=["POST"])
def chat_assistant():
    payload = request.get_json(silent=True) or {}
    project = sanitize_project(payload.get("project") or DEFAULT_PROJECT)
    message = (payload.get("message") or "").strip()
    attachments_raw = payload.get("attachments") or []
    agent_mode_enabled = bool(payload.get("agentMode"))
    permissions_payload = payload.get("agentPermissions") or {}
    allow_layout_edits = bool(permissions_payload.get("allowLayoutEdits"))
    allow_web_search = agent_mode_enabled and bool(permissions_payload.get("allowWebSearch"))
    mode_setting = (
        payload.get("agentModePreset")
        or payload.get("agentModeProfile")
        or payload.get("agentModeSetting")
        or DEFAULT_AGENT_TOOL_MODE
    )
    mode_label, requested_tool_limit = _resolve_agent_tool_budget(mode_setting, payload.get("agentToolLimit"))
    global_tool_cap = MAX_AGENT_TOOL_CALLS if MAX_AGENT_TOOL_CALLS > 0 else None
    if requested_tool_limit is None:
        effective_tool_limit = global_tool_cap
    elif global_tool_cap is None:
        effective_tool_limit = requested_tool_limit
    else:
        effective_tool_limit = min(requested_tool_limit, global_tool_cap)
    progress_token = (payload.get("progressToken") or "").strip() or None
    _init_agent_progress(progress_token, "starting", "Contacting the assistant…")

    attachments: List[Dict[str, Any]] = []
    for item in attachments_raw:
        if not isinstance(item, dict):
            continue
        if len(attachments) >= CHAT_ATTACHMENT_LIMIT:
            break
        attachments.append(
            {
                "type": (item.get("type") or "attachment")[:32],
                "label": (item.get("label") or "attachment")[:80],
                "dataUrl": item.get("dataUrl"),
                "meta": item.get("meta") or {},
            }
        )

    agent_snapshot = None
    client_snapshot = payload.get("agentSnapshot")
    if agent_mode_enabled:
        if isinstance(client_snapshot, dict):
            agent_snapshot = client_snapshot
        else:
            agent_snapshot = _build_project_snapshot(project)
    layout = agent_snapshot["layout"] if agent_snapshot else load_layout(project)
    allow_tools = agent_mode_enabled
    tool_permissions = {
        "allow_layout_edits": allow_layout_edits,
        "allow_web_search": allow_web_search,
    }
    def _progress(status: str, detail: Optional[str] = None) -> None:
        _update_agent_progress(progress_token, status=status, detail=detail or status)

    reply, layout_updated, agent_trace = _generate_chat_reply(
        message,
        attachments,
        agent_snapshot,
        project=project,
        allow_tools=allow_tools,
        tool_permissions=tool_permissions,
        tool_limit=effective_tool_limit if allow_tools else None,
        agent_mode=mode_label if allow_tools else None,
        progress_callback=_progress,
    )
    if layout_updated:
        agent_snapshot = _build_project_snapshot(project)
        layout = agent_snapshot.get("layout", layout)
    pages = layout.get("pages") or []
    total_blocks = sum(len(page.get("blocks", [])) for page in pages)
    if not total_blocks:
        total_blocks = len(layout.get("blocks", []))
    tokens_used, image_bytes = _estimate_chat_token_usage(message, attachments, reply or "")
    _record_token_usage(tokens_used, image_bytes)
    stats = _get_token_stats()
    _update_agent_progress(progress_token, status="complete", detail="Assistant reply ready.", done=True)
    return jsonify(
        {
            "success": True,
            "reply": reply,
            "agentSnapshot": agent_snapshot,
            "agentTrace": agent_trace,
            "actions": {
                "layoutUpdated": layout_updated,
            },
            "summary": {
                "project": project,
                "blocks": total_blocks,
            },
            "progressToken": progress_token,
            "tokenStats": stats,
            "agentOptions": {
                "mode": mode_label,
                "toolLimit": effective_tool_limit,
            },
        }
    )


@app.route("/api/chat/attachments/canvas", methods=["POST"])
def chat_canvas_attachment():
    payload = request.get_json(silent=True) or {}
    project = sanitize_project(payload.get("project") or DEFAULT_PROJECT)
    try:
        attachment = _render_canvas_preview(project)
    except Exception as exc:  # pragma: no cover - UI surfacing only
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "attachment": attachment})


@app.route("/api/chat/agent-snapshot", methods=["GET"])
def chat_agent_snapshot():
    project = sanitize_project(request.args.get("project") or DEFAULT_PROJECT)
    snapshot = _build_project_snapshot(project)
    return jsonify({"success": True, "snapshot": snapshot})


@app.route("/api/chat/progress/<progress_id>", methods=["GET"])
def chat_progress(progress_id: str):
    progress = _get_agent_progress(progress_id)
    if not progress:
        placeholder = {
            "status": "pending",
            "detail": "Waiting for assistant to report progress…",
            "updated": time.time(),
            "done": False,
            "error": None,
            "events": [
                {
                    "timestamp": time.time(),
                    "status": "pending",
                    "detail": "Waiting for assistant to report progress…",
                }
            ],
        }
        return jsonify({"success": True, "progress": {**placeholder, "id": progress_id}})
    return jsonify({"success": True, "progress": {**progress, "id": progress_id}})


@app.route("/api/chat/token-stats", methods=["GET"])
def chat_token_stats():
    return jsonify({"success": True, "stats": _get_token_stats()})


@app.route("/api/terminal", methods=["POST"])
def terminal_command():
    payload = request.get_json(silent=True) or {}
    command = (payload.get("command") or "").strip()
    if not command:
        return jsonify({"success": False, "error": "Command is required."}), 400
    project = sanitize_project(payload.get("project") or DEFAULT_PROJECT)
    layout = load_layout(project)
    processor = TerminalProcessor(project=project, layout=deepcopy(layout), block_id_factory=_generate_block_id)
    try:
        result = processor.run(command)
    except TerminalCommandError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception:  # pragma: no cover - defensive logging
        app.logger.exception("terminal command failed")
        return jsonify({"success": False, "error": "Unable to run command."}), 500

    if result.layout is not None:
        save_layout(project, result.layout)
    return jsonify(
        {
            "success": True,
            "output": result.output,
            "layoutUpdated": bool(result.layout),
        }
    )


def _load_token_usage_state() -> Dict[str, float]:
    if not TOKEN_USAGE_FILE.exists():
        return {
            "session_tokens": 0,
            "session_image_bytes": 0,
            "lifetime_tokens": 0,
            "lifetime_image_bytes": 0,
        }
    try:
        data = json.loads(TOKEN_USAGE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    return {
        "session_tokens": 0,
        "session_image_bytes": 0,
        "lifetime_tokens": float(data.get("lifetime_tokens", 0)),
        "lifetime_image_bytes": float(data.get("lifetime_image_bytes", 0)),
    }


def _save_token_usage_state() -> None:
    payload = {
        "lifetime_tokens": TOKEN_USAGE_STATE.get("lifetime_tokens", 0),
        "lifetime_image_bytes": TOKEN_USAGE_STATE.get("lifetime_image_bytes", 0),
    }
    try:
        TOKEN_USAGE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def _record_token_usage(tokens: int, image_bytes: float) -> None:
    if tokens <= 0 and image_bytes <= 0:
        return
    with TOKEN_USAGE_LOCK:
        TOKEN_USAGE_STATE["session_tokens"] = TOKEN_USAGE_STATE.get("session_tokens", 0) + max(tokens, 0)
        TOKEN_USAGE_STATE["lifetime_tokens"] = TOKEN_USAGE_STATE.get("lifetime_tokens", 0) + max(tokens, 0)
        TOKEN_USAGE_STATE["session_image_bytes"] = TOKEN_USAGE_STATE.get("session_image_bytes", 0.0) + max(image_bytes, 0.0)
        TOKEN_USAGE_STATE["lifetime_image_bytes"] = TOKEN_USAGE_STATE.get("lifetime_image_bytes", 0.0) + max(image_bytes, 0.0)
    _save_token_usage_state()


def _get_token_stats() -> Dict[str, float]:
    with TOKEN_USAGE_LOCK:
        return {
            "sessionTokens": int(TOKEN_USAGE_STATE.get("session_tokens", 0)),
            "lifetimeTokens": int(TOKEN_USAGE_STATE.get("lifetime_tokens", 0)),
            "sessionImages": float(TOKEN_USAGE_STATE.get("session_image_bytes", 0.0)),
            "lifetimeImages": float(TOKEN_USAGE_STATE.get("lifetime_image_bytes", 0.0)),
        }


def _estimate_text_tokens(text: Optional[str]) -> int:
    """Return the number of UTF-8 bytes sent for textual content."""
    if not text:
        return 0
    try:
        return len(text.encode("utf-8"))
    except AttributeError:
        return 0


def _estimate_attachment_usage(attachments: List[Dict[str, Any]]) -> Tuple[int, float]:
    tokens = 0
    image_bytes = 0.0
    for attachment in attachments or []:
        if not isinstance(attachment, dict):
            continue
        data_url = attachment.get("dataUrl")
        if isinstance(data_url, str) and data_url.startswith("data:image"):
            bytes_count = _estimate_image_bytes(data_url)
            image_bytes += bytes_count
        else:
            label = attachment.get("label")
            meta = attachment.get("meta")
            tokens += _estimate_text_tokens(label)
            if meta:
                tokens += _estimate_text_tokens(json.dumps(meta))
    return tokens, image_bytes


def _estimate_image_bytes(data_url: str) -> float:
    try:
        header, encoded = data_url.split(",", 1)
    except ValueError:
        return 0.0
    padding = encoded.count("=")
    length = len(encoded.strip())
    return max(0.0, (length * 3 / 4) - padding)


def _estimate_chat_token_usage(message: str, attachments: List[Dict[str, Any]], reply: str) -> Tuple[int, float]:
    tokens = _estimate_text_tokens(message) + _estimate_text_tokens(reply)
    attachment_tokens, image_bytes = _estimate_attachment_usage(attachments)
    tokens += attachment_tokens
    return tokens, image_bytes


TOKEN_USAGE_STATE.update(_load_token_usage_state())


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
