#!/usr/bin/env python3
"""
Utility to render a lightweight visual snapshot of a magazine layout.

The script reads a layout bundle produced by the Fiona workspace and
generates a PNG preview that approximates the canvas. It is intended for
automation workflows where an agent needs a quick visual reference after
editing layout JSON.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

from snapshot import (
    DEFAULT_PROJECT,
    DEFAULT_SNAPSHOT_SIZE,
    STATE_ROOT,
    encode_image,
    load_layout,
    render_snapshot,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a magazine layout snapshot to PNG.")
    parser.add_argument(
        "--project",
        type=str,
        default=DEFAULT_PROJECT,
        help="Project name inside the state directory (default: %(default)s).",
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Explicit layout.json path. Overrides --project if provided.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path where the generated PNG should be written.",
    )
    parser.add_argument(
        "--size",
        type=str,
        default=f"{DEFAULT_SNAPSHOT_SIZE[0]}x{DEFAULT_SNAPSHOT_SIZE[1]}",
        help="Preview size in WIDTHxHEIGHT format (default: %(default)s).",
    )
    parser.add_argument(
        "--no-base64",
        action="store_true",
        help="Suppress base64 output. Only emit JSON when used.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a structured JSON response instead of plain base64.",
    )
    return parser.parse_args()


def resolve_layout_path(args: argparse.Namespace) -> Path:
    if args.source:
        return args.source
    project_dir = STATE_ROOT / args.project
    return project_dir / "layout.json"


def parse_size(raw: str) -> Tuple[int, int]:
    match = re.match(r"^\s*(\d+)\s*[xX]\s*(\d+)\s*$", raw or "")
    if not match:
        return DEFAULT_SNAPSHOT_SIZE
    return max(100, int(match.group(1))), max(100, int(match.group(2)))


def main() -> None:
    args = parse_args()
    size = parse_size(args.size)
    layout_path = resolve_layout_path(args)
    layout = load_layout(layout_path)
    image = render_snapshot(layout, size)

    result: Dict[str, Any] = {}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.output, format="PNG")
        result["path"] = str(args.output)

    if not args.no_base64:
        result["base64"] = encode_image(image)

    if args.json or result.get("path") or result.get("base64") is not None:
        print(json.dumps(result))
    else:
        # Fallback: print base64 directly for convenience
        print(encode_image(image))


if __name__ == "__main__":
    main()
