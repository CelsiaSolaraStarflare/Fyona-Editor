from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class TerminalCommandError(Exception):
    """Raised when a terminal command cannot be parsed or executed."""


@dataclass
class TerminalResult:
    output: str
    layout: Optional[Dict[str, Any]] = None
    refresh_layout: bool = False


CommandHandler = Callable[[Sequence[str]], TerminalResult]


class TerminalProcessor:
    """Parses and executes simplified terminal commands against a layout."""

    def __init__(
        self,
        project: str,
        layout: Dict[str, Any],
        block_id_factory: Optional[Callable[[], str]] = None,
    ):
        self.project = project
        self.layout = layout
        self._block_id_factory = block_id_factory or (lambda: f"block-{id(self):x}")

    def run(self, command: str) -> TerminalResult:
        try:
            tokens = shlex.split(command)
        except ValueError as exc:  # pragma: no cover - user input validation
            raise TerminalCommandError(str(exc)) from exc
        if not tokens:
            raise TerminalCommandError("Type a command such as `help` or `echo 1`.")
        verb = tokens[0].lower()
        handler: Optional[CommandHandler] = getattr(self, f"_cmd_{verb}", None)
        if handler is None:
            raise TerminalCommandError(f"Unknown command “{verb}”. Type `help` to see options.")
        return handler(tokens[1:])

    # ------------------------------------------------------------------ commands
    def _cmd_help(self, _: Sequence[str]) -> TerminalResult:
        lines = [
            "Fyona terminal commands:",
            "  help                                Show this menu.",
            "  pages                               List known pages and block counts.",
            "  echo <page number>                  Summarize the blocks on a page.",
            "  add --text \"Copy\" --font Inter --position (x,y) [--page N] [--size WxH]",
            "  add --image \"Label\" --position (x,y) [--page N] [--size WxH]",
        ]
        return TerminalResult(output="\n".join(lines))

    def _cmd_pages(self, _: Sequence[str]) -> TerminalResult:
        pages = self._sorted_pages()
        if not pages:
            return TerminalResult(output="No pages were found in this project.")
        lines = ["Pages:"]
        for index, page in enumerate(pages, start=1):
            name = page.get("name") or f"Page {index}"
            block_count = len(page.get("blocks") or [])
            lines.append(f"  {index:>2}. {name} · {block_count} block{'s' if block_count != 1 else ''}")
        return TerminalResult(output="\n".join(lines))

    def _cmd_echo(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: echo <page number>")
        page_number = self._coerce_positive_int(args[0], "page number")
        page = self._get_page_by_number(page_number)
        blocks = page.get("blocks") or []
        name = page.get("name") or f"Page {page_number}"
        lines = [
            f"Page {page_number}: {name}",
            f"Blocks: {len(blocks)}",
        ]
        if not blocks:
            lines.append("  (no blocks yet)")
        else:
            for idx, block in enumerate(blocks, start=1):
                lines.append(f"  {idx:>2}. {self._summarize_block(block)}")
        return TerminalResult(output="\n".join(lines))

    def _cmd_add(self, args: Sequence[str]) -> TerminalResult:
        options = self._parse_add_arguments(args)
        page = self._get_target_page(options["page"])
        block = self._build_block(options)
        page_blocks = page.setdefault("blocks", [])
        page_blocks.append(block)
        active_page_id = self.layout.get("activePageId")
        if not active_page_id:
            self.layout["activePageId"] = page.get("id")
            active_page_id = page.get("id")
        if page.get("id") == active_page_id:
            self.layout["blocks"] = list(page_blocks)
        message = self._describe_block_addition(block, page)
        return TerminalResult(output=message, layout=self.layout, refresh_layout=True)

    # ------------------------------------------------------------------ helpers
    def _sorted_pages(self) -> List[Dict[str, Any]]:
        pages = self.layout.get("pages") or []
        return sorted(pages, key=lambda p: p.get("order", 0))

    def _get_page_by_number(self, page_number: int) -> Dict[str, Any]:
        pages = self._sorted_pages()
        if not pages:
            raise TerminalCommandError("This project has no pages yet.")
        if not 1 <= page_number <= len(pages):
            raise TerminalCommandError(f"Page {page_number} does not exist.")
        return pages[page_number - 1]

    def _get_target_page(self, requested_page: Optional[int]) -> Dict[str, Any]:
        pages = self._sorted_pages()
        if not pages:
            page = {
                "id": self.layout.get("activePageId") or "page-1",
                "name": "Page 1",
                "order": 0,
                "blocks": [],
            }
            self.layout["pages"] = [page]
            self.layout["activePageId"] = page["id"]
            return page
        if requested_page is not None:
            if not 1 <= requested_page <= len(pages):
                raise TerminalCommandError(f"Page {requested_page} does not exist.")
            return pages[requested_page - 1]
        active_page_id = self.layout.get("activePageId")
        if active_page_id:
            for page in pages:
                if page.get("id") == active_page_id:
                    return page
        return pages[0]

    def _build_block(self, options: Dict[str, Any]) -> Dict[str, Any]:
        block_id = self._block_id_factory()
        width, height = options.get("size") or (240, 120)
        left, top = options["position"]
        base_block = {
            "id": block_id,
            "type": options["kind"],
            "content": "",
            "position": {
                "left": int(left),
                "top": int(top),
                "width": int(width),
                "height": int(height),
            },
        }
        if options["kind"] == "text":
            base_block["content"] = options["text"]
            if options.get("font"):
                base_block["typography"] = {"fontFamily": options["font"]}
        else:
            label = options.get("image_label") or "Image placeholder"
            base_block["content"] = label
            if options.get("image_label"):
                base_block["imageUrl"] = options["image_label"]
        return base_block

    def _parse_add_arguments(self, args: Sequence[str]) -> Dict[str, Any]:
        if not args:
            raise TerminalCommandError("Usage: add --text \"Copy\" --font Inter --position (x,y)")
        options: Dict[str, Any] = {
            "kind": None,
            "text": None,
            "image_label": None,
            "font": None,
            "position": None,
            "size": None,
            "page": None,
        }
        i = 0
        while i < len(args):
            token = args[i]
            if token == "--text":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide text content after --text.")
                options["kind"] = "text"
                options["text"] = args[i]
            elif token == "--image":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a label or URL after --image.")
                options["kind"] = "image"
                options["image_label"] = args[i]
            elif token == "--font":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a font name after --font.")
                options["font"] = args[i]
            elif token == "--position":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide coordinates after --position.")
                options["position"] = self._parse_position(args[i])
            elif token == "--page":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --page.")
                options["page"] = self._coerce_positive_int(args[i], "page number")
            elif token == "--size":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide width x height after --size.")
                options["size"] = self._parse_size(args[i])
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1

        if options["kind"] is None:
            raise TerminalCommandError("Specify either --text \"Copy\" or --image \"Label\".")
        if options["kind"] == "text":
            if not options["text"]:
                raise TerminalCommandError("Text blocks require content after --text.")
        if options["position"] is None:
            raise TerminalCommandError("Add commands require --position (x,y).")
        return options

    @staticmethod
    def _coerce_positive_int(value: Any, label: str) -> int:
        try:
            number = int(str(value))
        except (TypeError, ValueError):
            raise TerminalCommandError(f"{label.capitalize()} must be a whole number.")
        if number <= 0:
            raise TerminalCommandError(f"{label.capitalize()} must be greater than zero.")
        return number

    @staticmethod
    def _parse_position(raw_value: str) -> Tuple[int, int]:
        value = raw_value.strip().lstrip("(").rstrip(")")
        match = re.match(r"^\s*(-?\d+)\s*,\s*(-?\d+)\s*$", value)
        if not match:
            raise TerminalCommandError("Position must look like (x,y).")
        return int(match.group(1)), int(match.group(2))

    @staticmethod
    def _parse_size(raw_value: str) -> Tuple[int, int]:
        value = raw_value.strip().lower().replace(" ", "")
        match = re.match(r"^(?P<width>\d+)[x,](?P<height>\d+)$", value)
        if not match:
            raise TerminalCommandError("Size must look like 240x120.")
        return int(match.group("width")), int(match.group("height"))

    @staticmethod
    def _summarize_block(block: Dict[str, Any]) -> str:
        block_type = block.get("type") or "text"
        position = block.get("position") or {}
        left = position.get("left", 0)
        top = position.get("top", 0)
        width = position.get("width", 0)
        height = position.get("height", 0)
        raw_content = block.get("content") or ""
        summary = raw_content.strip()
        if len(summary) > 42:
            summary = summary[:39] + "…"
        if block_type == "image" and not summary:
            summary = block.get("imageUrl") or "[Image]"
        return f"{block_type} · {summary or '(empty)'} @ ({left}, {top}) {width}×{height}"

    def _describe_block_addition(self, block: Dict[str, Any], page: Dict[str, Any]) -> str:
        pages = self._sorted_pages()
        try:
            page_index = pages.index(page) + 1
        except ValueError:
            page_index = 1
        name = page.get("name") or f"Page {page_index}"
        pos = block.get("position") or {}
        return f"Added {block.get('type')} block to {name} at ({pos.get('left')}, {pos.get('top')})."

