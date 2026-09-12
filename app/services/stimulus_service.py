import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.core.settings import settings
from app.core.storage import ensure_bucket, upload_object
from app.db.models import ScreenModel, ScreenTransitionModel, StimulusModel


class StimulusService:
    """Owns the `stimuli`/`screens` tables plus the Supabase Storage asset for a
    stimulus — storage is this Service's own external call (like S3 in the
    reference pattern), not a second Service. Vision-model screen/element
    extraction is a separate agent step (VisionProvider, planning/05), not this."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_with_asset(
        self,
        study_id: uuid.UUID,
        stimulus_type: str,
        source_url: str | None,
        file_bytes: bytes | None,
        file_content_type: str | None,
        metadata: dict | None,
    ) -> StimulusModel:
        stimulus = StimulusModel(
            study_id=study_id, type=stimulus_type, source_url=source_url, metadata_=metadata
        )
        self._session.add(stimulus)
        await self._session.flush()  # need stimulus.id before uploading under its path

        if file_bytes is not None:
            await ensure_bucket(settings.supabase_storage_bucket)
            stored_path = await upload_object(
                settings.supabase_storage_bucket,
                f"{stimulus.id}/original",
                file_bytes,
                file_content_type or "application/octet-stream",
            )
            stimulus.source_url = stored_path
            self._session.add(
                ScreenModel(stimulus_id=stimulus.id, screen_key="screen_01", image_url=stored_path)
            )
            await self._session.flush()

        return await self.get_with_screens(stimulus.id)

    async def list_for_study(self, study_id: uuid.UUID) -> list[StimulusModel]:
        result = await self._session.scalars(
            select(StimulusModel)
            .where(StimulusModel.study_id == study_id)
            .options(selectinload(StimulusModel.screens).selectinload(ScreenModel.elements))
            .order_by(StimulusModel.created_at)
        )
        return list(result)

    async def list_ids_for_study(self, study_id: uuid.UUID) -> list[uuid.UUID]:
        result = await self._session.scalars(
            select(StimulusModel.id).where(StimulusModel.study_id == study_id)
        )
        return list(result)

    async def get_with_screens(self, stimulus_id: uuid.UUID) -> StimulusModel:
        stimulus = await self._session.scalar(
            select(StimulusModel)
            .where(StimulusModel.id == stimulus_id)
            .options(selectinload(StimulusModel.screens).selectinload(ScreenModel.elements))
        )
        if stimulus is None:
            raise NotFoundError(f"Stimulus {stimulus_id} not found")
        return stimulus

    async def get_latest_for_study(self, study_id: uuid.UUID) -> StimulusModel:
        """The stimulus a simulation run should perceive (planning/07-simulation-engine.md)
        — most recently created, screens/elements eager-loaded for the screen graph."""
        stimulus = await self._session.scalar(
            select(StimulusModel)
            .where(StimulusModel.study_id == study_id)
            .options(selectinload(StimulusModel.screens).selectinload(ScreenModel.elements))
            .order_by(StimulusModel.created_at.desc())
        )
        if stimulus is None:
            raise NotFoundError(f"No stimulus defined for study {study_id}")
        return stimulus

    async def list_transitions_for_stimulus(
        self, stimulus_id: uuid.UUID
    ) -> list[ScreenTransitionModel]:
        """The screen graph's edges (LLD §7) — joined through `screens` since a
        transition doesn't carry its own stimulus_id."""
        result = await self._session.scalars(
            select(ScreenTransitionModel)
            .join(ScreenModel, ScreenTransitionModel.from_screen_id == ScreenModel.id)
            .where(ScreenModel.stimulus_id == stimulus_id)
        )
        return list(result)
