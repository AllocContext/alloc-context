from __future__ import annotations

import html
import re
from typing import Literal

_INLINE = re.compile(r"\*\*(.+?)\*\*|_(.+?)_|`(.+?)`")
_TABLE_ROW = re.compile(r"^\|(.+)\|$")
_TABLE_SEP = re.compile(r"^\|[\s\-:|]+\|$")


def _inline_plain(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return match.group(1) or match.group(2) or match.group(3) or ""

    return _INLINE.sub(repl, text).strip()


def _inline_html(text: str) -> str:
    parts: list[str] = []
    pos = 0
    for match in _INLINE.finditer(text):
        if match.start() > pos:
            parts.append(html.escape(text[pos : match.start()]))
        if match.group(1):
            parts.append(f"<strong>{html.escape(match.group(1))}</strong>")
        elif match.group(2):
            parts.append(f"<em>{html.escape(match.group(2))}</em>")
        elif match.group(3):
            parts.append(f"<code>{html.escape(match.group(3))}</code>")
        pos = match.end()
    parts.append(html.escape(text[pos:]))
    return "".join(parts)


def _split_table_cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip("|").split("|")]


def markdown_to_plain(markdown: str) -> str:
    """Convert brief markdown to a readable plain-text email body."""
    lines: list[str] = []
    in_table = False

    for raw in markdown.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            if lines and lines[-1] != "":
                lines.append("")
            in_table = False
            continue

        if _TABLE_SEP.match(stripped):
            in_table = True
            continue

        table_match = _TABLE_ROW.match(stripped)
        if table_match:
            cells = [_inline_plain(cell) for cell in _split_table_cells(stripped)]
            if in_table and len(cells) >= 2:
                if cells[0].lower() == "id":
                    continue
                label = " — ".join(cell for cell in cells[2:5] if cell and cell != "—")
                status = cells[5] if len(cells) > 5 else ""
                row_text = f"• #{cells[0]} ({cells[1]}): {label}"
                if status:
                    row_text = f"{row_text} [{status}]"
                lines.append(row_text)
            else:
                lines.append(" | ".join(cells))
            in_table = True
            continue

        in_table = False

        if stripped.startswith("# "):
            lines.append(_inline_plain(stripped[2:]).upper())
            lines.append("")
            continue
        if stripped.startswith("## "):
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(_inline_plain(stripped[3:]))
            continue
        if stripped.startswith("- "):
            lines.append(f"• {_inline_plain(stripped[2:])}")
            continue
        lines.append(_inline_plain(stripped))

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def markdown_to_html(markdown: str) -> str:
    """Convert brief markdown to a simple HTML email body."""
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    table_rows: list[list[str]] = []
    in_table = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(
                f"<p>{'<br>'.join(_inline_html(line) for line in paragraph)}</p>"
            )
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            items = "".join(f"<li>{_inline_html(item)}</li>" for item in list_items)
            blocks.append(f"<ul style=\"margin:0 0 1em 1.2em;padding:0;\">{items}</ul>")
            list_items = []

    def flush_table() -> None:
        nonlocal table_rows, in_table
        if not table_rows:
            in_table = False
            return
        head, *body = table_rows
        thead = "".join(f"<th>{_inline_html(cell)}</th>" for cell in head)
        tbody_rows = []
        for row in body:
            tbody_rows.append(
                "".join(f"<td>{_inline_html(cell)}</td>" for cell in row)
            )
        tbody = "".join(f"<tr>{row}</tr>" for row in tbody_rows)
        blocks.append(
            "<table style=\"border-collapse:collapse;width:100%;margin:0 0 1em;\">"
            f"<thead><tr>{thead}</tr></thead>"
            f"<tbody>{tbody}</tbody></table>"
        )
        table_rows = []
        in_table = False

    for raw in markdown.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_list()
            flush_paragraph()
            flush_table()
            continue

        if _TABLE_SEP.match(stripped):
            in_table = True
            continue

        table_match = _TABLE_ROW.match(stripped)
        if table_match:
            flush_list()
            flush_paragraph()
            table_rows.append([_inline_plain(cell) for cell in _split_table_cells(stripped)])
            in_table = True
            continue

        if in_table:
            flush_table()

        if stripped.startswith("# "):
            flush_list()
            flush_paragraph()
            blocks.append(
                f"<h1 style=\"font-size:1.25em;margin:0 0 0.75em;\">"
                f"{_inline_html(stripped[2:])}</h1>"
            )
            continue
        if stripped.startswith("## "):
            flush_list()
            flush_paragraph()
            blocks.append(
                f"<h2 style=\"font-size:1.05em;margin:1.25em 0 0.5em;\">"
                f"{_inline_html(stripped[3:])}</h2>"
            )
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            list_items.append(stripped[2:])
            continue

        flush_list()
        paragraph.append(stripped)

    flush_list()
    flush_paragraph()
    flush_table()

    inner = "\n".join(blocks)
    return (
        "<!DOCTYPE html><html><body "
        'style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;'
        "line-height:1.5;color:#1a1a1a;max-width:640px;margin:0;padding:16px;\">"
        f"{inner}</body></html>"
    )


def render_markdown_email(markdown: str) -> tuple[str, str]:
    """Return (plain_text, html) suitable for multipart email."""
    return markdown_to_plain(markdown), markdown_to_html(markdown)
