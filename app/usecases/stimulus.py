import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import JobModel, StimulusModel, UserModel
from app.services.job_service import JobService
from app.services.stimulus_service import StimulusService
from app.services.study_service import StudyService


class StimulusUseCase:
    """Orchestration for the StimulusModel resource (planning/02-api.md). Composes
    StudyService (ownership), StimulusService (asset + persistence), and
    JobService (analyze_stimulus enqueue)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._stimuli = StimulusService(session)
        self._jobs = JobService(session)

    async def create(
        self,
        user: UserModel,
        study_id: uuid.UUID,
        stimulus_type: str,
        source_url: str | None,
        file_bytes: bytes | None,
        file_content_type: str | None,
        metadata: dict | None,
    ) -> StimulusModel:
        await self._studies.get_owned(user, study_id)
        stimulus = await self._stimuli.create_with_asset(
            study_id, stimulus_type, source_url, file_bytes, file_content_type, metadata
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
