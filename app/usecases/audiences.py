import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AudienceModel, ParticipantRecordModel, UserModel
from app.services.audience_engine import AudienceEngine
from app.services.audience_service import AudienceService
from app.services.study_service import StudyService


class AudienceUseCase:
    """Orchestration for the AudienceModel resource (planning/02-api.md). Composes
    StudyService (ownership), AudienceEngine (pure statistics), and
    AudienceService (persistence) — none of which call each other directly."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._audiences = AudienceService(session)
        self._engine = AudienceEngine()

    async def create(
        self, user: UserModel, study_id: uuid.UUID, name: str, definition: dict
    ) -> AudienceModel:
        await self._studies.get_owned(user, study_id)
        prior = self._engine.build_prior(definition)
        audience = await self._audiences.create(study_id, name, definition, prior)
        await self._session.commit()
        return audience

    async def get(self, user: UserModel, study_id: uuid.UUID) -> AudienceModel:
        await self._studies.get_owned(user, study_id)
        return await self._audiences.get_latest_for_study(study_id)

    async def generate_population(
        self, user: UserModel, study_id: uuid.UUID, population_size: int, seed: int | None
    ) -> list[ParticipantRecordModel]:
        await self._studies.get_owned(user, study_id)
        audience = await self._audiences.get_latest_for_study(study_id)
        traits_list = self._engine.sample_participants(audience.prior, population_size, seed)
        participants = await self._audiences.create_participants(audience.id, traits_list, seed)
        await self._session.commit()
        return participants
