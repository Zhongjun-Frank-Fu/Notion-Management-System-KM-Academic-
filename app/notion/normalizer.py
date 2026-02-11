"""
Block Normalizer — converts Notion blocks to structured Markdown.
v1.1: Updated to accept NoteEntry list for context building.
"""

from __future__ import annotations
from typing import Optional

from app.models import TaskMetadata, NoteEntry


def normalize_blocks(blocks: list[dict], depth: int = 0) -> str:
    lines: list[str] = []
    for block in blocks:
        line = _block_to_md(block, depth)
        if line is not None:
            lines.append(line)
        children = block.get("children", [])
        if children:
            lines.append(normalize_blocks(children, depth + 1))
    return "\n".join(lines)


def _block_to_md(block: dict, depth: int) -> Optional[str]:
    btype = block.get("type", "")
    data = block.get(btype, {})
    indent = "  " * depth

    match btype:
        case "heading_1":
            return f"# {_rich_text(data)}"
        case "heading_2":
            return f"## {_rich_text(data)}"
        case "heading_3":
            return f"### {_rich_text(data)}"
        case "paragraph":
            text = _rich_text(data)
            return f"{indent}{text}" if text else ""
        case "bulleted_list_item":
            return f"{indent}- {_rich_text(data)}"
        case "numbered_list_item":
            return f"{indent}1. {_rich_text(data)}"
        case "to_do":
            checked = "x" if data.get("checked") else " "
            return f"{indent}- [{checked}] {_rich_text(data)}"
        case "quote":
            text = _rich_text(data)
            return "\n".join(f"{indent}> {line}" for line in text.split("\n"))
        case "code":
            lang = data.get("language", "")
            text = _rich_text(data)
            return f"{indent}```{lang}\n{indent}{text}\n{indent}```"
        case "callout":
            icon = data.get("icon", {}).get("emoji", "\U0001f4a1")
            return f"{indent}> {icon} {_rich_text(data)}"
        case "divider":
            return f"{indent}---"
        case "toggle":
            return f"{indent}## {_rich_text(data)} (collapsed)"
        case "image":
            caption = _rich_text_list(data.get("caption", []))
            url = _get_file_url(data)
            return f"{indent}[image: {caption or url or 'untitled'}]"
        case "file" | "pdf":
            url = _get_file_url(data)
            return f"{indent}[file: {url or 'attachment'}]"
        case "embed" | "bookmark":
            url = data.get("url", "")
            return f"{indent}[embed: {url}]"
        case "child_page":
            title = data.get("title", "untitled")
            return f"{indent}[subpage: {title}]"
        case "child_database":
            title = data.get("title", "untitled")
            return f"{indent}[database: {title}]"
        case "table_of_contents" | "breadcrumb" | "column_list" | "column":
            return None
        case _:
            text = _rich_text(data)
            return f"{indent}{text}" if text else None


def _rich_text(data: dict) -> str:
    rt = data.get("rich_text", [])
    return _rich_text_list(rt)


def _rich_text_list(rt_list: list[dict]) -> str:
    parts: list[str] = []
    for rt in rt_list:
        text = rt.get("plain_text", "")
        annotations = rt.get("annotations", {})
        if annotations.get("code"):
            text = f"`{text}`"
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("strikethrough"):
            text = f"~~{text}~~"
        href = rt.get("href")
        if href and not annotations.get("code"):
            text = f"[{text}]({href})"
        if rt.get("type") == "mention":
            mention = rt.get("mention", {})
            mtype = mention.get("type", "")
            if mtype == "page":
                text = f"[[{text}]]"
            elif mtype == "user":
                text = f"@{text}"
        parts.append(text)
    return "".join(parts)


def _get_file_url(data: dict) -> str:
    if "file" in data:
        return data["file"].get("url", "")
    if "external" in data:
        return data["external"].get("url", "")
    return ""


def build_llm_input(
    markdown: str,
    metadata: TaskMetadata,
    notes: Optional[list[NoteEntry]] = None,
) -> str:
    """Assemble full LLM input with metadata header + content + notes."""
    header_lines = ["---", f"title: {metadata.title}"]
    if metadata.source_name:
        header_lines.append(f"source: {metadata.source_name} ({metadata.source_type or 'unknown'})")
    if metadata.source_citation:
        header_lines.append(f"citation: {metadata.source_citation}")
    if metadata.source_url:
        header_lines.append(f"source_url: {metadata.source_url}")
    if metadata.status:
        header_lines.append(f"task_status: {metadata.status}")
    header_lines.append("---\n")

    parts = ["\n".join(header_lines), markdown]

    # Append linked notes
    if notes:
        parts.append(f"\n\n---\n## Linked Notes ({len(notes)} entries)\n")
        for i, note in enumerate(notes, 1):
            parts.append(f"### Note {i}: {note.title}")
            if note.note_type:
                parts.append(f"**Type:** {note.note_type}")
            if note.location:
                parts.append(f"**Location:** {note.location}")
            if note.tags:
                parts.append(f"**Tags:** {', '.join(note.tags)}")
            parts.append(f"\n{note.content}\n")

    return "\n".join(parts)
