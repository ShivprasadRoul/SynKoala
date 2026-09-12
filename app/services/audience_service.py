import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import AudienceModel, ParticipantRecordModel


class AudienceService:
    """Owns the `audiences`/`participants` tables only — no other Service, no
    statistics (that's AudienceEngine) and no ownership check (that's StudyService,
    composed in app/usecases/audiences.py:AudienceUseCase)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, study_id: uuid.UUID, name: str, definition: dict, prior: dict
    ) -> AudienceModel:
        audience = AudienceModel(study_id=study_id, name=name, definition=definition, prior=prior)
        self._session.add(audience)
        await self._session.flush()
        return audience

    async def get_latest_for_study(self, study_id: uuid.UUID) -> AudienceModel:
        audience = await self._session.scalar(
            select(AudienceModel)
            .where(AudienceModel.study_id == study_id)
            .order_by(AudienceModel.created_at.desc())
        )
        if audience is None:
            raise NotFoundError(f"No audience defined for study {study_id}")
        return audience

    async def list_participants(self, audience_id: uuid.UUID) -> list[ParticipantRecordModel]:
        result = await self._session.scalars(
            select(ParticipantRecordModel).where(ParticipantRecordModel.audience_id == audience_id)
        )
        return list(result)

    async def get_participant(self, participant_id: uuid.UUID) -> ParticipantRecordModel:
        participant = await self._session.get(ParticipantRecordModel, participant_id)
        if participant is None:
            raise NotFoundError(f"Participant {participant_id} not found")
        return participant

    async def create_participants(
        self,
        audience_id: uuid.UUID,
        traits_list: list[dict],
        seed: int | None,
        personas: list[dict] | None = None,
    ) -> list[ParticipantRecordModel]:
        personas = personas or [None] * len(traits_list)
        participants = [
            ParticipantRecordModel(
                audience_id=audience_id, traits=traits, persona=persona, seed=seed
            )
            for traits, persona in zip(traits_list, personas, strict=True)
        ]
        self._session.add_all(participants)
        await self._session.flush()
        return participants
