"""
Job Queue — async in-process queue for MVP.
Replace with Redis + RQ for production.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Callable, Awaitable, Optional

from app.models import Job

logger = logging.getLogger(__name__)


class JobQueue:
    """Simple asyncio-based job queue for single-process MVP."""

    def __init__(self):
        self._queue: Optional[asyncio.Queue[Job]] = None
        self._worker_task: asyncio.Task | None = None
        self._handler: Callable[[Job], Awaitable[None]] | None = None

    def _ensure_queue(self) -> asyncio.Queue[Job]:
        """Lazy-init queue on the current event loop."""
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    def set_handler(self, handler: Callable[[Job], Awaitable[None]]):
        """Set the function that processes each job."""
        self._handler = handler

    async def enqueue(self, job: Job):
        """Add a job to the queue."""
        q = self._ensure_queue()
        await q.put(job)
        logger.info(f"Job {job.job_id} enqueued (action={job.action_type.value})")

    async def start_worker(self):
        """Start the background worker loop."""
        if self._worker_task is not None:
            return
        self._ensure_queue()
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Queue worker started")

    async def stop_worker(self):
        """Stop the worker gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Queue worker stopped")

    async def _worker_loop(self):
        """Process jobs sequentially from the queue."""
        q = self._ensure_queue()
        while True:
            try:
                job = await q.get()
                logger.info(f"Processing job {job.job_id}")
                if self._handler:
                    try:
                        await self._handler(job)
                    except Exception as e:
                        logger.error(f"Job {job.job_id} handler error: {e}", exc_info=True)
                q.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(1)

    @property
    def pending(self) -> int:
        if self._queue is None:
            return 0
        return self._queue.qsize()


# Singleton
job_queue = JobQueue()
