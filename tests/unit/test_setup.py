"""
Unit tests for workspace setup — schema validation and dashboard blocks.
"""

import pytest

from app.notion.setup import (
    reading_tasks_schema,
    notes_schema,
    tree_nodes_schema,
    knowledge_pages_schema,
    _dashboard_blocks,
    _title_prop,
    _rich_text_prop,
    _select_prop,
    _multi_select_prop,
    _relation_prop,
    _self_relation_prop,
    SetupResult,
)


# ── Property helpers ────────────────────────────────────────────────

class TestPropertyHelpers:
    def test_title_prop(self):
        assert _title_prop() == {"title": {}}

    def test_rich_text_prop(self):
        assert _rich_text_prop() == {"rich_text": {}}

    def test_select_prop_with_options(self):
        result = _select_prop(["A", "B"], ["red", "blue"])
        opts = result["select"]["options"]
        assert len(opts) == 2
        assert opts[0] == {"name": "A", "color": "red"}
        assert opts[1] == {"name": "B", "color": "blue"}

    def test_select_prop_default_colors(self):
        result = _select_prop(["X", "Y", "Z"])
        opts = result["select"]["options"]
        assert len(opts) == 3
        assert all("color" in o for o in opts)

    def test_multi_select_empty(self):
        result = _multi_select_prop()
        assert result["multi_select"]["options"] == []

    def test_multi_select_with_values(self):
        result = _multi_select_prop(["tag1", "tag2"])
        opts = result["multi_select"]["options"]
        assert len(opts) == 2
        assert opts[0]["name"] == "tag1"

    def test_relation_prop(self):
        result = _relation_prop("db-123")
        assert result["relation"]["database_id"] == "db-123"

    def test_self_relation_prop(self):
        result = _self_relation_prop("db-456")
        assert result["relation"]["database_id"] == "db-456"
        assert result["relation"]["type"] == "single_property"


# ── Database schemas ────────────────────────────────────────────────

class TestSchemas:
    def test_reading_tasks_schema_keys(self):
        schema = reading_tasks_schema()
        required = [
            "Name", "Status", "AI Stage", "Source Name", "Source Type",
            "Source URL", "Source Citation", "Checklist Page ID",
            "Tree Page ID", "Gen Pages Root ID", "Run ID", "Error",
            "Created", "Last Edited",
        ]
        for key in required:
            assert key in schema, f"Missing key: {key}"

    def test_reading_tasks_schema_types(self):
        schema = reading_tasks_schema()
        assert "title" in schema["Name"]
        assert "select" in schema["Status"]
        assert "select" in schema["AI Stage"]
        assert "rich_text" in schema["Source Name"]
        assert "url" in schema["Source URL"]
        assert "created_time" in schema["Created"]

    def test_reading_tasks_ai_stage_options(self):
        schema = reading_tasks_schema()
        stage_names = [o["name"] for o in schema["AI Stage"]["select"]["options"]]
        assert "Idle" in stage_names
        assert "Queued" in stage_names
        assert "Running" in stage_names
        assert "Needs review" in stage_names
        assert "Approved" in stage_names
        assert "Failed" in stage_names

    def test_notes_schema_has_task_relation(self):
        schema = notes_schema("tasks-db-id")
        assert "Task" in schema
        assert schema["Task"]["relation"]["database_id"] == "tasks-db-id"

    def test_notes_schema_keys(self):
        schema = notes_schema("tasks-db-id")
        for key in ["Name", "Type", "Location", "Content", "Tags", "Task"]:
            assert key in schema

    def test_notes_type_options(self):
        schema = notes_schema("tasks-db-id")
        types = [o["name"] for o in schema["Type"]["select"]["options"]]
        assert "Quote" in types
        assert "Idea" in types
        assert "Question" in types
        assert "TODO" in types

    def test_tree_nodes_schema_has_scope_relation(self):
        schema = tree_nodes_schema("tasks-db-id")
        assert "Scope" in schema
        assert schema["Scope"]["relation"]["database_id"] == "tasks-db-id"

    def test_tree_nodes_schema_keys(self):
        schema = tree_nodes_schema("tasks-db-id")
        for key in ["Name", "Summary", "Keywords", "Status", "Scope"]:
            assert key in schema

    def test_knowledge_pages_schema_keys(self):
        schema = knowledge_pages_schema("tasks-db-id")
        for key in ["Name", "Task", "Status", "Version", "Page ID", "Template"]:
            assert key in schema

    def test_knowledge_pages_template_options(self):
        schema = knowledge_pages_schema("tasks-db-id")
        templates = [o["name"] for o in schema["Template"]["select"]["options"]]
        assert "concept" in templates
        assert "process" in templates
        assert "comparison" in templates
        assert "case_study" in templates


# ── Dashboard blocks ────────────────────────────────────────────────

class TestDashboardBlocks:
    def test_generates_blocks(self):
        db_ids = {
            "tasks": "t-id",
            "notes": "n-id",
            "tree_nodes": "tn-id",
            "knowledge_pages": "kp-id",
        }
        blocks = _dashboard_blocks(db_ids, "parent-id")
        assert len(blocks) > 0

    def test_contains_env_code_block(self):
        db_ids = {
            "tasks": "t-id",
            "notes": "n-id",
            "tree_nodes": "tn-id",
            "knowledge_pages": "kp-id",
        }
        blocks = _dashboard_blocks(db_ids, "parent-id")
        code_blocks = [b for b in blocks if b.get("type") == "code"]
        assert len(code_blocks) >= 1
        # Find the env block
        env_block = None
        for b in code_blocks:
            text = b["code"]["rich_text"][0]["text"]["content"]
            if "NOTES_DB_ID" in text:
                env_block = b
                break
        assert env_block is not None
        content = env_block["code"]["rich_text"][0]["text"]["content"]
        assert "n-id" in content
        assert "tn-id" in content
        assert "kp-id" in content

    def test_contains_callout_header(self):
        blocks = _dashboard_blocks({"tasks": "t"}, "p")
        callouts = [b for b in blocks if b.get("type") == "callout"]
        assert len(callouts) >= 1
        first_text = callouts[0]["callout"]["rich_text"][0]["text"]["content"]
        assert "Knowledge Management System" in first_text


# ── SetupResult ─────────────────────────────────────────────────────

class TestSetupResult:
    def test_success_true(self):
        r = SetupResult(parent_page_id="p", tasks_db_id="t")
        assert r.success is True

    def test_success_false_no_tasks(self):
        r = SetupResult(parent_page_id="p")
        assert r.success is False

    def test_success_false_with_errors(self):
        r = SetupResult(parent_page_id="p", tasks_db_id="t", errors=["oops"])
        assert r.success is False

    def test_to_env(self):
        r = SetupResult(
            parent_page_id="p",
            tasks_db_id="t",
            notes_db_id="n",
            tree_nodes_db_id="tn",
            knowledge_pages_db_id="kp",
        )
        env = r.to_env()
        assert "NOTES_DB_ID=n" in env
        assert "TREE_NODES_DB_ID=tn" in env
        assert "KNOWLEDGE_PAGES_DB_ID=kp" in env

    def test_to_dict(self):
        r = SetupResult(parent_page_id="p", tasks_db_id="t")
        d = r.to_dict()
        assert d["success"] is True
        assert d["databases"]["reading_tasks"] == "t"
        assert "env_snippet" in d
