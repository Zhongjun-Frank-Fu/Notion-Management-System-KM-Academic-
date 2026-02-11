"""
Worker — executes the generation pipeline for each job.
v1.1: Notes integration, version tracking, flashcard pipeline.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime

from app.config import settings
from app.models import Job, Run, JobStatus, ActionType, TaskMetadata, AIStage, NoteEntry
from app.db.repository import repo
from app.notion.client import notion, NotionClient
from app.notion.normalizer import normalize_blocks, build_llm_input
from app.notion.writer import writer
from app.notion.notes_fetcher import NotesFetcher
from app.llm.client import llm, SchemaValidationError

logger = logging.getLogger(__name__)
notes_fetcher = NotesFetcher(notion)


async def process_job(job: Job):
    """Main pipeline entry point."""
    run = Run(
        job_id=job.job_id,
        task_page_id=job.task_page_id,
        action_type=job.action_type,
        llm_model=settings.llm_model,
        prompt_version=settings.prompt_version,
    )
    await repo.create_run(run)
    await repo.update_job_status(job.job_id, JobStatus.RUNNING, increment_attempts=True)

    try:
        # ── 1. AI Stage → Running ────────────────────────────────
        await notion.update_page_properties(job.task_page_id, {
            "AI Stage": NotionClient.prop_select(AIStage.RUNNING.value),
        })

        # ── 2. Approve action (no LLM) ───────────────────────────
        if job.action_type == ActionType.APPROVE:
            await writer.write_approve(job.task_page_id, run.run_id)
            await _finish_success(job, run)
            return

        # ── 3. Fetch page content ────────────────────────────────
        logger.info(f"Fetching content for {job.task_page_id}")
        page = await notion.get_page(job.task_page_id)
        blocks = await notion.get_blocks(job.task_page_id)

        # ── 4. Extract metadata ──────────────────────────────────
        metadata = _extract_metadata(page)

        # ── 5. Normalize blocks ──────────────────────────────────
        markdown = normalize_blocks(blocks)
        if not markdown.strip():
            raise ValueError("Reading Task page has no content. Add reading material before generating.")

        # ── 6. Fetch linked notes (v1.1) ─────────────────────────
        notes: list[NoteEntry] = await notes_fetcher.fetch_notes_for_task(job.task_page_id)
        llm_input = build_llm_input(markdown, metadata, notes=notes if notes else None)
        logger.info(f"Normalized content: {len(llm_input)} chars ({len(notes)} notes injected)")

        # ── 7. Content size check ────────────────────────────────
        est_tokens = len(llm_input) // 4
        if est_tokens > 100_000:
            raise ValueError(f"Content too large (~{est_tokens} tokens). Break into smaller tasks.")

        # ── 8. Version tracking (v1.2) ───────────────────────────
        version = await repo.create_version(job.task_page_id, job.action_type.value, run.run_id)
        logger.info(f"Version {version} for {job.action_type.value}")

        # ── 9. LLM Generate ─────────────────────────────────────
        logger.info(f"Generating {job.action_type.value} via LLM (v{version})")
        result, in_tokens, out_tokens = llm.generate(
            action_type=job.action_type.value,
            content=llm_input,
        )

        # ── 10. Write back ──────────────────────────────────────
        logger.info(f"Writing {job.action_type.value} v{version} back to Notion")
        match job.action_type:
            case ActionType.CHECKLIST:
                await writer.write_checklist(job.task_page_id, result, run.run_id, version)
            case ActionType.TREE:
                await writer.write_tree(job.task_page_id, result, run.run_id, version)
            case ActionType.PAGES:
                await writer.write_pages(job.task_page_id, result, run.run_id, version)
            case ActionType.FLASHCARDS:
                await writer.write_flashcards(job.task_page_id, result, run.run_id, version)

        # ── 11. Success ─────────────────────────────────────────
        await _finish_success(job, run, in_tokens, out_tokens, result)

    except SchemaValidationError as e:
        error_msg = f"Schema validation failed: {str(e)[:500]}"
        logger.error(error_msg)
        await _finish_failure(job, run, error_msg)

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        await _finish_failure(job, run, str(e))

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:500]}"
        logger.error(f"Pipeline error: {error_msg}", exc_info=True)
        if job.attempts < job.max_attempts:
            logger.info(f"Job {job.job_id} will retry ({job.attempts}/{job.max_attempts})")
            await repo.update_job_status(job.job_id, JobStatus.QUEUED, error=error_msg)
        else:
            await _finish_failure(job, run, error_msg)


async def _finish_success(job, run, in_tokens=0, out_tokens=0, result=None):
    snapshot = json.dumps(result, ensure_ascii=False)[:10000] if result else None
    await repo.finish_run(
        run.run_id, JobStatus.SUCCESS,
        input_tokens=in_tokens, output_tokens=out_tokens,
        output_snapshot=snapshot,
    )
    await repo.update_job_status(job.job_id, JobStatus.SUCCESS)
    logger.info(f"Job {job.job_id} completed successfully")


async def _finish_failure(job, run, error_msg):
    await repo.finish_run(run.run_id, JobStatus.FAILED, error=error_msg)
    await repo.update_job_status(job.job_id, JobStatus.FAILED, error=error_msg)
    await writer.write_error(job.task_page_id, error_msg)
    logger.error(f"Job {job.job_id} failed: {error_msg}")


def _extract_metadata(page: dict) -> TaskMetadata:
    props = page.get("properties", {})
    title = ""
    title_prop = props.get("Name", {}).get("title", [])
    if title_prop:
        title = title_prop[0].get("plain_text", "")

    status = None
    status_prop = props.get("Status", {}).get("select")
    if status_prop:
        status = status_prop.get("name")

    return TaskMetadata(
        title=title,
        status=status,
        checklist_page_id=_get_rich_text_value(props, "Checklist Page ID"),
        tree_page_id=_get_rich_text_value(props, "Tree Page ID"),
        gen_pages_root_id=_get_rich_text_value(props, "Gen Pages Root ID"),
        flashcards_page_id=_get_rich_text_value(props, "Flashcards Page ID"),
    )


def _get_rich_text_value(props: dict, key: str) -> str | None:
    rt = props.get(key, {}).get("rich_text", [])
    return rt[0].get("plain_text", "") if rt else None
