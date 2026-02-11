"""
conftest.py — Set test environment variables BEFORE any app imports.
This file is loaded by pytest before collecting tests.
"""
import os

os.environ.setdefault("NOTION_TOKEN", "test-token")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("SQLITE_PATH", "/tmp/test_km.db")
os.environ.setdefault("NOTES_DB_ID", "")
os.environ.setdefault("TREE_NODES_DB_ID", "")
os.environ.setdefault("KNOWLEDGE_PAGES_DB_ID", "")
