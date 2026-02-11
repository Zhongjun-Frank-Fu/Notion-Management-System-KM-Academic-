"""
Repository — CRUD for jobs, runs, page_cache, versions, tree node map, stats.
v1.1: Added versioning, tree node tracking, dashboard aggregation.
"""

from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

import aiosqlite

from app.config import settings
from app.models import Job, Run, JobStatus, TaskStats


class Repository:

    def __init__(self):
        self._path = settings.sqlite_path

    @asynccontextmanager
    async def _conn(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        db = await aiosqlite.connect(self._path)
        db.row_factory = aiosqlite.Row
        try:
            yield db
        finally:
            await db.close()

    # ── Jobs ────────────────────────────────────────────────────────

    async def create_job(self, job: Job) -> Job:
        async with self._conn() as db:
            await db.execute(
                """INSERT INTO jobs
                   (job_id, task_page_id, action_type, status, attempts, max_attempts, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (job.job_id, job.task_page_id, job.action_type.value,
                 job.status.value, job.attempts, job.max_attempts,
                 job.created_at.isoformat(), job.updated_at.isoformat()),
            )
            await db.commit()
        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        async with self._conn() as db:
            cursor = await db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return Job(**dict(row))

    async def update_job_status(
        self, job_id: str, status: JobStatus,
        error: Optional[str] = None, increment_attempts: bool = False,
    ):
        async with self._conn() as db:
            if increment_attempts:
                await db.execute(
                    """UPDATE jobs SET status = ?, error = ?, attempts = attempts + 1,
                       updated_at = datetime('now') WHERE job_id = ?""",
                    (status.value, error, job_id),
                )
            else:
                await db.execute(
                    """UPDATE jobs SET status = ?, error = ?, updated_at = datetime('now')
                       WHERE job_id = ?""",
                    (status.value, error, job_id),
                )
            await db.commit()

    # ── Runs ────────────────────────────────────────────────────────

    async def create_run(self, run: Run) -> Run:
        async with self._conn() as db:
            await db.execute(
                """INSERT INTO runs
                   (run_id, job_id, task_page_id, action_type, status,
                    llm_model, prompt_version, started_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run.run_id, run.job_id, run.task_page_id,
                 run.action_type.value, run.status.value,
                 run.llm_model, run.prompt_version,
                 run.started_at.isoformat()),
            )
            await db.commit()
        return run

    async def finish_run(
        self, run_id: str, status: JobStatus,
        input_tokens: int = 0, output_tokens: int = 0,
        error: Optional[str] = None, output_snapshot: Optional[str] = None,
    ):
        async with self._conn() as db:
            await db.execute(
                """UPDATE runs SET status = ?, ended_at = ?, input_tokens = ?,
                   output_tokens = ?, error = ?, output_snapshot = ?
                   WHERE run_id = ?""",
                (status.value, datetime.utcnow().isoformat(),
                 input_tokens, output_tokens, error, output_snapshot, run_id),
            )
            await db.commit()

    # ── Page Cache ──────────────────────────────────────────────────

    async def get_cached_page(self, task_page_id: str, page_type: str) -> Optional[str]:
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT notion_page_id FROM page_cache WHERE task_page_id = ? AND page_type = ?",
                (task_page_id, page_type),
            )
            row = await cursor.fetchone()
            return row["notion_page_id"] if row else None

    async def set_cached_page(self, task_page_id: str, page_type: str, notion_page_id: str):
        async with self._conn() as db:
            await db.execute(
                """INSERT OR REPLACE INTO page_cache
                   (task_page_id, page_type, notion_page_id) VALUES (?, ?, ?)""",
                (task_page_id, page_type, notion_page_id),
            )
            await db.commit()

    # ── Version History (v1.2) ──────────────────────────────────────

    async def get_latest_version(self, task_page_id: str, action_type: str) -> int:
        """Return the latest version number (0 if none exists)."""
        async with self._conn() as db:
            cursor = await db.execute(
                """SELECT MAX(version) as v FROM version_history
                   WHERE task_page_id = ? AND action_type = ?""",
                (task_page_id, action_type),
            )
            row = await cursor.fetchone()
            return row["v"] if row and row["v"] else 0

    async def create_version(self, task_page_id: str, action_type: str, run_id: str) -> int:
        """Create a new version record and return the new version number."""
        current = await self.get_latest_version(task_page_id, action_type)
        new_version = current + 1
        async with self._conn() as db:
            await db.execute(
                """INSERT INTO version_history
                   (task_page_id, action_type, version, run_id) VALUES (?, ?, ?, ?)""",
                (task_page_id, action_type, new_version, run_id),
            )
            await db.commit()
        return new_version

    # ── Tree Node Map (v1.1) ────────────────────────────────────────

    async def save_tree_node(self, task_page_id: str, node_id: str, notion_page_id: str):
        async with self._conn() as db:
            await db.execute(
                """INSERT OR REPLACE INTO tree_node_map
                   (task_page_id, node_id, notion_page_id, status) VALUES (?, ?, ?, 'Draft')""",
                (task_page_id, node_id, notion_page_id),
            )
            await db.commit()

    async def approve_tree_nodes(self, task_page_id: str):
        """Mark all tree nodes for a task as Approved."""
        async with self._conn() as db:
            await db.execute(
                "UPDATE tree_node_map SET status = 'Approved' WHERE task_page_id = ?",
                (task_page_id,),
            )
            await db.commit()

    async def get_tree_nodes(self, task_page_id: str) -> list[dict]:
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT * FROM tree_node_map WHERE task_page_id = ?",
                (task_page_id,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Dashboard Stats (v1.1) ──────────────────────────────────────

    async def get_stats(self) -> TaskStats:
        stats = TaskStats()
        async with self._conn() as db:
            # Job counts
            cursor = await db.execute("SELECT COUNT(*) as c FROM jobs")
            row = await cursor.fetchone()
            stats.total_tasks = row["c"]

            cursor = await db.execute(
                "SELECT action_type, COUNT(*) as c FROM jobs GROUP BY action_type"
            )
            for row in await cursor.fetchall():
                stats.by_status[row["action_type"]] = row["c"]

            # Run stats
            cursor = await db.execute("SELECT COUNT(*) as c FROM runs")
            stats.total_runs = (await cursor.fetchone())["c"]

            cursor = await db.execute("SELECT COUNT(*) as c FROM runs WHERE status = 'success'")
            stats.successful_runs = (await cursor.fetchone())["c"]

            cursor = await db.execute("SELECT COUNT(*) as c FROM runs WHERE status = 'failed'")
            stats.failed_runs = (await cursor.fetchone())["c"]

            cursor = await db.execute(
                "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) as t FROM runs"
            )
            stats.total_tokens = (await cursor.fetchone())["t"]

            # Tree nodes
            cursor = await db.execute("SELECT COUNT(*) as c FROM tree_node_map")
            stats.total_tree_nodes = (await cursor.fetchone())["c"]

            # Flashcard + pages counts from runs
            cursor = await db.execute(
                "SELECT COUNT(*) as c FROM runs WHERE action_type = 'flashcards' AND status = 'success'"
            )
            stats.total_flashcards = (await cursor.fetchone())["c"]

            cursor = await db.execute(
                "SELECT COUNT(*) as c FROM runs WHERE action_type = 'pages' AND status = 'success'"
            )
            stats.total_pages_generated = (await cursor.fetchone())["c"]

        return stats

    async def get_recent_runs(self, limit: int = 20) -> list[dict]:
        async with self._conn() as db:
            cursor = await db.execute(
                """SELECT run_id, task_page_id, action_type, status,
                          llm_model, input_tokens, output_tokens,
                          started_at, ended_at, error
                   FROM runs ORDER BY started_at DESC LIMIT ?""",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


repo = Repository()
