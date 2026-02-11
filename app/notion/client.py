"""
Notion API client — wraps notion-client with token-bucket rate limiting,
automatic pagination, and retry-on-429.
v1.1: Added query_database for Notes fusion + Tree Nodes sync.
"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Any, Optional

from notion_client import AsyncClient
from notion_client.errors import APIResponseError

from app.config import settings

logger = logging.getLogger(__name__)


# ── Token Bucket Rate Limiter ──────────────────────────────────────

class TokenBucket:
    def __init__(self, capacity: float = 3.0, refill_rate: float = 3.0):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
            self._last_refill = now
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self.refill_rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


# ── Notion Client ──────────────────────────────────────────────────

class NotionClient:

    MAX_RETRIES = 5
    INITIAL_BACKOFF = 1.0

    def __init__(self):
        self._client = AsyncClient(auth=settings.notion_token)
        self._bucket = TokenBucket(
            capacity=settings.notion_rate_limit,
            refill_rate=settings.notion_rate_limit,
        )

    async def _call(self, method, *args, **kwargs) -> Any:
        backoff = self.INITIAL_BACKOFF
        for attempt in range(self.MAX_RETRIES):
            await self._bucket.acquire()
            try:
                return await method(*args, **kwargs)
            except APIResponseError as e:
                if e.status == 429:
                    retry_after = backoff
                    try:
                        retry_after = float(e.headers.get("Retry-After", backoff))
                    except Exception:
                        pass
                    logger.warning(f"429 rate limited, retry in {retry_after}s (attempt {attempt + 1})")
                    await asyncio.sleep(retry_after)
                    backoff = min(backoff * 2, 30.0)
                    continue
                raise
        raise RuntimeError(f"Notion API: exhausted {self.MAX_RETRIES} retries on 429")

    # ── Pages ──────────────────────────────────────────────────────

    async def get_page(self, page_id: str) -> dict:
        return await self._call(self._client.pages.retrieve, page_id=page_id)

    async def create_page(
        self, parent_page_id: str, title: str,
        properties: Optional[dict] = None, icon: Optional[str] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "properties": {"title": [{"type": "text", "text": {"content": title}}]},
        }
        if icon:
            payload["icon"] = {"type": "emoji", "emoji": icon}
        if properties:
            payload["properties"].update(properties)
        return await self._call(self._client.pages.create, **payload)

    async def create_db_page(self, database_id: str, properties: dict) -> dict:
        return await self._call(
            self._client.pages.create,
            parent={"type": "database_id", "database_id": database_id},
            properties=properties,
        )

    async def update_page_properties(self, page_id: str, properties: dict) -> dict:
        return await self._call(
            self._client.pages.update, page_id=page_id, properties=properties,
        )

    # ── Blocks ─────────────────────────────────────────────────────

    async def get_blocks(self, block_id: str) -> list[dict]:
        all_blocks = []
        cursor = None
        while True:
            kwargs = {"block_id": block_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = await self._call(self._client.blocks.children.list, **kwargs)
            blocks = resp.get("results", [])
            for block in blocks:
                if block.get("has_children"):
                    block["children"] = await self.get_blocks(block["id"])
                all_blocks.append(block)
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return all_blocks

    async def append_blocks(self, parent_id: str, blocks: list[dict]) -> list[dict]:
        batch_size = settings.block_batch_size
        created = []
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i : i + batch_size]
            resp = await self._call(
                self._client.blocks.children.append,
                block_id=parent_id, children=batch,
            )
            created.extend(resp.get("results", []))
        return created

    async def delete_all_blocks(self, page_id: str):
        blocks = await self._call(self._client.blocks.children.list, block_id=page_id)
        for block in blocks.get("results", []):
            await self._call(self._client.blocks.delete, block_id=block["id"])

    # ── Database CRUD (v1.1 query, v1.2 create) ─────────────────────

    async def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: dict[str, Any],
        icon: Optional[str] = None,
        is_inline: bool = True,
    ) -> dict:
        """Create a new Notion database under a parent page."""
        payload: dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
            "is_inline": is_inline,
        }
        if icon:
            payload["icon"] = {"type": "emoji", "emoji": icon}
        return await self._call(self._client.databases.create, **payload)

    async def update_database(self, database_id: str, **kwargs) -> dict:
        """Update a Notion database (title, properties, etc.)."""
        return await self._call(
            self._client.databases.update, database_id=database_id, **kwargs,
        )

    async def query_database(
        self, database_id: str,
        filter_payload: Optional[dict] = None,
        sorts: Optional[list[dict]] = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Query a Notion database with filters. Returns all pages (auto-paginated)."""
        all_pages = []
        cursor = None
        while True:
            kwargs: dict[str, Any] = {"database_id": database_id, "page_size": page_size}
            if filter_payload:
                kwargs["filter"] = filter_payload
            if sorts:
                kwargs["sorts"] = sorts
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = await self._call(self._client.databases.query, **kwargs)
            all_pages.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return all_pages

    # ── Property Helpers ───────────────────────────────────────────

    @staticmethod
    def prop_select(value: str) -> dict:
        return {"select": {"name": value}}

    @staticmethod
    def prop_rich_text(value: str) -> dict:
        return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]}

    @staticmethod
    def prop_relation(page_ids: list[str]) -> dict:
        return {"relation": [{"id": pid} for pid in page_ids]}

    @staticmethod
    def prop_number(value: float) -> dict:
        return {"number": value}

    @staticmethod
    def prop_multi_select(values: list[str]) -> dict:
        return {"multi_select": [{"name": v} for v in values]}

    @staticmethod
    def prop_title(text: str) -> dict:
        return {"title": [{"type": "text", "text": {"content": text}}]}


notion = NotionClient()
