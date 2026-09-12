import random
import uuid
from unittest.mock import AsyncMock, Mock

from app.services.persona_sampler import PersonaSampler
from app.usecases.audiences import AudienceUseCase

_CORE_TRAITS_A = {
    "digital_confidence": 0.7,
    "product_familiarity": 0.3,
    "exploration": 0.5,
    "patience": 0.4,
    "goal_directedness": 0.9,
}
_CORE_TRAITS_B = {
    "digital_confidence": 0.2,
    "product_familiarity": 0.6,
    "exploration": 0.8,
    "patience": 0.7,
    "goal_directedness": 0.3,
}


class _NoOpSession:
    async def commit(self) -> None:
        pass


async def test_generate_population_samples_one_persona_per_participant():
    use_case = AudienceUseCase(_NoOpSession())
    use_case._studies = AsyncMock()
    use_case._studies.get_owned.return_value = None

    audience = Mock(
        id=uuid.uuid4(),
        prior={"traits": {}},
        definition={"demographics": {"country": "India", "city": "Mumbai", "age_range": [25, 35]}},
    )
    use_case._audiences = AsyncMock()
    use_case._audiences.get_latest_for_study.return_value = audience
    use_case._audiences.create_participants.return_value = []

    use_case._tasks = AsyncMock()
    use_case._tasks.list_for_study.return_value = []

    use_case._engine = Mock()
    use_case._engine.sample_participants.return_value = [_CORE_TRAITS_A, _CORE_TRAITS_B]

    await use_case.generate_population(
        user=Mock(), study_id=uuid.uuid4(), population_size=2, seed=42
    )

    use_case._audiences.create_participants.assert_awaited_once()
    _audience_id, passed_traits, passed_seed, passed_personas = (
        use_case._audiences.create_participants.await_args.args
    )
    assert passed_traits == [_CORE_TRAITS_A, _CORE_TRAITS_B]
    assert passed_seed == 42
    assert [p["persona_id"] for p in passed_personas] == ["P-001", "P-002"]
    # Different core traits must actually produce different behavior, not
    # 50 clones of the same values.
    assert (
        passed_personas[0]["behavior"]["digital_confidence"]
        != passed_personas[1]["behavior"]["digital_confidence"]
    )


def test_persona_sampler_is_reproducible_for_the_same_seed():
    definition = {"demographics": {"country": "India", "age_range": [20, 40]}}
    sampler = PersonaSampler()

    persona_a = sampler.sample(
        rng=random.Random(123),
        core_traits=_CORE_TRAITS_A,
        definition=definition,
        index=0,
        task=None,
    )
    persona_b = sampler.sample(
        rng=random.Random(123),
        core_traits=_CORE_TRAITS_A,
        definition=definition,
        index=0,
        task=None,
    )

    assert persona_a == persona_b


def test_persona_sampler_derives_mental_model_from_the_real_task_text():
    task = {
        "instruction": "Send ₹1,000 to a saved beneficiary",
        "starting_point": "home_screen",
        "success_conditions": None,
    }
    persona = PersonaSampler().sample(
        rng=random.Random(1), core_traits=_CORE_TRAITS_A, definition={}, index=0, task=task
    )

    assert persona["goal"]["primary_goal"] == task["instruction"]
    assert persona["mental_model"]["expected_action"] == "Send ₹1,000"
    assert persona["mental_model"]["expected_location"] == "home_screen"
    assert "Beneficiary" in persona["mental_model"]["expected_terminology"]


def test_persona_sampler_without_a_task_is_honest_about_it():
    persona = PersonaSampler().sample(
        rng=random.Random(1), core_traits=_CORE_TRAITS_A, definition={}, index=0, task=None
    )

    assert persona["goal"]["primary_goal"] == "No task defined yet for this study"
    assert persona["mental_model"]["expected_terminology"] == []


def test_persona_sampler_keeps_every_numeric_trait_within_bounds():
    extreme_traits = {
        "digital_confidence": 1.0,
        "product_familiarity": 1.0,
        "exploration": 1.0,
        "patience": 1.0,
        "goal_directedness": 1.0,
    }
    persona = PersonaSampler().sample(
        rng=random.Random(7), core_traits=extreme_traits, definition={}, index=0, task=None
    )

    for section in ("behavior", "friction", "ui_preferences"):
        for key, value in persona[section].items():
            if isinstance(value, int | float):
                assert 0.0 <= value <= 1.0, f"{section}.{key} out of bounds: {value}"
