"""
Knowledge Management System — FastAPI Application
v1.1: Added /dashboard/stats, /dashboard/runs, flashcard action support.
"""

from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import Job, WebhookPayload, WebhookResponse, JobStatus
from app.db import init_db
from app.db.repository import repo
from app.queue import job_queue
from app.worker import process_job
from app.notion.setup import WorkspaceSetup

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Knowledge Management System v1.2...")
    await init_db()
    job_queue.set_handler(process_job)
    await job_queue.start_worker()
    logger.info("System ready.")
    yield
    logger.info("Shutting down...")
    await job_queue.stop_worker()


app = FastAPI(
    title="Knowledge Management System",
    version="1.2.0",
    description="Notion + AI knowledge generation backend — with auto-setup",
    lifespan=lifespan,
)


# ── Health ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.2.0",
        "queue_pending": job_queue.pending,
        "features": ["checklist", "tree", "pages", "flashcards", "approve",
                      "notes_integration", "versioning", "dashboard", "auto_setup"],
    }


# ── Webhook ─────────────────────────────────────────────────────────

@app.post("/webhook/notion", response_model=WebhookResponse)
async def webhook_notion(payload: WebhookPayload):
    if payload.secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid secret")
    if not payload.task_page_id:
        raise HTTPException(status_code=422, detail="Missing required field: task_page_id")

    job = Job(
        task_page_id=payload.task_page_id,
        action_type=payload.action_type,
        max_attempts=settings.max_job_attempts,
    )
    await repo.create_job(job)
    await job_queue.enqueue(job)

    logger.info(
        f"Webhook: action={payload.action_type.value} "
        f"task={payload.task_page_id[:12]}... job={job.job_id[:8]}..."
    )
    return WebhookResponse(job_id=job.job_id)


# ── Jobs ────────────────────────────────────────────────────────────

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.job_id,
        "task_page_id": job.task_page_id,
        "action_type": job.action_type.value if hasattr(job.action_type, 'value') else job.action_type,
        "status": job.status.value if hasattr(job.status, 'value') else job.status,
        "attempts": job.attempts,
        "error": job.error,
        "created_at": str(job.created_at),
        "updated_at": str(job.updated_at),
    }


@app.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    job = await repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    status = job.status.value if hasattr(job.status, 'value') else job.status
    if status != "failed":
        raise HTTPException(status_code=400, detail=f"Job is {status}, not failed")
    await repo.update_job_status(job_id, JobStatus.QUEUED)
    job.status = JobStatus.QUEUED
    await job_queue.enqueue(job)
    return {"job_id": job_id, "status": "queued", "message": "Job re-enqueued for retry"}


# ── Dashboard (v1.1) ───────────────────────────────────────────────

@app.get("/dashboard/stats")
async def dashboard_stats():
    """
    Aggregated statistics for the knowledge management dashboard.
    Can be polled by Notion embed, external dashboard, or CLI.
    """
    stats = await repo.get_stats()
    return {
        "total_tasks": stats.total_tasks,
        "by_action_type": stats.by_status,
        "runs": {
            "total": stats.total_runs,
            "successful": stats.successful_runs,
            "failed": stats.failed_runs,
        },
        "tokens": {
            "total": stats.total_tokens,
            "estimated_cost_usd": round(stats.total_tokens * 0.000003, 4),
        },
        "outputs": {
            "tree_nodes": stats.total_tree_nodes,
            "pages_generated": stats.total_pages_generated,
            "flashcard_runs": stats.total_flashcards,
        },
    }


@app.get("/dashboard/runs")
async def dashboard_runs(limit: int = 20):
    """Recent run history for monitoring."""
    runs = await repo.get_recent_runs(limit=min(limit, 100))
    return {"runs": runs, "count": len(runs)}


@app.get("/dashboard/versions/{task_page_id}")
async def task_versions(task_page_id: str):
    """Get version history for a specific task."""
    versions = {}
    for action in ["checklist", "tree", "pages", "flashcards"]:
        v = await repo.get_latest_version(task_page_id, action)
        versions[action] = v
    return {"task_page_id": task_page_id, "versions": versions}


# ── Setup (v1.2) ────────────────────────────────────────────────────

@app.post("/setup/init")
async def setup_init(payload: dict):
    """
    Initialize the full Notion workspace: creates all 4 databases
    and a Dashboard page under the given parent page.

    Body: { "parent_page_id": "...", "secret": "..." }
    Returns: DB IDs, .env snippet, dashboard page link.
    """
    secret = payload.get("secret", "")
    if secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid secret")

    parent_page_id = payload.get("parent_page_id", "").strip()
    if not parent_page_id:
        raise HTTPException(status_code=422, detail="Missing required field: parent_page_id")

    setup = WorkspaceSetup()
    result = await setup.run(parent_page_id)

    if not result.success:
        return JSONResponse(status_code=500, content={
            "error": "Setup failed",
            "details": result.to_dict(),
        })

    logger.info(f"Setup complete for parent {parent_page_id[:12]}...")
    return result.to_dict()


# ── Error Handler ───────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})
