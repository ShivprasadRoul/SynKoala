import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.core.settings import settings
from app.core.storage import ensure_bucket, upload_object
from app.db.models import ScreenModel, ScreenTransitionModel, StimulusModel, UIElementModel


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

    async def list_screens_for_study(self, study_id: uuid.UUID) -> list[ScreenModel]:
        """Every screen across every stimulus upload for the study, elements
        eager-loaded. A multi-screen prototype flow is represented as *multiple*
        `stimuli` rows today (`create_with_asset` creates exactly one screen per
        upload), so "the screen graph for a study" (planning/07-simulation-engine.md)
        has to span every stimulus, not just one — see `05-stimulus-engine.md`."""
        result = await self._session.scalars(
            select(ScreenModel)
            .join(StimulusModel, ScreenModel.stimulus_id == StimulusModel.id)
            .where(StimulusModel.study_id == study_id)
            .options(selectinload(ScreenModel.elements))
            .order_by(ScreenModel.created_at)
        )
        return list(result)

    async def list_transitions_for_study(self, study_id: uuid.UUID) -> list[ScreenTransitionModel]:
        """The screen graph's edges (LLD §7), scoped to the whole study for the
        same reason as `list_screens_for_study`."""
        result = await self._session.scalars(
            select(ScreenTransitionModel)
            .join(ScreenModel, ScreenTransitionModel.from_screen_id == ScreenModel.id)
            .join(StimulusModel, ScreenModel.stimulus_id == StimulusModel.id)
            .where(StimulusModel.study_id == study_id)
        )
        return list(result)

    async def has_analyzed_screens(self, study_id: uuid.UUID) -> bool:
        """Readiness gate for `SimulationUseCase.create_run`
        (planning/06-study-orchestrator.md item 1): at least one element has
        actually been detected somewhere in the study's stimuli (planning/05's
        VisionProvider has run for it) — not just that a stimulus was uploaded."""
        screens = await self.list_screens_for_study(study_id)
        return any(element for screen in screens for element in screen.elements)

    async def save_screen_analysis(
        self, screen: ScreenModel, elements: list[dict], raw_analysis: dict
    ) -> None:
        """Persists the VisionProvider's output (planning/05): `raw_analysis` is
        kept on `screens.analysis` as an audit trail of what the model actually
        returned; `elements` become normalized `ui_elements` rows. `properties`
        is where `semantic_role`/`interactable` live — see that doc's note on why
        `ui_elements` has no dedicated columns for them."""
        screen.analysis = raw_analysis
        for element in elements:
            self._session.add(
                UIElementModel(
                    screen_id=screen.id,
                    element_key=element["element_key"],
                    type=element["type"],
                    text=element.get("text"),
                    bbox=list(element["bbox"]),
                    properties={
                        "semantic_role": element["semantic_role"],
                        "interactable": element["interactable"],
                    },
                )
            )
        await self._session.flush()

    async def replace_transitions_for_study(
        self, study_id: uuid.UUID, transitions: list[dict]
    ) -> None:
        """Wholesale replace (LLD §7's screen graph is re-derived, not appended
        to) — re-running inference after a new stimulus is analyzed must not
        leave stale edges from a smaller screen set around. `transitions`:
        `[{"from_screen_id", "trigger_element_id", "action", "to_screen_id"}]`."""
        screen_ids = (
            select(ScreenModel.id)
            .join(StimulusModel, ScreenModel.stimulus_id == StimulusModel.id)
            .where(StimulusModel.study_id == study_id)
        )
        await self._session.execute(
            delete(ScreenTransitionModel).where(
                ScreenTransitionModel.from_screen_id.in_(screen_ids)
            )
        )
        self._session.add_all([ScreenTransitionModel(**t) for t in transitions])
        await self._session.flush()
