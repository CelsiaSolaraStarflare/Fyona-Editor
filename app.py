import base64
import io
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory, url_for
from werkzeug.utils import secure_filename

from export_formats import ExportFormatError, export_layout
from pdf_export import PdfExportError
from raster_export import rasterize_layout

app = Flask(__name__, template_folder="templates", static_folder="static")

BASE_DIR = Path(app.root_path)
PROJECTS_ROOT = BASE_DIR / "projects"
DEFAULT_PROJECT = "default"
ASSET_ROUTE = "serve_project_asset"
CHAT_ATTACHMENT_LIMIT = 6
MAX_AGENT_FILES = 24
MAX_AGENT_BYTES = 8_192

PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)

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
    "layers": [
        {
            "id": "layer-main",
            "name": "Layer 1",
            "order": 0,
        }
    ],
    "activeLayer": "layer-main",
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


def layout_path(name: str) -> Path:
    return project_dir(name) / "layout.json"


def media_dir(name: str) -> Path:
    folder = project_dir(name) / "media"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


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
        result["typography"] = dict(typography)

    extra_keys = set(block.keys()) - {"id", "type", "content", "position", "backgroundColor", "textColor", "borderRadius", "imageUrl", "typography"}
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


def normalize_layout(data: Dict[str, Any], project_name: str) -> Dict[str, Any]:
    layout = deepcopy(DEFAULT_LAYOUT)
    layout.update({k: v for k, v in data.items() if k != "blocks"})
    layout["project"] = project_name

    incoming_blocks: Iterable[Dict[str, Any]] = data.get("blocks") or []
    layout["blocks"] = [normalize_block(block) for block in incoming_blocks if isinstance(block, dict)]
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
    if typography is not None and not isinstance(typography, dict):
        block.pop("typography", None)


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
    files = _gather_agent_files(root)
    return {
        "project": project,
        "tree": tree_text,
        "filesIndexed": stats["files"],
        "directoriesIndexed": stats["dirs"],
        "files": files,
        "layout": layout,
    }


def _generate_chat_reply(message: str, attachments: List[Dict[str, Any]], agent_snapshot: Optional[Dict[str, Any]]) -> str:
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
    return " ".join(sections)


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/projects", methods=["GET"])
def list_projects():
    projects = {DEFAULT_PROJECT}
    projects.update({p.name for p in PROJECTS_ROOT.iterdir() if p.is_dir()})
    return jsonify({"projects": sorted(projects)})


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
    blocks = layout.setdefault("blocks", [])

    if operation == "add":
        block_data = payload.get("block")
        if not isinstance(block_data, dict):
            return jsonify({"success": False, "error": "block must be an object"}), 400

        new_block = normalize_block(block_data)
        while locate_block(blocks, new_block["id"]):
            new_block["id"] = _generate_block_id()
        blocks.append(new_block)
        save_layout(project, layout)
        return jsonify({"success": True, "block": new_block})

    block_id = payload.get("block_id")
    if not isinstance(block_id, str) or not block_id.strip():
        return jsonify({"success": False, "error": "block_id is required"}), 400

    block = locate_block(blocks, block_id)
    if not block:
        return jsonify({"success": False, "error": "block not found"}), 404

    if operation == "delete":
        layout["blocks"] = [b for b in blocks if b.get("id") != block_id]
        save_layout(project, layout)
        return jsonify({"success": True})

    updates = payload.get("updates")
    if not isinstance(updates, dict):
        return jsonify({"success": False, "error": "updates must be an object"}), 400

    deep_merge(block, updates)
    _sanitize_block_after_update(block)
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
    if block_id:
        layout = load_layout(project)
        block = locate_block(layout.get("blocks", []), block_id)
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


@app.route("/api/chat", methods=["POST"])
def chat_assistant():
    payload = request.get_json(silent=True) or {}
    project = sanitize_project(payload.get("project") or DEFAULT_PROJECT)
    message = (payload.get("message") or "").strip()
    attachments_raw = payload.get("attachments") or []
    agent_mode = bool(payload.get("agentMode"))

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
    if agent_mode:
        if isinstance(client_snapshot, dict):
            agent_snapshot = client_snapshot
        else:
            agent_snapshot = _build_project_snapshot(project)
    layout = agent_snapshot["layout"] if agent_snapshot else load_layout(project)
    reply = _generate_chat_reply(message, attachments, agent_snapshot)
    return jsonify(
        {
            "success": True,
            "reply": reply,
            "agentSnapshot": agent_snapshot,
            "summary": {
                "project": project,
                "blocks": len(layout.get("blocks", [])),
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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
