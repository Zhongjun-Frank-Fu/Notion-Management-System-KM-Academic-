"""
Notion Workspace Setup — automatically creates all required databases
and a Dashboard page under a user-specified parent page.

Usage:
    POST /setup/init  { "parent_page_id": "..." }
    CLI:  python -m app.notion.setup <parent_page_id>

Creates:
    📚 Reading Tasks DB    — main task tracker
    📝 Notes DB            — extracts & annotations
    🌳 Tree Nodes DB       — generated knowledge taxonomy
    📄 Knowledge Pages DB  — generated knowledge articles
    📊 Dashboard           — overview page with callouts + embeds

Returns all database IDs for .env configuration.

v1.2: New module.
"""

from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.notion.client import NotionClient, notion

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# Property builder helpers
# ══════════════════════════════════════════════════════════════════

def _title_prop() -> dict:
    return {"title": {}}


def _rich_text_prop() -> dict:
    return {"rich_text": {}}


def _url_prop() -> dict:
    return {"url": {}}


def _number_prop(fmt: str = "number") -> dict:
    return {"number": {"format": fmt}}


def _checkbox_prop() -> dict:
    return {"checkbox": {}}


def _select_prop(options: list[str], colors: Optional[list[str]] = None) -> dict:
    opts = []
    default_colors = ["blue", "green", "yellow", "orange", "red",
                      "purple", "pink", "gray", "brown", "default"]
    for i, name in enumerate(options):
        color = (colors[i] if colors and i < len(colors)
                 else default_colors[i % len(default_colors)])
        opts.append({"name": name, "color": color})
    return {"select": {"options": opts}}


def _multi_select_prop(options: Optional[list[str]] = None) -> dict:
    if not options:
        return {"multi_select": {"options": []}}
    return {"multi_select": {"options": [{"name": o} for o in options]}}


def _relation_prop(database_id: str, single: bool = False) -> dict:
    rel: dict[str, Any] = {"database_id": database_id}
    if single:
        rel["type"] = "single_property"
        rel["single_property"] = {}
    else:
        rel["type"] = "dual_property"
        rel["dual_property"] = {}
    return {"relation": rel}


def _self_relation_prop(database_id: str) -> dict:
    """Self-referencing relation (e.g. Parent → same DB)."""
    return {"relation": {
        "database_id": database_id,
        "type": "single_property",
        "single_property": {},
    }}


def _date_prop() -> dict:
    return {"date": {}}


def _created_time_prop() -> dict:
    return {"created_time": {}}


def _last_edited_time_prop() -> dict:
    return {"last_edited_time": {}}


# ══════════════════════════════════════════════════════════════════
# Database schemas
# ══════════════════════════════════════════════════════════════════

def reading_tasks_schema() -> dict[str, Any]:
    """Reading Tasks DB — main task tracker."""
    return {
        "Name":              _title_prop(),
        "Status":            _select_prop(
            ["Not started", "Reading", "Synthesizing", "Complete", "Archived"],
            ["gray",        "blue",    "yellow",       "green",    "brown"],
        ),
        "AI Stage":          _select_prop(
            ["Idle",  "Queued", "Running", "Needs review", "Approved", "Failed"],
            ["gray",  "blue",   "yellow",  "orange",       "green",    "red"],
        ),
        "Source Name":       _rich_text_prop(),
        "Source Type":       _select_prop(
            ["Book", "Article", "Paper", "Video", "Podcast", "Course", "Other"],
        ),
        "Source URL":        _url_prop(),
        "Source Citation":   _rich_text_prop(),
        "Checklist Page ID": _rich_text_prop(),
        "Tree Page ID":      _rich_text_prop(),
        "Gen Pages Root ID": _rich_text_prop(),
        "Run ID":            _rich_text_prop(),
        "Error":             _rich_text_prop(),
        "Created":           _created_time_prop(),
        "Last Edited":       _last_edited_time_prop(),
    }


def notes_schema(tasks_db_id: str) -> dict[str, Any]:
    """Notes / Extracts DB — linked to Reading Tasks."""
    return {
        "Name":     _title_prop(),
        "Type":     _select_prop(
            ["Quote", "Idea", "Question", "TODO", "Summary", "Critique"],
            ["blue",  "green", "yellow",  "orange", "purple", "red"],
        ),
        "Location": _rich_text_prop(),
        "Content":  _rich_text_prop(),
        "Tags":     _multi_select_prop(),
        "Task":     _relation_prop(tasks_db_id),
        "Created":  _created_time_prop(),
    }


def tree_nodes_schema(tasks_db_id: str) -> dict[str, Any]:
    """Tree Nodes DB — generated knowledge taxonomy.
    Note: Parent (self-relation) is added in a second step after DB creation.
    """
    return {
        "Name":     _title_prop(),
        "Summary":  _rich_text_prop(),
        "Keywords": _multi_select_prop(),
        "Status":   _select_prop(
            ["Draft", "Approved", "Archived"],
            ["gray",  "green",    "brown"],
        ),
        "Scope":    _relation_prop(tasks_db_id),
        "Created":  _created_time_prop(),
    }


def knowledge_pages_schema(tasks_db_id: str) -> dict[str, Any]:
    """Knowledge Pages DB — generated knowledge articles."""
    return {
        "Name":     _title_prop(),
        "Task":     _relation_prop(tasks_db_id),
        "Status":   _select_prop(
            ["Needs review", "Approved", "Archived"],
            ["orange",       "green",    "brown"],
        ),
        "Version":  _number_prop(),
        "Page ID":  _rich_text_prop(),
        "Template": _select_prop(
            ["concept", "process", "comparison", "case_study", "definition", "example"],
            ["blue",    "green",   "yellow",     "orange",     "purple",     "pink"],
        ),
        "Created":  _created_time_prop(),
    }


# ══════════════════════════════════════════════════════════════════
# Dashboard page builder
# ══════════════════════════════════════════════════════════════════

def _dashboard_blocks(db_ids: dict[str, str], parent_page_id: str) -> list[dict]:
    """Build the Notion blocks for the Dashboard page."""
    blocks: list[dict] = []

    # ── Header callout
    blocks.append({
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "🧠"},
            "rich_text": [{"type": "text", "text": {
                "content": "Knowledge Management System — Dashboard\n"
                           "Auto-generated by KM System v1.2 Setup"
            }}],
            "color": "blue_background",
        },
    })
    blocks.append(_divider())

    # ── System Info
    blocks.append(_heading2("⚙️ System Configuration"))
    blocks.append(_callout(
        "📋",
        f"Parent Page: {parent_page_id}\n"
        f"Reading Tasks DB: {db_ids.get('tasks', 'N/A')}\n"
        f"Notes DB: {db_ids.get('notes', 'N/A')}\n"
        f"Tree Nodes DB: {db_ids.get('tree_nodes', 'N/A')}\n"
        f"Knowledge Pages DB: {db_ids.get('knowledge_pages', 'N/A')}",
        color="gray_background",
    ))

    # ── .env block
    blocks.append(_heading3("📄 .env Configuration (copy to your .env file)"))
    env_lines = (
        f"# KM System — Auto-generated DB IDs\n"
        f"NOTES_DB_ID={db_ids.get('notes', '')}\n"
        f"TREE_NODES_DB_ID={db_ids.get('tree_nodes', '')}\n"
        f"KNOWLEDGE_PAGES_DB_ID={db_ids.get('knowledge_pages', '')}\n"
    )
    blocks.append({"type": "code", "code": {
        "rich_text": [{"type": "text", "text": {"content": env_lines}}],
        "language": "shell",
    }})
    blocks.append(_divider())

    # ── Quick links section
    blocks.append(_heading2("📚 Databases"))

    for label, emoji, db_id in [
        ("Reading Tasks",   "📚", db_ids.get("tasks")),
        ("Notes",           "📝", db_ids.get("notes")),
        ("Tree Nodes",      "🌳", db_ids.get("tree_nodes")),
        ("Knowledge Pages", "📄", db_ids.get("knowledge_pages")),
    ]:
        if db_id:
            # Linked database embed — shows an inline view of the DB
            blocks.append({
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": f"{emoji} {label}"}}],
                    "is_toggleable": True,
                },
            })

    blocks.append(_divider())

    # ── API Endpoints section
    blocks.append(_heading2("🔌 API Endpoints"))
    api_info = (
        "POST /webhook/notion — Trigger AI generation\n"
        "  Body: {task_page_id, action_type, secret}\n"
        "  Actions: checklist | tree | pages | flashcards | approve\n\n"
        "GET /health — System health check\n"
        "GET /jobs/{job_id} — Job status\n"
        "POST /jobs/{job_id}/retry — Retry failed job\n"
        "GET /dashboard/stats — Aggregated statistics\n"
        "GET /dashboard/runs — Recent run history\n"
        "GET /dashboard/versions/{task_page_id} — Version history"
    )
    blocks.append({"type": "code", "code": {
        "rich_text": [{"type": "text", "text": {"content": api_info}}],
        "language": "plain text",
    }})
    blocks.append(_divider())

    # ── Workflow guide
    blocks.append(_heading2("🔄 Workflow"))
    steps = [
        ("1️⃣", "Add a reading task to the Reading Tasks DB"),
        ("2️⃣", "Add notes/extracts to the Notes DB, linked to the task"),
        ("3️⃣", "Trigger AI generation via webhook (checklist → tree → pages → flashcards)"),
        ("4️⃣", "Review generated content (AI Stage = Needs review)"),
        ("5️⃣", "Approve via webhook (cascades to all generated content)"),
    ]
    for emoji, text in steps:
        blocks.append(_callout(emoji, text, color="default"))

    return blocks


def _heading2(text: str) -> dict:
    return {"type": "heading_2", "heading_2": {
        "rich_text": [{"type": "text", "text": {"content": text}}],
    }}


def _heading3(text: str) -> dict:
    return {"type": "heading_3", "heading_3": {
        "rich_text": [{"type": "text", "text": {"content": text}}],
    }}


def _callout(emoji: str, text: str, color: str = "default") -> dict:
    return {"type": "callout", "callout": {
        "icon": {"type": "emoji", "emoji": emoji},
        "rich_text": [{"type": "text", "text": {"content": text}}],
        "color": color,
    }}


def _divider() -> dict:
    return {"type": "divider", "divider": {}}


# ══════════════════════════════════════════════════════════════════
# Result model
# ══════════════════════════════════════════════════════════════════

@dataclass
class SetupResult:
    parent_page_id: str
    tasks_db_id: str = ""
    notes_db_id: str = ""
    tree_nodes_db_id: str = ""
    knowledge_pages_db_id: str = ""
    dashboard_page_id: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return bool(self.tasks_db_id) and not self.errors

    def to_env(self) -> str:
        """Generate .env snippet."""
        return (
            f"# KM System — Auto-generated by setup\n"
            f"NOTES_DB_ID={self.notes_db_id}\n"
            f"TREE_NODES_DB_ID={self.tree_nodes_db_id}\n"
            f"KNOWLEDGE_PAGES_DB_ID={self.knowledge_pages_db_id}\n"
        )

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "parent_page_id": self.parent_page_id,
            "databases": {
                "reading_tasks": self.tasks_db_id,
                "notes": self.notes_db_id,
                "tree_nodes": self.tree_nodes_db_id,
                "knowledge_pages": self.knowledge_pages_db_id,
            },
            "dashboard_page_id": self.dashboard_page_id,
            "env_snippet": self.to_env(),
            "errors": self.errors,
        }


# ══════════════════════════════════════════════════════════════════
# Main setup orchestrator
# ══════════════════════════════════════════════════════════════════

class WorkspaceSetup:
    """
    Creates the full Notion workspace for the KM system.

    Flow:
      1. Create Reading Tasks DB (inline in parent page)
      2. Create Notes DB (relation → Tasks)
      3. Create Tree Nodes DB (relation → Tasks, self-relation Parent)
      4. Create Knowledge Pages DB (relation → Tasks)
      5. Create Dashboard page with config + embeds
    """

    def __init__(self, client: Optional[NotionClient] = None):
        self.notion = client or notion

    async def run(self, parent_page_id: str) -> SetupResult:
        result = SetupResult(parent_page_id=parent_page_id)
        logger.info(f"Starting workspace setup under page {parent_page_id[:12]}...")

        # Step 1: Reading Tasks DB
        try:
            tasks_db = await self.notion.create_database(
                parent_page_id=parent_page_id,
                title="📚 Reading Tasks",
                properties=reading_tasks_schema(),
                icon="📚",
            )
            result.tasks_db_id = tasks_db["id"]
            logger.info(f"✅ Created Reading Tasks DB: {result.tasks_db_id}")
        except Exception as e:
            result.errors.append(f"Failed to create Reading Tasks DB: {e}")
            logger.error(f"❌ Reading Tasks DB: {e}")
            return result  # Can't continue without main DB

        # Step 2: Notes DB
        try:
            notes_db = await self.notion.create_database(
                parent_page_id=parent_page_id,
                title="📝 Notes & Extracts",
                properties=notes_schema(result.tasks_db_id),
                icon="📝",
            )
            result.notes_db_id = notes_db["id"]
            logger.info(f"✅ Created Notes DB: {result.notes_db_id}")
        except Exception as e:
            result.errors.append(f"Failed to create Notes DB: {e}")
            logger.error(f"❌ Notes DB: {e}")

        # Step 3: Tree Nodes DB (two-phase: create, then add self-relation)
        try:
            tree_db = await self.notion.create_database(
                parent_page_id=parent_page_id,
                title="🌳 Tree Nodes",
                properties=tree_nodes_schema(result.tasks_db_id),
                icon="🌳",
            )
            result.tree_nodes_db_id = tree_db["id"]
            logger.info(f"✅ Created Tree Nodes DB: {result.tree_nodes_db_id}")

            # Add self-referencing Parent relation
            try:
                await self.notion.update_database(
                    database_id=result.tree_nodes_db_id,
                    properties={
                        "Parent": _self_relation_prop(result.tree_nodes_db_id),
                    },
                )
                logger.info("  └─ Added Parent self-relation")
            except Exception as e:
                result.errors.append(f"Failed to add Parent relation to Tree Nodes DB: {e}")
                logger.warning(f"  └─ ⚠️ Parent relation: {e}")

        except Exception as e:
            result.errors.append(f"Failed to create Tree Nodes DB: {e}")
            logger.error(f"❌ Tree Nodes DB: {e}")

        # Step 4: Knowledge Pages DB
        try:
            kp_db = await self.notion.create_database(
                parent_page_id=parent_page_id,
                title="📄 Knowledge Pages",
                properties=knowledge_pages_schema(result.tasks_db_id),
                icon="📄",
            )
            result.knowledge_pages_db_id = kp_db["id"]
            logger.info(f"✅ Created Knowledge Pages DB: {result.knowledge_pages_db_id}")
        except Exception as e:
            result.errors.append(f"Failed to create Knowledge Pages DB: {e}")
            logger.error(f"❌ Knowledge Pages DB: {e}")

        # Step 5: Dashboard page
        try:
            db_ids = {
                "tasks": result.tasks_db_id,
                "notes": result.notes_db_id,
                "tree_nodes": result.tree_nodes_db_id,
                "knowledge_pages": result.knowledge_pages_db_id,
            }
            dashboard = await self.notion.create_page(
                parent_page_id=parent_page_id,
                title="📊 KM Dashboard",
                icon="📊",
            )
            result.dashboard_page_id = dashboard["id"]

            blocks = _dashboard_blocks(db_ids, parent_page_id)
            await self.notion.append_blocks(result.dashboard_page_id, blocks)
            logger.info(f"✅ Created Dashboard: {result.dashboard_page_id}")
        except Exception as e:
            result.errors.append(f"Failed to create Dashboard: {e}")
            logger.error(f"❌ Dashboard: {e}")

        # Summary
        created = sum(1 for x in [
            result.tasks_db_id, result.notes_db_id,
            result.tree_nodes_db_id, result.knowledge_pages_db_id,
        ] if x)
        logger.info(
            f"Setup complete: {created}/4 databases, "
            f"dashboard={'✅' if result.dashboard_page_id else '❌'}, "
            f"errors={len(result.errors)}"
        )
        return result


# ══════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════

async def _main(parent_page_id: str):
    setup = WorkspaceSetup()
    result = await setup.run(parent_page_id)

    print("\n" + "=" * 60)
    print("  KM System — Workspace Setup Result")
    print("=" * 60)

    if result.success:
        print(f"\n✅ Setup successful!\n")
    else:
        print(f"\n⚠️  Setup completed with {len(result.errors)} error(s)\n")

    print(f"  📚 Reading Tasks DB:    {result.tasks_db_id or '❌ Failed'}")
    print(f"  📝 Notes DB:            {result.notes_db_id or '❌ Failed'}")
    print(f"  🌳 Tree Nodes DB:       {result.tree_nodes_db_id or '❌ Failed'}")
    print(f"  📄 Knowledge Pages DB:  {result.knowledge_pages_db_id or '❌ Failed'}")
    print(f"  📊 Dashboard:           {result.dashboard_page_id or '❌ Failed'}")

    if result.errors:
        print(f"\nErrors:")
        for err in result.errors:
            print(f"  ⚠️  {err}")

    print(f"\n{'─' * 60}")
    print("Add these to your .env file:\n")
    print(result.to_env())
    print("─" * 60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m app.notion.setup <parent_page_id>")
        print("\n  parent_page_id: The Notion page ID where databases will be created.")
        print("  You can find this in the Notion page URL:")
        print("    https://notion.so/Your-Page-<page_id>")
        sys.exit(1)

    page_id = sys.argv[1].strip().replace("-", "")
    asyncio.run(_main(page_id))
