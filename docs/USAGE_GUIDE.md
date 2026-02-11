# KM System v1.1 — 使用说明

## 目录

1. [系统概述](#1-系统概述)
2. [环境要求](#2-环境要求)
3. [快速开始](#3-快速开始)
4. [初始化 Notion 工作区](#4-初始化-notion-工作区)
5. [配置文件说明](#5-配置文件说明)
6. [启动服务](#6-启动服务)
7. [核心使用流程](#7-核心使用流程)
8. [五种 Action 详解](#8-五种-action-详解)
9. [API 接口参考](#9-api-接口参考)
10. [Dashboard 统计](#10-dashboard-统计)
11. [Notion 数据库结构](#11-notion-数据库结构)
12. [高级功能](#12-高级功能)
13. [常见问题](#13-常见问题)
14. [项目结构](#14-项目结构)

---

## 1. 系统概述

KM System 是一个 **AI 驱动的知识管理后端**，与 Notion 深度集成。它能自动将你的阅读笔记转化为结构化的知识资产：

```
阅读笔记 → AI 分析 → 清单 / 知识树 / 知识页面 / 闪卡
```

**核心能力**：

| 功能 | 说明 |
|------|------|
| ✅ Checklist | 从笔记生成阅读清单（关键概念 + 分析要点） |
| 🌳 Tree | 生成层级知识树（分类 + 摘要 + 关键词） |
| 📄 Pages | 生成独立知识页面（概念/框架/案例/对比等模板） |
| 🎴 Flashcards | 生成闪卡（basic/cloze/reverse/definition），可导出 Anki/Quizlet |
| ✅ Approve | 一键级联批准所有生成内容 |

**架构**：

```
Notion Webhook/API → FastAPI Server → Claude LLM → Notion Write-back
                          ↓
                     SQLite (Jobs/Runs/Versions)
```

---

## 2. 环境要求

| 依赖 | 版本要求 |
|------|---------|
| Python | 3.11+ |
| pip 包 | 见 `requirements.txt` |
| Notion Integration | 需要创建一个 Internal Integration |
| Anthropic API Key | 需要有效的 Claude API 密钥 |

**Python 依赖**：

```
fastapi
uvicorn[standard]
notion-client
anthropic
pydantic-settings
aiosqlite
```

---

## 3. 快速开始

### 3.1 克隆/解压项目

```bash
unzip km-system-v1.1.zip -d km-system
cd km-system
pip install -r requirements.txt
```

### 3.2 创建 Notion Integration

1. 打开 https://www.notion.so/my-integrations
2. 点击 **"+ New integration"**
3. 填写名称（如 `KM System`），选择你的 workspace
4. 勾选以下 Capabilities：
   - ✅ Read content
   - ✅ Update content
   - ✅ Insert content
   - ✅ Read user information（可选）
5. 点击 **Submit** → 复制 Token（以 `ntn_` 开头）

### 3.3 创建工作区根页面

1. 在 Notion 中新建一个页面，命名如 `📚 KM Workspace`
2. 点击页面右上角 `...` → **Add connections** → 选择刚创建的 `KM System` integration
3. 复制该页面的 URL，提取其中的 Page ID（URL 末尾的 32 位十六进制字符串）

```
https://www.notion.so/Your-Workspace/KM-Workspace-abc123def456ghi789jkl012mno345pq
                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                     这就是 Page ID（去掉中间的 -）
```

### 3.4 运行初始化脚本

```bash
python scripts/setup_notion.py \
  --parent-page <你的PAGE_ID> \
  --token <你的NOTION_TOKEN> \
  --write-env .env
```

该脚本会自动创建：
- 📚 **Reading Tasks** 数据库 — 阅读任务主表
- 📝 **Notes** 数据库 — 笔记/摘录表
- 🌳 **Tree Nodes** 数据库 — 知识树节点表
- 📄 **Knowledge Pages** 数据库 — 知识页面追踪表
- 📊 **Dashboard** 页面 — 总控面板（含使用指南 + 流程图 + API 参考）
- 📖 **Sample Task** — 示例阅读任务（可用于测试）

脚本运行完成后会输出所有 Database ID，并自动写入 `.env` 文件。

### 3.5 补全 .env 配置

打开 `.env`，确保以下字段都已填写：

```dotenv
# ── Required ──────────────────────────────────
NOTION_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
WEBHOOK_SECRET=your-secure-random-string

# ── Notion DB IDs (setup_notion.py 自动写入) ──
NOTES_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TREE_NODES_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
KNOWLEDGE_PAGES_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3.6 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

验证：

```bash
curl http://localhost:8000/health
# 返回: {"status":"ok","version":"1.1.0","features":[...]}
```

---

## 4. 初始化 Notion 工作区

### 4.1 setup_notion.py 完整参数

```bash
python scripts/setup_notion.py --help
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `--parent-page` | ✅ | Notion 页面 ID（32位十六进制） |
| `--token` | ✅ | Notion Integration Token |
| `--write-env` | 可选 | 自动追加 DB IDs 到指定 .env 文件 |

### 4.2 脚本执行过程

```
╔════════════════════════════════════════════╗
║  KM System — Notion Workspace Setup       ║
╚════════════════════════════════════════════╝

🔍 Verifying parent page access …
  ✅ Parent page: KM Workspace

📦 Creating databases …
  ✅ Created: 📚 Reading Tasks  →  abc123...
  ✅ Created: 📝 Notes          →  def456...
  ✅ Created: 🌳 Tree Nodes     →  ghi789...
  ✅ Created: 📄 Knowledge Pages →  jkl012...

🔗 Adding cross-database relations …
  🔗 Added relation: Task on def456…
  🔗 Added relation: Scope on ghi789…
  🔗 Added relation: Parent on ghi789…
  🔗 Added relation: Task on jkl012…

📊 Creating Dashboard page …
  ✅ Created: 📊 KM Dashboard  →  mno345...

📝 Creating sample Reading Task …
  ✅ Sample task: pqr678...

═══════════════════════════════════════════════
  🎉 Setup complete!
═══════════════════════════════════════════════
```

### 4.3 Dashboard 页面内容

初始化后的 Dashboard 页面包含：

- **🚀 Quick Start** — 5 步快速上手指南
- **📚 ~ 📄 数据库说明** — 各数据库用途说明
- **⚙️ AI Pipeline Workflow** — 完整的流程图
- **🔌 API Endpoints** — 接口速查
- **🔧 Database IDs** — 自动生成的配置信息

你可以在 Dashboard 中手动添加 Linked Database Views 来创建自定义的数据视图。

---

## 5. 配置文件说明

### .env 完整参数

```dotenv
# ── 必填 ────────────────────────────────────
NOTION_TOKEN=ntn_xxx          # Notion Integration Token
ANTHROPIC_API_KEY=sk-ant-xxx  # Claude API 密钥
WEBHOOK_SECRET=my-secret      # Webhook 验证密钥（自定义任意字符串）

# ── Notion DB IDs（由 setup_notion.py 生成）──
NOTES_DB_ID=                  # 笔记数据库 ID（可选，为空则跳过 Notes 融合）
TREE_NODES_DB_ID=             # 知识树节点 DB（可选，为空则不同步到 DB）
KNOWLEDGE_PAGES_DB_ID=        # 知识页面 DB（可选，为空则不追踪到 DB）

# ── 可选调优 ────────────────────────────────
NOTION_RATE_LIMIT=3.0         # Notion API 每秒请求数（默认 3）
LLM_MODEL=claude-sonnet-4-5-20250929  # Claude 模型
SQLITE_PATH=./data/jobs.db    # SQLite 数据库路径
LOG_LEVEL=INFO                # 日志级别
MAX_JOB_ATTEMPTS=3            # 失败重试次数
BLOCK_BATCH_SIZE=50           # Notion blocks 批量写入大小
```

### 功能开关

v1.1 的扩展功能通过 DB ID 是否配置来控制：

| 功能 | 开启条件 | 关闭时的行为 |
|------|---------|------------|
| Notes 融合 | `NOTES_DB_ID` 非空 | AI 仅分析 Task 页面正文 |
| Tree Nodes 同步 | `TREE_NODES_DB_ID` 非空 | 知识树仅写入子页面 |
| Knowledge Pages 追踪 | `KNOWLEDGE_PAGES_DB_ID` 非空 | 知识页面仅写入子页面 |
| Approve 级联 | 以上任一非空 | 仅更新 Task 本身的 AI Stage |

---

## 6. 启动服务

### 6.1 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动（开发模式，自动重载）
uvicorn app.main:app --reload --port 8000
```

### 6.2 Docker

```bash
docker build -t km-system .
docker run -d \
  --env-file .env \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  km-system
```

### 6.3 首次启动

首次启动时，系统会自动：
1. 创建 SQLite 数据库及表结构（`data/jobs.db`）
2. 启动后台 Worker 协程（处理队列中的任务）

---

## 7. 核心使用流程

### 7.1 完整工作流（推荐顺序）

```
Step 1: 在 Reading Tasks DB 中创建阅读任务
        ├─ 填写标题、来源信息
        └─ 在页面正文中写下你的笔记/批注/摘要

Step 2:（可选）在 Notes DB 中添加细粒度笔记
        ├─ 设置 Task 关联字段 → 链接到对应任务
        └─ 分类（Quote/Idea/Question/TODO/Summary/Definition）

Step 3: 触发 AI 生成（按需选择一个或多个 action）
        ├─ checklist  → 先总览全局
        ├─ tree       → 构建知识框架
        ├─ pages      → 深入各个主题
        └─ flashcards → 制作复习卡片

Step 4: 在 Notion 中审阅（AI Stage = Needs review）
        └─ 查看 AI 生成的子页面内容

Step 5: 触发 approve
        └─ 级联更新所有关联状态 → Approved
```

### 7.2 触发 AI 生成

通过 HTTP POST 请求触发：

```bash
# 生成阅读清单
curl -X POST http://localhost:8000/webhook/notion \
  -H "Content-Type: application/json" \
  -d '{
    "task_page_id": "你的TASK页面ID",
    "action_type": "checklist",
    "secret": "your-webhook-secret"
  }'
```

返回值：

```json
{
  "job_id": "uuid-xxx-xxx",
  "status": "queued",
  "message": "Job enqueued successfully"
}
```

### 7.3 查看任务状态

```bash
# 通过 job_id 查询
curl http://localhost:8000/jobs/<job_id>

# 返回示例
{
  "job_id": "uuid-xxx",
  "task_page_id": "abc123",
  "action_type": "checklist",
  "status": "success",      // queued | running | success | failed
  "attempts": 1,
  "error": null
}
```

也可以直接在 Notion 中查看 **AI Stage** 字段的变化：

| AI Stage | 含义 |
|----------|------|
| Idle | 未触发 |
| Queued | 已入队，等待处理 |
| Running | AI 正在生成 |
| Needs review | 生成完毕，等待审阅 |
| Approved | 已批准 |
| Failed | 生成失败（查看 Error 字段） |

---

## 8. 五种 Action 详解

### 8.1 checklist — 阅读清单

**用途**：快速了解一篇内容的核心结构，生成待勾选的分析清单。

**输入**：Task 页面正文 + 关联 Notes

**输出**：在 Task 页面下创建子页面 `✅ Checklist v1: <标题>`，包含：
- 分组的待办项（to_do blocks）
- 每组有标题和简要说明
- 关键概念、论点、方法论等

**触发**：

```bash
curl -X POST http://localhost:8000/webhook/notion \
  -d '{"task_page_id":"xxx","action_type":"checklist","secret":"xxx"}'
```

### 8.2 tree — 知识树

**用途**：将内容组织成层级分类体系。

**输入**：Task 页面正文 + 关联 Notes

**输出**：
- 子页面 `🌳 Tree v1: <主题>` — 可视化的层级列表
- Tree Nodes DB 中创建对应记录（Status=Draft），包含：
  - Name（节点名）
  - Summary（摘要）
  - Keywords（关键词标签）
  - Scope（关联到 Task）
  - Parent（父节点关系，实现树状结构）

**触发**：

```bash
curl -X POST http://localhost:8000/webhook/notion \
  -d '{"task_page_id":"xxx","action_type":"tree","secret":"xxx"}'
```

### 8.3 pages — 知识页面

**用途**：为每个重要主题生成独立的知识页面。

**输入**：Task 页面正文 + 关联 Notes

**输出**：
- 根页面 `📚 Generated Pages v1` 下创建多个子页面
- 每个子页面使用特定模板：
  - `concept` — 概念解析（定义 + 特征 + 实例）
  - `framework` — 框架分析（组件 + 关系 + 应用）
  - `comparison` — 对比分析（异同 + 优劣）
  - `case_study` — 案例研究（背景 + 分析 + 启示）
  - `methodology` — 方法论（步骤 + 工具 + 注意事项）
- Knowledge Pages DB 中追踪每个生成的页面

**触发**：

```bash
curl -X POST http://localhost:8000/webhook/notion \
  -d '{"task_page_id":"xxx","action_type":"pages","secret":"xxx"}'
```

### 8.4 flashcards — 闪卡

**用途**：生成用于复习的闪卡，支持多种题型。

**输入**：Task 页面正文 + 关联 Notes

**输出**：子页面 `🎴 Flashcards v1 (N cards)` 包含：

**可视化卡片**（Notion blocks）：
- 每个 Deck 一个 heading_2
- 每张卡片：front（heading_3 + 难度 emoji）+ back（paragraph）
- 难度标识：🟢(1) 🟡(2) 🟠(3) 🔴(4) ⚫(5)
- 灰色显示 context 和 tags

**CSV 导出块**（code block）：
- 格式：`Front,Back,Tags,Deck,Type,Difficulty`
- 直接复制粘贴导入 Anki 或 Quizlet

**卡片类型**：

| Type | 说明 | 示例 |
|------|------|------|
| basic | 基本问答 | Q: 什么是 ROI？A: Return on Investment... |
| cloze | 填空题 | {{c1::净利润}} / 总投资 × 100% = ROI |
| reverse | 双向卡片 | 正向 + 反向都生成 |
| definition | 术语定义 | 术语 → 定义 |

**触发**：

```bash
curl -X POST http://localhost:8000/webhook/notion \
  -d '{"task_page_id":"xxx","action_type":"flashcards","secret":"xxx"}'
```

### 8.5 approve — 批准

**用途**：审阅满意后，一键批准所有生成内容。

**级联操作**：
1. Tree Nodes DB → 所有关联节点 Status 更新为 `Approved`
2. Knowledge Pages DB → 所有关联页面 Status 更新为 `Approved`
3. Task 本身 → AI Stage = `Approved`，Status = `Synthesizing`

**触发**：

```bash
curl -X POST http://localhost:8000/webhook/notion \
  -d '{"task_page_id":"xxx","action_type":"approve","secret":"xxx"}'
```

---

## 9. API 接口参考

### POST /webhook/notion

触发 AI 生成任务。

**请求体**：

```json
{
  "task_page_id": "notion-page-id",
  "action_type": "checklist | tree | pages | flashcards | approve",
  "secret": "your-webhook-secret",
  "timestamp": "2025-01-01T00:00:00Z",  // 可选
  "requested_by": "user-name"             // 可选
}
```

**响应** (200)：

```json
{
  "job_id": "uuid-string",
  "status": "queued",
  "message": "Job enqueued successfully"
}
```

**错误响应**：
- `401` — secret 不匹配
- `422` — action_type 无效

### GET /jobs/{job_id}

查询任务状态。

**响应** (200)：

```json
{
  "job_id": "...",
  "task_page_id": "...",
  "action_type": "checklist",
  "status": "success",
  "attempts": 1,
  "error": null,
  "created_at": "2025-01-01T00:00:00",
  "updated_at": "2025-01-01T00:00:05"
}
```

### GET /dashboard/stats

全局统计数据。

**响应**：

```json
{
  "total_tasks": 42,
  "by_status": {"success": 35, "failed": 3, "running": 2, "queued": 2},
  "runs": {"total": 120, "successful": 110, "failed": 10},
  "tokens": {"total": 580000, "estimated_cost_usd": 2.32},
  "outputs": {"tree_nodes": 256, "pages_generated": 89, "flashcard_runs": 15}
}
```

### GET /dashboard/runs?limit=20

最近的运行记录。

**参数**：`limit`（默认 20，最大 100）

**响应**：

```json
{
  "runs": [
    {
      "run_id": "...",
      "task_page_id": "...",
      "action_type": "flashcards",
      "status": "success",
      "input_tokens": 3200,
      "output_tokens": 4800,
      "started_at": "...",
      "ended_at": "...",
      "error": null
    }
  ]
}
```

### GET /dashboard/versions/{task_page_id}

查询某个 Task 的各 action 版本号。

**响应**：

```json
{
  "task_page_id": "abc123",
  "versions": {
    "checklist": 2,
    "tree": 1,
    "pages": 1,
    "flashcards": 0
  }
}
```

### GET /health

健康检查。

**响应**：

```json
{
  "status": "ok",
  "version": "1.1.0",
  "features": ["checklist","tree","pages","flashcards","approve",
               "notes_integration","versioning","dashboard"]
}
```

---

## 10. Dashboard 统计

### 10.1 API Dashboard

通过 `/dashboard/*` 端点获取统计数据，可用于构建自定义前端仪表盘。

### 10.2 Notion Dashboard

`setup_notion.py` 创建的 Dashboard 页面提供：
- 流程图概览
- API 快速参考
- 数据库 ID 配置信息

**自定义视图建议**：你可以在 Dashboard 页面中手动添加 Linked Database Views：

1. 在 Dashboard 页面中输入 `/linked` 选择 **Linked view of database**
2. 选择 Reading Tasks DB
3. 推荐创建以下视图：
   - **Board View** — 按 AI Stage 分组（看清当前流水线状态）
   - **Table View** — 筛选 Status = "Reading"（当前在读）
   - **Gallery View** — 按 Source Type 分类

---

## 11. Notion 数据库结构

### 11.1 📚 Reading Tasks

主表，每条记录代表一个阅读任务。

| 字段 | 类型 | 说明 |
|------|------|------|
| Name | Title | 任务标题 |
| Status | Select | Not started / Reading / Annotating / Synthesizing / Done / Archived |
| AI Stage | Select | Idle / Queued / Running / Needs review / Approved / Failed |
| Source Name | Rich Text | 来源名称 |
| Source Type | Select | Book / Article / Paper / Video / Podcast / Course / Other |
| Source URL | URL | 来源链接 |
| Source Citation | Rich Text | 引用格式 |
| Tags | Multi-select | 自定义标签 |
| Priority | Select | High / Medium / Low |
| Checklist Page ID | Rich Text | AI 生成的清单子页面 ID（系统写入） |
| Tree Page ID | Rich Text | AI 生成的知识树子页面 ID（系统写入） |
| Gen Pages Root ID | Rich Text | AI 生成的知识页面根页面 ID（系统写入） |
| Run ID | Rich Text | 最近一次运行 ID（系统写入） |
| Error | Rich Text | 错误信息（系统写入） |

### 11.2 📝 Notes

笔记/摘录表，每条记录是从阅读材料中提取的一条笔记。

| 字段 | 类型 | 说明 |
|------|------|------|
| Name | Title | 笔记标题 |
| Type | Select | Quote / Idea / Question / TODO / Summary / Definition |
| Location | Rich Text | 来源位置（页码、章节等） |
| Content | Rich Text | 笔记正文 |
| Tags | Multi-select | 标签 |
| Task | Relation → Reading Tasks | 关联的阅读任务 |

**AI 如何使用 Notes**：当触发生成时，系统会自动查询与该 Task 关联的所有 Notes，将它们附加到 LLM 输入中，使 AI 拥有更丰富的上下文。

### 11.3 🌳 Tree Nodes

知识树节点表，由 `tree` action 自动写入。

| 字段 | 类型 | 说明 |
|------|------|------|
| Name | Title | 节点名称 |
| Summary | Rich Text | 节点摘要 |
| Keywords | Multi-select | 关键词标签 |
| Status | Select | Draft / Approved / Archived |
| Scope | Relation → Reading Tasks | 所属阅读任务 |
| Parent | Relation → Tree Nodes (self) | 父节点（实现树状层级） |

### 11.4 📄 Knowledge Pages

知识页面追踪表，由 `pages` action 自动写入。

| 字段 | 类型 | 说明 |
|------|------|------|
| Name | Title | 页面标题 |
| Status | Select | Needs review / Approved / Archived |
| Template | Select | concept / framework / comparison / case_study / methodology |
| Version | Number | 生成版本号 |
| Page ID | Rich Text | Notion 页面 ID |
| Task | Relation → Reading Tasks | 所属阅读任务 |

---

## 12. 高级功能

### 12.1 版本控制

每次触发同一 Task 的同一 action，版本号自动递增：

```
第 1 次 checklist → ✅ Checklist v1: 标题
第 2 次 checklist → ✅ Checklist v2: 标题  （覆盖同一子页面内容）
第 3 次 tree      → 🌳 Tree v1: 主题       （tree 第 1 次，独立计数）
```

通过 API 查询版本：

```bash
curl http://localhost:8000/dashboard/versions/<task_page_id>
```

### 12.2 Notes 上下文融合

当 `NOTES_DB_ID` 配置后，AI 生成时会自动：

1. 查询 Notes DB 中 `Task` 关联为当前 Task 的所有笔记
2. 将笔记内容格式化后附加到 LLM 输入中
3. AI 在生成时能够综合页面正文 + 所有笔记

**最佳实践**：
- 用 `Quote` 类型记录原文引用
- 用 `Idea` 记录你的思考
- 用 `Question` 记录疑问（AI 可能在生成中回答）
- 用 `Definition` 记录术语定义

### 12.3 Flashcard CSV 导入

生成的闪卡页面底部包含一个 CSV 代码块：

```csv
Front,Back,Tags,Deck,Type,Difficulty
"什么是 ROI？","Return on Investment…","finance;metrics","核心概念","basic",2
```

**导入 Anki**：
1. 复制 CSV 内容
2. Anki → File → Import
3. 选择 "Text separated by tabs or semicolons"
4. 映射字段

**导入 Quizlet**：
1. 复制 CSV 内容
2. Quizlet → Create → Import
3. 粘贴内容

### 12.4 重新生成

对同一 Task 重复触发同一 action，系统会：
1. 版本号 +1
2. 清空子页面内容
3. 重新生成并写入
4. 不会创建新的子页面（复用已有的）

这意味着你可以在修改笔记后反复生成，直到满意为止。

---

## 13. 常见问题

### Q: 触发生成后 AI Stage 一直停在 Queued？

**A**: 检查服务日志。常见原因：
- Worker 协程未正常启动（检查 startup 日志）
- Anthropic API Key 无效或额度不足
- Notion Token 过期或无权限

### Q: 生成失败，Error 字段显示 "429 rate limited"？

**A**: Notion API 限流。可以：
- 降低 `NOTION_RATE_LIMIT`（如改为 `2.0`）
- 等待一分钟后重试

### Q: Notes 没有被 AI 读取？

**A**: 检查以下几点：
1. `NOTES_DB_ID` 是否正确配置
2. Notes 的 `Task` 关联字段是否正确指向目标 Task
3. Notes 的 `Content` 字段是否有内容

### Q: 如何在 N8N / Make / Zapier 中触发？

**A**: 使用 HTTP Request 节点：
- Method: POST
- URL: `http://your-server:8000/webhook/notion`
- Body: `{"task_page_id":"xxx","action_type":"checklist","secret":"xxx"}`
- Headers: `Content-Type: application/json`

### Q: 如何部署到云端？

**A**: 推荐方案：
- **Railway / Render** — 直接部署 Docker 镜像
- **VPS** — 使用 `docker-compose` + nginx 反向代理
- **Vercel / AWS Lambda** — 不推荐（需要持久化 Worker 协程）

---

## 14. 项目结构

```
km-system/
├── .env.example              # 环境变量模板
├── .env                      # 实际配置（不要提交到 git）
├── requirements.txt          # Python 依赖
├── Dockerfile                # Docker 构建文件
├── README.md                 # 项目简介
│
├── scripts/
│   └── setup_notion.py       # 🆕 Notion 工作区初始化脚本
│
├── docs/
│   └── USAGE_GUIDE.md        # 🆕 本使用说明文档
│
├── app/
│   ├── __init__.py
│   ├── config.py             # 配置（环境变量）
│   ├── models.py             # Pydantic 数据模型
│   ├── main.py               # FastAPI 入口 + 路由
│   ├── worker.py             # 后台 Worker（处理队列）
│   ├── queue.py              # 异步任务队列
│   │
│   ├── db/
│   │   ├── __init__.py       # SQLite 表创建
│   │   └── repository.py     # 数据库操作（CRUD + 统计）
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py         # Claude API 调用
│   │   ├── schemas.py        # JSON Schema（约束 LLM 输出）
│   │   └── prompts/
│   │       ├── checklist_v1.txt
│   │       ├── tree_v1.txt
│   │       ├── pages_v1.txt
│   │       └── flashcards_v1.txt
│   │
│   └── notion/
│       ├── __init__.py
│       ├── client.py         # Notion API 封装（限流 + 重试）
│       ├── normalizer.py     # Notion Blocks → Markdown
│       ├── notes_fetcher.py  # Notes DB 查询
│       ├── renderer.py       # 数据 → Notion Blocks
│       └── writer.py         # 写回 Notion（5 种 action）
│
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   └── samples.py        # 测试数据
    ├── unit/
    │   ├── test_normalizer.py     # 15 tests ✅
    │   └── test_renderer_schema.py # 23 tests ✅
    └── integration/
        └── test_webhook.py        # 12 tests (3✅ + 9⚠️ DB thread issue)
```

---

*KM System v1.1 — Built with FastAPI + Claude + Notion*
