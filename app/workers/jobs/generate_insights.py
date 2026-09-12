import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.providers.insight_provider import (
    PatternFact,
    PydanticAIInsightProvider,
    ValidationFact,
)
from app.db.models import InsightEvidenceModel, InsightModel
from app.services.insight_engine import InsightEngine, MetricRecord, SegmentRecord
from app.services.results_service import ResultsService
from app.services.simulation_run_service import SimulationRunService
from app.services.stimulus_service import StimulusService
from app.services.study_service import StudyService
from app.services.task_service import TaskService


async def _metric_records(
    results: ResultsService,
    run_id: uuid.UUID,
    element_key_by_id: dict[uuid.UUID, str],
    screen_key_by_id: dict[uuid.UUID, str],
) -> list[MetricRecord]:
    metrics_by_level = await results.get_metrics(run_id)
    return [
        MetricRecord(
            id=m.id,
            level=m.level,
            metric=m.metric,
            element=element_key_by_id.get(m.element_id) if m.element_id else None,
            screen=screen_key_by_id.get(m.screen_id) if m.screen_id else None,
            value=m.value,
            sample_size=m.sample_size,
        )
        for level in metrics_by_level.values()
        for m in level
        if m.value is not None and m.sample_size is not None
    ]


async def _segment_records(results: ResultsService, run_id: uuid.UUID) -> list[SegmentRecord]:
    return [
        SegmentRecord(
            id=s.id, segment=s.segment, metric=s.metric, value=s.value, sample_size=s.sample_size
        )
        for s in await results.list_segment_results(run_id)
        if s.value is not None and s.sample_size is not None
    ]


async def _validation_facts(results: ResultsService, run_id: uuid.UUID) -> list[ValidationFact]:
    return [
        ValidationFact(
            metric=v.metric, comparison=v.comparison, value=v.value, sample_size=v.sample_size
        )
        for v in await results.list_validation_results(run_id)
        if v.value is not None and v.sample_size is not None
    ]


async def _pattern_facts(results: ResultsService, run_id: uuid.UUID) -> list[PatternFact]:
    return [
        PatternFact(pattern_type=p.pattern_type, payload=p.payload or {})
        for p in await results.list_patterns(run_id)
    ]


async def handle_generate_insights(session: AsyncSession, payload: dict) -> None:
    """The Insight Engine's job (planning/11-insight-engine.md): last link in
    the Study Orchestrator's chain. Builds the evidence package (§16-17 of the
    LLD, HLD §1's key rule — `metrics`/`segment_results`/`validation_results`/
    `patterns`, never a raw screenshot or observation stream), calls
    `PydanticAIInsightProvider.synthesize` once, mechanically validates every
    returned `InsightDraft` against that same evidence (LLD §27 — a citation
    that doesn't match a real, sufficiently-sampled row gets the whole insight
    dropped, never "fixed" by re-prompting), and computes `evidence_strength`
    from the validated evidence rather than the model's own confidence.

    Deliberately does not touch `simulation_runs.status` (planning/11's own
    text says this job "marks simulation_runs.status = COMPLETED", but
    `SimulationRunService.finalize_run` already sets that the moment every
    participant is terminal, long before this job ever runs — re-setting it
    here would be a no-op at best; see planning/06's own note on why that
    status means "the synthetic population run is done," not "the full
    pipeline is done"). Whether/how a *study's* status should reflect "insights
    generated" is a separate, currently-open gap, not decided here."""
    run_id = uuid.UUID(payload["simulation_run_id"])

    runs = SimulationRunService(session)
    results = ResultsService(session)
    stimuli = StimulusService(session)
    studies = StudyService(session)
    tasks = TaskService(session)
    engine = InsightEngine()
    provider = PydanticAIInsightProvider()

    run = await runs.get_by_id(run_id)
    study = await studies.get_by_id(run.study_id)
    task_instruction = (
        (await tasks.get_by_id(run.task_id)).instruction
        if run.task_id is not None
        else "(no task on record for this run)"
    )
    element_key_by_id = await stimuli.get_element_key_map(run.study_id)
    screen_key_by_id = await stimuli.get_screen_key_map(run.study_id)

    metrics = await _metric_records(results, run_id, element_key_by_id, screen_key_by_id)
    segments = await _segment_records(results, run_id)
    validation = await _validation_facts(results, run_id)
    patterns = await _pattern_facts(results, run_id)

    evidence = engine.build_evidence_package(
        study.name, task_instruction, metrics, segments, validation, patterns
    )
    synthesis = await provider.synthesize(evidence)

    # Idempotent under retry: insight_evidence must go before insights, since
    # it FKs to insights.id with no ON DELETE CASCADE.
    existing_ids = select(InsightModel.id).where(InsightModel.simulation_run_id == run_id)
    await session.execute(
        delete(InsightEvidenceModel).where(InsightEvidenceModel.insight_id.in_(existing_ids))
    )
    await session.execute(delete(InsightModel).where(InsightModel.simulation_run_id == run_id))

    for draft in synthesis.insights:
        validated = engine.validate(draft, metrics, segments)
        if validated is None:
            continue
        strength = engine.compute_evidence_strength(validated, metrics, segments, validation)
        insight = InsightModel(
            simulation_run_id=run_id,
            title=validated.draft.title,
            severity=validated.draft.severity,
            summary=validated.draft.summary,
            affected_segments=validated.draft.affected_segments,
            recommendation=validated.draft.recommendation,
            evidence_strength=strength,
        )
        session.add(insight)
        await session.flush()  # need insight.id before its evidence rows
        session.add_all(
            InsightEvidenceModel(
                insight_id=insight.id,
                metric_id=row_id if kind == "metric" else None,
                segment_result_id=row_id if kind == "segment" else None,
                value=value,
            )
            for kind, row_id, value in validated.evidence_links
        )
