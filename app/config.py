"""
Application configuration — loaded from environment variables.
v1.1: Added Notion database IDs for Notes, Tree Nodes, Knowledge Pages.
"""

from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # ── Notion ──────────────────────────────────────
    notion_token: str
    notion_rate_limit: float = 3.0

    # Notion Database IDs (v1.1 — needed for Notes fusion + Tree Nodes sync)
    notes_db_id: str = ""               # Notes / Extracts DB
    tree_nodes_db_id: str = ""          # Tree Nodes DB
    knowledge_pages_db_id: str = ""     # Knowledge Pages DB (optional)

    # ── LLM ─────────────────────────────────────────
    anthropic_api_key: str
    llm_model: str = "claude-sonnet-4-5-20250929"

    # ── Webhook ─────────────────────────────────────
    webhook_secret: str

    # ── Database ────────────────────────────────────
    sqlite_path: str = "./data/jobs.db"

    # ── Application ─────────────────────────────────
    log_level: str = "INFO"
    max_job_attempts: int = 3
    block_batch_size: int = 50
    prompt_version: str = "KM-v1.1"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def sqlite_dir(self) -> Path:
        return Path(self.sqlite_path).parent


settings = Settings()
