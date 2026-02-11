"""
Writer — orchestrates write-back to Notion.
v1.1: Added flashcards, tree nodes DB sync, enhanced approve, versioning.
"""

from __future__ import annotations
import logging
from typing import Optional

from app.notion.client import notion, NotionClient
from app.notion.renderer import (
    render_checklist, render_tree, render_knowledge_page,
    render_flashcards, render_flashcards_csv,
)
from app.db.repository import repo
from app.config import settings
from app.models import AIStage

logger = logging.getLogger(__name__)


class NotionWriter:

    def __init__(self, client: Optional[NotionClient] = None):
        self.notion = client or notion

    # ── Checklist ──────────────────────────────────────────────────

    async def write_checklist(self, task_page_id: str, data: dict, run_id: str, version: int) -> str:
        title = f"\u2705 Checklist v{version}: {data.get('task_title', 'Untitled')}"
        page_id = await self._get_or_create_subpage(task_page_id, "checklist", title, icon="\u2705")
        await self.notion.delete_all_blocks(page_id)
        blocks = render_checklist(data)
        await self.notion.append_blocks(page_id, blocks)
        await self.notion.update_page_properties(task_page_id, {
            "AI Stage": NotionClient.prop_select(AIStage.NEEDS_REVIEW.value),
            "Checklist Page ID": NotionClient.prop_rich_text(page_id),
            "Run ID": NotionClient.prop_rich_text(run_id),
        })
        logger.info(f"Checklist v{version} written to {page_id} ({len(blocks)} blocks)")
        return page_id

    # ── Tree + DB Sync ─────────────────────────────────────────────

    async def write_tree(self, task_page_id: str, data: dict, run_id: str, version: int) -> str:
        scope = data.get("scope", "Untitled")
        title = f"\U0001f333 Tree v{version}: {scope}"
        page_id = await self._get_or_create_subpage(task_page_id, "tree", title, icon="\U0001f333")
        await self.notion.delete_all_blocks(page_id)
        blocks = render_tree(data)
        await self.notion.append_blocks(page_id, blocks)

        # v1.1: Sync tree nodes to Tree Nodes DB
        await self._sync_tree_nodes_db(task_page_id, data)

        await self.notion.update_page_properties(task_page_id, {
            "AI Stage": NotionClient.prop_select(AIStage.NEEDS_REVIEW.value),
            "Tree Page ID": NotionClient.prop_rich_text(page_id),
            "Run ID": NotionClient.prop_rich_text(run_id),
        })
        logger.info(f"Tree v{version} written to {page_id} ({len(blocks)} blocks)")
        return page_id

    async def _sync_tree_nodes_db(self, task_page_id: str, data: dict):
        """Create records in Tree Nodes DB for each node (status=Draft)."""
        if not settings.tree_nodes_db_id:
            logger.debug("Tree Nodes DB ID not configured, skipping DB sync")
            return

        nodes = data.get("nodes", [])
        node_page_ids: dict[str, str] = {}  # node_id → notion_page_id

        # Pass 1: create all nodes
        for node in nodes:
            properties = {
                "Name": NotionClient.prop_title(node["title"]),
                "Summary": NotionClient.prop_rich_text(node.get("summary", "")),
                "Keywords": NotionClient.prop_multi_select(node.get("keywords", [])),
                "Status": NotionClient.prop_select("Draft"),
                "Scope": NotionClient.prop_relation([task_page_id]),
            }
            page = await self.notion.create_db_page(settings.tree_nodes_db_id, properties)
            node_page_ids[node["node_id"]] = page["id"]
            await repo.save_tree_node(task_page_id, node["node_id"], page["id"])

        # Pass 2: set Parent relations
        for node in nodes:
            parent_id = node.get("parent_id")
            if parent_id and parent_id in node_page_ids:
                notion_id = node_page_ids[node["node_id"]]
                await self.notion.update_page_properties(notion_id, {
                    "Parent": NotionClient.prop_relation([node_page_ids[parent_id]]),
                })

        logger.info(f"Synced {len(nodes)} tree nodes to DB")

    # ── Knowledge Pages ────────────────────────────────────────────

    async def write_pages(self, task_page_id: str, data: dict, run_id: str, version: int) -> str:
        root_title = f"\U0001f4da Generated Pages v{version}"
        root_id = await self._get_or_create_subpage(task_page_id, "pages_root", root_title, icon="\U0001f4da")
        page_ids: list[str] = []
        for page_data in data.get("pages", []):
            page_title = page_data.get("title", "Untitled Page")
            child = await self.notion.create_page(parent_page_id=root_id, title=page_title, icon="\U0001f4c4")
            child_id = child["id"]
            page_ids.append(child_id)
            blocks = render_knowledge_page(page_data)
            await self.notion.append_blocks(child_id, blocks)

            # v1.1: Sync to Knowledge Pages DB if configured
            if settings.knowledge_pages_db_id:
                await self.notion.create_db_page(settings.knowledge_pages_db_id, {
                    "Name": NotionClient.prop_title(page_title),
                    "Task": NotionClient.prop_relation([task_page_id]),
                    "Status": NotionClient.prop_select("Needs review"),
                    "Version": NotionClient.prop_number(version),
                    "Page ID": NotionClient.prop_rich_text(child_id),
                    "Template": NotionClient.prop_select(page_data.get("template", "concept")),
                })

        await self.notion.update_page_properties(task_page_id, {
            "AI Stage": NotionClient.prop_select(AIStage.NEEDS_REVIEW.value),
            "Gen Pages Root ID": NotionClient.prop_rich_text(root_id),
            "Run ID": NotionClient.prop_rich_text(run_id),
        })
        logger.info(f"Pages v{version}: root {root_id}, {len(page_ids)} pages created")
        return root_id

    # ── Flashcards (v1.1) ──────────────────────────────────────────

    async def write_flashcards(self, task_page_id: str, data: dict, run_id: str, version: int) -> str:
        """
        Write flashcards to a subpage with two sections:
        1. Visual flashcard blocks in Notion
        2. CSV export block for Anki/Quizlet import
        """
        total_cards = sum(len(d.get("cards", [])) for d in data.get("decks", []))
        title = f"\U0001f3b4 Flashcards v{version} ({total_cards} cards)"

        page_id = await self._get_or_create_subpage(task_page_id, "flashcards", title, icon="\U0001f3b4")
        await self.notion.delete_all_blocks(page_id)

        # Render visual blocks
        blocks = render_flashcards(data)

        # Append CSV export as a code block
        csv_content = render_flashcards_csv(data)
        blocks.append({"type": "heading_2", "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "\U0001f4e5 Anki/Quizlet CSV Export"}}]
        }})
        blocks.append({"type": "paragraph", "paragraph": {
            "rich_text": [{"type": "text", "text": {
                "content": "Copy the CSV below and import into Anki or Quizlet:"
            }, "annotations": {"color": "gray"}}]
        }})
        blocks.append({"type": "code", "code": {
            "rich_text": [{"type": "text", "text": {"content": csv_content[:2000]}}],
            "language": "csv",
        }})

        await self.notion.append_blocks(page_id, blocks)

        await self.notion.update_page_properties(task_page_id, {
            "AI Stage": NotionClient.prop_select(AIStage.NEEDS_REVIEW.value),
            "Run ID": NotionClient.prop_rich_text(run_id),
        })

        logger.info(f"Flashcards v{version} written to {page_id} ({total_cards} cards)")
        return page_id

    # ── Approve (v1.2 enhanced) ────────────────────────────────────

    async def write_approve(self, task_page_id: str, run_id: str):
        """
        Full cascade approve:
        1. Update Tree Nodes DB → Approved
        2. Update Knowledge Pages DB → Approved
        3. Update Reading Task → AI Stage=Approved, Status=Synthesizing
        """
        # 1. Approve tree nodes in local DB
        await repo.approve_tree_nodes(task_page_id)

        # 2. Approve tree nodes in Notion DB
        tree_nodes = await repo.get_tree_nodes(task_page_id)
        for node in tree_nodes:
            try:
                await self.notion.update_page_properties(node["notion_page_id"], {
                    "Status": NotionClient.prop_select("Approved"),
                })
            except Exception as e:
                logger.warning(f"Failed to approve tree node {node['node_id']}: {e}")

        # 3. Approve knowledge pages in Notion DB
        if settings.knowledge_pages_db_id:
            pages = await self.notion.query_database(
                database_id=settings.knowledge_pages_db_id,
                filter_payload={
                    "property": "Task",
                    "relation": {"contains": task_page_id},
                },
            )
            for page in pages:
                try:
                    await self.notion.update_page_properties(page["id"], {
                        "Status": NotionClient.prop_select("Approved"),
                    })
                except Exception as e:
                    logger.warning(f"Failed to approve knowledge page: {e}")

        # 4. Update Reading Task
        await self.notion.update_page_properties(task_page_id, {
            "AI Stage": NotionClient.prop_select(AIStage.APPROVED.value),
            "Status": NotionClient.prop_select("Synthesizing"),
            "Run ID": NotionClient.prop_rich_text(run_id),
        })
        logger.info(f"Task {task_page_id} fully approved (tree nodes + pages)")

    # ── Error Write-back ───────────────────────────────────────────

    async def write_error(self, task_page_id: str, error_msg: str):
        try:
            await self.notion.update_page_properties(task_page_id, {
                "AI Stage": NotionClient.prop_select(AIStage.FAILED.value),
                "Error": NotionClient.prop_rich_text(error_msg[:2000]),
            })
        except Exception as e:
            logger.error(f"Failed to write error to Notion: {e}")

    # ── Helpers ─────────────────────────────────────────────────────

    async def _get_or_create_subpage(
        self, task_page_id: str, page_type: str, title: str, icon: str = ""
    ) -> str:
        cached = await repo.get_cached_page(task_page_id, page_type)
        if cached:
            # Update title to reflect new version
            try:
                await self.notion.update_page_properties(cached, {
                    "title": [{"type": "text", "text": {"content": title}}]
                })
            except Exception:
                pass
            return cached

        page = await self.notion.create_page(
            parent_page_id=task_page_id, title=title,
            icon=icon if icon else None,
        )
        page_id = page["id"]
        await repo.set_cached_page(task_page_id, page_type, page_id)
        return page_id


writer = NotionWriter()
