from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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


def _handle_read_layout(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    layout = context.load_layout(context.project)
    pages = layout.get("pages") or []
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
    if "layout" in params:
        layout_payload = params["layout"]
    elif "layout_json" in params:
        layout_payload = params["layout_json"]
    else:
        raise AgentToolError("Pass the updated layout as 'layout' (object) or 'layout_json' (string).")
    layout = _coerce_layout_payload(layout_payload)
    saved = context.save_layout(context.project, layout)
    summary = _summarize_layout(saved)
    return ToolResult(content=f"layout.json saved successfully.\n{summary}", layout_changed=True)


def _handle_terminal_command(context: AgentToolContext, params: Dict[str, Any]) -> ToolResult:
    command = (params.get("command") or "").strip()
    if not command:
        raise AgentToolError("'command' is required when calling run_terminal_command.")
    if context.terminal_factory is None:
        raise AgentToolError("Terminal access is not available in this environment.")
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
    root = context.project_root
    if root is None:
        raise AgentToolError("Project root is unavailable; cannot write files.")
    path_value = (params.get("path") or "").strip()
    if not path_value:
        raise AgentToolError("'path' is required when writing a project file.")
    content = params.get("content")
    if not isinstance(content, str):
        raise AgentToolError("Provide the file contents as a string via 'content'.")
    append = bool(params.get("append"))
    target = (root / path_value).resolve()
    try:
        root_resolved = root.resolve()
    except OSError as exc:  # pragma: no cover - filesystem guard
        raise AgentToolError(f"Unable to access project root: {exc}") from exc
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise AgentToolError("File path must stay inside the project directory.") from exc
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


class AgentToolset:
    """Registry of function-callable tools for the AI agent."""

    def __init__(self, context: AgentToolContext):
        self.context = context
        self._tools: Dict[str, ToolDefinition] = {
            tool.name: tool
            for tool in (
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
                                "description": "Exact terminal command to run, such as 'add --text ""Title"" --position (120,80)'.",
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
            )
        }

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
