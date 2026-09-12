import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.core import crypto
from app.core.auth import get_capture_token
from app.core.errors import LifecycleError
from app.db.models import ParticipantRunModel, SimulationRunModel
from app.usecases.journey_capture import JourneyCaptureUseCase


class _FakeSession:
    """Stands in for AsyncSession in get_capture_token — only `.scalar()` is
    exercised, same "verify without a real DB" contract as test_auth.py's
    _FakeJWKClient."""

    def __init__(self, participant_run: ParticipantRunModel | None) -> None:
        self._participant_run = participant_run

    async def scalar(self, _stmt):
        return self._participant_run


class _NoOpSession:
    async def commit(self) -> None:
        pass


def _make_token(participant_run_id: uuid.UUID, *, exp_delta: timedelta = timedelta(hours=1)) -> str:
    payload = {
        "participant_run_id": str(participant_run_id),
        "exp": (datetime.now(UTC) + exp_delta).timestamp(),
    }
    return crypto.encrypt(json.dumps(payload))


def _make_participant_run(
    *, source: str = "HUMAN", status: str = "IN_PROGRESS"
) -> ParticipantRunModel:
    run = SimulationRunModel(
        id=uuid.uuid4(), study_id=uuid.uuid4(), population_size=0, source=source
    )
    participant_run = ParticipantRunModel(id=uuid.uuid4(), simulation_run_id=run.id, status=status)
    participant_run.simulation_run = run
    return participant_run


# --- get_capture_token ------------------------------------------------------------


async def test_get_capture_token_accepts_valid_token():
    participant_run = _make_participant_run()
    token = _make_token(participant_run.id)

    result = await get_capture_token(x_capture_token=token, session=_FakeSession(participant_run))

    assert result is participant_run


async def test_get_capture_token_rejects_expired_token():
    participant_run = _make_participant_run()
    token = _make_token(participant_run.id, exp_delta=timedelta(hours=-1))

    with pytest.raises(HTTPException) as exc_info:
        await get_capture_token(x_capture_token=token, session=_FakeSession(participant_run))

    assert exc_info.value.status_code == 401


async def test_get_capture_token_rejects_malformed_token():
    with pytest.raises(HTTPException) as exc_info:
        await get_capture_token(x_capture_token="not-a-real-token", session=_FakeSession(None))

    assert exc_info.value.status_code == 401


async def test_get_capture_token_rejects_missing_participant_run():
    token = _make_token(uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await get_capture_token(x_capture_token=token, session=_FakeSession(None))

    assert exc_info.value.status_code == 404


async def test_get_capture_token_rejects_non_human_run():
    participant_run = _make_participant_run(source="SYNTHETIC")
    token = _make_token(participant_run.id)

    with pytest.raises(HTTPException) as exc_info:
        await get_capture_token(x_capture_token=token, session=_FakeSession(participant_run))

    assert exc_info.value.status_code == 409


async def test_get_capture_token_rejects_terminal_session():
    participant_run = _make_participant_run(status="COMPLETED")
    token = _make_token(participant_run.id)

    with pytest.raises(HTTPException) as exc_info:
        await get_capture_token(x_capture_token=token, session=_FakeSession(participant_run))

    assert exc_info.value.status_code == 409


# --- JourneyCaptureUseCase (Services mocked at the boundary) -----------------------


async def test_create_session_rejects_non_human_run():
    use_case = JourneyCaptureUseCase(_NoOpSession())
    fake_run = SimulationRunModel(
        id=uuid.uuid4(), study_id=uuid.uuid4(), population_size=0, source="SYNTHETIC"
    )
    use_case._runs = AsyncMock()
    use_case._runs.get_by_id.return_value = fake_run
    use_case._studies = AsyncMock()
    use_case._studies.get_owned.return_value = None

    with pytest.raises(LifecycleError):
        await use_case.create_session(user=Mock(), run_id=fake_run.id, tester_label=None)


async def test_complete_session_finalizes_run_once_all_terminal():
    use_case = JourneyCaptureUseCase(_NoOpSession())
    participant_run = _make_participant_run()
    use_case._runs = AsyncMock()
    use_case._runs.complete_participant_run.return_value = participant_run
    use_case._runs.is_run_complete.return_value = True

    await use_case.complete_session(
        participant_run, "COMPLETED", {"reached_intended_path_end": True}
    )

    use_case._runs.finalize_run.assert_awaited_once_with(participant_run.simulation_run_id)


async def test_complete_session_leaves_run_open_when_incomplete():
    use_case = JourneyCaptureUseCase(_NoOpSession())
    participant_run = _make_participant_run()
    use_case._runs = AsyncMock()
    use_case._runs.complete_participant_run.return_value = participant_run
    use_case._runs.is_run_complete.return_value = False

    await use_case.complete_session(participant_run, "FAILED", None)

    use_case._runs.finalize_run.assert_not_awaited()
