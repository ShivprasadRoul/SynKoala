"""Full end-to-end pipeline run over all 12 real "Classroom" app onboarding
screenshots in .test_image/ (the complete raw set, not the 6-screen curated
subset e2e_classroom_smoke.py used) — now that OPENROUTER_API_KEY is
configured and both settings.vision_model (openai/gpt-4o-mini) and
settings.insight_model (deepseek/deepseek-v4-pro) are confirmed working
against real screenshots (see chat).

Logs the exact input/output at every stage of the HLD §2 pipeline, in order:
  1. Stimulus Engine  (analyze_stimulus)  — per-screen upload + real VisionProvider output
  2. Simulation Engine (simulate_participant) — per-participant outcome + observation counts
  3. Analytics Engine (aggregate_run) — computed metrics/segments
  4. Validation Engine (validate_run) — agreement/stability results
  5. Insight Engine (generate_insights) — cited, evidence-validated insights

Any job failure's exact exception text lives only in the worker process's own
log (app/workers/runner.py's logger.warning/exception), not in the jobs table
— run the worker with output redirected to a file alongside this script (see
module-level USAGE) so both logs can be cross-referenced.

Usage (two terminals):
    # 1. worker
    uv run python -m app.workers.runner > tests/fixtures/classroom_onboarding/logs/worker.log 2>&1

    # 2. this script
    uv run python scripts/e2e_classroom_full.py 2>&1 | \\
        tee tests/fixtures/classroom_onboarding/logs/full_run.log
"""

import asyncio
import sys
import uuid
from pathlib import Path

from sqlalchemy import func, select

from app.db.models import InsightEvidenceModel, JobModel, MetricModel, SegmentResultModel, UserModel
from app.db.session import async_session_factory
from app.services.auth_service import AuthService
from app.usecases.audiences import AudienceUseCase
from app.usecases.results import ResultsUseCase
from app.usecases.simulations import SimulationUseCase
from app.usecases.stimulus import StimulusUseCase
from app.usecases.studies import StudyUseCase
from app.usecases.tasks import TaskUseCase

IMAGE_DIR = Path(__file__).resolve().parent.parent / ".test_image"
# Logical onboarding-flow order, derived from filenames (not folder order).
SCREENSHOTS = [
    "Launch screen.png",
    "Create new account.png",
    "Create with email (unfilled).png",
    "Create with email (unfilled)-1.png",
    "Create password (unfilled).png",
    "Create password (weak password).png",
    "Create password (better password).png",
    "Create password (strong password).png",
    "Verify email (unfilled).png",
    "Verify email (filled).png",
    "Verify email (show states).png",
    "Account created (Go to log in).png",
]
POPULATION_SIZE = 3
SEED = 7
TERMINAL_RUN_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}

SMOKE_USER_EMAIL = "e2e-smoke@synkoala.local"
SMOKE_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, SMOKE_USER_EMAIL))


def _section(title: str) -> None:
    print(f"\n{'=' * 20} {title} {'=' * 20}", flush=True)


def _log(msg: str) -> None:
    print(f"[e2e] {msg}", flush=True)


async def _get_smoke_user(session) -> UserModel:
    existing = await session.scalar(select(UserModel).where(UserModel.email == SMOKE_USER_EMAIL))
    if existing is not None:
        return existing
    return await AuthService(session).get_or_create_user(
        user_id=SMOKE_USER_ID, email=SMOKE_USER_EMAIL
    )


async def _wait_until(check, *, timeout_s: int, interval_s: int, description: str) -> bool:
    elapsed = 0
    while elapsed < timeout_s:
        if await check():
            return True
        await asyncio.sleep(interval_s)
        elapsed += interval_s
    _log(f"TIMEOUT after {timeout_s}s waiting for: {description}")
    return False


async def _no_pending_jobs_by_id(job_ids: list[uuid.UUID]) -> bool:
    async with async_session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(JobModel)
            .where(JobModel.id.in_(job_ids), JobModel.status.in_(("PENDING", "RUNNING")))
        )
        return (count or 0) == 0


async def _jobs_by_id(job_ids: list[uuid.UUID]) -> list[JobModel]:
    async with async_session_factory() as session:
        result = await session.scalars(select(JobModel).where(JobModel.id.in_(job_ids)))
        return list(result)


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
    _section("SETUP")
    async with async_session_factory() as session:
        user = await _get_smoke_user(session)
        _log(f"user_id={user.id}")

        studies = StudyUseCase(session)
        study = await studies.create(
            user,
            name="Classroom onboarding — full 12-screen e2e",
            objective="Full pipeline test over the complete Classroom app signup flow",
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
        for p in participants:
            _log(f"  participant {p.id} traits={p.traits}")

        tasks = TaskUseCase(session)
        task = await tasks.create(
            user,
            study.id,
            instruction=(
                "Create a new Classroom account with your email, verify it, and set a password."
            ),
            starting_point="launch_screen",
            # The task's actual finish line (app/agents/graphs/simulation_graph.py's
            # _success_condition_met) — reaching this screen is the only way
            # task_progress hits 1.0. Previously unset, with
            # expected_critical_actions=["primary_action"] alone: since every
            # screen has its own primary_action-tagged CTA, matching that one
            # shared *role* let the very first click complete the whole task in
            # 1 step (see chat) — this is exactly the bug that was just fixed.
            success_conditions={"screen_key": "account_created_go_to_log_in"},
            constraints=None,
            # Now milestones/evidence toward success_conditions, not a completion
            # shortcut — specific element_keys along the real funnel, not a role.
            expected_critical_actions=[
                "create_account_button",
                "continue_with_email_button",
                "continue_button",
                "verify_email_button",
            ],
        )
        _log(f"task_id={task.id} starting_point={task.starting_point}")

    _section("STIMULUS ENGINE — input")
    stimulus_ids: list[uuid.UUID] = []
    async with async_session_factory() as session:
        stimuli = StimulusUseCase(session)
        for filename in SCREENSHOTS:
            path = IMAGE_DIR / filename
            image_bytes = path.read_bytes()
            stimulus = await stimuli.create(
                user, study.id, "mobile_ui", None, image_bytes, "image/png", None, filename
            )
            stimulus_ids.append(stimulus.id)
            screen_key = stimulus.screens[0].screen_key if stimulus.screens else "?"
            _log(
                f"uploaded {filename!r} ({len(image_bytes)} bytes) -> "
                f"stimulus_id={stimulus.id} screen_key={screen_key}"
            )

        jobs = await stimuli.request_analysis(user, study.id)
        _log(f"enqueued {len(jobs)} analyze_stimulus jobs — waiting on the worker...")

    job_ids = [j.id for j in jobs]
    ok = await _wait_until(
        lambda: _no_pending_jobs_by_id(job_ids),
        timeout_s=600,
        interval_s=5,
        description="analyze_stimulus jobs to finish",
    )
    if not ok:
        sys.exit(1)

    _section("STIMULUS ENGINE — output")
    finished_jobs = await _jobs_by_id(job_ids)
    failed = [j for j in finished_jobs if j.status == "FAILED"]
    if failed:
        _log(f"ERROR: {len(failed)} analyze_stimulus job(s) permanently failed after retries:")
        for job in failed:
            _log(f"  job {job.id} attempts={job.attempts} payload={job.payload}")
            _log("  -> exact exception text is in the worker's own log file (see USAGE header)")

    async with async_session_factory() as session:
        stimuli = StimulusUseCase(session)
        uploaded = await stimuli.list_stimuli(user, study.id)
        analyzed = 0
        for s in uploaded:
            for screen in s.screens:
                if not screen.elements:
                    _log(f"screen_key={screen.screen_key}: NOT ANALYZED (no elements)")
                    continue
                analyzed += 1
                _log(f"screen_key={screen.screen_key}: {len(screen.elements)} element(s)")
                for el in screen.elements:
                    _log(
                        f"    - {el.element_key} type={el.type} "
                        f"role={(el.properties or {}).get('semantic_role')} "
                        f"interactable={(el.properties or {}).get('interactable')} "
                        f"bbox={el.bbox} text={el.text!r}"
                    )
        _log(f"TOTAL: {analyzed}/{len(SCREENSHOTS)} screens analyzed")

        study_use_case = StudyUseCase(session)
        study = await study_use_case.update(user, study.id, status="READY")
        _log(f"study marked READY (status={study.status})")

    _section("SIMULATION ENGINE — input")
    async with async_session_factory() as session:
        simulations = SimulationUseCase(session)
        run = await simulations.create_run(
            user,
            study.id,
            population_size=POPULATION_SIZE,
            task_id=task.id,
            config=None,
            seed=SEED,
        )
        _log(
            f"simulation_run_id={run.id} population={POPULATION_SIZE} seed={SEED} "
            f"task_id={task.id} — waiting on the worker..."
        )

    async def _run_is_terminal() -> bool:
        async with async_session_factory() as session:
            current = await SimulationUseCase(session).get_run(user, run.id)
            return current.status in TERMINAL_RUN_STATUSES

    if not await _wait_until(
        _run_is_terminal, timeout_s=900, interval_s=5, description="simulation run to finish"
    ):
        sys.exit(1)

    _section("SIMULATION ENGINE — output")
    async with async_session_factory() as session:
        current_run = await SimulationUseCase(session).get_run(user, run.id)
        _log(f"simulation run finished: status={current_run.status}")

        results = ResultsUseCase(session)
        participant_runs = await results.list_participants(user, run.id)
        for pr in participant_runs:
            outcome = pr.final_outcome or {}
            _log(
                f"participant_run={pr.id} status={pr.status} "
                f"steps={outcome.get('steps')} events_written={outcome.get('events_written')} "
                f"task_progress={outcome.get('task_progress')} "
                f"failure_reason={outcome.get('failure_reason')}"
            )

    chain_job_types = ("aggregate_run", "validate_run", "generate_insights")
    await _wait_until(
        lambda: _no_pending_run_chain_jobs(run.id, chain_job_types),
        timeout_s=300,
        interval_s=5,
        description="aggregate_run/validate_run/generate_insights chain to finish",
    )
    for job_type in chain_job_types:
        failed_chain = await _failed_run_chain_jobs(run.id, (job_type,))
        if failed_chain:
            _log(f"ERROR: {len(failed_chain)} {job_type} job(s) permanently failed")
            for job in failed_chain:
                _log(f"  job {job.id} attempts={job.attempts}")

    async with async_session_factory() as session:
        results = ResultsUseCase(session)

        _section("ANALYTICS ENGINE — output (metrics)")
        metrics = await results.get_metrics(user, run.id)
        for level, rows in metrics.items():
            for m in rows:
                _log(
                    f"  [{level}] {m.metric} = {m.value:.4f} (n={m.sample_size}, "
                    f"element={m.element_id}, screen={m.screen_id})"
                )

        _section("ANALYTICS ENGINE — output (segments)")
        segments = await results.list_segments(user, run.id)
        for s in segments:
            _log(f"  {s.segment} · {s.metric} = {s.value:.4f} (n={s.sample_size})")

        _section("ANALYTICS ENGINE — output (heatmap)")
        heatmap = await results.get_heatmap(user, run.id)
        for h in heatmap:
            _log(
                f"  screen={h['screen_id']} element={h['element_id']} "
                f"intensity={h['intensity']} fixations={h['fixation_count']}"
            )

        _section("ANALYTICS ENGINE — output (paths)")
        paths = await results.get_paths(user, run.id)
        for p in paths:
            _log(f"  participant_run={p['participant_run_id']} screens={p['screens']}")

        _section("VALIDATION ENGINE — output")
        validation = await results.get_validation(user, run.id)
        _log(f"status={validation['status']}")
        for v in validation["results"]:
            _log(f"  {v.metric} ({v.comparison}) = {v.value:.4f} (n={v.sample_size})")

        _section("INSIGHT ENGINE — output")
        insights = await results.list_insights(user, run.id)
        _log(f"{len(insights)} insight(s) passed evidence validation")
        for i in insights:
            _log(f"[{i.severity}] {i.title}")
            _log(f"  summary: {i.summary}")
            _log(f"  affected_segments: {i.affected_segments}")
            _log(f"  recommendation: {i.recommendation}")
            _log(f"  evidence_strength: {i.evidence_strength}")
            evidence_rows = await session.scalars(
                select(InsightEvidenceModel).where(InsightEvidenceModel.insight_id == i.id)
            )
            for ev in evidence_rows:
                if ev.metric_id is not None:
                    metric = await session.get(MetricModel, ev.metric_id)
                    _log(
                        f"    evidence: metric={metric.metric} level={metric.level} "
                        f"value={ev.value} sample_size={metric.sample_size}"
                    )
                elif ev.segment_result_id is not None:
                    segment = await session.get(SegmentResultModel, ev.segment_result_id)
                    _log(
                        f"    evidence: segment={segment.segment} metric={segment.metric} "
                        f"value={ev.value} sample_size={segment.sample_size}"
                    )

    _section("DONE")
    _log(f"study_id={study.id} run_id={run.id}")


if __name__ == "__main__":
    asyncio.run(main())
