# SynKoala

Synthetic-audience platform for UX testing — researchers define an audience and a critical user task, upload a UI/prototype, and the system simulates a population of audience-conditioned synthetic participants attempting the task. Results are aggregated into attention heatmaps, interaction paths, task-completion metrics, and evidence-backed UX insights.

## Stack

FastAPI + Postgres (Supabase) + a Postgres-backed job queue with worker loop and `LISTEN`/`NOTIFY` realtime.

## Commands

Uses [`uv`](https://docs.astral.sh/uv/):

```
uv sync --group dev                      # install dependencies
uv run uvicorn app.main:app --reload     # run the API locally (needs .env populated)
uv run python -m app.workers.runner      # run the job-queue worker (needs .env populated)
uv run pytest tests/                     # run tests
uv run ruff check .                      # lint
uv run black .                           # format
uv run alembic upgrade head              # apply migrations (needs a real DATABASE_URL)
```

See `.env.example` for required environment variables. Setting up Figma import specifically (creating the OAuth app, getting `FIGMA_CLIENT_ID`/`FIGMA_CLIENT_SECRET`) is covered in [`docs/figma-setup.md`](docs/figma-setup.md).
