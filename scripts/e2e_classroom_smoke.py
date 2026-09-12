"""End-to-end smoke test: drives the full SynKoala pipeline for real, against
the real dev Supabase DB, using the "Classroom" app onboarding screenshots in
tests/fixtures/classroom_onboarding/ as the stimulus.

study -> audience -> generate population -> task -> upload 6 screenshots ->
analyze (real VisionProvider call, one per screen) -> mark READY -> start a
simulation run -> wait for simulate_participant/aggregate_run/validate_run/
generate_insights (real InsightProvider call) to finish -> print results.

Calls UseCases directly in-process rather than over HTTP: a real Supabase
JWT login isn't scriptable here, and this only needs a real `users` row, not
a real session — the same "smoke test" pattern
.claude/skills/backend-feature/SKILL.md references for exercising Services
against the real DB. The job queue itself is untouched: this script only
enqueues jobs and polls the real `jobs`/`simulation_runs` rows for
completion — every job still runs through the real `app/workers/runner.py`
in a separate process, exactly as it would from the real API.

Usage (two terminals):
    # 1. worker
    uv run python -m app.workers.runner

    # 2. this script
    uv run python scripts/e2e_classroom_smoke.py
"""

import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import func, select

from app.db.models import JobModel, UserModel
from app.db.session import async_session_factory
from app.services.auth_service import AuthService
from app.usecases.audiences import AudienceUseCase
from app.usecases.results import ResultsUseCase
from app.usecases.simulations import SimulationUseCase
from app.usecases.stimulus import StimulusUseCase
from app.usecases.studies import StudyUseCase
from app.usecases.tasks import TaskUseCase

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "classroom_onboarding"
SCREENSHOTS = [
    "01_launch_screen.png",
    "02_create_new_account.png",
    "03_add_email.png",
    "04_verify_email.png",
    "05_create_password.png",
    "06_account_created.png",
]
POPULATION_SIZE = 1
SEED = 42
TERMINAL_RUN_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}


def _log(msg: str) -> None:
    print(f"[e2e] {msg}", flush=True)


async def _no_pending_jobs_by_id(job_ids: list[uuid.UUID]) -> bool:
    """Scoped to exact job ids (what `request_analysis` itself returned) —
    not by job_type alone. A job_type-wide check would also count unrelated
    jobs (e.g. a stale row stuck RUNNING from an earlier crash) that will
    never finish, hanging this forever waiting on jobs that were never ours."""
    async with async_session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(JobModel)
            .where(JobModel.id.in_(job_ids), JobModel.status.in_(("PENDING", "RUNNING")))
        )
        return (count or 0) == 0


async def _failed_jobs_by_id(job_ids: list[uuid.UUID]) -> list[JobModel]:
    async with async_session_factory() as session:
        result = await session.scalars(
            select(JobModel).where(JobModel.id.in_(job_ids), JobModel.status == "FAILED")
        )
        return list(result)


async def _no_pending_run_chain_jobs(run_id: uuid.UUID, job_types: tuple[str, ...]) -> bool:
    """Same scoping fix, for the aggregate_run/validate_run/generate_insights
    tail — these are enqueued by the worker itself (we never see their ids),
    but every one of their payloads carries `simulation_run_id`, so filtering
    on that instead of job_type alone keeps this from waiting on some other
    run's jobs too."""
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


async def _wait_until(check, *, timeout_s: int, interval_s: int, description: str) -> bool:
    elapsed = 0
    while elapsed < timeout_s:
        if await check():
            return True
        await asyncio.sleep(interval_s)
        elapsed += interval_s
    _log(f"TIMEOUT after {timeout_s}s waiting for: {description}")
    return False


SMOKE_USER_EMAIL = "e2e-smoke@synkoala.local"
# Fixed, not a fresh uuid4() per run: get_or_create_user looks the user up by
# id, and `email` is unique — a random id every run would try to INSERT a new
# row with this same email each time and hit UniqueViolationError on the
# second run onward. A stable id makes reruns idempotent instead — except a
# row from a prior *broken* run of this same script (before this fix existed)
# may already have a *different*, randomly-generated id under this email;
# _get_smoke_user checks for that first so this script is idempotent
# regardless of which id an earlier attempt happened to use.
SMOKE_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, SMOKE_USER_EMAIL))


async def _get_smoke_user(session) -> UserModel:
    existing = await session.scalar(select(UserModel).where(UserModel.email == SMOKE_USER_EMAIL))
    if existing is not None:
        return existing
    return await AuthService(session).get_or_create_user(
        user_id=SMOKE_USER_ID, email=SMOKE_USER_EMAIL
    )


async def main() -> None:
    async with async_session_factory() as session:
        user = await _get_smoke_user(session)
        _log(f"user_id={user.id}")

        studies = StudyUseCase(session)
        study = await studies.create(
            user,
            name="Classroom onboarding smoke test",
            objective="E2E pipeline smoke test over the Classroom app's signup flow",
            population_size=POPULATION_SIZE,
        )
        _log(f"study_id={study.id} (status={study.status})")

        audiences = AudienceUseCase(session)
        await audiences.create(
            user,
            study.id,
            "General learners",
            {
                "demographics": {"country": "India", "age_range": [20, 40]},
                "digital": {"confidence": "medium", "familiarity": "medium"},
                "behaviour": {
                    "exploration": "medium",
                    "patience": "medium",
                    "goal_directedness": "high",
                },
            },
        )
        participants = await audiences.generate_population(user, study.id, POPULATION_SIZE, SEED)
        _log(f"generated {len(participants)} participants (seed={SEED})")

        tasks = TaskUseCase(session)
        task = await tasks.create(
            user,
            study.id,
            instruction=(
                "Create a new Classroom account with your email, verify it, and set a password."
            ),
            starting_point="01_launch_screen",
            success_conditions=None,
            constraints=None,
            # Every key screen's main CTA is expected to carry semantic_role
            # "primary_action" (see app/agents/providers/vision_provider.py's
            # own prompt) — more robust than guessing the exact snake_case
            # element_key a real vision-model call will invent.
            expected_critical_actions=["primary_action"],
        )
        _log(f"task_id={task.id} starting_point={task.starting_point}")

        stimuli = StimulusUseCase(session)
        for filename in SCREENSHOTS:
            path = FIXTURES / filename
            stimulus = await stimuli.create(
                user,
                study.id,
                "mobile_ui",
                None,
                path.read_bytes(),
                "image/png",
                None,
                filename,
            )
            screen_key = stimulus.screens[0].screen_key if stimulus.screens else "?"
            _log(f"uploaded {filename} -> stimulus_id={stimulus.id} screen_key={screen_key}")

        jobs = await stimuli.request_analysis(user, study.id)
        _log(f"enqueued {len(jobs)} analyze_stimulus jobs — waiting on the worker...")

    job_ids = [j.id for j in jobs]
    ok = await _wait_until(
        lambda: _no_pending_jobs_by_id(job_ids),
        timeout_s=300,
        interval_s=5,
        description="analyze_stimulus jobs to finish",
    )
    if not ok:
        sys.exit(1)
    failed = await _failed_jobs_by_id(job_ids)
    if failed:
        _log(f"WARNING: {len(failed)} analyze_stimulus job(s) permanently failed")
        for job in failed:
            _log(f"  job {job.id} payload={job.payload}")

    async with async_session_factory() as session:
        stimuli = StimulusUseCase(session)
        uploaded = await stimuli.list_stimuli(user, study.id)
        analyzed_screens = sum(1 for s in uploaded for screen in s.screens if screen.elements)
        _log(f"{analyzed_screens}/{len(SCREENSHOTS)} screens analyzed (have elements)")

        studies = StudyUseCase(session)
        study = await studies.update(user, study.id, status="READY")
        _log(f"study marked READY (status={study.status})")

        simulations = SimulationUseCase(session)
        run = await simulations.create_run(
            user,
            study.id,
            population_size=POPULATION_SIZE,
            task_id=task.id,
            config=None,
            seed=SEED,
        )
        _log(f"simulation_run_id={run.id} — waiting on the worker...")

    async def _run_is_terminal() -> bool:
        async with async_session_factory() as session:
            current = await SimulationUseCase(session).get_run(user, run.id)
            return current.status in TERMINAL_RUN_STATUSES

    if not await _wait_until(
        _run_is_terminal, timeout_s=600, interval_s=5, description="simulation run to finish"
    ):
        sys.exit(1)

    async with async_session_factory() as session:
        current_run = await SimulationUseCase(session).get_run(user, run.id)
        _log(f"simulation run finished: status={current_run.status}")

    # aggregate_run -> validate_run -> generate_insights chain, triggered by
    # the run finishing above — wait for that tail to drain too.
    chain_job_types = ("aggregate_run", "validate_run", "generate_insights")
    await _wait_until(
        lambda: _no_pending_run_chain_jobs(run.id, chain_job_types),
        timeout_s=300,
        interval_s=5,
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

    _log(f"DONE. study_id={study.id} run_id={run.id}")


if __name__ == "__main__":
    asyncio.run(main())
