#!/usr/bin/env python3
"""
KM System — Notion Workspace Initializer
==========================================

Creates all required Notion databases and a Dashboard page under a
user-specified parent page.

Usage:
    python scripts/setup_notion.py --parent-page <NOTION_PAGE_ID> --token <NOTION_TOKEN>

What it creates:
    1. 📚 Reading Tasks DB      — main task tracker
    2. 📝 Notes DB              — linked notes / extracts
    3. 🌳 Tree Nodes DB         — knowledge taxonomy nodes
    4. 📄 Knowledge Pages DB    — generated knowledge pages
    5. 📊 Dashboard page        — overview with linked DB views

Output:
    - Prints a ready-to-paste .env block with all DB IDs.
    - Optionally writes to .env file with --write-env flag.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# We use the raw notion-client SDK directly (not our app wrapper)
# so this script has zero dependency on the rest of the app.
# ---------------------------------------------------------------------------
try:
    from notion_client import AsyncClient
    from notion_client.errors import APIResponseError
except ImportError:
    print("ERROR: notion-client not installed.  Run:  pip install notion-client")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
# Database Schema Definitions
# ═══════════════════════════════════════════════════════════════════════════

READING_TASKS_SCHEMA: dict[str, Any] = {
    "Name": {"title": {}},
    "Status": {
        "select": {
            "options": [
                {"name": "Not started", "color": "default"},
                {"name": "Reading", "color": "blue"},
                {"name": "Annotating", "color": "yellow"},
                {"name": "Synthesizing", "color": "purple"},
                {"name": "Done", "color": "green"},
                {"name": "Archived", "color": "gray"},
            ]
        }
    },
    "AI Stage": {
        "select": {
            "options": [
                {"name": "Idle", "color": "default"},
                {"name": "Queued", "color": "yellow"},
                {"name": "Running", "color": "blue"},
                {"name": "Needs review", "color": "orange"},
                {"name": "Approved", "color": "green"},
                {"name": "Failed", "color": "red"},
            ]
        }
    },
    "Source Name": {"rich_text": {}},
    "Source Type": {
        "select": {
            "options": [
                {"name": "Book", "color": "brown"},
                {"name": "Article", "color": "blue"},
                {"name": "Paper", "color": "purple"},
                {"name": "Video", "color": "red"},
                {"name": "Podcast", "color": "orange"},
                {"name": "Course", "color": "green"},
                {"name": "Other", "color": "default"},
            ]
        }
    },
    "Source URL": {"url": {}},
    "Source Citation": {"rich_text": {}},
    "Tags": {"multi_select": {"options": []}},
    "Priority": {
        "select": {
            "options": [
                {"name": "High", "color": "red"},
                {"name": "Medium", "color": "yellow"},
                {"name": "Low", "color": "gray"},
            ]
        }
    },
    "Checklist Page ID": {"rich_text": {}},
    "Tree Page ID": {"rich_text": {}},
    "Gen Pages Root ID": {"rich_text": {}},
    "Run ID": {"rich_text": {}},
    "Error": {"rich_text": {}},
}

NOTES_DB_SCHEMA: dict[str, Any] = {
    "Name": {"title": {}},
    "Type": {
        "select": {
            "options": [
                {"name": "Quote", "color": "yellow"},
                {"name": "Idea", "color": "blue"},
                {"name": "Question", "color": "orange"},
                {"name": "TODO", "color": "red"},
                {"name": "Summary", "color": "green"},
                {"name": "Definition", "color": "purple"},
            ]
        }
    },
    "Location": {"rich_text": {}},
    "Content": {"rich_text": {}},
    "Tags": {"multi_select": {"options": []}},
    # "Task" relation is added AFTER the Reading Tasks DB is created
}

TREE_NODES_DB_SCHEMA: dict[str, Any] = {
    "Name": {"title": {}},
    "Summary": {"rich_text": {}},
    "Keywords": {"multi_select": {"options": []}},
    "Status": {
        "select": {
            "options": [
                {"name": "Draft", "color": "yellow"},
                {"name": "Approved", "color": "green"},
                {"name": "Archived", "color": "gray"},
            ]
        }
    },
    # "Scope" relation → Reading Tasks DB (added after creation)
    # "Parent" self-relation (added after creation)
}

KNOWLEDGE_PAGES_DB_SCHEMA: dict[str, Any] = {
    "Name": {"title": {}},
    "Status": {
        "select": {
            "options": [
                {"name": "Needs review", "color": "orange"},
                {"name": "Approved", "color": "green"},
                {"name": "Archived", "color": "gray"},
            ]
        }
    },
    "Template": {
        "select": {
            "options": [
                {"name": "concept", "color": "blue"},
                {"name": "framework", "color": "purple"},
                {"name": "comparison", "color": "orange"},
                {"name": "case_study", "color": "green"},
                {"name": "methodology", "color": "red"},
            ]
        }
    },
    "Version": {"number": {"format": "number"}},
    "Page ID": {"rich_text": {}},
    # "Task" relation → Reading Tasks DB (added after creation)
}


# ═══════════════════════════════════════════════════════════════════════════
# Dashboard Content Blocks
# ═══════════════════════════════════════════════════════════════════════════

def make_dashboard_blocks(db_ids: dict[str, str]) -> list[dict]:
    """Build Notion blocks for the Dashboard page."""
    blocks: list[dict] = []

    # Header callout
    blocks.append({
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "🧠"},
            "rich_text": [{
                "type": "text",
                "text": {"content": "KM System Dashboard — AI-powered knowledge management hub. All databases and workflows are managed from here."},
            }],
            "color": "blue_background",
        }
    })
    blocks.append({"type": "divider", "divider": {}})

    # ── Quick Guide ─────────────────────────────────────────────────
    blocks.append({
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "🚀 Quick Start"}}]}
    })

    guide_steps = [
        "1️⃣  在 Reading Tasks 中新建一条阅读任务，填写标题、来源信息，把你的笔记/批注写在正文里。",
        "2️⃣  在 Notes DB 中添加你的摘录和笔记，通过 Task 关联字段链接到对应的阅读任务。",
        "3️⃣  通过 Webhook 或 API 触发 AI 生成（checklist → tree → pages → flashcards）。",
        "4️⃣  AI 生成完毕后，在 Notion 中审阅结果（AI Stage = Needs review）。",
        "5️⃣  满意后触发 approve 动作，自动级联更新所有关联数据库的状态。",
    ]
    for step in guide_steps:
        blocks.append({
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": step}}]}
        })

    blocks.append({"type": "divider", "divider": {}})

    # ── Linked Database Views ───────────────────────────────────────
    blocks.append({
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "📚 Reading Tasks"}}]}
    })
    blocks.append({
        "type": "paragraph",
        "paragraph": {"rich_text": [{
            "type": "text",
            "text": {"content": "所有阅读任务的总览。可以按 Status 或 AI Stage 筛选。"},
            "annotations": {"color": "gray"},
        }]}
    })

    blocks.append({
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "📝 Notes & Extracts"}}]}
    })
    blocks.append({
        "type": "paragraph",
        "paragraph": {"rich_text": [{
            "type": "text",
            "text": {"content": "阅读摘录和笔记。每条笔记可以关联到一个阅读任务，AI 生成时会自动读取。"},
            "annotations": {"color": "gray"},
        }]}
    })

    blocks.append({
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "🌳 Knowledge Tree Nodes"}}]}
    })
    blocks.append({
        "type": "paragraph",
        "paragraph": {"rich_text": [{
            "type": "text",
            "text": {"content": "AI 生成的知识树节点。每个节点有 Draft/Approved 状态，approve 时自动更新。"},
            "annotations": {"color": "gray"},
        }]}
    })

    blocks.append({
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "📄 Knowledge Pages"}}]}
    })
    blocks.append({
        "type": "paragraph",
        "paragraph": {"rich_text": [{
            "type": "text",
            "text": {"content": "AI 生成的知识页面。每个页面有模板类型（concept, framework, case_study 等）和版本号。"},
            "annotations": {"color": "gray"},
        }]}
    })

    blocks.append({"type": "divider", "divider": {}})

    # ── Workflow Diagram ────────────────────────────────────────────
    blocks.append({
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "⚙️ AI Pipeline Workflow"}}]}
    })
    blocks.append({
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content":
                "Reading Task (Notion Page)\n"
                "  │\n"
                "  ├─ 1. checklist  → ✅ 生成阅读清单（关键概念 + 分析要点）\n"
                "  │                   └─ 写入子页面 → AI Stage = Needs review\n"
                "  │\n"
                "  ├─ 2. tree       → 🌳 生成知识树（层级分类 + 关键词）\n"
                "  │                   ├─ 写入子页面\n"
                "  │                   └─ 同步到 Tree Nodes DB (Status=Draft)\n"
                "  │\n"
                "  ├─ 3. pages      → 📄 生成知识页面（concept/framework/case_study…）\n"
                "  │                   ├─ 每个页面写入独立子页面\n"
                "  │                   └─ 同步到 Knowledge Pages DB\n"
                "  │\n"
                "  ├─ 4. flashcards → 🎴 生成闪卡（basic/cloze/reverse/definition）\n"
                "  │                   ├─ 可视化卡片 + CSV 导出\n"
                "  │                   └─ 支持 Anki / Quizlet 导入\n"
                "  │\n"
                "  └─ 5. approve    → ✅ 级联批准\n"
                "                      ├─ Tree Nodes  → Approved\n"
                "                      ├─ Knowledge Pages → Approved\n"
                "                      └─ Task AI Stage → Approved\n"
            }}],
            "language": "plain text",
        }
    })

    blocks.append({"type": "divider", "divider": {}})

    # ── API Reference ───────────────────────────────────────────────
    blocks.append({
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "🔌 API Endpoints"}}]}
    })
    blocks.append({
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content":
                "# 触发生成\n"
                "POST /webhook/notion\n"
                '  Body: {"task_page_id": "xxx", "action_type": "checklist|tree|pages|flashcards|approve", "secret": "YOUR_SECRET"}\n\n'
                "# 查询任务状态\n"
                "GET /jobs/{job_id}\n\n"
                "# 仪表盘\n"
                "GET /dashboard/stats         → 全局统计\n"
                "GET /dashboard/runs?limit=20 → 最近运行记录\n"
                "GET /dashboard/versions/{task_page_id} → 各 action 的版本号\n\n"
                "# 健康检查\n"
                "GET /health\n"
            }}],
            "language": "plain text",
        }
    })

    blocks.append({"type": "divider", "divider": {}})

    # ── Configuration Reference ─────────────────────────────────────
    blocks.append({
        "type": "heading_2",
        "heading_2": {"rich_text": [{"type": "text", "text": {"content": "🔧 Database IDs (auto-generated)"}}]}
    })
    config_text = "\n".join(f"{k} = {v}" for k, v in db_ids.items())
    blocks.append({
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content": config_text}}],
            "language": "plain text",
        }
    })

    return blocks


# ═══════════════════════════════════════════════════════════════════════════
# Main Setup Logic
# ═══════════════════════════════════════════════════════════════════════════

class NotionSetup:
    """Creates all KM System databases and dashboard in Notion."""

    RATE_DELAY = 0.35  # seconds between API calls to avoid 429

    def __init__(self, token: str, parent_page_id: str):
        self.client = AsyncClient(auth=token)
        self.parent_page_id = parent_page_id
        self.db_ids: dict[str, str] = {}

    async def _wait(self):
        await asyncio.sleep(self.RATE_DELAY)

    async def _create_database(
        self, title: str, properties: dict, icon: str, is_inline: bool = True,
    ) -> str:
        await self._wait()
        resp = await self.client.databases.create(
            parent={"type": "page_id", "page_id": self.parent_page_id},
            title=[{"type": "text", "text": {"content": title}}],
            properties=properties,
            icon={"type": "emoji", "emoji": icon},
            is_inline=is_inline,
        )
        db_id = resp["id"]
        print(f"  ✅ Created: {title}  →  {db_id}")
        return db_id

    async def _add_relation(self, db_id: str, prop_name: str, target_db_id: str, is_self: bool = False):
        """Add a relation property to an existing database."""
        await self._wait()
        if is_self:
            await self.client.databases.update(
                database_id=db_id,
                properties={
                    prop_name: {
                        "relation": {
                            "database_id": target_db_id,
                            "type": "single_property",
                            "single_property": {},
                        }
                    }
                },
            )
        else:
            await self.client.databases.update(
                database_id=db_id,
                properties={
                    prop_name: {
                        "relation": {
                            "database_id": target_db_id,
                            "type": "single_property",
                            "single_property": {},
                        }
                    }
                },
            )
        print(f"  🔗 Added relation: {prop_name} on {db_id[:8]}…")

    async def _create_page(self, title: str, icon: str, blocks: list[dict]) -> str:
        await self._wait()
        resp = await self.client.pages.create(
            parent={"type": "page_id", "page_id": self.parent_page_id},
            properties={"title": [{"type": "text", "text": {"content": title}}]},
            icon={"type": "emoji", "emoji": icon},
        )
        page_id = resp["id"]

        # Append blocks in batches of 50
        for i in range(0, len(blocks), 50):
            await self._wait()
            await self.client.blocks.children.append(
                block_id=page_id, children=blocks[i : i + 50],
            )

        print(f"  ✅ Created: {title}  →  {page_id}")
        return page_id

    # ── Main Orchestrator ─────────────────────────────────────────

    async def run(self):
        print("\n╔════════════════════════════════════════════╗")
        print("║  KM System — Notion Workspace Setup       ║")
        print("╚════════════════════════════════════════════╝\n")

        # Verify parent page access
        print("🔍 Verifying parent page access …")
        try:
            await self._wait()
            page = await self.client.pages.retrieve(page_id=self.parent_page_id)
            # Extract title safely
            title_prop = page.get("properties", {}).get("title", {})
            if isinstance(title_prop, dict):
                parts = title_prop.get("title", [])
                if parts:
                    parent_title = parts[0].get("plain_text", "Untitled")
                else:
                    parent_title = "Untitled"
            else:
                parent_title = "Untitled"
            print(f"  ✅ Parent page: {parent_title}\n")
        except APIResponseError as e:
            print(f"  ❌ Cannot access page: {e}")
            print("     Make sure the Notion integration has access to this page.")
            sys.exit(1)

        # ── Step 1: Create Databases ───────────────────────────────
        print("📦 Creating databases …\n")

        # 1) Reading Tasks DB
        tasks_db_id = await self._create_database(
            "📚 Reading Tasks", READING_TASKS_SCHEMA, "📚",
        )
        self.db_ids["TASKS_DB_ID"] = tasks_db_id

        # 2) Notes DB (without Task relation yet)
        notes_db_id = await self._create_database(
            "📝 Notes", NOTES_DB_SCHEMA, "📝",
        )
        self.db_ids["NOTES_DB_ID"] = notes_db_id

        # 3) Tree Nodes DB (without relations yet)
        tree_db_id = await self._create_database(
            "🌳 Tree Nodes", TREE_NODES_DB_SCHEMA, "🌳",
        )
        self.db_ids["TREE_NODES_DB_ID"] = tree_db_id

        # 4) Knowledge Pages DB (without Task relation yet)
        kp_db_id = await self._create_database(
            "📄 Knowledge Pages", KNOWLEDGE_PAGES_DB_SCHEMA, "📄",
        )
        self.db_ids["KNOWLEDGE_PAGES_DB_ID"] = kp_db_id

        # ── Step 2: Add Relations ──────────────────────────────────
        print("\n🔗 Adding cross-database relations …\n")

        # Notes.Task → Reading Tasks
        await self._add_relation(notes_db_id, "Task", tasks_db_id)

        # Tree Nodes.Scope → Reading Tasks
        await self._add_relation(tree_db_id, "Scope", tasks_db_id)

        # Tree Nodes.Parent → Tree Nodes (self-relation)
        await self._add_relation(tree_db_id, "Parent", tree_db_id, is_self=True)

        # Knowledge Pages.Task → Reading Tasks
        await self._add_relation(kp_db_id, "Task", tasks_db_id)

        # ── Step 3: Create Dashboard Page ──────────────────────────
        print("\n📊 Creating Dashboard page …\n")

        dashboard_blocks = make_dashboard_blocks(self.db_ids)
        dashboard_id = await self._create_page(
            "📊 KM Dashboard", "📊", dashboard_blocks,
        )
        self.db_ids["DASHBOARD_PAGE_ID"] = dashboard_id

        # ── Step 4: Add sample task for testing ────────────────────
        print("\n📝 Creating sample Reading Task …\n")
        await self._wait()
        sample = await self.client.pages.create(
            parent={"type": "database_id", "database_id": tasks_db_id},
            properties={
                "Name": {"title": [{"type": "text", "text": {"content": "📖 Sample: Getting Started with KM System"}}]},
                "Status": {"select": {"name": "Not started"}},
                "AI Stage": {"select": {"name": "Idle"}},
                "Source Type": {"select": {"name": "Other"}},
                "Source Name": {"rich_text": [{"type": "text", "text": {"content": "KM System Setup Guide"}}]},
            },
        )
        sample_id = sample["id"]

        # Add content blocks to the sample task
        await self._wait()
        await self.client.blocks.children.append(
            block_id=sample_id,
            children=[
                {"type": "heading_2", "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Welcome to KM System"}}],
                }},
                {"type": "paragraph", "paragraph": {
                    "rich_text": [{"type": "text", "text": {
                        "content": "这是一个示例阅读任务。你可以在这里写下你的阅读笔记和批注。"
                    }}],
                }},
                {"type": "paragraph", "paragraph": {
                    "rich_text": [{"type": "text", "text": {
                        "content": "AI 系统会读取此页面的所有内容（包括关联的 Notes），然后根据 action_type 生成对应的输出。"
                    }}],
                }},
                {"type": "heading_3", "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": "Knowledge Management 的核心概念"}}],
                }},
                {"type": "bulleted_list_item", "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": "知识获取 (Knowledge Acquisition) — 通过阅读、观察、实验等方式获取新知识"}}],
                }},
                {"type": "bulleted_list_item", "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": "知识组织 (Knowledge Organization) — 使用分类、标签、层级结构整理知识"}}],
                }},
                {"type": "bulleted_list_item", "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": "知识内化 (Knowledge Internalization) — 通过复习、应用、教学等方式深化理解"}}],
                }},
                {"type": "paragraph", "paragraph": {
                    "rich_text": [{"type": "text", "text": {
                        "content": "\n💡 试试用这个示例任务触发 checklist 生成，看看 AI 会产出什么结果！"
                    }}],
                }},
            ],
        )
        print(f"  ✅ Sample task: {sample_id}")

        # ── Summary ────────────────────────────────────────────────
        self._print_summary()

    def _print_summary(self):
        print("\n" + "═" * 56)
        print("  🎉 Setup complete!  All databases and dashboard created.")
        print("═" * 56)
        print("\n📋 Add these to your .env file:\n")
        print("# ── Notion Database IDs (auto-generated) ──")
        for key, value in self.db_ids.items():
            clean = value.replace("-", "")
            print(f"{key}={clean}")
        print()

    def write_env(self, env_path: str):
        """Append DB IDs to .env file."""
        path = Path(env_path)
        lines = ["\n# ── KM System Database IDs (auto-generated) ──\n"]
        for key, value in self.db_ids.items():
            clean = value.replace("-", "")
            lines.append(f"{key}={clean}\n")

        with open(path, "a", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"📝 Database IDs appended to {path}")


# ═══════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="KM System — Initialize Notion workspace with all required databases and dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic setup
  python scripts/setup_notion.py \\
    --parent-page abc123def456 \\
    --token ntn_xxxxxxxxxxxx

  # Setup + auto-write .env
  python scripts/setup_notion.py \\
    --parent-page abc123def456 \\
    --token ntn_xxxxxxxxxxxx \\
    --write-env .env

Notes:
  - The parent page must be shared with your Notion integration.
  - You can find the page ID in the Notion page URL:
    https://www.notion.so/Your-Page-Title-<PAGE_ID>
  - Page ID is the 32-char hex string at the end of the URL.
        """,
    )
    parser.add_argument(
        "--parent-page", required=True,
        help="Notion page ID where databases will be created",
    )
    parser.add_argument(
        "--token", required=True,
        help="Notion integration token (starts with ntn_ or secret_)",
    )
    parser.add_argument(
        "--write-env", metavar="PATH",
        help="Append generated DB IDs to this .env file",
    )

    args = parser.parse_args()

    # Clean the page ID (remove dashes, whitespace)
    parent_id = args.parent_page.strip().replace("-", "")
    if len(parent_id) != 32:
        # Maybe it has dashes already stripped or is a URL
        # Try extracting from URL
        if "notion.so" in parent_id or "notion.site" in parent_id:
            # Extract the last 32 hex chars
            import re
            match = re.search(r"([a-f0-9]{32})", parent_id.replace("-", ""))
            if match:
                parent_id = match.group(1)
            else:
                print("ERROR: Cannot extract page ID from URL. Please provide a 32-char page ID.")
                sys.exit(1)

    setup = NotionSetup(token=args.token, parent_page_id=parent_id)

    async def _run():
        await setup.run()
        if args.write_env:
            setup.write_env(args.write_env)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
