import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class BaseModel(DeclarativeBase):
    pass


class UserModel(BaseModel):
    """See planning/01-auth.md "User sync" — id is always the Supabase auth `sub`
    claim, never server-generated, so this row's id matches auth.users.id exactly."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    figma_connection: Mapped["FigmaConnectionModel | None"] = relationship(
        back_populates="user", uselist=False
    )
    projects: Mapped[list["ProjectModel"]] = relationship(back_populates="owner")


class FigmaConnectionModel(BaseModel):
    """Account-linking flow, distinct from sign-in — planning/01-auth.md "Figma OAuth"."""

    __tablename__ = "figma_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    access_token_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["UserModel"] = relationship(back_populates="figma_connection")


class ProjectModel(BaseModel):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped["UserModel"] = relationship(back_populates="projects")
    studies: Mapped[list["StudyModel"]] = relationship(back_populates="project")


class StudyModel(BaseModel):
    """Lifecycle: DRAFT -> READY -> RUNNING -> COMPLETED / FAILED (PRD FR-01)."""

    __tablename__ = "studies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    objective: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Soft-delete: DELETE /studies/:id sets this instead of removing the row, since
    # a hard delete would try to null out NOT NULL child FKs (audiences.study_id
    # etc.) and blow up with an integrity error. Every read (get_owned/list_owned)
    # filters deleted_at IS NULL, so a soft-deleted study behaves as gone.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["ProjectModel"] = relationship(back_populates="studies")
    audiences: Mapped[list["AudienceModel"]] = relationship(back_populates="study")
    stimuli: Mapped[list["StimulusModel"]] = relationship(back_populates="study")
    tasks: Mapped[list["TaskModel"]] = relationship(back_populates="study")
    human_benchmarks: Mapped[list["HumanBenchmarkModel"]] = relationship(back_populates="study")
    simulation_runs: Mapped[list["SimulationRunModel"]] = relationship(back_populates="study")


class AudienceModel(BaseModel):
    """`definition` is the researcher's raw input; `prior` is the derived AudiencePrior
    (LLD §4) — distributions, not point values. See planning/04-audience-engine.md."""

    __tablename__ = "audiences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    study_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("studies.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    prior: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study: Mapped["StudyModel"] = relationship(back_populates="audiences")
    participants: Mapped[list["ParticipantRecordModel"]] = relationship(back_populates="audience")


class ParticipantRecordModel(BaseModel):
    __tablename__ = "participants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audience_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("audiences.id"))
    traits: Mapped[dict] = mapped_column(JSONB, nullable=False)
    persona: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    audience: Mapped["AudienceModel"] = relationship(back_populates="participants")


class StimulusModel(BaseModel):
    __tablename__ = "stimuli"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    study_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("studies.id"))
    type: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # "metadata" is reserved on Declarative models (DeclarativeBase.metadata); map to a
    # differently-named attribute while keeping the LLD's actual column name.
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study: Mapped["StudyModel"] = relationship(back_populates="stimuli")
    screens: Mapped[list["ScreenModel"]] = relationship(
        back_populates="stimulus", order_by="ScreenModel.created_at"
    )


class ScreenModel(BaseModel):
    __tablename__ = "screens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    stimulus_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stimuli.id"))
    screen_key: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    stimulus: Mapped["StimulusModel"] = relationship(back_populates="screens")
    elements: Mapped[list["UIElementModel"]] = relationship(
        back_populates="screen", order_by="UIElementModel.created_at"
    )


class UIElementModel(BaseModel):
    __tablename__ = "ui_elements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    screen_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("screens.id"))
    element_key: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str | None] = mapped_column(String, nullable=True)
    bbox: Mapped[dict] = mapped_column(JSONB, nullable=False)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    screen: Mapped["ScreenModel"] = relationship(back_populates="elements")


class ScreenTransitionModel(BaseModel):
    """The screen graph (LLD §7) — basis for navigation simulation. Added alongside
    the Stimulus Engine plan (planning/05-stimulus-engine.md), not in the original
    LLD table list."""

    __tablename__ = "screen_transitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    from_screen_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("screens.id"))
    trigger_element_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ui_elements.id")
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    to_screen_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("screens.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaskModel(BaseModel):
    """Critical User Task (PRD §6) — expected_critical_actions and starting_point are
    additions beyond the original LLD table, added when the PRD was narrowed."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    study_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("studies.id"))
    instruction: Mapped[str] = mapped_column(String, nullable=False)
    starting_point: Mapped[str | None] = mapped_column(String, nullable=True)
    success_conditions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    constraints: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    expected_critical_actions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Defined journey (planning/13-journey-capture.md): the creator's own ground-truth
    # walkthrough, captured once and submitted whole — not a stream, not a run.
    intended_path: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study: Mapped["StudyModel"] = relationship(back_populates="tasks")


class HumanBenchmarkModel(BaseModel):
    """Optional, per study — feeds the Validation Engine (planning/10-validation-engine.md).
    See 04-Evaluation-Spec-Synthetic-Koala.md §2 for the minimum data required per metric."""

    __tablename__ = "human_benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    study_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("studies.id"))
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    task_outcomes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    interaction_rates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    segment_labels: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attention_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study: Mapped["StudyModel"] = relationship(back_populates="human_benchmarks")


class SimulationRunModel(BaseModel):
    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    study_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("studies.id"))
    population_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="PENDING")
    # 'SYNTHETIC' | 'HUMAN' — planning/13-journey-capture.md. A human run reuses this
    # exact table/status machine, so is_run_complete/finalize_run need no branching.
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="SYNTHETIC")
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_versions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    study: Mapped["StudyModel"] = relationship(back_populates="simulation_runs")
    participant_runs: Mapped[list["ParticipantRunModel"]] = relationship(
        back_populates="simulation_run"
    )
    metrics: Mapped[list["MetricModel"]] = relationship(back_populates="simulation_run")
    segment_results: Mapped[list["SegmentResultModel"]] = relationship(
        back_populates="simulation_run"
    )
    patterns: Mapped[list["PatternModel"]] = relationship(back_populates="simulation_run")
    validation_results: Mapped[list["ValidationResultModel"]] = relationship(
        back_populates="simulation_run"
    )
    insights: Mapped[list["InsightModel"]] = relationship(back_populates="simulation_run")


class ParticipantRunModel(BaseModel):
    __tablename__ = "participant_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id")
    )
    # NULL for a human tester's session (planning/13-journey-capture.md) — every
    # synthetic-path caller (SimulationRunService.create_participant_run, the worker)
    # always passes a real participant_id, so this relaxation doesn't affect them.
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id"), nullable=True
    )
    tester_label: Mapped[str | None] = mapped_column(String, nullable=True)
    voice_note_url: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="PENDING")
    current_screen_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("screens.id"), nullable=True
    )
    task_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    final_outcome: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    simulation_run: Mapped["SimulationRunModel"] = relationship(back_populates="participant_runs")
    observations: Mapped[list["ObservationModel"]] = relationship(back_populates="participant_run")


class ObservationModel(BaseModel):
    """Append-only — see planning/08-observation-store.md. No update/delete path."""

    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    participant_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participant_runs.id")
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    screen_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    element_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Raw Figma node refs from a human capture session (planning/13-journey-capture.md)
    # — resolved to screen_id/element_id only once the Stimulus Engine exists; this
    # module never blocks on that resolution happening.
    screen_figma_node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    element_figma_node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    x: Mapped[float | None] = mapped_column(Float, nullable=True)
    y: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    participant_run: Mapped["ParticipantRunModel"] = relationship(back_populates="observations")


class MetricModel(BaseModel):
    """One row per computed metric per run — planning/09-analytics-engine.md.
    `level` is one of task_success / friction / discoverability (PRD §7)."""

    __tablename__ = "metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id")
    )
    level: Mapped[str] = mapped_column(String, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    element_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    segment: Mapped[str | None] = mapped_column(String, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    simulation_run: Mapped["SimulationRunModel"] = relationship(back_populates="metrics")


class SegmentResultModel(BaseModel):
    __tablename__ = "segment_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id")
    )
    segment: Mapped[str] = mapped_column(String, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    simulation_run: Mapped["SimulationRunModel"] = relationship(back_populates="segment_results")


class PatternModel(BaseModel):
    __tablename__ = "patterns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id")
    )
    pattern_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    simulation_run: Mapped["SimulationRunModel"] = relationship(back_populates="patterns")


class ValidationResultModel(BaseModel):
    """planning/10-validation-engine.md. `human_benchmark_id` is NULL for stability
    and baseline-comparison rows, since those don't require human data."""

    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id")
    )
    human_benchmark_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("human_benchmarks.id"), nullable=True
    )
    metric: Mapped[str] = mapped_column(String, nullable=False)
    comparison: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    simulation_run: Mapped["SimulationRunModel"] = relationship(back_populates="validation_results")


class InsightModel(BaseModel):
    """`evidence_strength` replaces a bare confidence float — planning/11-insight-engine.md,
    01-PRD-Synthetic-Koala.md §7."""

    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    simulation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id")
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    affected_segments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_strength: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    simulation_run: Mapped["SimulationRunModel"] = relationship(back_populates="insights")
    evidence: Mapped[list["InsightEvidenceModel"]] = relationship(back_populates="insight")


class InsightEvidenceModel(BaseModel):
    """LLD §17 — every insight references metric IDs / observation-derived aggregates,
    never an unsupported claim."""

    __tablename__ = "insight_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    insight_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insights.id"))
    metric_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("metrics.id"), nullable=True
    )
    segment_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("segment_results.id"), nullable=True
    )
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    insight: Mapped["InsightModel"] = relationship(back_populates="evidence")


class JobModel(BaseModel):
    """The Postgres-backed queue — planning/03-data-model-and-infra.md. Polled with
    SELECT ... FOR UPDATE SKIP LOCKED; no Redis for MVP scale."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
