import uuid
from unittest.mock import AsyncMock, Mock

from app.agents.providers.insight_provider import EvidenceRef, InsightDraft, InsightSynthesis
from app.workers.jobs import generate_insights as job_module


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list = []
        self.added: list = []

    async def execute(self, stmt) -> None:
        self.executed.append(stmt)

    def add(self, row) -> None:
        self.added.append(row)

    def add_all(self, rows) -> None:
        self.added.extend(rows)

    async def flush(self) -> None:
        for row in self.added:
            if getattr(row, "id", None) is None:
                row.id = uuid.uuid4()


def _metric(level, metric, value, element_id=None, screen_id=None, sample_size=40):
    return Mock(
        id=uuid.uuid4(),
        level=level,
        metric=metric,
        value=value,
        element_id=element_id,
        screen_id=screen_id,
        sample_size=sample_size,
    )


def _patch_services(
    monkeypatch,
    *,
    run,
    study,
    task,
    element_key_map,
    metrics_response,
    segment_results,
    validation_results,
    patterns,
    synthesis,
):
    fake_runs = AsyncMock()
    fake_runs.get_by_id.return_value = run
    fake_results = AsyncMock()
    fake_results.get_metrics.return_value = metrics_response
    fake_results.list_segment_results.return_value = segment_results
    fake_results.list_validation_results.return_value = validation_results
    fake_results.list_patterns.return_value = patterns
    fake_stimuli = AsyncMock()
    fake_stimuli.get_element_key_map.return_value = element_key_map
    fake_stimuli.get_screen_key_map.return_value = {}
    fake_studies = AsyncMock()
    fake_studies.get_by_id.return_value = study
    fake_tasks = AsyncMock()
    fake_tasks.get_by_id.return_value = task
    fake_provider = AsyncMock()
    fake_provider.synthesize.return_value = synthesis

    monkeypatch.setattr(job_module, "SimulationRunService", lambda session: fake_runs)
    monkeypatch.setattr(job_module, "ResultsService", lambda session: fake_results)
    monkeypatch.setattr(job_module, "StimulusService", lambda session: fake_stimuli)
    monkeypatch.setattr(job_module, "StudyService", lambda session: fake_studies)
    monkeypatch.setattr(job_module, "TaskService", lambda session: fake_tasks)
    monkeypatch.setattr(job_module, "PydanticAIInsightProvider", lambda: fake_provider)
    return fake_provider


async def test_generate_insights_persists_a_validated_insight_and_its_evidence(monkeypatch):
    run_id = uuid.uuid4()
    cta_id = uuid.uuid4()
    run = Mock(id=run_id, study_id=uuid.uuid4(), task_id=uuid.uuid4())
    study = Mock()
    study.name = "Checkout Study"
    task = Mock(instruction="Add a shoe to cart")
    metric = _metric("discoverability", "first_attention_rate", 0.21, element_id=cta_id)

    draft = InsightDraft(
        title="Users struggle to find the CTA",
        severity="HIGH",
        summary="Low first-attention rate on the primary action.",
        evidence=[EvidenceRef(metric="first_attention_rate", element="cta", value=0.21)],
        affected_segments=[],
        recommendation="Increase CTA visual prominence.",
    )

    _patch_services(
        monkeypatch,
        run=run,
        study=study,
        task=task,
        element_key_map={cta_id: "cta"},
        metrics_response={"task_success": [], "friction": [], "discoverability": [metric]},
        segment_results=[],
        validation_results=[],
        patterns=[],
        synthesis=InsightSynthesis(insights=[draft]),
    )
    session = _FakeSession()

    await job_module.handle_generate_insights(session, {"simulation_run_id": str(run_id)})

    insights = [r for r in session.added if isinstance(r, job_module.InsightModel)]
    evidence_rows = [r for r in session.added if isinstance(r, job_module.InsightEvidenceModel)]
    assert len(insights) == 1
    assert insights[0].title == "Users struggle to find the CTA"
    assert insights[0].evidence_strength["sample_size"] == 40
    assert len(evidence_rows) == 1
    assert evidence_rows[0].metric_id == metric.id
    assert evidence_rows[0].insight_id == insights[0].id
    assert len(session.executed) == 2  # delete insight_evidence, delete insights


async def test_generate_insights_drops_an_unsupported_draft(monkeypatch):
    run_id = uuid.uuid4()
    run = Mock(id=run_id, study_id=uuid.uuid4(), task_id=None)
    study = Mock()
    study.name = "Checkout Study"

    draft = InsightDraft(
        title="Fabricated finding",
        severity="HIGH",
        summary="Cites a metric that was never computed.",
        evidence=[EvidenceRef(metric="does_not_exist", element="cta", value=0.5)],
        affected_segments=[],
        recommendation="N/A",
    )

    _patch_services(
        monkeypatch,
        run=run,
        study=study,
        task=None,
        element_key_map={},
        metrics_response={"task_success": [], "friction": [], "discoverability": []},
        segment_results=[],
        validation_results=[],
        patterns=[],
        synthesis=InsightSynthesis(insights=[draft]),
    )
    session = _FakeSession()

    await job_module.handle_generate_insights(session, {"simulation_run_id": str(run_id)})

    assert session.added == []
