from __future__ import annotations

import re
import shlex
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


class TerminalCommandError(Exception):
    """Raised when a terminal command cannot be parsed or executed."""


@dataclass
class TerminalResult:
    output: str
    layout: Optional[Dict[str, Any]] = None
    refresh_layout: bool = False


CommandHandler = Callable[[Sequence[str]], TerminalResult]

TERMINAL_COMMANDS = [
    "help",
    "status",
    "pages",
    "echo",
    "blocks",
    "move",
    "resize",
    "duplicate",
    "delete",
    "remove",
    "newpage",
    "renamepage",
    "deletepage",
    "activate",
    "grid",
    "add",
    "edit",
    "content",
    "append",
    "prepend",
]

DEFAULT_FONT = "inter"
DEFAULT_FONT_SIZE = 16
DEFAULT_TEXT_COLOR = "#1c2333"
DEFAULT_BG_COLOR = "#ffffff"
DEFAULT_RADIUS = 12
DEFAULT_TEXT_MARGIN = {"top": 16, "right": 16, "bottom": 16, "left": 16}
DEFAULT_IMAGE_MARGIN = {"top": 0, "right": 0, "bottom": 0, "left": 0}
CANVAS_PRESETS: Dict[str, Tuple[int, int]] = {
    "a5": (559, 794),
    "a4": (794, 1123),
    "a3": (1123, 1587),
    "letter": (816, 1056),
}


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
            raise TerminalCommandError("Type a command such as `help` or `echo 1`. TIP: Run `help` to see all available commands!")
        verb = tokens[0].lower()
        handler: Optional[CommandHandler] = getattr(self, f"_cmd_{verb}", None)
        if handler is None:
            raise TerminalCommandError(f"Unknown command “{verb}”. Type `help` to see options. TIP: Run `help` to see all available commands!")
        return handler(tokens[1:])

    # ------------------------------------------------------------------ commands
    def _cmd_help(self, _: Sequence[str]) -> TerminalResult:
        lines = [
            "Fyona terminal commands:",
            "  help                                Show this menu.",
            "  pages                               List known pages and block counts.",
            "  echo <page number>                  Summarize the blocks on a page.",
            "  status                              Show layout, grid, and theme details.",
            "  blocks [--page N] [--type text]     List blocks on a page with filters.",
            "  move <block> --to (x,y)|--by (dx,dy) [--page N]",
            "  resize <block> --size WxH [--page N]",
            "  duplicate <block> [--page N] [--to-page M] [--offset (x,y)]",
            "  delete <block> [--page N]           Remove a block from a page.",
            "  remove <block> [--page N]           Remove a block from a page (alternative to delete).",
            "  newpage \"Name\" [--after N] [--from N]",
            "  renamepage <page> \"Name\"        Rename a page.",
            "  deletepage <page>                   Remove a page from the layout.",
            "  activate <page>                     Switch the active canvas page.",
            "  grid [--columns N --gutter N ...]   Inspect or update grid settings.",
            "  add --text \"Copy\" --font Inter --position (x,y) [--page N] [--size WxH]",
            "    [--style '{\"fontFamily\": \"Inter\", \"fontSize\": 16, ...}'] [--fontsize N] [--bold true|false] [--italic true|false] [--underline true|false]",
            "    [--strikethrough true|false] [--textcolor \"#RRGGBB\"] [--bg \"#RRGGBB\"]",
            "    [--align left|center|right|justify] [--lineheight N] [--radius N] [--border N]",
            "    [--bordercolor \"#RRGGBB\"] [--shadow \"blur,offsetX,offsetY,#color\"] [--opacity 0.0-1.0]",
            "    [--padding \"T,R,B,L\"] [--margin \"T,R,B,L\"] [--zindex N] [--rotate N]",
            "  add --image \"Label\" --position (x,y) [--page N] [--size WxH]",
            "    [--style '{\"fontSize\": 16, \"color\": \"#rrggbb\", ...}'] [--bg \"#RRGGBB\"] [--radius N] [--border N] [--bordercolor \"#RRGGBB\"]",
            "    [--shadow \"blur,offsetX,offsetY,#color\"] [--opacity 0.0-1.0] [--padding \"T,R,B,L\"]",
            "    [--margin \"T,R,B,L\"] [--zindex N] [--rotate N]",
            "  edit <block> [--bold true|false] [--italic true|false] [--underline true|false]",
            "    [--strikethrough true|false] [--fontsize N] [--fontfamily \"FontName\"]",
            "    [--textcolor \"#RRGGBB\"] [--bg \"#RRGGBB\"] [--align left|center|right|justify]",
            "    [--lineheight N] [--width N] [--height N] [--left N] [--top N] [--radius N]",
            "    [--border N] [--bordercolor \"#RRGGBB\"] [--shadow \"blur,offsetX,offsetY,#color\"]",
            "    [--opacity 0.0-1.0] [--padding \"T,R,B,L\"] [--margin \"T,R,B,L\"] [--zindex N]",
            "    [--rotate N] [--page N]",
            "  content <block> --text \"New content\" [--page N]",
            "  append <block> --text \"Additional content\" [--page N]",
            "  prepend <block> --text \"Prepended content\" [--page N]",
            "",
            "TIP: Run 'help' at the start of your session to see all available commands and options!"
        ]
        return TerminalResult(output="\n".join(lines))

    def _cmd_status(self, _: Sequence[str]) -> TerminalResult:
        pages = self._sorted_pages()
        block_total = sum(len(page.get("blocks") or []) for page in pages)
        lines = [
            f"Project: {self.project or 'untitled'}",
            f"Pages: {len(pages)} · Blocks: {block_total}",
        ]
        active_page_id = self.layout.get("activePageId")
        if active_page_id:
            for idx, page in enumerate(pages, start=1):
                if page.get("id") == active_page_id:
                    block_count = len(page.get("blocks") or [])
                    lines.append(
                        f"Active page: {self._page_label(page, idx)} (#{idx}) · {block_count} block"
                        f"{'s' if block_count != 1 else ''}"
                    )
                    break
        if self.layout.get("activeLayer"):
            lines.append(f"Active layer: {self.layout.get('activeLayer')}")
        theme = self.layout.get("theme") or {}
        if theme.get("name"):
            lines.append(f"Theme: {theme['name']}")
        palette = theme.get("palette") or {}
        if palette:
            formatted_palette = ", ".join(f"{key}={value}" for key, value in palette.items())
            lines.append(f"Palette: {formatted_palette}")
        typography = theme.get("typography") or {}
        if typography:
            lines.append(f"Typography styles: {', '.join(sorted(typography.keys()))}")
        grid_description = self._describe_grid()
        if grid_description:
            lines.append("Grid:")
            lines.extend(f"  {line}" for line in grid_description.splitlines())
        return TerminalResult(output="\n".join(lines))

    def _cmd_blocks(self, args: Sequence[str]) -> TerminalResult:
        page_number: Optional[int] = None
        block_type: Optional[str] = None
        contains: Optional[str] = None
        limit: Optional[int] = None
        i = 0
        while i < len(args):
            token = args[i]
            if token == "--page":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --page.")
                page_number = self._coerce_positive_int(args[i], "page number")
            elif token == "--type":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a block type after --type.")
                block_type = args[i].lower()
            elif token == "--contains":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide text to search for after --contains.")
                contains = args[i].lower()
            elif token == "--limit":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide how many blocks to show after --limit.")
                limit_value = self._coerce_positive_int(args[i], "limit")
                limit = limit_value
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1

        page = self._get_target_page(page_number)
        blocks = page.get("blocks") or []
        filtered: List[Dict[str, Any]] = []
        for block in blocks:
            if block_type and str(block.get("type")).lower() != block_type:
                continue
            if contains:
                searchable = " ".join(
                    str(value or "")
                    for value in [block.get("content"), block.get("imageUrl"), block.get("id")]
                )
                if contains not in searchable.lower():
                    continue
            filtered.append(block)
            if limit is not None and len(filtered) >= limit:
                break

        page_index = self._page_index(page)
        header = f"Blocks on {self._page_label(page, page_index)}"
        if page_index:
            header += f" (page {page_index})"
        if block_type:
            header += f" · type: {block_type}"
        if contains:
            header += f" · matching “{contains}”"
        if not filtered:
            return TerminalResult(output=f"{header}\n  No blocks matched these filters.")
        lines = [header]
        for idx, block in enumerate(filtered, start=1):
            lines.append(f"  {idx:>2}. {self._summarize_block(block)}")
        if limit is not None and len(filtered) == limit and len(filtered) < len(blocks):
            lines.append("  …limit reached; refine filters to see more…")
        return TerminalResult(output="\n".join(lines))

    def _cmd_move(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: move <block> --to (x,y) or move <block> --by (dx,dy)")
        selector = args[0]
        if selector.startswith("--"):
            raise TerminalCommandError("Specify the block number or id as the first argument.")
        options = {"page": None, "to": None, "by": None}
        i = 1
        while i < len(args):
            token = args[i]
            if token == "--page":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --page.")
                options["page"] = self._coerce_positive_int(args[i], "page number")
            elif token == "--to":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide coordinates after --to.")
                options["to"] = self._parse_position(args[i])
            elif token == "--by":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide an offset after --by.")
                options["by"] = self._parse_position(args[i])
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1
        if not options["to"] and not options["by"]:
            raise TerminalCommandError("Move commands need --to (x,y) or --by (dx,dy).")
        page = self._get_target_page(options["page"])
        block, _ = self._find_block(page, selector)
        position = self._ensure_position(block)
        if options["to"]:
            left, top = options["to"]
            position["left"] = int(left)
            position["top"] = int(top)
        if options["by"]:
            dx, dy = options["by"]
            position["left"] = int(position.get("left", 0) + dx)
            position["top"] = int(position.get("top", 0) + dy)
        self._sync_active_blocks(page)
        label = self._page_label(page, self._page_index(page))
        block_id = block.get("id") or selector
        return TerminalResult(
            output=f"Moved block {block_id} on {label} to ({position['left']}, {position['top']}).",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_resize(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: resize <block> --size WxH")
        selector = args[0]
        options = {"page": None, "size": None}
        i = 1
        while i < len(args):
            token = args[i]
            if token == "--page":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --page.")
                options["page"] = self._coerce_positive_int(args[i], "page number")
            elif token == "--size":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide width × height after --size.")
                options["size"] = self._parse_size(args[i])
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1
        if options["size"] is None:
            raise TerminalCommandError("Resize commands require --size 240x120 (for example).")
        page = self._get_target_page(options["page"])
        block, _ = self._find_block(page, selector)
        position = self._ensure_position(block)
        width, height = options["size"]
        position["width"] = int(width)
        position["height"] = int(height)
        self._sync_active_blocks(page)
        label = self._page_label(page, self._page_index(page))
        block_id = block.get("id") or selector
        return TerminalResult(
            output=f"Resized block {block_id} on {label} to {width}×{height}.",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_duplicate(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: duplicate <block> [--page N] [--to-page M] [--offset (x,y)]")
        selector = args[0]
        options = {"page": None, "target_page": None, "offset": (32, 32)}
        i = 1
        while i < len(args):
            token = args[i]
            if token == "--page":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --page.")
                options["page"] = self._coerce_positive_int(args[i], "page number")
            elif token in ("--to-page", "--page-to", "--dest"):
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --to-page.")
                options["target_page"] = self._coerce_positive_int(args[i], "page number")
            elif token == "--offset":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide an offset like (24,24) after --offset.")
                options["offset"] = self._parse_position(args[i])
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1
        source_page = self._get_target_page(options["page"])
        destination_page = source_page
        if options["target_page"] is not None:
            destination_page = self._get_page_by_number(options["target_page"])
        block, _ = self._find_block(source_page, selector)
        clone = deepcopy(block)
        clone["id"] = self._block_id_factory()
        clone_position = self._ensure_position(clone)
        offset_x, offset_y = options["offset"] or (0, 0)
        clone_position["left"] = int(clone_position.get("left", 0) + offset_x)
        clone_position["top"] = int(clone_position.get("top", 0) + offset_y)
        destination_page.setdefault("blocks", []).append(clone)
        self._sync_active_blocks(destination_page)
        label = self._page_label(destination_page, self._page_index(destination_page))
        source_id = block.get("id") or selector
        return TerminalResult(
            output=f"Duplicated block {source_id} onto {label} as {clone['id']}.",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_delete(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: delete <block> [--page N]")
        selector = args[0]
        page_number: Optional[int] = None
        i = 1
        while i < len(args):
            token = args[i]
            if token == "--page":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --page.")
                page_number = self._coerce_positive_int(args[i], "page number")
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1
        page = self._get_target_page(page_number)
        blocks = page.get("blocks") or []
        block, index = self._find_block(page, selector)
        blocks.pop(index)
        self._sync_active_blocks(page)
        label = self._page_label(page, self._page_index(page))
        block_id = block.get("id") or selector
        return TerminalResult(
            output=f"Deleted block {block_id} from {label}.",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_remove(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: remove <block> [--page N]")
        selector = args[0]
        page_number: Optional[int] = None
        i = 1
        while i < len(args):
            token = args[i]
            if token == "--page":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --page.")
                page_number = self._coerce_positive_int(args[i], "page number")
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1
        page = self._get_target_page(page_number)
        blocks = page.get("blocks") or []
        block, index = self._find_block(page, selector)
        blocks.pop(index)
        self._sync_active_blocks(page)
        label = self._page_label(page, self._page_index(page))
        block_id = block.get("id") or selector
        return TerminalResult(
            output=f"Removed block {block_id} from {label}.",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_newpage(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: newpage \"Name\" [--after N] [--from N]")
        name_tokens: List[str] = []
        after_page_number: Optional[int] = None
        copy_page_number: Optional[int] = None
        i = 0
        while i < len(args):
            token = args[i]
            if token == "--after":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --after.")
                after_page_number = self._coerce_positive_int(args[i], "page number")
            elif token in ("--from", "--copy"):
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --from.")
                copy_page_number = self._coerce_positive_int(args[i], "page number")
            else:
                name_tokens.append(token)
            i += 1
        name = " ".join(name_tokens).strip()
        if not name:
            raise TerminalCommandError("Provide a name for the new page, e.g., newpage \"Feature\".")
        pages = self._sorted_pages()
        template_page: Optional[Dict[str, Any]] = None
        if copy_page_number is not None:
            template_page = self._get_page_by_number(copy_page_number)
        if after_page_number is not None and (after_page_number <= 0 or after_page_number > len(pages)):
            raise TerminalCommandError(f"Page {after_page_number} does not exist.")
        new_page_id = self._generate_page_id(name)
        new_blocks: List[Dict[str, Any]] = []
        if template_page:
            for block in template_page.get("blocks") or []:
                clone = deepcopy(block)
                clone["id"] = self._block_id_factory()
                new_blocks.append(clone)
        if template_page and template_page.get("dimensions"):
            dimensions = deepcopy(template_page.get("dimensions"))
        else:
            dimensions = deepcopy(self.layout.get("dimensions") or {})
        new_page = {
            "id": new_page_id,
            "name": name,
            "order": len(pages),
            "blocks": new_blocks,
            "dimensions": dimensions,
        }
        insert_index = len(pages)
        if after_page_number is not None:
            insert_index = after_page_number
        pages.insert(insert_index, new_page)
        self._normalize_page_orders()
        if not self.layout.get("activePageId"):
            self.layout["activePageId"] = new_page_id
            self.layout["blocks"] = list(new_blocks)
        lines = [
            f"Added page '{name}' with id {new_page_id} at position {insert_index + 1}.",
        ]
        if template_page:
            template_name = self._page_label(template_page, self._page_index(template_page))
            lines.append(f"Copied {len(new_blocks)} block{'s' if len(new_blocks) != 1 else ''} from {template_name}.")
        return TerminalResult(output="\n".join(lines), layout=self.layout, refresh_layout=True)

    def _cmd_renamepage(self, args: Sequence[str]) -> TerminalResult:
        if len(args) < 2:
            raise TerminalCommandError("Usage: renamepage <page number> \"New Name\"")
        page_number = self._coerce_positive_int(args[0], "page number")
        new_name = " ".join(args[1:]).strip()
        if not new_name:
            raise TerminalCommandError("Provide a valid page name after the page number.")
        page = self._get_page_by_number(page_number)
        old_label = self._page_label(page, page_number)
        page["name"] = new_name
        return TerminalResult(
            output=f"Renamed {old_label} to {new_name}.",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_deletepage(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: deletepage <page number>")
        page_number = self._coerce_positive_int(args[0], "page number")
        pages = self._sorted_pages()
        if not pages:
            raise TerminalCommandError("This project has no pages to delete.")
        if not 1 <= page_number <= len(pages):
            raise TerminalCommandError(f"Page {page_number} does not exist.")
        target_page = pages.pop(page_number - 1)
        removed_label = self._page_label(target_page, page_number)
        self._normalize_page_orders()
        active_page_id = self.layout.get("activePageId")
        if not pages:
            self.layout["activePageId"] = None
            self.layout["blocks"] = []
        elif target_page.get("id") == active_page_id:
            new_active = pages[0]
            self.layout["activePageId"] = new_active.get("id")
            self.layout["blocks"] = list(new_active.get("blocks") or [])
        return TerminalResult(
            output=f"Deleted {removed_label} (page {page_number}).",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_activate(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: activate <page number>")
        page_number = self._coerce_positive_int(args[0], "page number")
        page = self._get_page_by_number(page_number)
        self.layout["activePageId"] = page.get("id")
        self.layout["blocks"] = list(page.get("blocks") or [])
        label = self._page_label(page, page_number)
        return TerminalResult(
            output=f"Activated {label}.",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_grid(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            return TerminalResult(output=self._describe_grid())
        columns = None
        gutter = None
        baseline = None
        snap: Optional[bool] = None
        zoom = None
        format_name = None
        orientation = None
        dimensions: Optional[Tuple[int, int]] = None
        i = 0
        while i < len(args):
            token = args[i]
            if token == "--columns":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a number after --columns.")
                columns = self._coerce_positive_int(args[i], "columns")
            elif token == "--gutter":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a number after --gutter.")
                gutter = self._coerce_positive_int(args[i], "gutter")
            elif token == "--baseline":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a number after --baseline.")
                baseline = self._coerce_positive_int(args[i], "baseline")
            elif token == "--snap":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Set snap to on/off after --snap.")
                value = args[i].lower()
                if value in ("on", "true", "1"):
                    snap = True
                elif value in ("off", "false", "0"):
                    snap = False
                else:
                    raise TerminalCommandError("Snap must be on/off/true/false.")
            elif token == "--zoom":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a zoom value after --zoom.")
                try:
                    zoom = float(args[i])
                except ValueError:
                    raise TerminalCommandError("Zoom must be a number like 1 or 0.75.")
            elif token == "--format":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a format name after --format.")
                format_name = args[i]
            elif token == "--orientation":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide an orientation after --orientation.")
                orientation = args[i]
            elif token == "--dimensions":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide width×height after --dimensions.")
                dimensions = self._parse_size(args[i])
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1
        changes: List[str] = []
        if columns is not None:
            self.layout["columns"] = columns
            changes.append(f"columns→{columns}")
        if gutter is not None:
            self.layout["gutter"] = gutter
            changes.append(f"gutter→{gutter}")
        if baseline is not None:
            self.layout["baseline"] = baseline
            changes.append(f"baseline→{baseline}")
        if snap is not None:
            self.layout["snap"] = snap
            changes.append(f"snap→{'on' if snap else 'off'}")
        if zoom is not None:
            self.layout["zoom"] = zoom
            changes.append(f"zoom→{zoom}")
        if format_name is not None:
            self.layout["format"] = format_name
            changes.append(f"format→{format_name}")
        if orientation is not None:
            self.layout["orientation"] = orientation
            changes.append(f"orientation→{orientation}")
        if dimensions is not None:
            width, height = dimensions
            self.layout.setdefault("dimensions", {})
            self.layout["dimensions"]["width"] = width
            self.layout["dimensions"]["height"] = height
            changes.append(f"dimensions→{width}×{height}")
        description = self._describe_grid()
        if not changes:
            return TerminalResult(output=description)
        lines = ["Grid updated:"]
        lines.extend(f"  {change}" for change in changes)
        lines.append("")
        lines.extend(description.splitlines())
        return TerminalResult(output="\n".join(lines), layout=self.layout, refresh_layout=True)

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

    def _cmd_edit(self, args: Sequence[str]) -> TerminalResult:
        if not args:
            raise TerminalCommandError("Usage: edit <block> [--property value]...")

        selector = args[0]
        options = self._parse_edit_arguments(args[1:])
        page = self._get_target_page(options.get("page"))
        block, _ = self._find_block(page, selector)

        # Apply all the edits
        self._apply_block_edits(block, options)

        self._sync_active_blocks(page)
        label = self._page_label(page, self._page_index(page))
        block_id = block.get("id") or selector
        return TerminalResult(
            output=f"Edited block {block_id} on {label}.",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_content(self, args: Sequence[str]) -> TerminalResult:
        if len(args) < 2:
            raise TerminalCommandError("Usage: content <block> --text \"New content\"")

        selector = args[0]
        options = self._parse_content_arguments(args[1:])
        page = self._get_target_page(options.get("page"))
        block, _ = self._find_block(page, selector)

        if block.get("type") != "text":
            raise TerminalCommandError("Content can only be updated for text blocks.")

        block["content"] = options["text"]

        self._sync_active_blocks(page)
        label = self._page_label(page, self._page_index(page))
        block_id = block.get("id") or selector
        return TerminalResult(
            output=f"Updated content for block {block_id} on {label}.",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_append(self, args: Sequence[str]) -> TerminalResult:
        if len(args) < 2:
            raise TerminalCommandError("Usage: append <block> --text \"Additional content\"")

        selector = args[0]
        options = self._parse_content_arguments(args[1:])
        page = self._get_target_page(options.get("page"))
        block, _ = self._find_block(page, selector)

        if block.get("type") != "text":
            raise TerminalCommandError("Content can only be appended to text blocks.")

        block["content"] = f"{block.get('content', '')}{options['text']}"

        self._sync_active_blocks(page)
        label = self._page_label(page, self._page_index(page))
        block_id = block.get("id") or selector
        return TerminalResult(
            output=f"Appended content to block {block_id} on {label}.",
            layout=self.layout,
            refresh_layout=True,
        )

    def _cmd_prepend(self, args: Sequence[str]) -> TerminalResult:
        if len(args) < 2:
            raise TerminalCommandError("Usage: prepend <block> --text \"Prepended content\"")

        selector = args[0]
        options = self._parse_content_arguments(args[1:])
        page = self._get_target_page(options.get("page"))
        block, _ = self._find_block(page, selector)

        if block.get("type") != "text":
            raise TerminalCommandError("Content can only be prepended to text blocks.")

        block["content"] = f"{options['text']}{block.get('content', '')}"

        self._sync_active_blocks(page)
        label = self._page_label(page, self._page_index(page))
        block_id = block.get("id") or selector
        return TerminalResult(
            output=f"Prepended content to block {block_id} on {label}.",
            layout=self.layout,
            refresh_layout=True,
        )

    # ------------------------------------------------------------------ helpers
    def _sorted_pages(self) -> List[Dict[str, Any]]:
        pages = self.layout.setdefault("pages", [])
        pages.sort(key=lambda p: p.get("order", 0))
        for index, page in enumerate(pages):
            page["order"] = index
        return pages

    def _sync_active_blocks(self, page: Dict[str, Any]) -> None:
        active_page_id = self.layout.get("activePageId")
        if not active_page_id:
            return
        if page.get("id") != active_page_id:
            return
        self.layout["blocks"] = list(page.get("blocks") or [])

    def _page_label(self, page: Dict[str, Any], fallback_index: Optional[int] = None) -> str:
        if page.get("name"):
            return str(page["name"])
        if fallback_index is not None:
            return f"Page {fallback_index}"
        return page.get("id") or "Page"

    def _normalize_page_orders(self) -> None:
        pages = self.layout.get("pages") or []
        for index, page in enumerate(pages):
            page["order"] = index

    def _find_block(self, page: Dict[str, Any], selector: str) -> Tuple[Dict[str, Any], int]:
        blocks = page.get("blocks") or []
        if not blocks:
            raise TerminalCommandError("This page has no blocks to operate on.")
        if re.fullmatch(r"\d+", selector):
            block_index = int(selector)
            if not 1 <= block_index <= len(blocks):
                raise TerminalCommandError(f"Block number {selector} does not exist on this page.")
            return blocks[block_index - 1], block_index - 1
        for index, block in enumerate(blocks):
            if str(block.get("id")) == selector:
                return block, index
        raise TerminalCommandError(f"Block “{selector}” was not found on this page.")

    def _page_index(self, page: Dict[str, Any]) -> Optional[int]:
        pages = self._sorted_pages()
        try:
            return pages.index(page) + 1
        except ValueError:
            return None

    def _generate_page_id(self, name: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
        if not cleaned:
            cleaned = "page"
        cleaned = cleaned.strip("-") or "page"
        existing = {str(page.get("id")) for page in self.layout.get("pages") or []}
        candidate = f"page-{cleaned}" if not cleaned.startswith("page-") else cleaned
        suffix = 2
        while candidate in existing:
            candidate = f"{cleaned}-{suffix}"
            suffix += 1
        return candidate

    def _describe_grid(self) -> str:
        dimensions = self.layout.get("dimensions") or {}
        columns = self.layout.get("columns")
        gutter = self.layout.get("gutter")
        baseline = self.layout.get("baseline")
        snap = self.layout.get("snap")
        zoom = self.layout.get("zoom")
        format_name = self.layout.get("format") or "custom"
        orientation = self.layout.get("orientation") or "portrait"
        lines = [
            f"Dimensions: {dimensions.get('width', '—')} × {dimensions.get('height', '—')} px",
            f"Columns: {columns or '—'} · Gutter: {gutter or '—'} px",
            f"Baseline: {baseline or '—'} px · Snap: {'on' if snap else 'off'}",
            f"Zoom: {zoom or 1} · Format: {format_name} · Orientation: {orientation}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _ensure_position(block: Dict[str, Any]) -> Dict[str, int]:
        position = block.setdefault("position", {})
        position.setdefault("left", 0)
        position.setdefault("top", 0)
        position.setdefault("width", 0)
        position.setdefault("height", 0)
        return position

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

        # Text formatting options
        typography = {}
        if options.get("font"):
            typography["fontFamily"] = options["font"]
        if options.get("fontsize"):
            typography["fontSize"] = options["fontsize"]
        if options.get("bold") is not None:
            typography["bold"] = options["bold"]
        if options.get("italic") is not None:
            typography["italic"] = options["italic"]
        if options.get("underline") is not None:
            typography["underline"] = options["underline"]
        if options.get("strikethrough") is not None:
            typography["strikethrough"] = options["strikethrough"]
        if options.get("textcolor"):
            typography["color"] = options["textcolor"]
        if options.get("align"):
            typography["textAlign"] = options["align"]
        if options.get("lineheight"):
            typography["lineHeight"] = options["lineheight"]

        if typography:
            base_block["typography"] = typography

        if options["kind"] == "text":
            base_block["content"] = options["text"]
        else:
            label = options.get("image_label") or "Image placeholder"
            base_block["content"] = label
            if options.get("image_label"):
                base_block["imageUrl"] = options["image_label"]

        # Visual styling options
        if options.get("bg"):
            base_block["backgroundColor"] = options["bg"]
        if options.get("radius") is not None:
            base_block["borderRadius"] = options["radius"]
        if options.get("border") is not None:
            base_block["borderWidth"] = options["border"]
        if options.get("bordercolor"):
            base_block["borderColor"] = options["bordercolor"]
        if options.get("shadow"):
            base_block["shadow"] = options["shadow"]
        if options.get("opacity") is not None:
            base_block["opacity"] = options["opacity"]
        if options.get("padding"):
            base_block["padding"] = options["padding"]
        if options.get("margin"):
            base_block["margin"] = options["margin"]
        if options.get("zindex") is not None:
            base_block["zIndex"] = options["zindex"]
        if options.get("rotate") is not None:
            base_block["rotate"] = options["rotate"]

        return base_block

    def _parse_add_arguments(self, args: Sequence[str]) -> Dict[str, Any]:
        if not args:
            raise TerminalCommandError("Usage: add --text \"Copy\" --font Inter --position (x,y)")
        options: Dict[str, Any] = {
            "kind": None,
            "text": None,
            "image_label": None,
            "font": None,
            "fontsize": None,
            "position": None,
            "size": None,
            "page": None,
            "bold": None,
            "italic": None,
            "underline": None,
            "strikethrough": None,
            "textcolor": None,
            "bg": None,
            "align": None,
            "lineheight": None,
            "radius": None,
            "border": None,
            "bordercolor": None,
            "shadow": None,
            "opacity": None,
            "padding": None,
            "margin": None,
            "zindex": None,
            "rotate": None,
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
            elif token == "--fontsize":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a font size after --fontsize.")
                try:
                    options["fontsize"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--fontsize must be a number.")
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
            elif token == "--style":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a style object after --style.")
                try:
                    # Try to parse as JSON string first
                    import json
                    style_obj = json.loads(args[i])
                    if not isinstance(style_obj, dict):
                        raise TerminalCommandError("--style must be a JSON object with style properties.")

                    # Map style properties to individual options
                    if "fontFamily" in style_obj:
                        options["font"] = str(style_obj["fontFamily"])
                    if "fontSize" in style_obj:
                        options["fontsize"] = int(style_obj["fontSize"])
                    if "fontWeight" in style_obj:
                        options["bold"] = style_obj["fontWeight"] in ("bold", "bolder", "700", "800", "900")
                    if "textAlign" in style_obj:
                        options["align"] = str(style_obj["textAlign"])
                    if "color" in style_obj:
                        options["textcolor"] = str(style_obj["color"])
                    if "backgroundColor" in style_obj:
                        options["bg"] = str(style_obj["backgroundColor"])
                    if "borderRadius" in style_obj:
                        options["radius"] = int(style_obj["borderRadius"])
                    if "opacity" in style_obj:
                        options["opacity"] = float(style_obj["opacity"])
                    if "lineHeight" in style_obj:
                        options["lineheight"] = float(style_obj["lineHeight"])
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to parse as CSS-like string
                    style_str = args[i]
                    # Handle CSS-like string: "fontFamily: Arial; fontSize: 16"
                    if ":" in style_str and ";" in style_str:
                        # This is a CSS-like string, not supported for now
                        raise TerminalCommandError("--style must be a valid JSON object like '{\"fontFamily\": \"Arial\", \"fontSize\": 16}'")
                    else:
                        raise TerminalCommandError("--style must be a valid JSON object like '{\"fontFamily\": \"Arial\", \"fontSize\": 16}'")
            elif token == "--bold":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide true or false after --bold.")
                value = args[i].lower()
                if value in ("true", "1", "on"):
                    options["bold"] = True
                elif value in ("false", "0", "off"):
                    options["bold"] = False
                else:
                    raise TerminalCommandError("--bold must be true/false.")
            elif token == "--italic":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide true or false after --italic.")
                value = args[i].lower()
                if value in ("true", "1", "on"):
                    options["italic"] = True
                elif value in ("false", "0", "off"):
                    options["italic"] = False
                else:
                    raise TerminalCommandError("--italic must be true/false.")
            elif token == "--underline":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide true or false after --underline.")
                value = args[i].lower()
                if value in ("true", "1", "on"):
                    options["underline"] = True
                elif value in ("false", "0", "off"):
                    options["underline"] = False
                else:
                    raise TerminalCommandError("--underline must be true/false.")
            elif token == "--strikethrough":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide true or false after --strikethrough.")
                value = args[i].lower()
                if value in ("true", "1", "on"):
                    options["strikethrough"] = True
                elif value in ("false", "0", "off"):
                    options["strikethrough"] = False
                else:
                    raise TerminalCommandError("--strikethrough must be true/false.")
            elif token == "--textcolor":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a color value after --textcolor.")
                options["textcolor"] = args[i]
            elif token == "--bg":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a color value after --bg.")
                options["bg"] = args[i]
            elif token == "--align":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide an alignment value after --align.")
                align_value = args[i].lower()
                if align_value not in ("left", "center", "right", "justify"):
                    raise TerminalCommandError("--align must be left/center/right/justify.")
                options["align"] = align_value
            elif token == "--lineheight":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a line height value after --lineheight.")
                try:
                    options["lineheight"] = float(args[i])
                except ValueError:
                    raise TerminalCommandError("--lineheight must be a number.")
            elif token == "--radius":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a radius value after --radius.")
                try:
                    options["radius"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--radius must be a number.")
            elif token == "--border":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a border width value after --border.")
                try:
                    options["border"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--border must be a number.")
            elif token == "--bordercolor":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a border color value after --bordercolor.")
                options["bordercolor"] = args[i]
            elif token == "--shadow":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide shadow values after --shadow.")
                options["shadow"] = args[i]
            elif token == "--opacity":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide an opacity value after --opacity.")
                try:
                    opacity = float(args[i])
                    if not 0.0 <= opacity <= 1.0:
                        raise TerminalCommandError("--opacity must be between 0.0 and 1.0.")
                    options["opacity"] = opacity
                except ValueError:
                    raise TerminalCommandError("--opacity must be a number between 0.0 and 1.0.")
            elif token == "--padding":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide padding values after --padding.")
                options["padding"] = args[i]
            elif token == "--margin":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide margin values after --margin.")
                options["margin"] = args[i]
            elif token == "--zindex":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a z-index value after --zindex.")
                try:
                    options["zindex"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--zindex must be a number.")
            elif token == "--rotate":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a rotation value after --rotate.")
                try:
                    options["rotate"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--rotate must be a number.")
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

    def _parse_edit_arguments(self, args: Sequence[str]) -> Dict[str, Any]:
        """Parse arguments for the edit command."""
        options: Dict[str, Any] = {
            "page": None,
            "bold": None,
            "italic": None,
            "underline": None,
            "strikethrough": None,
            "fontsize": None,
            "fontfamily": None,
            "textcolor": None,
            "bg": None,
            "align": None,
            "lineheight": None,
            "width": None,
            "height": None,
            "left": None,
            "top": None,
            "radius": None,
            "border": None,
            "bordercolor": None,
            "shadow": None,
            "opacity": None,
            "padding": None,
            "margin": None,
            "zindex": None,
            "rotate": None,
        }

        i = 0
        while i < len(args):
            token = args[i]
            if token == "--page":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --page.")
                options["page"] = self._coerce_positive_int(args[i], "page number")
            elif token == "--bold":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide true or false after --bold.")
                value = args[i].lower()
                if value in ("true", "1", "on"):
                    options["bold"] = True
                elif value in ("false", "0", "off"):
                    options["bold"] = False
                else:
                    raise TerminalCommandError("--bold must be true/false.")
            elif token == "--italic":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide true or false after --italic.")
                value = args[i].lower()
                if value in ("true", "1", "on"):
                    options["italic"] = True
                elif value in ("false", "0", "off"):
                    options["italic"] = False
                else:
                    raise TerminalCommandError("--italic must be true/false.")
            elif token == "--underline":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide true or false after --underline.")
                value = args[i].lower()
                if value in ("true", "1", "on"):
                    options["underline"] = True
                elif value in ("false", "0", "off"):
                    options["underline"] = False
                else:
                    raise TerminalCommandError("--underline must be true/false.")
            elif token == "--strikethrough":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide true or false after --strikethrough.")
                value = args[i].lower()
                if value in ("true", "1", "on"):
                    options["strikethrough"] = True
                elif value in ("false", "0", "off"):
                    options["strikethrough"] = False
                else:
                    raise TerminalCommandError("--strikethrough must be true/false.")
            elif token == "--fontsize":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a font size after --fontsize.")
                try:
                    options["fontsize"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--fontsize must be a number.")
            elif token == "--fontfamily":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a font family after --fontfamily.")
                options["fontfamily"] = args[i]
            elif token == "--textcolor":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a color value after --textcolor.")
                options["textcolor"] = args[i]
            elif token == "--bg":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a color value after --bg.")
                options["bg"] = args[i]
            elif token == "--align":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide an alignment value after --align.")
                align_value = args[i].lower()
                if align_value not in ("left", "center", "right", "justify"):
                    raise TerminalCommandError("--align must be left/center/right/justify.")
                options["align"] = align_value
            elif token == "--lineheight":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a line height value after --lineheight.")
                try:
                    options["lineheight"] = float(args[i])
                except ValueError:
                    raise TerminalCommandError("--lineheight must be a number.")
            elif token == "--width":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a width value after --width.")
                try:
                    options["width"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--width must be a number.")
            elif token == "--height":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a height value after --height.")
                try:
                    options["height"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--height must be a number.")
            elif token == "--left":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a left position value after --left.")
                try:
                    options["left"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--left must be a number.")
            elif token == "--top":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a top position value after --top.")
                try:
                    options["top"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--top must be a number.")
            elif token == "--radius":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a radius value after --radius.")
                try:
                    options["radius"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--radius must be a number.")
            elif token == "--border":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a border width value after --border.")
                try:
                    options["border"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--border must be a number.")
            elif token == "--bordercolor":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a border color value after --bordercolor.")
                options["bordercolor"] = args[i]
            elif token == "--shadow":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide shadow values after --shadow.")
                options["shadow"] = args[i]
            elif token == "--opacity":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide an opacity value after --opacity.")
                try:
                    opacity = float(args[i])
                    if not 0.0 <= opacity <= 1.0:
                        raise TerminalCommandError("--opacity must be between 0.0 and 1.0.")
                    options["opacity"] = opacity
                except ValueError:
                    raise TerminalCommandError("--opacity must be a number between 0.0 and 1.0.")
            elif token == "--padding":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide padding values after --padding.")
                options["padding"] = args[i]
            elif token == "--margin":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide margin values after --margin.")
                options["margin"] = args[i]
            elif token == "--zindex":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a z-index value after --zindex.")
                try:
                    options["zindex"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--zindex must be a number.")
            elif token == "--rotate":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a rotation value after --rotate.")
                try:
                    options["rotate"] = int(args[i])
                except ValueError:
                    raise TerminalCommandError("--rotate must be a number.")
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1

        return options

    def _parse_content_arguments(self, args: Sequence[str]) -> Dict[str, Any]:
        """Parse arguments for content-related commands."""
        options: Dict[str, Any] = {
            "text": None,
            "page": None,
        }

        i = 0
        while i < len(args):
            token = args[i]
            if token == "--text":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide text content after --text.")
                options["text"] = args[i]
            elif token == "--page":
                i += 1
                if i >= len(args):
                    raise TerminalCommandError("Provide a page number after --page.")
                options["page"] = self._coerce_positive_int(args[i], "page number")
            else:
                raise TerminalCommandError(f"Unrecognized flag “{token}”.")
            i += 1

        if options["text"] is None:
            raise TerminalCommandError("Text content is required.")

        return options

    def _apply_block_edits(self, block: Dict[str, Any], options: Dict[str, Any]) -> None:
        """Apply edits to a block based on the provided options."""
        # Text formatting
        if options["bold"] is not None:
            block.setdefault("typography", {})["bold"] = options["bold"]
        if options["italic"] is not None:
            block.setdefault("typography", {})["italic"] = options["italic"]
        if options["underline"] is not None:
            block.setdefault("typography", {})["underline"] = options["underline"]
        if options["strikethrough"] is not None:
            block.setdefault("typography", {})["strikethrough"] = options["strikethrough"]
        if options["fontsize"] is not None:
            block.setdefault("typography", {})["fontSize"] = options["fontsize"]
        if options["fontfamily"] is not None:
            block.setdefault("typography", {})["fontFamily"] = options["fontfamily"]
        if options["textcolor"] is not None:
            block.setdefault("typography", {})["color"] = options["textcolor"]
        if options["align"] is not None:
            block.setdefault("typography", {})["textAlign"] = options["align"]
        if options["lineheight"] is not None:
            block.setdefault("typography", {})["lineHeight"] = options["lineheight"]

        # Position and sizing
        position = block.setdefault("position", {})
        if options["width"] is not None:
            position["width"] = options["width"]
        if options["height"] is not None:
            position["height"] = options["height"]
        if options["left"] is not None:
            position["left"] = options["left"]
        if options["top"] is not None:
            position["top"] = options["top"]

        # Visual styling
        if options["bg"] is not None:
            block["backgroundColor"] = options["bg"]
        if options["radius"] is not None:
            block["borderRadius"] = options["radius"]
        if options["border"] is not None:
            block["borderWidth"] = options["border"]
        if options["bordercolor"] is not None:
            block["borderColor"] = options["bordercolor"]
        if options["shadow"] is not None:
            block["shadow"] = options["shadow"]
        if options["opacity"] is not None:
            block["opacity"] = options["opacity"]
        if options["padding"] is not None:
            block["padding"] = options["padding"]
        if options["margin"] is not None:
            block["margin"] = options["margin"]
        if options["zindex"] is not None:
            block["zIndex"] = options["zindex"]
        if options["rotate"] is not None:
            block["rotate"] = options["rotate"]
