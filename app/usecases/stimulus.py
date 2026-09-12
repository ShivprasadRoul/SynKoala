import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import LifecycleError, NotFoundError
from app.db.models import JobModel, StimulusModel, UserModel
from app.services.figma_oauth_service import FigmaOAuthService
from app.services.job_service import JobService
from app.services.stimulus_service import StimulusService
from app.services.study_service import StudyService


class StimulusUseCase:
    """Orchestration for the StimulusModel resource (planning/02-api.md). Composes
    StudyService (ownership), StimulusService (asset + persistence), JobService
    (analyze_stimulus enqueue), and FigmaOAuthService (connection check for a
    `type == "figma"` stimulus)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._stimuli = StimulusService(session)
        self._jobs = JobService(session)
        self._figma_oauth = FigmaOAuthService(session)

    async def create(
        self,
        user: UserModel,
        study_id: uuid.UUID,
        stimulus_type: str,
        source_url: str | None,
        file_bytes: bytes | None,
        file_content_type: str | None,
        metadata: dict | None,
        original_filename: str | None = None,
    ) -> StimulusModel:
        await self._studies.get_owned(user, study_id)
        if stimulus_type == "figma" and await self._figma_oauth.get_connection(user.id) is None:
            # Fail synchronously, in this request, rather than creating a
            # stimulus row that can only ever fail later inside the background
            # import_figma_prototype job (planning/05-stimulus-engine.md) with
            # no way for the researcher to see why — get_valid_access_token
            # raises the same "hasn't connected Figma yet" case there too, but
            # only once the job actually runs.
            raise LifecycleError(
                "Connect your Figma account before importing a Figma prototype "
                "(GET /api/v1/auth/figma/authorize)."
            )
        stimulus = await self._stimuli.create_with_asset(
            study_id,
            stimulus_type,
            source_url,
            file_bytes,
            file_content_type,
            metadata,
            original_filename,
        )
        await self._session.commit()
        return stimulus

    async def list_stimuli(self, user: UserModel, study_id: uuid.UUID) -> list[StimulusModel]:
        await self._studies.get_owned(user, study_id)
        return await self._stimuli.list_for_study(study_id)

    async def request_analysis(self, user: UserModel, study_id: uuid.UUID) -> list[JobModel]:
        """Enqueues one job per stimulus belonging to the study —
        planning/02-api.md's /stimulus/analyze has no per-stimulus id, it analyzes
        everything uploaded for the study so far. A `type == "figma"` stimulus
        needs the owner's Figma OAuth token, which only exists in this
        authenticated request's context — not the `figma` job's own payload —
        so it's the one thing the job type branches on that VisionProvider's
        `analyze_stimulus` path never needed."""
        await self._studies.get_owned(user, study_id)
        stimuli = await self._stimuli.list_for_study(study_id)
        if not stimuli:
            raise NotFoundError(f"No stimulus uploaded for study {study_id}")
        jobs = []
        for stimulus in stimuli:
            if stimulus.type == "figma":
                job = await self._jobs.enqueue(
                    "import_figma_prototype",
                    {"stimulus_id": str(stimulus.id), "user_id": str(user.id)},
                )
            else:
                job = await self._jobs.enqueue(
                    "analyze_stimulus", {"stimulus_id": str(stimulus.id)}
                )
            jobs.append(job)
        await self._session.commit()
        return jobs
