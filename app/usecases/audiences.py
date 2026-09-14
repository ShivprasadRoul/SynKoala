import random
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AudienceModel, ParticipantRecordModel, UserModel
from app.services.audience_engine import AudienceEngine
from app.services.audience_service import AudienceService
from app.services.persona_sampler import PersonaSampler
from app.services.study_service import StudyService
from app.services.task_service import TaskService


class AudienceUseCase:
    """Orchestration for the AudienceModel resource (planning/02-api.md). Composes
    StudyService (ownership), AudienceEngine (pure statistics), TaskService
    (read-only, for the real task text a persona's mental model/goal are
    grounded in), PersonaSampler (pure, deterministic persona construction),
    and AudienceService (persistence) — none of which call each other
    directly."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._audiences = AudienceService(session)
        self._tasks = TaskService(session)
        self._engine = AudienceEngine()
        self._persona_sampler = PersonaSampler()

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

    async def list_participants(
        self, user: UserModel, study_id: uuid.UUID
    ) -> list[ParticipantRecordModel]:
        """Every previously generated participant/persona for the study's
        current audience — `generate_population` already persists these
        (`AudienceService.create_participants`), but until this method there
        was no way to read them back except from a `generate` call's own
        response, which a page refresh (or a second visit) loses entirely."""
        await self._studies.get_owned(user, study_id)
        audience = await self._audiences.get_latest_for_study(study_id)
        return await self._audiences.list_participants(audience.id)

    async def generate_population(
        self, user: UserModel, study_id: uuid.UUID, population_size: int, seed: int | None
    ) -> list[ParticipantRecordModel]:
        await self._studies.get_owned(user, study_id)
        audience = await self._audiences.get_latest_for_study(study_id)

        grounded = await self._engine.sample_participants(
            audience.definition, population_size, seed or 0
        )
        traits_list = [g["traits"] for g in grounded]

        tasks = await self._tasks.list_for_study(study_id)
        task = (
            {
                "instruction": tasks[0].instruction,
                "starting_point": tasks[0].starting_point,
                "success_conditions": tasks[0].success_conditions,
            }
            if tasks
            else None
        )
        # A second, independently-seeded RNG stream — persona identity/derived
        # fields never need to share draws with AudienceEngine's own trait
        # sampling, they just need to be reproducible on their own for the
        # same seed (PRD §7).
        persona_rng = random.Random(seed)
        personas = []
        for index, core_traits in enumerate(traits_list):
            persona = self._persona_sampler.sample(
                rng=persona_rng,
                core_traits=core_traits,
                definition=audience.definition,
                index=index,
                task=task,
            )
            # Real-data-grounded identity/demographics/observed_behavior/provenance
            # overlay PersonaSampler's cosmetic equivalents — PersonaSampler's
            # task-grounded mental_model/goal and its trait-derived
            # behavior/friction/ui_preferences formulas are kept.
            persona["identity"] = grounded[index]["identity"]
            persona["demographics"] = grounded[index]["demographics"]
            persona["observed_behavior"] = grounded[index]["observed_behavior"]
            persona["provenance"] = grounded[index]["provenance"]
            personas.append(persona)

        participants = await self._audiences.create_participants(
            audience.id, traits_list, seed, personas
        )
        await self._session.commit()
        return participants
