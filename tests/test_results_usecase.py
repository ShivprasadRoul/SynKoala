import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.errors import LifecycleError
from app.usecases.results import ResultsUseCase


class _NoOpSession:
    async def commit(self) -> None:
        pass


def _use_case() -> ResultsUseCase:
    use_case = ResultsUseCase(_NoOpSession())
    use_case._studies = AsyncMock()
    use_case._studies.get_owned.return_value = None
    use_case._runs = AsyncMock()
    use_case._results = AsyncMock()
    use_case._audiences = AsyncMock()
    return use_case


def _participant_run(participant_id: uuid.UUID) -> Mock:
    return Mock(id=uuid.uuid4(), participant_id=participant_id)


async def test_resolve_segment_participant_run_ids_splits_at_the_0_5_threshold():
    """Same convention as AnalyticsEngine.compute_segments (planning/09):
    '<trait>_low' is < 0.5, '<trait>_high' is >= 0.5."""
    use_case = _use_case()
    run = Mock(id=uuid.uuid4())

    low_participant_id = uuid.uuid4()
    high_participant_id = uuid.uuid4()
    low_run = _participant_run(low_participant_id)
    high_run = _participant_run(high_participant_id)
    use_case._results.list_participant_runs.return_value = [low_run, high_run]
    use_case._audiences.list_by_ids.return_value = {
        low_participant_id: Mock(traits={"patience": 0.2}),
        high_participant_id: Mock(traits={"patience": 0.8}),
    }

    low_ids = await use_case._resolve_segment_participant_run_ids(run, "patience_low")
    high_ids = await use_case._resolve_segment_participant_run_ids(run, "patience_high")

    assert low_ids == [low_run.id]
    assert high_ids == [high_run.id]


async def test_resolve_segment_participant_run_ids_rejects_an_unrecognized_shape():
    use_case = _use_case()
    run = Mock(id=uuid.uuid4())

    with pytest.raises(LifecycleError, match="Unrecognized segment"):
        await use_case._resolve_segment_participant_run_ids(run, "not_a_real_segment_shape")

    use_case._results.list_participant_runs.assert_not_awaited()


async def test_resolve_segment_participant_run_ids_skips_a_human_tester_run():
    """A HUMAN-sourced participant_run has participant_id=None (planning/13) —
    it was never sampled from an audience, so it can't belong to any trait
    segment and must be silently excluded, not crash on a missing lookup."""
    use_case = _use_case()
    run = Mock(id=uuid.uuid4())
    human_run = _participant_run(None)
    use_case._results.list_participant_runs.return_value = [human_run]
    use_case._audiences.list_by_ids.return_value = {}

    result = await use_case._resolve_segment_participant_run_ids(run, "patience_low")

    assert result == []


async def test_get_pixel_heatmap_skips_segment_resolution_when_none_given():
    use_case = _use_case()
    run_id = uuid.uuid4()
    use_case._runs.get_by_id.return_value = Mock(id=run_id, study_id=uuid.uuid4())
    use_case._results.get_pixel_heatmap.return_value = []

    await use_case.get_pixel_heatmap(user=Mock(), run_id=run_id, segment=None)

    use_case._results.list_participant_runs.assert_not_awaited()
    use_case._results.get_pixel_heatmap.assert_awaited_once_with(run_id, participant_run_ids=None)


async def test_get_pixel_heatmap_resolves_segment_before_delegating():
    use_case = _use_case()
    run_id = uuid.uuid4()
    participant_id = uuid.uuid4()
    use_case._runs.get_by_id.return_value = Mock(id=run_id, study_id=uuid.uuid4())
    matching_run = _participant_run(participant_id)
    use_case._results.list_participant_runs.return_value = [matching_run]
    use_case._audiences.list_by_ids.return_value = {
        participant_id: Mock(traits={"digital_confidence": 0.9})
    }
    use_case._results.get_pixel_heatmap.return_value = []

    await use_case.get_pixel_heatmap(user=Mock(), run_id=run_id, segment="digital_confidence_high")

    use_case._results.get_pixel_heatmap.assert_awaited_once_with(
        run_id, participant_run_ids=[matching_run.id]
    )
