"""
Notes Fetcher — queries the Notes/Extracts DB in Notion for entries
linked to a given Reading Task, and converts them to NoteEntry models.
v1.1: New module for Notes DB integration.
"""

from __future__ import annotations
import logging
from typing import Optional

from app.config import settings
from app.models import NoteEntry

logger = logging.getLogger(__name__)


class NotesFetcher:
    """Fetch linked notes from the Notion Notes DB."""

    def __init__(self, notion_client):
        self.notion = notion_client

    async def fetch_notes_for_task(self, task_page_id: str) -> list[NoteEntry]:
        """
        Query the Notes DB for entries where Task relation = task_page_id.
        Returns a list of NoteEntry objects.
        """
        if not settings.notes_db_id:
            logger.debug("Notes DB ID not configured, skipping notes fetch")
            return []

        try:
            results = await self.notion.query_database(
                database_id=settings.notes_db_id,
                filter_payload={
                    "property": "Task",
                    "relation": {"contains": task_page_id},
                },
            )

            notes = []
            for page in results:
                note = self._parse_note_page(page)
                if note:
                    notes.append(note)

            logger.info(f"Fetched {len(notes)} notes for task {task_page_id[:12]}...")
            return notes

        except Exception as e:
            logger.warning(f"Failed to fetch notes: {e}")
            return []

    def _parse_note_page(self, page: dict) -> Optional[NoteEntry]:
        """Parse a Notion page from Notes DB into a NoteEntry."""
        try:
            props = page.get("properties", {})

            # Title
            title = ""
            title_prop = props.get("Name", {}).get("title", [])
            if title_prop:
                title = title_prop[0].get("plain_text", "")

            # Type (select)
            note_type = None
            type_prop = props.get("Type", {}).get("select")
            if type_prop:
                note_type = type_prop.get("name")

            # Location (rich_text)
            location = self._get_rich_text(props, "Location")

            # Content (rich_text)
            content = self._get_rich_text(props, "Content")

            # Tags (multi_select)
            tags = []
            for tag in props.get("Tags", {}).get("multi_select", []):
                tags.append(tag.get("name", ""))

            return NoteEntry(
                note_id=page["id"],
                title=title or "Untitled",
                note_type=note_type,
                location=location,
                content=content,
                tags=tags,
            )
        except Exception as e:
            logger.warning(f"Failed to parse note page: {e}")
            return None

    @staticmethod
    def _get_rich_text(props: dict, key: str) -> str:
        rt = props.get(key, {}).get("rich_text", [])
        return "".join(r.get("plain_text", "") for r in rt)


def notes_to_context(notes: list[NoteEntry]) -> str:
    """Convert a list of NoteEntry to a Markdown section for LLM input."""
    if not notes:
        return ""

    lines = ["\n---", f"## Linked Notes ({len(notes)} entries)\n"]
    for i, note in enumerate(notes, 1):
        lines.append(f"### Note {i}: {note.title}")
        if note.note_type:
            lines.append(f"**Type:** {note.note_type}")
        if note.location:
            lines.append(f"**Location:** {note.location}")
        if note.tags:
            lines.append(f"**Tags:** {', '.join(note.tags)}")
        lines.append(f"\n{note.content}\n")

    return "\n".join(lines)
