import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.domain.schemas.audience import PersonaCreate
from app.usecases.audiences import AudienceUseCase


class _NoOpSession:
    async def commit(self) -> None:
        pass


def _minimal_persona_payload(**overrides) -> dict:
    payload = {
        "persona_name": "Priya",
        "subtitle": "Tech-savvy first-time investor",
        "age_group": "25-30",
        "country": "India",
        "language": "English",
    }
    payload.update(overrides)
    return payload


def test_persona_create_accepts_a_single_age_number():
    persona = PersonaCreate(**_minimal_persona_payload(age_group="27"))
    assert persona.age_group == "27"


def test_persona_create_accepts_an_age_range():
    persona = PersonaCreate(**_minimal_persona_payload(age_group="25-30"))
    assert persona.age_group == "25-30"


def test_persona_create_rejects_a_malformed_age_group():
    with pytest.raises(ValidationError):
        PersonaCreate(**_minimal_persona_payload(age_group="twenties"))


def test_persona_create_defaults_list_and_map_fields_to_empty():
    persona = PersonaCreate(**_minimal_persona_payload())
    assert persona.motivations == []
    assert persona.decision_criteria == {}


async def test_add_persona_appends_to_the_existing_personas_list():
    use_case = AudienceUseCase(_NoOpSession())
    use_case._studies = AsyncMock()
    use_case._studies.get_owned.return_value = None
    audience = Mock(definition={"personas": [{"persona_name": "Existing"}]})
    use_case._audiences = AsyncMock()
    use_case._audiences.get_latest_for_study.return_value = audience
    use_case._audiences.add_persona.return_value = audience

    result = await use_case.add_persona(
        user=Mock(), study_id=uuid.uuid4(), persona={"persona_name": "Priya"}
    )

    assert result is audience
    use_case._audiences.add_persona.assert_awaited_once_with(audience, {"persona_name": "Priya"})
