import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.db.models import JobModel
from app.db.session import async_session_factory
from app.workers.jobs import HANDLERS, ON_PERMANENT_FAILURE

logger = logging.getLogger("app.workers.runner")

# Independent concurrent workers (not a claim-a-batch-then-await-it-sequentially
# loop): a slow job (e.g. generate_insights' LLM call) only ties up the one worker
# that claimed it — the other NUM_WORKERS-1 keep claiming and finishing unrelated
# work instead of queuing up behind it.
NUM_WORKERS = 5
MAX_ATTEMPTS = 3
POLL_INTERVAL_SECONDS = 2.0


async def _claim_one_job() -> uuid.UUID | None:
    """`SELECT ... FOR UPDATE SKIP LOCKED` per planning/03-data-model-and-infra.md
    "Job queue" — only claims (marks RUNNING) and returns the id; `_process_job`
    opens its own session/transaction so one job's failure can't roll back
    another's claim or result. `SKIP LOCKED` is also what makes it safe for
    `NUM_WORKERS` of these to run concurrently: two workers racing this query
    never claim the same row."""
    async with async_session_factory() as session:
        job = await session.scalar(
            select(JobModel)
            .where(JobModel.status == "PENDING")
            .order_by(JobModel.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        job.status = "RUNNING"
        job.locked_at = datetime.now(UTC)
        await session.commit()
        return job.id


async def _process_job(job_id: uuid.UUID) -> None:
    async with async_session_factory() as session:
        job = await session.get(JobModel, job_id)
        if job is None:
            return
        job_type = job.job_type
        payload = job.payload
        handler = HANDLERS.get(job_type)
        try:
            if handler is None:
                raise ValueError(f"No handler registered for job_type={job_type!r}")
            await handler(session, payload)
        except Exception as exc:
            # A handler that fails mid-flush (e.g. a DB constraint violation)
            # leaves the session's transaction already rolled back server-side
            # — touching `job` below without rolling back the session first
            # raises `PendingRollbackError`, which used to escape this
            # `except` block entirely and crash the whole worker process
            # (see app/services/stimulus_service.py's null-byte-stripping fix,
            # landed alongside this one, for the case that first surfaced it).
            await session.rollback()
            # `rollback()` expires every attribute on `job` — reading
            # `job.attempts` as a plain Python attribute here would lazily
            # reload it, and that implicit reload path doesn't run inside
            # SQLAlchemy's async/greenlet bridge the way an explicit `await
            # session.execute(...)` does. It surfaced in production as a
            # `MissingGreenlet` crash that replaced the original job error
            # with a confusing, unrelated one and left the job stuck without
            # ever recording the failure. Computing the increment in SQL
            # (never reading the expired attribute in Python) sidesteps it —
            # job_type/payload above were already captured before the
            # handler ran, for the same reason.
            new_attempts = (
                await session.scalars(
                    update(JobModel)
                    .where(JobModel.id == job_id)
                    .values(attempts=JobModel.attempts + 1)
                    .returning(JobModel.attempts)
                )
            ).one()
            status = "PENDING" if new_attempts < MAX_ATTEMPTS else "FAILED"
            await session.execute(
                update(JobModel).where(JobModel.id == job_id).values(status=status)
            )
            logger.warning(
                "job %s (%s) failed attempt %s/%s: %s",
                job_id,
                job_type,
                new_attempts,
                MAX_ATTEMPTS,
                exc,
            )
            if status == "FAILED":
                on_permanent_failure = ON_PERMANENT_FAILURE.get(job_type)
                if on_permanent_failure is not None:
                    try:
                        await on_permanent_failure(session, payload)
                    except Exception:
                        logger.exception(
                            "job %s (%s) permanent-failure bookkeeping also failed",
                            job_id,
                            job_type,
                        )
        else:
            job.status = "DONE"
        await session.commit()


async def _worker_loop(worker_id: int) -> None:
    while True:
        job_id = await _claim_one_job()
        if job_id is None:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            continue
        try:
            await _process_job(job_id)
        except Exception:
            # Belt-and-suspenders: _process_job already catches a handler's
            # own exceptions, but this loop is one of NUM_WORKERS tasks under
            # one asyncio.gather() in run_forever() — anything that still
            # escapes it (a bug in the retry bookkeeping itself, a dropped
            # DB connection mid-commit, ...) would otherwise propagate through
            # gather() and take down every other worker with it, exactly the
            # failure this module's whole design is meant to prevent.
            logger.exception("worker %s: job %s failed unexpectedly", worker_id, job_id)


async def run_forever() -> None:
    logger.info(
        "worker started, %s concurrent workers, polling every %ss",
        NUM_WORKERS,
        POLL_INTERVAL_SECONDS,
    )
    await asyncio.gather(*(_worker_loop(i) for i in range(NUM_WORKERS)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
