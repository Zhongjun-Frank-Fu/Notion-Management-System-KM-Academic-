"""
Database initialization — SQLite tables.
v1.1: Added version_history and stats tables.
"""

import aiosqlite
from pathlib import Path

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id        TEXT PRIMARY KEY,
    task_page_id  TEXT NOT NULL,
    action_type   TEXT NOT NULL CHECK(action_type IN ('checklist','tree','pages','flashcards','approve')),
    status        TEXT NOT NULL DEFAULT 'queued'
                  CHECK(status IN ('queued','running','success','failed')),
    attempts      INTEGER NOT NULL DEFAULT 0,
    max_attempts  INTEGER NOT NULL DEFAULT 3,
    error         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    job_id          TEXT REFERENCES jobs(job_id),
    task_page_id    TEXT NOT NULL,
    action_type     TEXT NOT NULL,
    status          TEXT NOT NULL,
    llm_model       TEXT,
    prompt_version  TEXT,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    started_at      TEXT,
    ended_at        TEXT,
    error           TEXT,
    output_snapshot TEXT
);

CREATE TABLE IF NOT EXISTS page_cache (
    task_page_id   TEXT NOT NULL,
    page_type      TEXT NOT NULL,
    notion_page_id TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (task_page_id, page_type)
);

CREATE TABLE IF NOT EXISTS version_history (
    task_page_id  TEXT NOT NULL,
    action_type   TEXT NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1,
    run_id        TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (task_page_id, action_type, version)
);

CREATE TABLE IF NOT EXISTS tree_node_map (
    task_page_id    TEXT NOT NULL,
    node_id         TEXT NOT NULL,
    notion_page_id  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Draft',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (task_page_id, node_id)
);
"""


async def init_db():
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    return await aiosqlite.connect(settings.sqlite_path)
