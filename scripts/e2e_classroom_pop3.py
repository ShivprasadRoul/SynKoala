"""Continuation of the classroom onboarding smoke test at population_size=3:
tops up the audience to 3 participants (only 1 existed, from the earlier
n=1 run), then runs a fresh simulation run and prints results — same study/
task, already fully analyzed, so no re-upload / re-spent vision calls.
"""

import asyncio
import uuid

from sqlalchemy import func, select

from app.db.models import JobModel, UserModel
from app.db.session import async_session_factory
from app.usecases.audiences import AudienceUseCase
from app.usecases.results import ResultsUseCase
from app.usecases.simulations import SimulationUseCase

STUDY_ID = uuid.UUID("17b97670-936d-406d-a6dd-9394c7c02545")
TASK_ID = uuid.UUID("2abc75fe-2280-47b8-bb31-f21f3c23cbd4")
SMOKE_USER_EMAIL = "e2e-smoke@synkoala.local"
POPULATION_SIZE = 3
SEED = 43  # different draw than the n=1 run, so this isn't just a repeat
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

        audiences = AudienceUseCase(session)
        existing = await audiences.list_participants(user, STUDY_ID)
        _log(f"{len(existing)} participant(s) already generated")
        if len(existing) < POPULATION_SIZE:
            added = await audiences.generate_population(
                user, STUDY_ID, POPULATION_SIZE - len(existing), SEED
            )
            _log(f"generated {len(added)} more participant(s) (seed={SEED})")

        simulations = SimulationUseCase(session)
        run = await simulations.create_run(
            user,
            STUDY_ID,
            population_size=POPULATION_SIZE,
            task_id=TASK_ID,
            config=None,
            seed=SEED,
        )
        _log(
            f"simulation_run_id={run.id} (population={POPULATION_SIZE}) — waiting on the worker..."
        )

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

        participants = await results.list_participants(user, run.id)
        _log(f"--- participant_runs ({len(participants)}) ---")
        for p in participants:
            _log(f"  {p.id} status={p.status}")

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

        paths = await results.get_paths(user, run.id)
        _log(f"--- paths ({len(paths)}) ---")
        for p in paths:
            _log(f"  participant_run={p['participant_run_id']} screens={p['screens']}")

        heatmap = await results.get_heatmap(user, run.id)
        _log(f"--- heatmap ({len(heatmap)} cells) ---")
        for h in heatmap:
            _log(
                f"  screen={h['screen_id']} element={h['element_id']} "
                f"intensity={h['intensity']} n={h['fixation_count']}"
            )

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
