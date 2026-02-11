# Knowledge Management System v1.0

Notion + AI backend for automated knowledge extraction and organization.

**Flow:** Reading Task → Checklist → Categorization Tree → Knowledge Pages

## Architecture

```
Notion Button → Webhook POST → FastAPI → Job Queue → Worker
                                                      ├── Fetch Notion blocks
                                                      ├── Normalize → Markdown
                                                      ├── Claude API → JSON
                                                      ├── Validate schema
                                                      └── Write back → Notion
```

## Quick Start

### 1. Prerequisites

- Python 3.11+
- [Notion Internal Integration](https://www.notion.so/my-integrations) with page access
- [Anthropic API key](https://console.anthropic.com/)
- [ngrok](https://ngrok.com/) (for local webhook testing)

### 2. Setup

```bash
git clone <repo> && cd km-system
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your tokens
```

### 3. Initialize & Run

```bash
# Start the server
uvicorn app.main:app --reload --port 8000

# In another terminal: expose via ngrok
ngrok http 8000
```

### 4. Configure Notion

1. Create the 4 databases (Reading Tasks, Sources, Notes, Tree Nodes) per the Tech Spec.
2. Connect your integration to the workspace.
3. Add buttons to Reading Tasks with webhook actions:
   - **URL:** `https://<ngrok-url>/webhook/notion`
   - **Body:** `{"task_page_id":"{{page_id}}","action_type":"checklist","secret":"<your-secret>"}`

### 5. Test

```bash
pytest tests/unit/ -v
```

## Project Structure

```
app/
├── main.py              # FastAPI endpoints
├── config.py            # Environment settings
├── models.py            # Pydantic models
├── queue.py             # Async job queue
├── worker.py            # Pipeline orchestrator
├── notion/
│   ├── client.py        # Notion API + rate limiter
│   ├── normalizer.py    # Blocks → Markdown
│   ├── renderer.py      # JSON → Notion blocks
│   └── writer.py        # Write-back orchestration
├── llm/
│   ├── client.py        # Claude API wrapper
│   ├── schemas.py       # JSON schema validation
│   └── prompts/         # Versioned prompt templates
└── db/
    ├── __init__.py      # DB initialization
    └── repository.py    # CRUD operations
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhook/notion` | Receive Notion webhooks |
| GET | `/health` | Health check |
| GET | `/jobs/{id}` | Job status |
| POST | `/jobs/{id}/retry` | Retry failed job |

## Deployment

```bash
# Docker
docker build -t km-system .
docker run -p 8000:8000 --env-file .env km-system
```

See Tech Spec for Render/Fly.io/Railway deployment details.
# Notion-Management-System-KM-Academic-
# Notion-Management-System-KM-Academic-
# Notion-Management-System-KM-Academic-
