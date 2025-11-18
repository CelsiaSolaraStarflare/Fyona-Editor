from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
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


MAX_LAYOUT_CHARS = 20000
MAX_TOOL_RESPONSE = 16000


def _truncate(text: str, limit: int) -> str:
    snippet = (text or "").strip()
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
    serialized = json.dumps(layout, indent=2, ensure_ascii=False)
    limit = params.get("max_chars")
    try:
        limit_value = int(limit) if limit is not None else MAX_LAYOUT_CHARS
    except (TypeError, ValueError):
        limit_value = MAX_LAYOUT_CHARS
    return ToolResult(content=_truncate(serialized, max(limit_value, 512)))


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
                                "minimum": 256,
                                "maximum": 60000,
                                "description": "Limit for the size of the JSON snippet to return.",
                            }
                        },
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
                        "Execute a Fyona terminal command (e.g., add text blocks) to mutate the current layout."
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

