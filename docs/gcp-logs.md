# Viewing backend logs on Cloud Run

The FastAPI backend runs as the Cloud Run service `synkoala-backend`, project
`promptwars-503421`, region `us-central1`. This covers where to find its logs — both
request/response logs and anything the app itself prints (`print`, `logging`, unhandled
tracebacks) — via the GCP Console and via `gcloud`.

## 1. Console — quickest path

1. Go to [console.cloud.google.com/run](https://console.cloud.google.com/run) and make
   sure the project selector (top bar) is set to **promptwars-503421**.
2. Click the **synkoala-backend** service.
3. Open the **LOGS** tab. This shows every log line for the service — Cloud Run's own
   request logs (method, path, status, latency) interleaved with anything the container
   wrote to stdout/stderr.
4. Use the search bar above the log list to filter, e.g. `severity>=ERROR`, or a text
   search like `Traceback` to jump straight to unhandled exceptions.

Direct link (adjust if the project/region ever change):
[console.cloud.google.com/run/detail/us-central1/synkoala-backend/logs?project=promptwars-503421](https://console.cloud.google.com/run/detail/us-central1/synkoala-backend/logs?project=promptwars-503421)

For more powerful querying (time range picker, saved queries, correlating with other
services), open the same logs in **Logs Explorer** instead — there's a "Run query in Logs
Explorer" link at the top of the LOGS tab, or go directly to
[console.cloud.google.com/logs/query](https://console.cloud.google.com/logs/query) and
filter with:

```
resource.type="cloud_run_revision"
resource.labels.service_name="synkoala-backend"
```

Add `severity>=ERROR` on its own line to see only errors, or
`textPayload:"some string"` / `jsonPayload.message:"some string"` to search log content.

## 2. `gcloud` CLI

Read the most recent entries:

```bash
gcloud run services logs read synkoala-backend --region us-central1 --project promptwars-503421 --limit 100
```

Only errors:

```bash
gcloud run services logs read synkoala-backend --region us-central1 --project promptwars-503421 --log-filter="severity>=ERROR"
```

To tail logs live while reproducing an issue, `gcloud run services logs tail` needs the
`beta` component, which isn't installed on this machine yet — install it once with
`gcloud components install beta` (asks for confirmation), then:

```bash
gcloud beta run services logs tail synkoala-backend --region us-central1 --project promptwars-503421
```

For the same structured query as the Logs Explorer filter above, but from the terminal:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="synkoala-backend"' \
  --project promptwars-503421 --limit 100 --format json
```

Add `AND severity>=ERROR` inside the quoted filter to narrow to errors only.

## 3. What you'll actually see

- The worker (`uv run python -m app.workers.runner`) is **not** part of this Cloud Run
  service — it's a separate long-running process that, as of this writing, is only ever
  run locally (`CLAUDE.md` "Repository state": Cloud Run only hosts the API). Job
  processing logs (`analyze_stimulus`, `simulate_participant`) won't show up here unless
  the worker is later deployed as its own Cloud Run service or similar — check the local
  terminal it's running in instead.
- A stack trace from an unhandled exception in a request appears as a single multi-line
  log entry; expand it in the Console to see the full traceback rather than just the first
  line.
