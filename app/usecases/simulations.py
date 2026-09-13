import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graphs.simulation_graph import has_recognized_success_condition
from app.agents.types import ScreenGraph
from app.core.errors import LifecycleError, NotFoundError
from app.db.models import ParticipantRecordModel, SimulationRunModel, TaskModel, UserModel
from app.services.audience_service import AudienceService
from app.services.job_service import JobService
from app.services.results_service import ResultsService
from app.services.simulation_run_service import SimulationRunService
from app.services.stimulus_service import StimulusService
from app.services.study_service import StudyService
from app.services.task_service import TaskService

_TERMINAL_RUN_STATUSES = ("COMPLETED", "FAILED", "CANCELLED")


def task_has_finish_line(task: TaskModel) -> bool:
    """Without either a recognized success condition or expected critical
    actions, `update_state` (app/agents/graphs/simulation_graph.py) caps
    task_progress at 0.9 by exploration alone, so no participant can ever
    reach COMPLETED — shared by `create_run` and `publish` so a study can't
    reach either path with a task guaranteed to produce a 100% drop-off."""
    return bool(
        has_recognized_success_condition(task.success_conditions) or task.expected_critical_actions
    )


class SimulationUseCase:
    """Orchestration for the Simulation resource (planning/02-api.md /
    planning/06-study-orchestrator.md). Composes StudyService, TaskService,
    AudienceService, StimulusService, SimulationRunService, ResultsService, and
    JobService — fans out one simulate_participant job per participant (LLD §19)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._tasks = TaskService(session)
        self._audiences = AudienceService(session)
        self._stimuli = StimulusService(session)
        self._runs = SimulationRunService(session)
        self._results = ResultsService(session)
        self._jobs = JobService(session)

    async def _resolve_task(self, study_id: uuid.UUID, task_id: uuid.UUID | None) -> TaskModel:
        if task_id is not None:
            task = await self._tasks.get_by_id(task_id)
            if task.study_id != study_id:
                raise NotFoundError(f"Task {task_id} not found for study {study_id}")
            return task
        tasks = await self._tasks.list_for_study(study_id)
        if len(tasks) == 1:
            return tasks[0]
        if not tasks:
            raise LifecycleError(f"Study {study_id} has no task defined")
        raise LifecycleError(f"Study {study_id} has multiple tasks — specify task_id")

    def _verify_screen_keys_exist(self, task: TaskModel, screen_graph: ScreenGraph) -> None:
        """`task.starting_point` and `success_conditions.screen_key` are
        free-text — nothing stops them from naming a screen that doesn't
        exist (a paraphrase like "Signup Page" instead of the vision model's
        own `create_new_account`). `resolve_starting_screen` silently falls
        back to an arbitrary screen on a miss, and `_success_condition_met`
        silently never matches — so a typo like this doesn't error, it just
        starts every participant on the wrong screen and makes the task
        uncompletable, which reads exactly like a UX/product finding rather
        than what it actually is: a config typo. Reproduced directly: a task
        with `starting_point="Signup Page"` and `success_conditions=
        {"screen_key": "Complete page"}` against a study whose real screens
        are `create_new_account`/`account_created_go_to_log_in` etc. — every
        participant piled up dead-end clicks on one arbitrary starting screen
        for the entire run."""
        real_keys = {screen.screen_key for screen in screen_graph.screens.values()}
        if task.starting_point and task.starting_point not in real_keys:
            raise LifecycleError(
                f"Task {task.id}'s starting_point {task.starting_point!r} doesn't match "
                f"any analyzed screen — real screen keys are: {sorted(real_keys)}"
            )
        success_screen_key = (task.success_conditions or {}).get("screen_key")
        if success_screen_key and success_screen_key not in real_keys:
            raise LifecycleError(
                f"Task {task.id}'s success_conditions.screen_key {success_screen_key!r} doesn't "
                f"match any analyzed screen — real screen keys are: {sorted(real_keys)}"
            )

    async def _resolve_participants(self, study_id: uuid.UUID) -> list[ParticipantRecordModel]:
        audience = await self._audiences.get_latest_for_study(study_id)
        participants = await self._audiences.list_participants(audience.id)
        if not participants:
            raise LifecycleError(f"Study {study_id}'s audience has no generated participants")
        return participants

    async def create_run(
        self,
        user: UserModel,
        study_id: uuid.UUID,
        population_size: int | None,
        task_id: uuid.UUID | None,
        config: dict | None,
        seed: int | None,
    ) -> SimulationRunModel:
        study = await self._studies.get_owned(user, study_id)
        # READY: the common case, first run. RUNNING/COMPLETED: legacy values a
        # study's status could already carry from before study-level status
        # stopped being mutated by run creation (see the note below) — still
        # honored so an old row isn't suddenly unrunnable. Each run's own
        # lifecycle lives on `simulation_runs.status`; study status is about
        # setup readiness (DRAFT/READY), not "has a run ever happened" —
        # run_stability_cv (planning/10, >= 5 repeated runs) and baseline
        # comparisons both depend on a study accepting more than one run.
        if study.status not in ("READY", "RUNNING", "COMPLETED"):
            raise LifecycleError(
                f"Study {study_id} must be READY before a simulation can be started "
                f"(currently {study.status})"
            )
        if population_size is None:
            population_size = study.population_size
        if population_size is None:
            raise LifecycleError(
                f"Study {study_id} has no configured sample size — set one on the "
                "study or pass population_size explicitly"
            )
        existing_runs = await self._runs.list_by_study(study_id)
        active_run = next(
            (r for r in existing_runs if r.status not in _TERMINAL_RUN_STATUSES), None
        )
        if active_run is not None:
            raise LifecycleError(
                f"Study {study_id} already has a run in progress ({active_run.id}, "
                f"{active_run.status}) — wait for it to finish before starting another"
            )
        if not await self._stimuli.has_analyzed_screens(study_id):
            raise LifecycleError(
                f"Study {study_id} has no analyzed stimulus yet — "
                "run POST /studies/:id/stimulus/analyze first"
            )
        task = await self._resolve_task(study_id, task_id)
        if not task_has_finish_line(task):
            raise LifecycleError(
                f"Task {task.id} has no finish line — set success_conditions "
                "(screen_key, element_key or semantic_role) or "
                "expected_critical_actions, otherwise no participant can complete it"
            )
        screen_graph = await self._stimuli.get_screen_graph(study_id)
        self._verify_screen_keys_exist(task, screen_graph)
        participants = await self._resolve_participants(study_id)
        if population_size > len(participants):
            raise LifecycleError(
                f"Requested {population_size} participants but only "
                f"{len(participants)} were generated"
            )
        selected = participants[:population_size]

        run = await self._runs.create_run(study_id, population_size, config, seed, task_id=task.id)

        for participant in selected:
            participant_run = await self._runs.create_participant_run(run.id, participant.id)
            await self._jobs.enqueue(
                "simulate_participant",
                {
                    "simulation_run_id": str(run.id),
                    "participant_run_id": str(participant_run.id),
                    "participant_id": str(participant.id),
                    "study_id": str(study_id),
                    "task_id": str(task.id),
                    "seed": seed,
                },
            )

        # A study's status is no longer flipped to RUNNING/COMPLETED/FAILED by
        # run creation/completion — that conflated "is this study's setup
        # done" with "what did the latest run do," and made a study parked at
        # RUNNING forever once any run started (nothing ever moved it off
        # RUNNING, since finalize_run only ever touched simulation_runs.status).
        # A study's own lifecycle now only ever reaches READY via `publish`;
        # every run's actual state lives solely on `simulation_runs.status`,
        # queried per run or via `list_runs`/`get_progress`.
        await self._session.commit()
        return run

    async def publish(self, user: UserModel, study_id: uuid.UUID) -> SimulationRunModel:
        """DRAFT -> READY plus the study's first simulation run, as one
        transaction. `create_run` below does its own `flush()`-only work until
        its final `commit()` — nothing here commits before that point, so a
        study transitioned to READY and then a raised LifecycleError (missing
        audience/task/finish-line/analyzed stimulus) or a mid-flight DB error
        both roll back the whole attempt together: the study lands back at
        exactly DRAFT with no dangling run row, never "published but the run
        failed to start." `create_run` itself is reused verbatim rather than
        duplicated — every readiness rule it already enforces (analyzed
        stimulus, a task with a finish line, a generated audience) applies
        here for free, with the same specific, actionable error messages."""
        study = await self._studies.get_owned(user, study_id)
        if study.status != "DRAFT":
            raise LifecycleError(f"Study {study_id} is already published")
        if study.population_size is None:
            raise LifecycleError("Set a sample size for this study before publishing")
        study = await self._studies.update(study, status="READY")
        return await self.create_run(
            user, study_id, population_size=None, task_id=None, config=None, seed=None
        )

    async def list_runs(self, user: UserModel, study_id: uuid.UUID) -> list[dict]:
        """A study's run history (planning/02-api.md's `GET /studies/:id/
        simulations`), oldest first — each run's completion_rate is looked up
        in one batched query rather than N, since a study can accumulate many
        runs (run_stability_cv alone wants >= 5)."""
        await self._studies.get_owned(user, study_id)  # ownership + 404
        runs = await self._runs.list_by_study(study_id)
        rates = await self._results.get_completion_rates([run.id for run in runs])
        return [{"run": run, "completion_rate": rates.get(run.id)} for run in runs]

    async def get_run(self, user: UserModel, run_id: uuid.UUID) -> SimulationRunModel:
        run = await self._runs.get_by_id(run_id)
        await self._studies.get_owned(user, run.study_id)  # ownership check
        return run

    async def cancel_run(self, user: UserModel, run_id: uuid.UUID) -> SimulationRunModel:
        run = await self.get_run(user, run_id)
        if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
            raise LifecycleError(f"Cannot cancel a run in status {run.status}")
        run = await self._runs.mark_cancelling(run)
        await self._jobs.cancel_pending("simulate_participant", "simulation_run_id", str(run_id))
        # A cancelled job never reaches complete_participant_run, so its
        # participant_runs row would otherwise stay PENDING forever — abandon
        # those directly, then finalize immediately if that was every
        # remaining participant (no more jobs left running to trigger
        # simulate_participant.py's own finalize on completion).
        await self._runs.abandon_pending_participant_runs(run_id)
        if await self._runs.is_run_complete(run_id):
            run = await self._runs.finalize_run(run_id)
        await self._session.commit()
        return run

    async def get_progress(self, user: UserModel, run_id: uuid.UUID) -> dict:
        run = await self.get_run(user, run_id)
        total = await self._runs.count_total(run_id)
        completed = await self._runs.count_terminal(run_id)
        return {"status": run.status, "completed": completed, "total": total}
