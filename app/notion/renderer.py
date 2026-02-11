"""
Renderer — converts validated LLM JSON output into Notion block arrays.
v1.1: Added flashcard renderer + CSV export for Anki/Quizlet.
"""

from __future__ import annotations
import csv
import io
import re
from typing import Optional


ITEM_TYPE_COLORS = {
    "read": "default",
    "extract": "blue",
    "reflect": "purple",
    "apply": "green",
}

DIFFICULTY_EMOJI = {1: "🟢", 2: "🟡", 3: "🟠", 4: "🔴", 5: "⚫"}


# ═══════════════════════════════════════════════════════════════════
#  Checklist
# ═══════════════════════════════════════════════════════════════════

def render_checklist(data: dict) -> list[dict]:
    blocks: list[dict] = []
    for section in data.get("checklist", []):
        blocks.append(_heading2(section["section"]))
        for item in section.get("items", []):
            text = item["text"]
            suffixes = []
            if item.get("estimated_minutes"):
                suffixes.append(f"({item['estimated_minutes']}min)")
            if item.get("acceptance_criteria"):
                suffixes.append(f"\u2192 {item['acceptance_criteria']}")
            if suffixes:
                text += "  " + "  ".join(suffixes)
            color = ITEM_TYPE_COLORS.get(item.get("type", ""), "default")
            blocks.append(_to_do(text, color=color))
    return blocks


# ═══════════════════════════════════════════════════════════════════
#  Tree
# ═══════════════════════════════════════════════════════════════════

def render_tree(data: dict) -> list[dict]:
    nodes = data.get("nodes", [])
    children_map: dict[Optional[str], list[dict]] = {}
    for n in nodes:
        pid = n.get("parent_id")
        children_map.setdefault(pid, []).append(n)
    blocks: list[dict] = []
    for root in children_map.get(None, []):
        _render_tree_node(root, children_map, 0, blocks)
    return blocks


def _render_tree_node(node, children_map, depth, blocks):
    title = node["title"]
    summary = node.get("summary", "")
    keywords = node.get("keywords", [])
    if depth == 0:
        blocks.append(_heading1(title))
    elif depth == 1:
        blocks.append(_heading2(title))
    elif depth == 2:
        blocks.append(_heading3(title))
    else:
        blocks.append(_bullet(f"**{title}**"))
    if summary:
        blocks.append(_paragraph(summary))
    if keywords:
        blocks.append(_paragraph(f"Keywords: {', '.join(keywords)}", color="gray"))
    for child in children_map.get(node["node_id"], []):
        _render_tree_node(child, children_map, depth + 1, blocks)


# ═══════════════════════════════════════════════════════════════════
#  Knowledge Pages
# ═══════════════════════════════════════════════════════════════════

def render_knowledge_page(page: dict) -> list[dict]:
    blocks: list[dict] = []
    for section in page.get("sections", []):
        blocks.append(_heading2(section["heading"]))
        md_blocks = _markdown_to_blocks(section.get("content_markdown", ""))
        blocks.extend(md_blocks)
    questions = page.get("review_questions", [])
    if questions:
        blocks.append(_heading3("Review Questions"))
        for q in questions:
            blocks.append(_numbered(q))
    links = page.get("links_to", [])
    if links:
        blocks.append(_paragraph(f"Related: {', '.join(links)}", color="gray"))
    return blocks


# ═══════════════════════════════════════════════════════════════════
#  Flashcards (v1.1)
# ═══════════════════════════════════════════════════════════════════

def render_flashcards(data: dict) -> list[dict]:
    """
    Render flashcards JSON into Notion blocks.
    Layout: heading per deck → toggle block per card (front/back).
    """
    blocks: list[dict] = []

    # Summary header
    total = sum(len(d.get("cards", [])) for d in data.get("decks", []))
    blocks.append(_paragraph(f"\U0001f4da {total} flashcards generated across {len(data.get('decks', []))} deck(s)"))
    blocks.append(_divider())

    for deck in data.get("decks", []):
        deck_name = deck.get("name", "Untitled Deck")
        blocks.append(_heading2(f"\U0001f3b4 {deck_name}"))

        if deck.get("description"):
            blocks.append(_paragraph(deck["description"], color="gray"))

        for card in deck.get("cards", []):
            diff = card.get("difficulty", 1)
            emoji = DIFFICULTY_EMOJI.get(diff, "🟢")
            card_type_label = card.get("card_type", "basic").upper()

            # Front as a callout-style block
            blocks.append(_heading3(f"{emoji} {card.get('front', 'Q')}"))

            # Back as paragraph
            back_text = card.get("back", "")
            if card.get("card_type") == "cloze":
                # Render cloze with highlighting
                back_text = f"**Cloze:** {back_text}"

            blocks.append(_paragraph(back_text))

            # Extra context
            if card.get("context"):
                blocks.append(_paragraph(f"\U0001f4d6 Context: {card['context']}", color="gray"))

            # Tags
            if card.get("tags"):
                blocks.append(_paragraph(f"Tags: {', '.join(card['tags'])}", color="gray"))

        blocks.append(_divider())

    return blocks


def render_flashcards_csv(data: dict) -> str:
    """
    Export flashcards as CSV for Anki/Quizlet import.
    Columns: Front, Back, Tags, Deck, Type, Difficulty
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Front", "Back", "Tags", "Deck", "Type", "Difficulty"])

    for deck in data.get("decks", []):
        deck_name = deck.get("name", "Default")
        for card in deck.get("cards", []):
            writer.writerow([
                card.get("front", ""),
                card.get("back", ""),
                "; ".join(card.get("tags", [])),
                deck_name,
                card.get("card_type", "basic"),
                card.get("difficulty", 1),
            ])

    return output.getvalue()


# ═══════════════════════════════════════════════════════════════════
#  Markdown → Notion Blocks
# ═══════════════════════════════════════════════════════════════════

def _markdown_to_blocks(md: str) -> list[dict]:
    blocks: list[dict] = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            lang = line.strip().lstrip("`").strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(_code("\n".join(code_lines), lang or "plain text"))
            i += 1
            continue
        if line.startswith("### "):
            blocks.append(_heading3(line[4:].strip()))
        elif line.startswith("## "):
            blocks.append(_heading2(line[3:].strip()))
        elif line.startswith("# "):
            blocks.append(_heading1(line[2:].strip()))
        elif line.startswith("> "):
            blocks.append(_quote(line[2:].strip()))
        elif line.startswith("- ") or line.startswith("* "):
            blocks.append(_bullet(line[2:].strip()))
        elif re.match(r"^\d+\.\s", line):
            text = re.sub(r"^\d+\.\s", "", line).strip()
            blocks.append(_numbered(text))
        elif line.strip():
            blocks.append(_paragraph(line.strip()))
        i += 1
    return blocks


# ═══════════════════════════════════════════════════════════════════
#  Block Constructors
# ═══════════════════════════════════════════════════════════════════

def _rich_text(text: str, color: str = "default", bold: bool = False) -> list[dict]:
    segments = []
    for i in range(0, max(len(text), 1), 2000):
        chunk = text[i : i + 2000]
        if not chunk:
            chunk = " "
        rt: dict = {"type": "text", "text": {"content": chunk}}
        annotations = {}
        if bold:
            annotations["bold"] = True
        if color != "default":
            annotations["color"] = color
        if annotations:
            rt["annotations"] = annotations
        segments.append(rt)
    return segments

def _heading1(text: str) -> dict:
    return {"type": "heading_1", "heading_1": {"rich_text": _rich_text(text)}}

def _heading2(text: str) -> dict:
    return {"type": "heading_2", "heading_2": {"rich_text": _rich_text(text)}}

def _heading3(text: str) -> dict:
    return {"type": "heading_3", "heading_3": {"rich_text": _rich_text(text)}}

def _paragraph(text: str, color: str = "default") -> dict:
    return {"type": "paragraph", "paragraph": {"rich_text": _rich_text(text, color=color)}}

def _bullet(text: str) -> dict:
    return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rich_text(text)}}

def _numbered(text: str) -> dict:
    return {"type": "numbered_list_item", "numbered_list_item": {"rich_text": _rich_text(text)}}

def _to_do(text: str, checked: bool = False, color: str = "default") -> dict:
    return {"type": "to_do", "to_do": {"rich_text": _rich_text(text, color=color), "checked": checked}}

def _quote(text: str) -> dict:
    return {"type": "quote", "quote": {"rich_text": _rich_text(text)}}

def _code(text: str, language: str = "plain text") -> dict:
    return {"type": "code", "code": {"rich_text": _rich_text(text), "language": language}}

def _divider() -> dict:
    return {"type": "divider", "divider": {}}
