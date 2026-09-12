---
name: backend-feature
description: >
  Use when implementing or modifying SynKoala backend functionality — a new FastAPI
  endpoint, use case, service method, LangGraph/Pydantic AI agent, worker job, or DB model
  — under app/. Also trigger for "add an endpoint", "add a usecase", "add a service",
  "wire up auth for this route", "add a worker job", "add an agent/provider", or "this
  needs to enqueue a job". Walks through this repo's layering (Router → UseCase → Service
  → Model), which auth dependency applies, the job-queue convention, the
  evidence/validation rules for anything shown to a researcher, and the
  stochasticity/reproducibility rule for the simulation loop — so new code matches the
  existing architecture instead of introducing an ad-hoc pattern.
---

# SynKoala backend feature workflow

Work through these in order. Skip a step only if it's genuinely not applicable (e.g. no
new route, no cross-service call) — don't skip it because it's inconvenient.

Most of the data model, auth, and all 7 API resource groups from `planning/02-api.md` are
built and verified against the real Supabase DB (see `CLAUDE.md` "Repository state"). What
is **not** built yet is any actual model/agent call — the LangGraph simulation loop and
the Vision/Insight providers (`planning/05,07,10,11`) don't exist, so jobs get enqueued
correctly but nothing consumes them. That boundary is intentional; don't paper over it by
faking agent output.

## 1. Find the module doc before writing code

Every backend concern has a planning doc — read it before writing the corresponding
code, and update it if the implementation ends up diverging from what it says:

- `planning/01-auth.md` — auth
- `planning/02-api.md` — routers/endpoints (built)
- `planning/03-data-model-and-infra.md` — DB schema, migrations, job queue, Supabase wiring
- `planning/04-audience-engine.md` … `planning/11-insight-engine.md` — one doc per backend
  service/agent, in the same order as the HLD's component list
- `planning/12-web-app.md` — frontend, not this skill's concern

If you're about to write code that isn't described in any of these, that's a real gap —
say so and extend the relevant doc first. Don't just wing the implementation.

## 2. Follow the layering — don't collapse it

```
Router (app/api/v1/*.py, thin dispatcher)
  → UseCase (app/usecases/*.py)   — orchestration: decides what happens and in what order
    → Service(s) (app/services/*.py)   — one system/table each: DB queries, Supabase
      │                                   Storage, Figma API, enqueuing a job
      → Agent (app/agents/...)           — only for the step that needs a model call
        → Model (SQLAlchemy, app/db/models.py)
```

Naming, per `projectstruct.md` (adopted, with `app/`'s own adjustments noted):

- **Model**: `<Noun>Model` (`StudyModel`, `TaskModel`, `JobModel`). Exception: the
  `participants` table is `ParticipantRecordModel`, not `ParticipantModel` — that name is
  reserved for the LLD §28 `ParticipantModel` Protocol (the AI attention/action-selection
  interface, `planning/06,07-simulation-engine.md`), which was planned first. Never put the
  `Model`-suffixed class name in a user-facing string (error messages, API responses) —
  say "Study not found", not "StudyModel not found".
- **Service**: `<Noun>Service` (`StudyService`, `JobService`), except `AudienceEngine`
  (matches the HLD's own "Audience Engine" component name — same exception will apply to
  `StimulusEngine`/`SimulationEngine`/`AnalyticsEngine`/`ValidationEngine`/`InsightEngine`
  when those are built).
- **UseCase**: `<Noun>UseCase` exposing named lifecycle methods (`StudyUseCase.create/
  get/list_studies/update/delete`), matching the reference's `StudyCreditUseCase` style —
  not `<Verb><Noun>UseCase` per-call classes, since every resource here has several
  related operations.
- **Router**: variable named `<resource>_router_v1` (`studies_router_v1`, not bare
  `router`), registered in `app/api/v1/router.py`. One router per resource file — routes
  that used to need a second "flat" router (tasks, simulations) don't anymore, since paths
  come from `app/common/routes.py`'s `<Resource>Routes` constants instead of an
  `APIRouter(prefix=...)`, so a router file can mix path shapes freely.

- **Router**: parses/validates the request (Pydantic schema from `app/domain/schemas/`),
  builds a UseCase with plain arguments, calls it, returns the result. No business logic,
  no direct Service calls, no direct DB/HTTP access.
- **UseCase**: a plain class, constructed with `session`, exposing `execute()` or named
  methods (e.g. `StudyUseCase.create/get/list_studies/update/delete`,
  `SimulationUseCase.create_run/get_run/cancel_run/get_progress`). This is the **only**
  layer allowed to call more than one Service — e.g. `AudienceUseCase.generate_population`
  composes `StudyService` (ownership), `AudienceEngine` (pure stats), and
  `AudienceService` (persistence). Returns plain ORM objects/dicts, never an HTTP
  response.
- **Service**: owns exactly one table-group or one external system (Supabase Storage,
  the Figma API, the Postgres job table) and **never calls another Service class**. A
  Service *may* check ownership of its own entities (e.g. `StudyService.get_owned` joins
  `projects`, since a Study's owner is only reachable through its Project) and *may* make
  its own external calls (`StimulusService` calls `app/core/storage.py`,
  `FigmaOAuthService` calls the Figma API directly) — that's still one system, not
  cross-service composition.
- **Agent**: anything that calls a model — attention/action selection, screen analysis,
  insight synthesis — is a Pydantic AI `Agent` (single-shot structured output) or the
  LangGraph graph running the Simulation Engine's stateful loop
  (`planning/07-simulation-engine.md`), behind the LLD's
  `VisionProvider`/`ParticipantModel`/`InsightProvider` `Protocol`. Composed from a UseCase
  like any other Service — never called inline from a Service or Router.
- Simulation runs, stimulus analysis, and insight generation are **jobs**, not
  request-time work (`JobService`, the Postgres job table in
  `planning/03-data-model-and-infra.md`). A route that kicks one off returns 202 and a
  run/job id — it never awaits the job inline.

**Gotcha that already bit this codebase**: never name a UseCase method literally `list`
if any other method in the same class returns `list[Something]` — Python resolves that
bare `list` against the class body namespace at method-definition time, so it shadows the
builtin and `TypeError: 'function' object is not subscriptable` shows up on an unrelated
method. Name it `list_studies`/`list_tasks`/etc. instead.

**Second gotcha that already bit this codebase**: any Model column with `onupdate=` (or
otherwise server-computed after the initial insert, e.g. `updated_at`) needs an explicit
`await self._session.refresh(instance)` after `flush()` in the Service method that
mutates it — see `StudyService.update` and `FigmaOAuthService.save_tokens`. Without it
the attribute is left stale/expired, and serializing it later (e.g. `StudyRead.
model_validate(study)` in a router) raises `MissingGreenlet` because a sync attribute
access tries to trigger an async lazy-load outside a valid context. `flush()` alone is
only safe for columns fetched via INSERT-time `server_default` (Postgres+asyncpg fetches
those back automatically); anything set by `onupdate` on an UPDATE needs the explicit
refresh.

## 3. Auth — one dependency, don't hand-roll extraction

Every router except the health check and the Figma OAuth routes depends on
`get_current_user` (`planning/01-auth.md`) — a cached-JWKS Supabase JWT verification, not
a hand-written decode. It calls `AuthService` directly (no UseCase) because it's an
auth/context *dependency*, resolved before request handling even reaches a route —
same as the auth-dependency layer sitting above UseCases in the general pattern. Ownership
checks (`project.owner_id == current_user.id`) happen in `StudyService`, called from
whichever UseCase needs it — never duplicated per router. Figma OAuth
(`FigmaOAuthUseCase`/`FigmaOAuthService`) is a **separate** linked-provider flow for
importing a prototype file — it is not the sign-in mechanism, and Supabase Auth owns
sign-in; don't conflate the two when touching either.

## 4. Never let a model self-report what it can't back up

This is the one rule with no exceptions, straight from `01-PRD-Synthetic-Koala.md` §7 and
`04-Evaluation-Spec-Synthetic-Koala.md`:

- Heatmaps, click maps, and paths are rendered from stored `observations` — never
  generated by a model from a screenshot (`planning/09-analytics-engine.md`).
- An insight's `evidence_strength` is computed in code from validated
  `metrics`/`validation_results` rows *after* the model's output passes Insight
  Validation — never taken from the model's own confidence field
  (`planning/11-insight-engine.md`).
- The Validation Engine reports `{"status": "no_benchmark"}` when `human_benchmarks` is
  absent for a study — never fabricates an agreement number to fill the gap
  (`planning/10-validation-engine.md`, already implemented this way in
  `ResultsUseCase.get_validation`).

If a change would make any of these three guarantees looser "just for this feature,"
stop and flag it instead of implementing it.

## 5. Attention/action selection must stay stochastic

Per `planning/07-simulation-engine.md`: `select_attention`/`select_action` return a
**distribution over candidates**, and the calling LangGraph node samples from it using
the participant's own seeded RNG — not the model's sampling temperature. Don't collapse
this to "just take the top candidate" even if it looks like it'd simplify the code:
population diversity depends on the distribution being real, and reproducibility (same
participant + seed → same result, a PRD §7 requirement) depends on the sampling step
being ours, not the model's. `AudienceEngine.sample_participants` already follows this
shape (seeded `random.Random`, not model-driven) — match it.

## 6. Tests

- `pytest` + `httpx.AsyncClient` against the FastAPI app, transactional test DB (rollback
  per test) — per `planning/02-api.md`'s testing section. See `tests/test_auth.py` for
  the existing pattern.
- Mock at the UseCase's Service boundary for router/UseCase tests; test Services against
  a real test Supabase Postgres, not a fully mocked DB client — see the smoke-test scripts
  run during development (full flow through every UseCase against the real DB, with
  explicit cleanup) as the reference for what "really works" means here.
- Override `get_current_user` via `app.dependency_overrides` for router tests
  (`planning/01-auth.md`); keep exactly one real integration test that hits Supabase's
  JWKS endpoint end-to-end.
- Agent/graph tests (once built): mock the Pydantic AI `Agent.run` / LangGraph node calls
  with fixed structured outputs — don't hit a real model in unit tests.

## 7. Lint & commit

`uv run ruff check .` and `uv run black .` before considering a change done (see
`CLAUDE.md` "Commands"). Alembic-generated migrations are exempted from line-length
(`pyproject.toml`'s per-file-ignores) — don't hand-wrap those, they get regenerated.
