"""
Pydantic models — webhook payloads, job state, run records.
v1.1: Added FLASHCARDS action, version tracking, notes integration, dashboard stats.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────

class ActionType(str, Enum):
    CHECKLIST = "checklist"
    TREE = "tree"
    PAGES = "pages"
    FLASHCARDS = "flashcards"
    APPROVE = "approve"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class AIStage(str, Enum):
    IDLE = "Idle"
    QUEUED = "Queued"
    RUNNING = "Running"
    NEEDS_REVIEW = "Needs review"
    APPROVED = "Approved"
    FAILED = "Failed"


# ── Webhook ─────────────────────────────────────────────────────────

class WebhookPayload(BaseModel):
    task_page_id: str
    action_type: ActionType
    secret: str
    timestamp: Optional[str] = None
    requested_by: Optional[str] = None


class WebhookResponse(BaseModel):
    job_id: str
    status: str = "queued"
    message: str = "Job enqueued successfully"


# ── Job ─────────────────────────────────────────────────────────────

class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    task_page_id: str
    action_type: ActionType
    status: JobStatus = JobStatus.QUEUED
    attempts: int = 0
    max_attempts: int = 3
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Run ─────────────────────────────────────────────────────────────

class Run(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str
    task_page_id: str
    action_type: ActionType
    status: JobStatus = JobStatus.RUNNING
    llm_model: Optional[str] = None
    prompt_version: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    error: Optional[str] = None
    output_snapshot: Optional[str] = None


# ── Notion Metadata ────────────────────────────────────────────────

class TaskMetadata(BaseModel):
    title: str
    status: Optional[str] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    source_citation: Optional[str] = None
    checklist_page_id: Optional[str] = None
    tree_page_id: Optional[str] = None
    gen_pages_root_id: Optional[str] = None
    flashcards_page_id: Optional[str] = None


# ── Notes (v1.1) ──────────────────────────────────────────────────

class NoteEntry(BaseModel):
    """A single note/extract fetched from the Notes DB."""
    note_id: str
    title: str
    note_type: Optional[str] = None
    location: Optional[str] = None
    content: str = ""
    tags: list[str] = Field(default_factory=list)


# ── Dashboard Stats (v1.1) ─────────────────────────────────────────

class TaskStats(BaseModel):
    total_tasks: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_ai_stage: dict[str, int] = Field(default_factory=dict)
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_tokens: int = 0
    total_pages_generated: int = 0
    total_tree_nodes: int = 0
    total_flashcards: int = 0


# ── Version Info (v1.2) ────────────────────────────────────────────

class VersionRecord(BaseModel):
    task_page_id: str
    action_type: str
    version: int = 1
    run_id: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
