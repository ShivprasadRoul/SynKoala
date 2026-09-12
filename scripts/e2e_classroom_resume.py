"""One-off continuation of the first e2e_classroom_smoke.py run: that run's
6 screenshots were already fully analyzed (confirmed via the `jobs` table),
but its own polling had a scoping bug (fixed in e2e_classroom_smoke.py now)
that made it wait forever on unrelated stale jobs. Rather than re-upload and
re-spend 6 real vision-model calls, this picks up the same study/task by id
and finishes the rest: mark READY -> simulation run -> wait -> print results.
"""

import asyncio
import uuid

from sqlalchemy import func, select

from app.db.models import JobModel, UserModel
from app.db.session import async_session_factory
from app.usecases.results import ResultsUseCase
from app.usecases.simulations import SimulationUseCase
from app.usecases.studies import StudyUseCase

STUDY_ID = uuid.UUID("17b97670-936d-406d-a6dd-9394c7c02545")
TASK_ID = uuid.UUID("2abc75fe-2280-47b8-bb31-f21f3c23cbd4")
SMOKE_USER_EMAIL = "e2e-smoke@synkoala.local"
POPULATION_SIZE = 1
SEED = 42
TERMINAL_RUN_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


def _log(msg: str) -> None:
    print(f"[e2e] {msg}", flush=True)


async def _wait_until(check, *, timeout_s: int, interval_s: int, description: str) -> bool:
    elapsed = 0
    while elapsed < timeout_s:
        if await check():
            return True
        await asyncio.sleep(interval_s)
        elapsed += interval_s
    _log(f"TIMEOUT after {timeout_s}s waiting for: {description}")
    return False


async def _no_pending_run_chain_jobs(run_id: uuid.UUID, job_types: tuple[str, ...]) -> bool:
    async with async_session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(JobModel)
            .where(
                JobModel.job_type.in_(job_types),
                JobModel.payload["simulation_run_id"].astext == str(run_id),
                JobModel.status.in_(("PENDING", "RUNNING")),
            )
        )
        return (count or 0) == 0


async def _failed_run_chain_jobs(run_id: uuid.UUID, job_types: tuple[str, ...]) -> list[JobModel]:
    async with async_session_factory() as session:
        result = await session.scalars(
            select(JobModel).where(
                JobModel.job_type.in_(job_types),
                JobModel.payload["simulation_run_id"].astext == str(run_id),
                JobModel.status == "FAILED",
            )
        )
        return list(result)


async def main() -> None:
    async with async_session_factory() as session:
        user = await session.scalar(select(UserModel).where(UserModel.email == SMOKE_USER_EMAIL))
        assert user is not None, "smoke user not found — run e2e_classroom_smoke.py first"

        studies = StudyUseCase(session)
        study = await studies.update(user, STUDY_ID, status="READY")
        _log(f"study marked READY (status={study.status})")

        simulations = SimulationUseCase(session)
        run = await simulations.create_run(
            user,
            STUDY_ID,
            population_size=POPULATION_SIZE,
            task_id=TASK_ID,
            config=None,
            seed=SEED,
        )
        _log(f"simulation_run_id={run.id} — waiting on the worker...")

    async def _run_is_terminal() -> bool:
        async with async_session_factory() as session:
            current = await SimulationUseCase(session).get_run(user, run.id)
            return current.status in TERMINAL_RUN_STATUSES

    if not await _wait_until(
        _run_is_terminal, timeout_s=180, interval_s=3, description="simulation run to finish"
    ):
        return

    async with async_session_factory() as session:
        current_run = await SimulationUseCase(session).get_run(user, run.id)
        _log(f"simulation run finished: status={current_run.status}")

    chain_job_types = ("aggregate_run", "validate_run", "generate_insights")
    await _wait_until(
        lambda: _no_pending_run_chain_jobs(run.id, chain_job_types),
        timeout_s=180,
        interval_s=3,
        description="aggregate_run/validate_run/generate_insights chain to finish",
    )
    for job_type in chain_job_types:
        failed = await _failed_run_chain_jobs(run.id, (job_type,))
        if failed:
            _log(f"WARNING: {len(failed)} {job_type} job(s) permanently failed")

    async with async_session_factory() as session:
        results = ResultsUseCase(session)
        metrics = await results.get_metrics(user, run.id)
        _log("--- metrics ---")
        for level, rows in metrics.items():
            for m in rows:
                _log(
                    f"  [{level}] {m.metric} = {m.value} (n={m.sample_size}, "
                    f"element={m.element_id}, screen={m.screen_id})"
                )

        segments = await results.list_segments(user, run.id)
        _log(f"--- segment_results ({len(segments)} rows) ---")
        for s in segments:
            _log(f"  {s.segment} · {s.metric} = {s.value} (n={s.sample_size})")

        validation = await results.get_validation(user, run.id)
        _log(f"--- validation: status={validation['status']} ---")
        for v in validation["results"]:
            _log(f"  {v.metric} ({v.comparison}) = {v.value} (n={v.sample_size})")

        insights = await results.list_insights(user, run.id)
        _log(f"--- insights ({len(insights)}) ---")
        for i in insights:
            _log(f"  [{i.severity}] {i.title} — {i.summary}")
            _log(f"    evidence_strength={i.evidence_strength}")

    _log(f"DONE. study_id={STUDY_ID} run_id={run.id}")


if __name__ == "__main__":
    asyncio.run(main())
