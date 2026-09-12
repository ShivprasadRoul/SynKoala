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
        """Enqueues one analyze_stimulus job per stimulus belonging to the study —
        planning/02-api.md's /stimulus/analyze has no per-stimulus id, it analyzes
        everything uploaded for the study so far."""
        await self._studies.get_owned(user, study_id)
        stimulus_ids = await self._stimuli.list_ids_for_study(study_id)
        if not stimulus_ids:
            raise NotFoundError(f"No stimulus uploaded for study {study_id}")
        jobs = [
            await self._jobs.enqueue("analyze_stimulus", {"stimulus_id": str(sid)})
            for sid in stimulus_ids
        ]
        await self._session.commit()
        return jobs
