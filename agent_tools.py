"""
Agent tool helpers for Fiona's layout assistant.

This module defines the tool schema exposed to the chat model and provides
lightweight utilities to mutate a magazine layout in response to tool calls.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DEFAULT_LAYER_ID = "layer-main"
DEFAULT_LAYER_NAME = "Layer 1"
DEFAULT_COLUMNS = 3
DEFAULT_BASELINE = 24
DEFAULT_GUTTER = 32
DEFAULT_ORIENTATION = "portrait"
DEFAULT_FORMAT = "A4"
DEFAULT_CHAT_THEME = {
    "assistant": {
        "background": "rgba(255, 255, 255, 0.14)",
        "borderColor": "rgba(255, 255, 255, 0.18)",
        "textColor": "#f9fbff",
        "fontSize": 15.2,
        "maxWidth": 96.0,
        "alignment": "left",
    },
    "user": {
        "background": "linear-gradient(135deg, rgba(98, 208, 255, 0.32), rgba(56, 128, 255, 0.38))",
        "borderColor": "rgba(130, 210, 255, 0.45)",
        "textColor": "#f5faff",
        "fontSize": 15.2,
        "maxWidth": 96.0,
        "alignment": "right",
    },
}
CHAT_ALIGNMENTS = {"left", "center", "right"}


def _coerce_float(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    if not number and number != 0:
        return float(fallback)
    return float(number)


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return int(fallback)
    return int(number)


def _normalize_block_id(value: Any, fallback_prefix: str = "block") -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback_prefix
    normalized = re.sub(r"[^0-9a-zA-Z._-]+", "-", text).strip(".-_")
    if not normalized:
        normalized = fallback_prefix
    return normalized[:64]


def _ensure_layer_payload(layer: Dict[str, Any], order: int) -> Dict[str, Any]:
    identifier = str(layer.get("id") or "").strip() or DEFAULT_LAYER_ID
    name = str(layer.get("name") or "").strip() or DEFAULT_LAYER_NAME
    return {
        "id": identifier,
        "name": name,
        "order": order,
    }


def _default_layout(project: str) -> Dict[str, Any]:
    return {
        "project": project,
        "columns": DEFAULT_COLUMNS,
        "baseline": DEFAULT_BASELINE,
        "gutter": DEFAULT_GUTTER,
        "snap": True,
        "zoom": 1.0,
        "orientation": DEFAULT_ORIENTATION,
        "format": DEFAULT_FORMAT,
        "dimensions": {"width": 794, "height": 1123},
        "blocks": [],
        "layers": [
            {
                "id": DEFAULT_LAYER_ID,
                "name": DEFAULT_LAYER_NAME,
                "order": 0,
            }
        ],
        "activeLayer": DEFAULT_LAYER_ID,
        "chatTheme": deepcopy(DEFAULT_CHAT_THEME),
    }


def _sanitize_position(position: Optional[Dict[str, Any]]) -> Dict[str, float]:
    position = position or {}
    return {
        "left": _coerce_float(position.get("left"), 96),
        "top": _coerce_float(position.get("top"), 96),
        "width": _coerce_float(position.get("width"), 320),
        "height": _coerce_float(position.get("height"), 200),
    }


def _sanitize_typography(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    typography: Dict[str, Any] = {}
    if "fontSize" in payload:
        typography["fontSize"] = _coerce_float(payload["fontSize"], 18)
    if "lineHeight" in payload:
        typography["lineHeight"] = _coerce_float(payload["lineHeight"], 1.4)
    if "textAlign" in payload:
        typography["textAlign"] = str(payload["textAlign"]).strip().lower() or "left"
    if "textColor" in payload:
        typography["textColor"] = str(payload["textColor"]).strip()
    if "uppercase" in payload:
        typography["uppercase"] = bool(payload["uppercase"])
    return typography or None


def _select_layer_identifier(requested: Optional[str], layers: List[Dict[str, Any]]) -> str:
    if isinstance(requested, str) and requested.strip():
        candidate = requested.strip()
        for layer in layers:
            if layer.get("id") == candidate:
                return candidate
    if layers:
        return str(layers[0].get("id") or DEFAULT_LAYER_ID)
    return DEFAULT_LAYER_ID


def _sanitize_alignment(value: Any, fallback: str) -> str:
    if isinstance(value, str):
        token = value.strip().lower()
        if token in CHAT_ALIGNMENTS:
            return token
    return fallback


def _sanitize_max_width(value: Any, fallback: float) -> float:
    number = _coerce_float(value, fallback)
    return max(10.0, min(number, 100.0))


def _normalize_chat_theme(theme: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    base = deepcopy(DEFAULT_CHAT_THEME)
    if not isinstance(theme, dict):
        return base
    for role in ("assistant", "user"):
        current = theme.get(role)
        if not isinstance(current, dict):
            continue
        role_theme = base[role]
        if current.get("background") is not None:
            role_theme["background"] = str(current["background"])
        if current.get("borderColor") is not None:
            role_theme["borderColor"] = str(current["borderColor"])
        if current.get("textColor") is not None:
            role_theme["textColor"] = str(current["textColor"])
        if "fontSize" in current:
            role_theme["fontSize"] = max(8.0, min(_coerce_float(current["fontSize"], role_theme["fontSize"]), 48.0))
        if "maxWidth" in current:
            role_theme["maxWidth"] = _sanitize_max_width(current["maxWidth"], role_theme["maxWidth"])
        if "alignment" in current:
            role_theme["alignment"] = _sanitize_alignment(current["alignment"], role_theme["alignment"])
    return base


@dataclass
class ToolEvent:
    """Represents an executed tool call for UI summaries."""

    type: str
    description: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "description": self.description,
            "payload": self.payload,
        }


class LayoutSession:
    """
    Mutable view of the layout during a chat interaction.

    Tool handlers update this structure and record events so the caller can
    persist or discard the new state after the model finishes responding.
    """

    def __init__(self, layout: Optional[Dict[str, Any]], *, project: str) -> None:
        base = _default_layout(project)
        if isinstance(layout, dict):
            merged = deepcopy(layout)
            base.update({k: merged.get(k, v) for k, v in base.items() if k != "blocks"})
            base["blocks"] = deepcopy(merged.get("blocks") or [])
            layers = merged.get("layers")
            if isinstance(layers, list) and layers:
                base["layers"] = [
                    _ensure_layer_payload(layer, index)
                    for index, layer in enumerate(layers)
                    if isinstance(layer, dict)
                ] or base["layers"]
            base["activeLayer"] = str(merged.get("activeLayer") or base["layers"][0]["id"])
            base["chatTheme"] = _normalize_chat_theme(merged.get("chatTheme"))
        self.project = project
        self.layout = base
        self.modified = False
        self.events: List[ToolEvent] = []

    # ------------------------------------------------------------------ utils
    def _mark_modified(self, event: ToolEvent) -> None:
        self.modified = True
        self.events.append(event)

    def _next_unique_id(self, preferred: Optional[str] = None) -> str:
        existing = {block.get("id") for block in self.layout["blocks"]}
        base_id = _normalize_block_id(preferred, "block")
        if base_id not in existing:
            return base_id
        counter = 2
        while True:
            candidate = f"{base_id}-{counter}"
            if candidate not in existing:
                return candidate
            counter += 1

    def _find_block(self, block_id: str) -> Optional[Dict[str, Any]]:
        for block in self.layout["blocks"]:
            if block.get("id") == block_id:
                return block
        return None

    def _ensure_layer(self, layer_id: str, name: Optional[str] = None) -> str:
        layers = self.layout["layers"]
        for layer in layers:
            if layer.get("id") == layer_id:
                if name:
                    layer["name"] = name
                return layer_id
        layer_payload = _ensure_layer_payload({"id": layer_id, "name": name}, len(layers))
        layers.append(layer_payload)
        return layer_payload["id"]

    # ---------------------------------------------------------------- handlers
    def create_block(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        block_type = str(payload.get("type") or payload.get("block_type") or "body").strip().lower()
        if not block_type:
            block_type = "body"
        block_id = self._next_unique_id(payload.get("id"))
        position = _sanitize_position(payload.get("position"))
        typography = _sanitize_typography(payload.get("typography"))
        target_layer = self._ensure_layer(
            _select_layer_identifier(payload.get("layer"), self.layout["layers"])
        )

        block = {
            "id": block_id,
            "type": block_type,
            "position": position,
            "rotation": _coerce_float(payload.get("rotation"), 0),
            "locked": bool(payload.get("locked", False)),
            "layer": target_layer,
            "layerZ": _coerce_int(payload.get("layerZ"), 0),
            "opacity": max(0.05, min(_coerce_float(payload.get("opacity"), 1.0), 1.0)),
            "background": str(payload.get("background") or "").strip(),
            "typography": typography,
            "content": payload.get("content"),
        }
        self.layout["blocks"].append(block)
        self._mark_modified(
            ToolEvent(
                type="create_block",
                description=f"Added {block_type} block “{block_id}”.",
                payload={"blockId": block_id, "layer": target_layer},
            )
        )
        return {"status": "success", "block": block}

    def update_block(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        block_id = str(payload.get("id") or payload.get("block_id") or "").strip()
        if not block_id:
            return {"status": "error", "error": "block id required"}
        block = self._find_block(block_id)
        if not block:
            return {"status": "error", "error": f"block '{block_id}' not found"}

        if "type" in payload or "block_type" in payload:
            block["type"] = str(payload.get("type") or payload.get("block_type") or block["type"]).strip().lower()
        if payload.get("position"):
            block["position"] = _sanitize_position(payload["position"])
        if "rotation" in payload:
            block["rotation"] = _coerce_float(payload["rotation"], block.get("rotation", 0))
        if "locked" in payload:
            block["locked"] = bool(payload["locked"])
        if "layer" in payload:
            block["layer"] = self._ensure_layer(str(payload["layer"]).strip() or DEFAULT_LAYER_ID)
        if "layerZ" in payload:
            block["layerZ"] = _coerce_int(payload["layerZ"], block.get("layerZ", 0))
        if "opacity" in payload:
            block["opacity"] = max(0.05, min(_coerce_float(payload["opacity"], block.get("opacity", 1.0)), 1.0))
        if "background" in payload:
            block["background"] = str(payload["background"]).strip()
        if "content" in payload:
            block["content"] = payload["content"]
        if "typography" in payload:
            block["typography"] = _sanitize_typography(payload["typography"])

        self._mark_modified(
            ToolEvent(
                type="update_block",
                description=f"Updated block “{block_id}”.",
                payload={"blockId": block_id},
            )
        )
        return {"status": "success", "block": block}

    def delete_block(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        block_id = str(payload.get("id") or payload.get("block_id") or "").strip()
        if not block_id:
            return {"status": "error", "error": "block id required"}
        before = len(self.layout["blocks"])
        self.layout["blocks"] = [block for block in self.layout["blocks"] if block.get("id") != block_id]
        if len(self.layout["blocks"]) == before:
            return {"status": "error", "error": f"block '{block_id}' not found"}
        self._mark_modified(
            ToolEvent(
                type="delete_block",
                description=f"Deleted block “{block_id}”.",
                payload={"blockId": block_id},
            )
        )
        return {"status": "success"}

    def update_layout(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        layout = self.layout
        if "columns" in payload:
            layout["columns"] = max(1, min(_coerce_int(payload["columns"], layout.get("columns", DEFAULT_COLUMNS)), 12))
        if "baseline" in payload:
            layout["baseline"] = max(4, min(_coerce_int(payload["baseline"], layout.get("baseline", DEFAULT_BASELINE)), 64))
        if "gutter" in payload:
            layout["gutter"] = max(0, min(_coerce_int(payload["gutter"], layout.get("gutter", DEFAULT_GUTTER)), 256))
        if "snap" in payload:
            layout["snap"] = bool(payload["snap"])
        if "orientation" in payload:
            layout["orientation"] = str(payload["orientation"]).strip().lower() or layout.get("orientation", DEFAULT_ORIENTATION)
        if "format" in payload:
            layout["format"] = str(payload["format"]).strip() or layout.get("format", DEFAULT_FORMAT)
        if "dimensions" in payload and isinstance(payload["dimensions"], dict):
            width = _coerce_float(payload["dimensions"].get("width"), layout["dimensions"]["width"])
            height = _coerce_float(payload["dimensions"].get("height"), layout["dimensions"]["height"])
            layout["dimensions"] = {"width": max(120, width), "height": max(120, height)}
        if "activeLayer" in payload:
            layout["activeLayer"] = self._ensure_layer(str(payload["activeLayer"]).strip() or DEFAULT_LAYER_ID)
        self._mark_modified(
            ToolEvent(
                type="update_layout",
                description="Adjusted layout settings.",
                payload={
                    key: layout.get(key)
                    for key in ("columns", "baseline", "gutter", "orientation", "format")
                },
            )
        )
        return {"status": "success", "layout": layout}

    def ensure_layer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        layer_id = str(payload.get("id") or "").strip()
        name = str(payload.get("name") or "").strip() or None
        if not layer_id:
            layer_id = _normalize_block_id(name or DEFAULT_LAYER_ID, "layer")
        identifier = self._ensure_layer(layer_id, name)
        self._mark_modified(
            ToolEvent(
                type="ensure_layer",
                description=f"Ensured layer “{identifier}”.",
                payload={"layerId": identifier},
            )
        )
        return {"status": "success", "layer": identifier}

    def snapshot(self) -> Dict[str, Any]:
        return deepcopy(self.layout)

    def style_chat_bubble(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        role = str(payload.get("target") or "assistant").strip().lower()
        if role not in {"assistant", "user", "both", "all"}:
            role = "assistant"
        targets = ["assistant", "user"] if role in {"both", "all"} else [role]
        theme = self.layout.setdefault("chatTheme", deepcopy(DEFAULT_CHAT_THEME))
        theme = _normalize_chat_theme(theme)
        self.layout["chatTheme"] = theme

        for target in targets:
            bubble_theme = theme[target]
            if payload.get("background") is not None:
                bubble_theme["background"] = str(payload["background"])
            if payload.get("borderColor") is not None:
                bubble_theme["borderColor"] = str(payload["borderColor"])
            if payload.get("textColor") is not None:
                bubble_theme["textColor"] = str(payload["textColor"])
            if payload.get("fontSize") is not None:
                bubble_theme["fontSize"] = max(8.0, min(_coerce_float(payload["fontSize"], bubble_theme["fontSize"]), 48.0))
            if payload.get("maxWidth") is not None:
                bubble_theme["maxWidth"] = _sanitize_max_width(payload["maxWidth"], bubble_theme["maxWidth"])
            if payload.get("alignment") is not None:
                bubble_theme["alignment"] = _sanitize_alignment(payload["alignment"], bubble_theme["alignment"])

        self._mark_modified(
            ToolEvent(
                type="style_chat_bubble",
                description=f"Updated chat bubble styling for {', '.join(targets)}.",
                payload={"targets": targets},
            )
        )
        return {"status": "success", "chatTheme": theme}

    # --------------------------------------------------------------- execution
    def execute_tool(self, name: str, arguments: Dict[str, Any], call_id: Optional[str] = None) -> Dict[str, Any]:
        handlers = {
            "create_block": self.create_block,
            "update_block": self.update_block,
            "delete_block": self.delete_block,
            "update_layout": self.update_layout,
            "ensure_layer": self.ensure_layer,
            "style_chat_bubble": self.style_chat_bubble,
        }
        handler = handlers.get(name)
        if not handler:
            return {"status": "error", "error": f"unknown tool '{name}'"}
        return handler(arguments or {})


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_block",
            "description": "Insert a new block onto the canvas with optional text, colors, and placement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Optional preferred block id."},
                    "type": {
                        "type": "string",
                        "description": "Block type such as headline, body, image, pullquote, sidebar, caption, stat.",
                    },
                    "content": {"type": ["string", "null"], "description": "HTML/text content for text blocks."},
                    "background": {"type": "string", "description": "CSS color for block background."},
                    "position": {
                        "type": "object",
                        "properties": {
                            "left": {"type": "number", "description": "Left offset in pixels."},
                            "top": {"type": "number", "description": "Top offset in pixels."},
                            "width": {"type": "number", "description": "Block width in pixels."},
                            "height": {"type": "number", "description": "Block height in pixels."},
                        },
                    },
                    "layer": {"type": "string", "description": "Target layer id."},
                    "rotation": {"type": "number", "description": "Rotation in degrees."},
                    "opacity": {"type": "number", "description": "Opacity between 0 and 1."},
                    "typography": {
                        "type": "object",
                        "properties": {
                            "fontSize": {"type": "number"},
                            "lineHeight": {"type": "number"},
                            "textAlign": {"type": "string"},
                            "textColor": {"type": "string"},
                            "uppercase": {"type": "boolean"},
                        },
                    },
                },
                "required": ["type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_block",
            "description": "Modify an existing block's sizing, styling, or content by id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "ID of the block to update."},
                    "type": {"type": "string", "description": "New block type."},
                    "content": {"type": ["string", "null"], "description": "Replacement HTML/text content."},
                    "background": {"type": "string", "description": "CSS background color."},
                    "position": {
                        "type": "object",
                        "properties": {
                            "left": {"type": "number"},
                            "top": {"type": "number"},
                            "width": {"type": "number"},
                            "height": {"type": "number"},
                        },
                    },
                    "rotation": {"type": "number"},
                    "locked": {"type": "boolean"},
                    "layer": {"type": "string"},
                    "layerZ": {"type": "integer"},
                    "opacity": {"type": "number"},
                    "typography": {
                        "type": "object",
                        "properties": {
                            "fontSize": {"type": "number"},
                            "lineHeight": {"type": "number"},
                            "textAlign": {"type": "string"},
                            "textColor": {"type": "string"},
                            "uppercase": {"type": "boolean"},
                        },
                    },
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_block",
            "description": "Remove a block from the layout by id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "ID of the block to delete."},
                },
                "required": ["id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ensure_layer",
            "description": "Create or rename a layer to organize blocks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Layer identifier."},
                    "name": {"type": "string", "description": "Display name for the layer."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_layout",
            "description": "Adjust global layout settings such as columns, gutters, or orientation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "columns": {"type": "integer", "minimum": 1, "maximum": 12},
                    "baseline": {"type": "integer", "description": "Baseline grid step in pixels."},
                    "gutter": {"type": "integer", "description": "Column gutter width."},
                    "snap": {"type": "boolean"},
                    "orientation": {"type": "string", "description": "portrait or landscape."},
                    "format": {"type": "string", "description": "Page format label such as A4."},
                    "dimensions": {
                        "type": "object",
                        "properties": {
                            "width": {"type": "number", "description": "Canvas width in pixels."},
                            "height": {"type": "number", "description": "Canvas height in pixels."},
                        },
                    },
                    "activeLayer": {"type": "string", "description": "Active layer id."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "style_chat_bubble",
            "description": "Adjust chat transcript bubble styling, including colors, font size, and alignment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["assistant", "user", "both", "all"],
                        "description": "Which bubble group to style.",
                    },
                    "background": {"type": "string", "description": "CSS color or gradient for the bubble background."},
                    "borderColor": {"type": "string", "description": "CSS color for bubble borders."},
                    "textColor": {"type": "string", "description": "CSS color for bubble text."},
                    "fontSize": {"type": "number", "description": "Font size in pixels."},
                    "maxWidth": {
                        "type": "number",
                        "minimum": 10,
                        "maximum": 100,
                        "description": "Bubble width as a percentage of the panel.",
                    },
                    "alignment": {
                        "type": "string",
                        "enum": ["left", "center", "right"],
                        "description": "Horizontal alignment of the bubble.",
                    },
                },
            },
        },
    },
]


def summarize_events(events: List[ToolEvent]) -> str:
    """
    Produce a plain-text summary suitable for displaying under the assistant reply.
    """
    if not events:
        return ""
    lines = ["Agent actions:"]
    for event in events:
        lines.append(f"- {event.description}")
    return "\n".join(lines)


__all__ = [
    "LayoutSession",
    "TOOL_DEFINITIONS",
    "summarize_events",
    "DEFAULT_CHAT_THEME",
]
