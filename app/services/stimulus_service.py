import re
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.types import ElementView, ScreenGraph, ScreenView, TransitionView
from app.core.errors import NotFoundError
from app.core.settings import settings
from app.core.storage import ensure_bucket, upload_object
from app.db.models import ScreenModel, ScreenTransitionModel, StimulusModel, UIElementModel


def _strip_null_bytes(value):
    """Postgres `text`/`jsonb` columns can't store `\\u0000` at all (a hard
    Postgres limitation, not a bug in this app) — and a vision model has no
    reason to know that, so it can and does emit one (observed in the wild: a
    button's extracted `text` came back as a literal `\\u0000`). Without this,
    that one element poisons the whole `UPDATE screens SET analysis=...`
    statement and raises `UntranslatableCharacterError` — which used to crash
    the *entire* worker process (see the `runner.py` fix alongside this one),
    not just fail that one job."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {k: _strip_null_bytes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_null_bytes(v) for v in value]
    return value


def _slugify_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    stem = filename.rsplit(".", 1)[0]
    slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    return slug or None


def _infer_interactable(element_type: str, properties: dict) -> bool:
    if "interactable" in properties:
        return bool(properties["interactable"])
    return element_type in ("button", "input", "link", "select", "checkbox", "radio")


def _element_view_from_orm(element: UIElementModel) -> ElementView:
    properties = element.properties or {}
    return ElementView(
        id=element.id,
        element_key=element.element_key,
        type=element.type,
        text=element.text,
        bbox=tuple(element.bbox),
        semantic_role=properties.get("semantic_role"),
        interactable=_infer_interactable(element.type, properties),
    )


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
        original_filename: str | None = None,
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
            screen_key = await self._unique_screen_key(
                study_id, _slugify_filename(original_filename) or "screen"
            )
            self._session.add(
                ScreenModel(stimulus_id=stimulus.id, screen_key=screen_key, image_url=stored_path)
            )
            await self._session.flush()

        return await self.get_with_screens(stimulus.id)

    async def _unique_screen_key(self, study_id: uuid.UUID, base_key: str) -> str:
        """A multi-screenshot upload (a study's own multi-screen prototype flow
        is represented as *multiple* `stimuli` rows — see `list_screens_for_
        study`) used to give every screen the literal, hardcoded `screen_key`
        `"screen_01"` regardless of upload. That collapsed `resolve_starting_
        screen`/`infer_transitions` (both key screens by `screen_key` alone,
        across the whole study) onto a single indistinguishable screen the
        moment a second screenshot was uploaded — a task's `starting_point`
        could never reliably name one screen among several, and the inferred
        screen graph resolved every transition to whichever screen happened to
        be last in a `{screen_key: screen}` dict comprehension. Deriving the
        key from the uploaded filename (falling back to `"screen"`, then
        de-duplicating against this study's existing screens) gives each
        screen a real, distinct, human-typeable identity."""
        existing = {screen.screen_key for screen in await self.list_screens_for_study(study_id)}
        if base_key not in existing:
            return base_key
        suffix = 2
        while f"{base_key}_{suffix}" in existing:
            suffix += 1
        return f"{base_key}_{suffix}"

    async def list_for_study(self, study_id: uuid.UUID) -> list[StimulusModel]:
        result = await self._session.scalars(
            select(StimulusModel)
            .where(StimulusModel.study_id == study_id)
            .options(selectinload(StimulusModel.screens).selectinload(ScreenModel.elements))
            .order_by(StimulusModel.created_at)
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

    async def get_screen_graph(self, study_id: uuid.UUID) -> ScreenGraph:
        """Builds the Simulation Engine's own `ScreenGraph` shape (planning/07) from
        this study's persisted `screens`/`ui_elements`/`screen_transitions` — the one
        place that conversion happens, shared by `simulate_participant.py` (planning/
        07) and `aggregate_run.py` (planning/09's BFS baseline), instead of each job
        duplicating it."""
        screens = await self.list_screens_for_study(study_id)
        transitions = await self.list_transitions_for_study(study_id)
        screen_views = {
            screen.id: ScreenView(
                id=screen.id,
                screen_key=screen.screen_key,
                width=screen.width,
                height=screen.height,
                elements=[_element_view_from_orm(element) for element in screen.elements],
            )
            for screen in screens
        }
        transition_views = [
            TransitionView(
                from_screen_id=t.from_screen_id,
                trigger_element_id=t.trigger_element_id,
                action=t.action,
                to_screen_id=t.to_screen_id,
            )
            for t in transitions
        ]
        return ScreenGraph(screens=screen_views, transitions=transition_views)

    async def get_element_key_map(self, study_id: uuid.UUID) -> dict[uuid.UUID, str]:
        """`element_id -> element_key` for every element in the study — the
        Validation Engine (planning/10) needs this to join `metrics.element_id`
        (a synthetic run's own UUIDs) against `human_benchmarks.interaction_
        rates`/`attention_data`, which can only ever name elements by their
        stable `element_key` (a human benchmark uploader has no way to know a
        synthetic run's internal ids)."""
        screens = await self.list_screens_for_study(study_id)
        return {
            element.id: element.element_key for screen in screens for element in screen.elements
        }

    async def get_screen_key_map(self, study_id: uuid.UUID) -> dict[uuid.UUID, str]:
        """`screen_id -> screen_key` for every screen in the study — the
        Insight Engine (planning/11) needs this the same way
        `get_element_key_map` serves the Validation Engine: a `dead_end_rate`
        citation is per-screen, and only `screen_key` means anything outside
        this run's own internal ids."""
        screens = await self.list_screens_for_study(study_id)
        return {screen.id: screen.screen_key for screen in screens}

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
        screen.analysis = _strip_null_bytes(raw_analysis)
        for element in elements:
            element = _strip_null_bytes(element)
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

    async def save_figma_screen(
        self,
        stimulus_id: uuid.UUID,
        screen_key: str,
        name: str,
        width: int,
        height: int,
        image_url: str | None,
        elements: list[dict],
    ) -> tuple[ScreenModel, list[UIElementModel]]:
        """Persists one Figma-sourced screen (planning/05's Figma import path).
        Upserts by `(stimulus_id, screen_key)` — `screen_key` is the Figma
        node id, stable across re-imports of the same file — so re-running an
        import (retry, or re-syncing after the Figma file changed) replaces
        that screen's elements rather than duplicating the row. `elements`
        already carry `semantic_role`/`interactable` from
        `FigmaImportService`'s heuristics, same `properties` convention as the
        VisionProvider path. Returns the created element rows too (not just
        the screen) — the caller needs each element's real id to resolve
        Figma's `transitionNodeID` edges into `screen_transitions` rows
        afterward."""
        screen = await self._session.scalar(
            select(ScreenModel).where(
                ScreenModel.stimulus_id == stimulus_id, ScreenModel.screen_key == screen_key
            )
        )
        if screen is not None:
            await self._session.execute(
                delete(UIElementModel).where(UIElementModel.screen_id == screen.id)
            )
            screen.width, screen.height, screen.image_url = width, height, image_url
            screen.analysis = {"source": "figma", "name": name}
        else:
            screen = ScreenModel(
                stimulus_id=stimulus_id,
                screen_key=screen_key,
                width=width,
                height=height,
                image_url=image_url,
                analysis={"source": "figma", "name": name},
            )
            self._session.add(screen)
        await self._session.flush()
        element_models = [
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
            for element in elements
        ]
        self._session.add_all(element_models)
        await self._session.flush()
        return screen, element_models

    async def save_import_metadata(self, stimulus: StimulusModel, metadata: dict) -> None:
        """The raw parsed journey map (screens + hotspot/transition graph, in
        Figma's own node-id space) as an audit trail — reassigns the whole
        dict rather than mutating it in place, same `Mutable`-tracking
        limitation as `AudienceService.add_persona`."""
        stimulus.metadata_ = {**(stimulus.metadata_ or {}), "journey_map": metadata}
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
