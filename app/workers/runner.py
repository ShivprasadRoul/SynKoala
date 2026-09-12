import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import JobModel
from app.db.session import async_session_factory
from app.workers.jobs import HANDLERS

logger = logging.getLogger("app.workers.runner")

BATCH_SIZE = 5
MAX_ATTEMPTS = 3
POLL_INTERVAL_SECONDS = 2.0


async def _claim_jobs(limit: int) -> list[uuid.UUID]:
    """`SELECT ... FOR UPDATE SKIP LOCKED` per planning/03-data-model-and-infra.md
    "Job queue" — only claims (marks RUNNING) and returns ids; each job then gets
    its own session/transaction in `_process_job` so one job's failure can't roll
    back another's claim or result. That per-job boundary is the whole point: one
    participant failing must not fail the batch."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(JobModel)
            .where(JobModel.status == "PENDING")
            .order_by(JobModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = list(result.scalars())
        now = datetime.now(UTC)
        for job in jobs:
            job.status = "RUNNING"
            job.locked_at = now
        await session.commit()
        return [job.id for job in jobs]


async def _process_job(job_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        job = await session.get(JobModel, job_id)
        if job is None:
            return
        handler = HANDLERS.get(job.job_type)
        try:
            if handler is None:
                raise ValueError(f"No handler registered for job_type={job.job_type!r}")
            await handler(session, job.payload)
        except Exception as exc:
            job.attempts += 1
            job.status = "PENDING" if job.attempts < MAX_ATTEMPTS else "FAILED"
            logger.warning(
                "job %s (%s) failed attempt %s/%s: %s",
                job.id,
                job.job_type,
                job.attempts,
                MAX_ATTEMPTS,
                exc,
            )
        else:
            job.status = "DONE"
        await session.commit()


async def run_forever() -> None:
    logger.info("worker started, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        job_ids = await _claim_jobs(BATCH_SIZE)
        if not job_ids:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue
        for job_id in job_ids:
            await _process_job(job_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
