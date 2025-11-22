from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from terminal import TerminalCommandError, TerminalProcessor


class AgentToolError(RuntimeError):
    """Raised when an AI tool invocation fails."""


@dataclass
class ToolResult:
    content: str
    layout_changed: bool = False


@dataclass
class AgentToolContext:
    project: str
    load_layout: Callable[[str], Dict[str, Any]]
    save_layout: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    terminal_factory: Optional[Callable[[Dict[str, Any]], TerminalProcessor]] = None
    project_root: Optional[Path] = None
    project_media_dir: Optional[Path] = None
    allow_layout_edits: bool = False
    allow_web_search: bool = False
    web_search: Optional[Callable[[str, int], List[Dict[str, str]]]] = None
    web_image_search: Optional[Callable[[str, int], List[Dict[str, Any]]]] = None
    agent_view_mode: str = "document"  # Either "page" or "document"


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[[AgentToolContext, Dict[str, Any]], ToolResult]

    def spec(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


MAX_TOOL_RESPONSE = 16000
PROJECT_FILE_MAX_CHARS = 16_000
PROJECT_TREE_DEFAULT_MAX = 200
PROJECT_TREE_MAX_LIMIT = 800
PROJECT_TREE_MIN_DEPTH = 1
PROJECT_TREE_MAX_DEPTH = 6
PROJECT_SEARCH_MAX_MATCHES = 20
PROJECT_SEARCH_MIN_MATCHES = 3
PROJECT_SEARCH_MAX_FILE_BYTES = 512_000
PROJECT_SEARCH_SNIPPET_CHARS = 240
REMOTE_IMAGE_MAX_BYTES = 10_000_000
REMOTE_IMAGE_TIMEOUT = 12


def _truncate(text: str, limit: Optional[int]) -> str:
    snippet = (text or "").strip()
    if limit is None or limit <= 0:
        return snippet
    if len(snippet) <= limit:
        return snippet
    return f"{snippet[:limit]}… (+{len(snippet) - limit} more characters)"


def _summarize_layout(layout: Dict[str, Any]) -> str:
    pages = layout.get("pages") or []
    lines = [
        f"Layout now has {len(pages)} page(s) and {sum(len(p.get('blocks') or []) for p in pages)} total blocks."
    ]
    for page in pages[:6]:
        name = page.get("name") or page.get("id") or "Untitled"
        block_count = len(page.get("blocks") or [])
        lines.append(f"- {name}: {block_count} block{'s' if block_count != 1 else ''}")
    if len(pages) > 6:
        lines.append("- …additional pages omitted from summary…")
    return "\n".join(lines)


def _clamp_int(value: Any, *, default: int, min_value: int, max_value: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if number < min_value:
        return min_value
    if number > max_value:
        return max_value
    return number


def _require_project_root(context: AgentToolContext) -> Path:
    if context.project_root is None:
        raise AgentToolError("Project root is unavailable; launch Agent Mode to expose the project directory.")
    try:
        return context.project_root.resolve()
    except OSError as exc:  # pragma: no cover - filesystem guard
        raise AgentToolError(f"Unable to resolve project directory: {exc}") from exc


def _resolve_project_path(context: AgentToolContext, raw_path: str) -> Path:
    root = _require_project_root(context)
    relative_input = (raw_path or "").strip()
    if not relative_input:
        raise AgentToolError("'path' is required for this tool.")
    normalized = Path(relative_input.lstrip("/\\"))
    target = (root / normalized).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise AgentToolError("File path must stay inside the project directory.") from exc
    return target


def _ensure_edit_permission(context: AgentToolContext) -> None:
    if not context.allow_layout_edits:
        raise AgentToolError("Enable “Allow layout edits” in the agent options before running this tool.")


def _ensure_media_dir(context: AgentToolContext) -> Path:
    root = _require_project_root(context)
    media_dir = context.project_media_dir or (root / "media")
    try:
        media_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - filesystem guard
        raise AgentToolError(f"Unable to create media directory: {exc}") from exc
    return media_dir


def _is_hidden_name(name: str) -> bool:
    return name.startswith(".") and name not in {".", ".."}


def _path_contains_hidden(path: Path) -> bool:
    return any(_is_hidden_name(part) for part in path.parts)


def _format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _read_text_preview(path: Path, limit: int) -> str:
    try:
        data = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:  # pragma: no cover - filesystem guard
        raise AgentToolError(f"Unable to read {path.name}: {exc}") from exc
    return _truncate(data, limit)


def _handle_read_layout(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    layout = context.load_layout(context.project)
    pages = layout.get("pages") or []

    # If in page mode and no specific page is requested, only return the active page
    if context.agent_view_mode == "page" and not params.get("page_id") and params.get("page") is None and not params.get("block_id"):
        active_page_id = layout.get("activePageId")
        active_page = None

        # Find the active page
        for page in pages:
            if page.get("id") == active_page_id:
                active_page = page
                break

        # If no active page is set, use the first page
        if not active_page and pages:
            active_page = pages[0]

        # Create a layout-like object with only the active page
        if active_page:
            payload = {
                "columns": layout.get("columns"),
                "baseline": layout.get("baseline"),
                "gutter": layout.get("gutter"),
                "snap": layout.get("snap"),
                "zoom": layout.get("zoom"),
                "orientation": layout.get("orientation"),
                "format": layout.get("format"),
                "dimensions": layout.get("dimensions"),
                "pages": [deepcopy(active_page)],
                "activePageId": active_page.get("id"),
                "activePageName": active_page.get("name"),
                "totalPages": len(pages),
                "pageMode": True,  # Flag to indicate this is page-mode data
                "project": layout.get("project"),
            }
        else:
            # No active page exists, return minimal layout
            payload = {
                "columns": layout.get("columns"),
                "baseline": layout.get("baseline"),
                "gutter": layout.get("gutter"),
                "snap": layout.get("snap"),
                "zoom": layout.get("zoom"),
                "orientation": layout.get("orientation"),
                "format": layout.get("format"),
                "dimensions": layout.get("dimensions"),
                "pages": [],
                "activePageId": None,
                "activePageName": "No Active Page",
                "totalPages": len(pages),
                "pageMode": True,  # Flag to indicate this is page-mode data
                "project": layout.get("project"),
            }
    else:
        # Document mode behavior or when a specific page/block is requested
        payload: Any = deepcopy(layout)

        def _find_page_by_id(page_id: str) -> Optional[Dict[str, Any]]:
            for page in pages:
                if str(page.get("id")) == str(page_id):
                    return page
            return None

        def _find_page_by_number(page_number: int) -> Optional[Dict[str, Any]]:
            if page_number <= 0 or page_number > len(pages):
                return None
            return pages[page_number - 1]

        filter_block_id = params.get("block_id")
        filter_page_id = params.get("page_id")
        filter_page_number = params.get("page")

        resolved_page: Optional[Dict[str, Any]] = None
        if filter_page_id:
            resolved_page = _find_page_by_id(filter_page_id)
        elif filter_page_number is not None:
            try:
                resolved_page = _find_page_by_number(int(filter_page_number))
            except (TypeError, ValueError):
                resolved_page = None

        if filter_block_id:
            block_payload = None
            for page in pages:
                for block in page.get("blocks") or []:
                    if block.get("id") == filter_block_id:
                        block_payload = {
                            "page": {
                                "id": page.get("id"),
                                "name": page.get("name"),
                                "order": page.get("order"),
                                "index": pages.index(page) + 1 if pages else None,
                            },
                            "block": deepcopy(block),
                        }
                        break
                if block_payload:
                    break
            if block_payload:
                payload = block_payload
        elif resolved_page:
            payload = {
                "page": deepcopy(resolved_page),
                "page_index": pages.index(resolved_page) + 1 if resolved_page in pages else None,
                "project": layout.get("project"),
            }

    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    limit = params.get("max_chars")
    try:
        limit_value = int(limit) if limit is not None else None
    except (TypeError, ValueError):
        limit_value = None
    if limit_value is not None and limit_value < 0:
        limit_value = None
    if limit_value is not None:
        limit_value = max(limit_value, 512)
    return ToolResult(content=_truncate(serialized, limit_value))


def _coerce_layout_payload(data: Any) -> Dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
            raise AgentToolError(f"layout_json is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise AgentToolError("layout_json must decode to an object.")
        return parsed
    raise AgentToolError("Provide either a JSON string in 'layout_json' or an object in 'layout'.")


def _handle_write_layout(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    _ensure_edit_permission(context)
    if "layout" in params:
        layout_payload = params["layout"]
    elif "layout_json" in params:
        layout_payload = params["layout_json"]
    else:
        raise AgentToolError("Pass the updated layout as 'layout' (object) or 'layout_json' (string).")

    new_layout = _coerce_layout_payload(layout_payload)

    # If in page mode, we should merge only the pages part to avoid overwriting other pages
    if context.agent_view_mode == "page":
        current_layout = context.load_layout(context.project)

        # Update only the active page in the current layout
        active_page_id = current_layout.get("activePageId")
        new_pages = new_layout.get("pages", [])

        if new_pages and active_page_id:
            # Find and update the active page
            updated_pages = []
            page_updated = False

            for current_page in current_layout.get("pages", []):
                if current_page.get("id") == active_page_id:
                    # Update this active page with the new page data
                    if len(new_pages) > 0:  # Use the first page from the new layout
                        updated_page = deepcopy(new_pages[0])
                        updated_page["id"] = active_page_id  # Preserve the original ID
                        updated_pages.append(updated_page)
                        page_updated = True
                    else:
                        updated_pages.append(current_page)  # Keep unchanged if no new page data
                else:
                    updated_pages.append(current_page)  # Keep other pages unchanged

            # If the active page was not found, handle appropriately
            if not page_updated and len(new_pages) > 0:
                # The active page might not exist in the current layout, so add it
                new_page = deepcopy(new_pages[0])
                if not new_page.get("id"):
                    new_page["id"] = active_page_id
                updated_pages.append(new_page)
                page_updated = True

            # Update the current layout with the modified pages
            current_layout["pages"] = updated_pages
            # Preserve other important layout properties from the new layout
            for key in ["columns", "baseline", "gutter", "snap", "zoom", "orientation", "format", "dimensions"]:
                if key in new_layout:
                    current_layout[key] = new_layout[key]

            saved = context.save_layout(context.project, current_layout)
        else:
            # If there's no active page, just save the new layout as-is
            saved = context.save_layout(context.project, new_layout)
    else:
        # Document mode, save the entire layout as before
        saved = context.save_layout(context.project, new_layout)

    summary = _summarize_layout(saved)
    return ToolResult(content=f"layout.json saved successfully.\n{summary}", layout_changed=True)


def _handle_terminal_command(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    command = (params.get("command") or "").strip()
    if not command:
        raise AgentToolError("'command' is required when calling run_terminal_command.")
    if context.terminal_factory is None:
        raise AgentToolError("Terminal access is not available in this environment.")
    _ensure_edit_permission(context)
    layout = context.load_layout(context.project)
    processor = context.terminal_factory(deepcopy(layout))
    try:
        result = processor.run(command)
    except TerminalCommandError as exc:
        raise AgentToolError(str(exc)) from exc
    layout_changed = result.layout is not None
    if layout_changed:
        context.save_layout(context.project, result.layout)
    output = result.output or "Command completed."
    return ToolResult(content=_truncate(output, MAX_TOOL_RESPONSE), layout_changed=layout_changed)


def _handle_write_project_file(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    _ensure_edit_permission(context)
    path_value = (params.get("path") or "").strip()
    if not path_value:
        raise AgentToolError("'path' is required when writing a project file.")
    content = params.get("content")
    if not isinstance(content, str):
        raise AgentToolError("Provide the file contents as a string via 'content'.")
    append = bool(params.get("append"))
    target = _resolve_project_path(context, path_value)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with target.open(mode, encoding="utf-8") as handle:
            handle.write(content)
    except OSError as exc:  # pragma: no cover - filesystem guard
        raise AgentToolError(f"Unable to write file: {exc}") from exc
    operation = "Appended" if append else "Wrote"
    snippet = content[:200] + ("…" if len(content) > 200 else "")
    return ToolResult(content=f"{operation} {len(content)} characters to “{path_value}”.\nPreview:\n{snippet}")


def _handle_list_project_files(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    root = _require_project_root(context)
    depth = _clamp_int(
        params.get("depth"),
        default=3,
        min_value=PROJECT_TREE_MIN_DEPTH,
        max_value=PROJECT_TREE_MAX_DEPTH,
    )
    max_entries = _clamp_int(
        params.get("max_entries"),
        default=PROJECT_TREE_DEFAULT_MAX,
        min_value=20,
        max_value=PROJECT_TREE_MAX_LIMIT,
    )
    include_hidden = bool(params.get("include_hidden"))
    lines: List[str] = []
    listed = 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        depth_index = 0 if rel_dir == Path(".") else len(rel_dir.parts)
        dirnames[:] = sorted(
            [name for name in dirnames if include_hidden or not _is_hidden_name(name)]
        )
        visible_files = sorted(
            [name for name in filenames if include_hidden or not _is_hidden_name(name)]
        )
        label = context.project if depth_index == 0 else rel_dir.as_posix()
        lines.append(f"{'  ' * depth_index}{label}/")
        listed += 1
        if listed >= max_entries:
            break
        for filename in visible_files:
            target = Path(dirpath) / filename
            rel_file = target.relative_to(root).as_posix()
            try:
                size_label = _format_bytes(target.stat().st_size)
            except OSError:
                size_label = "?"
            lines.append(f"{'  ' * (depth_index + 1)}{rel_file} — {size_label}")
            listed += 1
            if listed >= max_entries:
                break
        if depth_index + 1 >= depth:
            dirnames[:] = []
        if listed >= max_entries:
            break
    if listed >= max_entries:
        lines.append(f"…stopped after {max_entries} entries. Increase 'max_entries' to see more.")
    return ToolResult(content=_truncate("\n".join(lines), MAX_TOOL_RESPONSE))


def _handle_read_project_file(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    target = _resolve_project_path(context, params.get("path") or "")
    if target.is_dir():
        raise AgentToolError("Target path is a directory. Provide a file path instead.")
    limit = _clamp_int(
        params.get("max_chars"),
        default=PROJECT_FILE_MAX_CHARS,
        min_value=256,
        max_value=MAX_TOOL_RESPONSE,
    )
    preview = _read_text_preview(target, limit)
    try:
        size_label = _format_bytes(target.stat().st_size)
    except OSError:
        size_label = "unknown size"
    header = f"{target.name} ({target.relative_to(_require_project_root(context))}) — {size_label}"
    return ToolResult(content=f"{header}\n{preview}")


def _safe_url_filename(url: str, fallback: str = "image") -> str:
    parsed = urllib.parse.urlparse(url)
    name = Path(parsed.path).name or fallback
    if "." not in name:
        return name
    stem, suffix = os.path.splitext(name)
    safe_stem = stem.strip() or fallback
    safe_suffix = suffix if suffix else ""
    return f"{safe_stem}{safe_suffix}"


def _download_remote_image(context: AgentToolContext, url: str, filename: Optional[str] = None) -> Path:
    media_dir = _ensure_media_dir(context)
    clean_url = (url or "").strip()
    if not clean_url:
        raise AgentToolError("'url' is required to download an image.")
    parsed = urllib.parse.urlparse(clean_url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise AgentToolError("Image URL must start with http or https.")
    request = urllib.request.Request(clean_url, headers={"User-Agent": "FyonaAgent/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=REMOTE_IMAGE_TIMEOUT) as response:
            info = response.info()
            mime_type = info.get_content_type()
            raw = response.read(REMOTE_IMAGE_MAX_BYTES + 2048)
    except urllib.error.HTTPError as exc:  # pragma: no cover - network guard
        raise AgentToolError(f"Download failed (HTTP {exc.code}).") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network guard
        raise AgentToolError(f"Download failed: {exc.reason}") from exc
    if len(raw) > REMOTE_IMAGE_MAX_BYTES:
        raise AgentToolError("Image is too large; limit is 10 MB.")
    ext = None
    if mime_type and mime_type != "application/octet-stream":
        ext = mimetypes.guess_extension(mime_type) or None
    name_hint = filename or _safe_url_filename(clean_url, "image")
    stem = Path(name_hint).stem or "image"
    suffix = Path(name_hint).suffix or ""
    if not suffix and ext:
        suffix = ext
    unique = f"{stem}-{uuid4().hex[:8]}{suffix or '.bin'}"
    target = media_dir / unique
    try:
        target.write_bytes(raw)
    except OSError as exc:  # pragma: no cover - filesystem guard
        raise AgentToolError(f"Unable to save image: {exc}") from exc
    return target


def _handle_search_project_files(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    root = _require_project_root(context)
    needle = (params.get("query") or "").strip()
    if not needle:
        raise AgentToolError("'query' is required when searching project files.")
    include_hidden = bool(params.get("include_hidden"))
    max_matches = _clamp_int(
        params.get("max_matches"),
        default=8,
        min_value=PROJECT_SEARCH_MIN_MATCHES,
        max_value=PROJECT_SEARCH_MAX_MATCHES,
    )
    matches: List[str] = []
    needle_lower = needle.lower()
    for path in sorted(root.rglob("*")):
        if len(matches) >= max_matches:
            break
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if not include_hidden and _path_contains_hidden(relative):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        if size > PROJECT_SEARCH_MAX_FILE_BYTES:
            continue
        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            contents = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        snippets: List[str] = []
        for line_number, line in enumerate(contents.splitlines(), 1):
            if needle_lower in line.lower():
                snippet = line.strip()
                if len(snippet) > PROJECT_SEARCH_SNIPPET_CHARS:
                    snippet = f"{snippet[:PROJECT_SEARCH_SNIPPET_CHARS]}…"
                snippets.append(f"  L{line_number}: {snippet}")
                if len(snippets) >= 3:
                    break
        if snippets:
            block = [relative.as_posix()]
            block.extend(snippets)
            matches.append("\n".join(block))
    if not matches:
        return ToolResult(content=f"No matches for “{needle}”. Try a different query or enable 'include_hidden'.")
    if len(matches) >= max_matches:
        matches.append(f"…stopped after {max_matches} files. Use 'max_matches' to scan more.")
    return ToolResult(content=_truncate("\n\n".join(matches), MAX_TOOL_RESPONSE))


def _handle_web_search(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    if not context.allow_web_search or context.web_search is None:
        raise AgentToolError("Enable Bing web search in the assistant options before using this tool.")
    query = (params.get("query") or "").strip()
    if not query:
        raise AgentToolError("'query' is required when calling web_search.")
    count = _clamp_int(params.get("count"), default=5, min_value=1, max_value=10)
    try:
        results = context.web_search(query, count)
    except AgentToolError:
        raise
    except Exception as exc:  # pragma: no cover - network and API guard
        raise AgentToolError(f"Bing search failed: {exc}") from exc
    if not results:
        return ToolResult(content=f"No Bing results for “{query}”.")
    lines: List[str] = [f"Bing search results for “{query}”:"]
    for index, item in enumerate(results, 1):
        title = item.get("title") or item.get("name") or f"Result {index}"
        url = item.get("url") or item.get("link") or ""
        snippet = (item.get("snippet") or item.get("description") or "").strip()
        entry = f"{index}. {title}"
        if url:
            entry += f"\n   {url}"
        if snippet:
            entry += f"\n   {snippet}"
        lines.append(entry)
    return ToolResult(content=_truncate("\n\n".join(lines), MAX_TOOL_RESPONSE))


def _handle_web_image_search(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    if not context.allow_web_search or context.web_image_search is None:
        raise AgentToolError("Enable Bing web search in the assistant options before using this tool.")
    query = (params.get("query") or "").strip()
    if not query:
        raise AgentToolError("'query' is required when calling web_image_search.")
    count = _clamp_int(params.get("count"), default=6, min_value=1, max_value=10)
    try:
        results = context.web_image_search(query, count)
    except AgentToolError:
        raise
    except Exception as exc:  # pragma: no cover - network and API guard
        raise AgentToolError(f"Bing image search failed: {exc}") from exc
    if not results:
        return ToolResult(content=f"No image results for “{query}”.")
    lines: List[str] = [f"Bing images for “{query}”:"]
    for index, item in enumerate(results, 1):
        title = item.get("title") or item.get("name") or f"Image {index}"
        thumb = item.get("thumbnail") or item.get("thumbnailUrl") or ""
        url = item.get("url") or item.get("contentUrl") or ""
        size = ""
        if item.get("width") and item.get("height"):
            size = f"{item['width']}×{item['height']}"
        entry = f"{index}. {title}"
        if size:
            entry += f" ({size})"
        if url:
            entry += f"\n   {url}"
        if thumb and thumb != url:
            entry += f"\n   preview: {thumb}"
        lines.append(entry)
    return ToolResult(content=_truncate("\n\n".join(lines), MAX_TOOL_RESPONSE))


def _handle_save_remote_image(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    _ensure_edit_permission(context)
    url = params.get("url") or ""
    filename = params.get("filename")
    block_id = params.get("block_id")
    target = _download_remote_image(context, url, filename)
    saved_url = f"/project-assets/{context.project}/{target.name}"
    detail_lines = [f"Saved image to media/{target.name}", f"URL: {saved_url}"]
    layout_changed = False
    if block_id:
        layout = context.load_layout(context.project)
        pages = layout.get("pages") or []
        owning_page = None
        target_block = None
        for page in pages:
            for block in page.get("blocks") or []:
                if block.get("id") == block_id:
                    owning_page = page
                    target_block = block
                    break
            if target_block:
                break
        if target_block:
            block_type = (target_block.get("type") or "").lower()
            if block_type != "image":
                detail_lines.append(f"Note: block {block_id} is type '{block_type or 'unknown'}'; layout not updated.")
            else:
                target_block["imageUrl"] = saved_url
                if not target_block.get("content"):
                    target_block["content"] = target.name
                saved_layout = context.save_layout(context.project, layout)
                summary = _summarize_layout(saved_layout)
                detail_lines.append(f"Linked to image block {block_id}.")
                detail_lines.append(summary)
                layout_changed = True
        else:
            detail_lines.append(f"Note: block {block_id} was not found; layout not updated.")
    return ToolResult(content="\n".join(detail_lines), layout_changed=layout_changed)


class AgentToolset:
    """Registry of function-callable tools for the AI agent."""

    def __init__(self, context: AgentToolContext):
        self.context = context
        tool_definitions: List[ToolDefinition] = [
            ToolDefinition(
                name="read_layout_file",
                description="Read the normalized layout.json for the current project.",
                parameters={
                    "type": "object",
                    "properties": {
                        "max_chars": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Optional limit for the size of the JSON snippet; set to 0 to disable truncation.",
                        },
                        "page": {
                            "type": "integer",
                            "minimum": 1,
                            "description": "Return only this 1-indexed page from the document.",
                        },
                        "page_id": {
                            "type": "string",
                            "description": "Return only the page whose ID matches this value.",
                        },
                        "block_id": {
                            "type": "string",
                            "description": "Return only the block (plus page context) with this ID.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=_handle_read_layout,
            ),
            ToolDefinition(
                name="write_layout_file",
                description=(
                    "Overwrite layout.json with a new JSON object. Provide either a serialized string via "
                    "'layout_json' or a structured object via 'layout'."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "layout_json": {"type": "string", "description": "Complete layout JSON as a string."},
                        "layout": {"type": "object", "description": "Complete layout object."},
                    },
                    "additionalProperties": False,
                },
                handler=_handle_write_layout,
            ),
            ToolDefinition(
                name="run_terminal_command",
                description=(
                    "Execute a Fyona terminal command (e.g., add text blocks, run `pages`, or `echo 2` to review captions)."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Exact terminal command to run, such as 'add --text \"Title\" --position (120,80)'.",
                        }
                    },
                    "required": ["command"],
                },
                handler=_handle_terminal_command,
            ),
            ToolDefinition(
                name="write_project_file",
                description=(
                    "Write or append text to a file inside the current project. "
                    "Useful for applying code fixes directly instead of returning patches."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path (inside the project directory) to write.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Exact file contents to write.",
                        },
                        "append": {
                            "type": "boolean",
                            "description": "Set true to append instead of replacing the file.",
                        },
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
                handler=_handle_write_project_file,
            ),
            ToolDefinition(
                name="list_project_files",
                description="List folders and files inside the project workspace.",
                parameters={
                    "type": "object",
                    "properties": {
                        "depth": {
                            "type": "integer",
                            "minimum": PROJECT_TREE_MIN_DEPTH,
                            "maximum": PROJECT_TREE_MAX_DEPTH,
                            "description": "How many directory levels to include (default 3).",
                        },
                        "max_entries": {
                            "type": "integer",
                            "minimum": 20,
                            "maximum": PROJECT_TREE_MAX_LIMIT,
                            "description": "Maximum items to include in the listing (default 200).",
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "Set true to include dotfiles and dot-directories.",
                        },
                    },
                    "additionalProperties": False,
                },
                handler=_handle_list_project_files,
            ),
            ToolDefinition(
                name="read_project_file",
                description="Read a text file from the project directory (UTF-8 preview).",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative file path to open.",
                        },
                        "max_chars": {
                            "type": "integer",
                            "minimum": 256,
                            "maximum": MAX_TOOL_RESPONSE,
                            "description": "Limit for the returned preview (default 16,000).",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
                handler=_handle_read_project_file,
            ),
            ToolDefinition(
                name="search_project_files",
                description="Find text matches across project files (UTF-8 only).",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Text to search for (case-insensitive).",
                        },
                        "max_matches": {
                            "type": "integer",
                            "minimum": PROJECT_SEARCH_MIN_MATCHES,
                            "maximum": PROJECT_SEARCH_MAX_MATCHES,
                            "description": "Maximum files to report (default 8).",
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "Include dotfiles while searching.",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
                handler=_handle_search_project_files,
            ),
            ToolDefinition(
                name="save_remote_image",
                description="Download an image from a URL into the project's media folder. Optionally attach it to an image block.",
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "HTTP or HTTPS URL of the image to download.",
                        },
                        "filename": {
                            "type": "string",
                            "description": "Preferred filename (extension optional).",
                        },
                        "block_id": {
                            "type": "string",
                            "description": "Optional block ID to link the downloaded image to.",
                        },
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
                handler=_handle_save_remote_image,
            ),
        ]
        if context.web_search is not None and context.allow_web_search:
            tool_definitions.append(
                ToolDefinition(
                    name="web_search",
                    description="Search the web via Bing and return the top organic results.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search phrase to send to Bing."},
                            "count": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 10,
                                "description": "Maximum number of results to return (default 5).",
                            },
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                    handler=_handle_web_search,
                )
            )
            if context.web_image_search is not None:
                tool_definitions.append(
                    ToolDefinition(
                        name="web_image_search",
                        description="Search Bing Images and return direct image URLs plus thumbnails.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Describe the image you need."},
                                "count": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 10,
                                    "description": "Maximum number of results to return (default 6).",
                                },
                            },
                            "required": ["query"],
                            "additionalProperties": False,
                        },
                        handler=_handle_web_image_search,
                    )
                )
        self._tools: Dict[str, ToolDefinition] = {tool.name: tool for tool in tool_definitions}

    @property
    def specs(self) -> List[Dict[str, Any]]:
        return [tool.spec() for tool in self._tools.values()]

    def invoke(self, tool_name: str, arg_json: Optional[str]) -> ToolResult:
        tool = self._tools.get(tool_name)
        if tool is None:
            raise AgentToolError(f"Unknown tool '{tool_name}'.")
        if arg_json and isinstance(arg_json, dict):  # pragma: no cover - defensive fallback
            params = arg_json
        else:
            raw_arguments = arg_json or "{}"
            try:
                params = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise AgentToolError(f"Invalid JSON arguments for {tool_name}: {exc}") from exc
        return tool.handler(self.context, params)
