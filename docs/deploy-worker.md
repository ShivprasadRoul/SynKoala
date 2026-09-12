# Deploying the job-queue worker

The job-queue worker (`app/workers/runner.py`) runs as its own Cloud Run service,
`synkoala-worker`, separate from the API (`synkoala-backend`) — same project
(`promptwars-503421`), same region (`us-central1`), same Docker image, different container
command.

## Why a second service, not a background thread in the API

Request volume and job-processing load scale independently, and a stuck/slow job
shouldn't affect the API's own autoscaling or restart behavior. Splitting them is also
what `planning/00-overview.md`'s "modular monolith + background workers" deployment shape
already called for — this just makes it real on Cloud Run instead of only running locally.

## Why it needs an HTTP wrapper at all

`app/workers/runner.py`'s `run_forever()` is a bare `asyncio.gather` of polling loops —
no HTTP server, nothing listening on a port. Cloud Run requires every service's container
to listen on `$PORT` and pass the platform's own startup/liveness checks, so
`app/workers/service.py` wraps it: a one-route FastAPI app (`/health`) that kicks off
`run_forever()` as a background `asyncio.Task` on startup and otherwise does nothing. No
application logic lives there — it's deploy-time plumbing only, and the Dockerfile's own
`CMD` (used by the API) is untouched; the worker service overrides the container command
at deploy time instead.

## Deploying / redeploying

Same Dockerfile, same `--source .` build as the API — only the command/args, scaling, and
env/secrets differ:

```bash
gcloud run deploy synkoala-worker \
  --source . \
  --region us-central1 \
  --project promptwars-503421 \
  --command python \
  --args="-m,app.workers.service" \
  --port 8080 \
  --no-allow-unauthenticated \
  --no-cpu-throttling \
  --min-instances 1 \
  --max-instances 1 \
  --cpu 1 \
  --memory 512Mi \
  --set-env-vars "SUPABASE_URL=<value>,FIGMA_CLIENT_ID=<value>,FIGMA_REDIRECT_URI=<value>" \
  --set-secrets "DATABASE_URL=DATABASE_URL:latest,SUPABASE_SERVICE_ROLE_KEY=SUPABASE_SERVICE_ROLE_KEY:latest,OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest,FIGMA_CLIENT_SECRET=FIGMA_CLIENT_SECRET:latest,FIGMA_TOKEN_ENCRYPTION_KEY=FIGMA_TOKEN_ENCRYPTION_KEY:latest"
```

Notes on the non-default flags:

- **`--no-cpu-throttling` + `--min-instances 1`**: Cloud Run throttles a container's CPU
  to near-zero between incoming requests by default, and scales to zero when idle — both
  would starve or kill a background polling loop that never receives HTTP traffic. These
  two flags keep exactly one instance always running with full CPU.
- **`--max-instances 1`**: the job queue's `SELECT ... FOR UPDATE SKIP LOCKED` claim
  (`app/workers/runner.py:_claim_one_job`) is safe under multiple concurrent workers — a
  second instance wouldn't cause double-processing — but one instance already runs
  `NUM_WORKERS=5` concurrent polling loops internally, so there's no reason to pay for a
  second Cloud Run instance right now.
- **`--no-allow-unauthenticated`**: nothing needs to call this service's HTTP surface from
  outside — `/health` only exists for Cloud Run's own platform-level probes, which don't
  go through the public IAM-gated ingress path.
- Same secrets as the API service (check its current config with
  `gcloud run services describe synkoala-backend --region us-central1 --format="yaml(spec.template.spec.containers[0].env)"`
  if these ever drift) — the worker's job handlers touch the same DB
  (`DATABASE_URL`), call the vision model (`OPENROUTER_API_KEY`, `analyze_stimulus`), and
  decrypt/refresh Figma OAuth tokens (`FIGMA_*`, `import_figma_prototype`).

## Verifying it's actually processing jobs

The service has no public endpoint worth curling. Check logs instead
(see `docs/gcp-logs.md`, same commands with `synkoala-worker` as the service name) — a
healthy startup logs exactly:

```
worker started, 5 concurrent workers, polling every 2.0s
```

To confirm it's really claiming rows from the real queue (not just alive), insert a
throwaway job with an unregistered `job_type` (e.g. `psql`/a short script inserting a
`JobModel(job_type="smoke_test", payload={}, status="PENDING")`) and watch it flip to
`FAILED` after 3 attempts within ~10 seconds — that exercises the exact claim →
process → retry path with no side effects on real study data. Delete the row afterward.

## What still doesn't run here

Nothing — this was the last piece of `planning/00-overview.md`'s deployment shape not yet
running in the cloud. `analyze_stimulus`, `simulate_participant`, `import_figma_prototype`,
`aggregate_run`, and `validate_run` jobs all now get picked up by this service instead of
requiring a local `uv run python -m app.workers.runner` terminal.
