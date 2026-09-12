"""Cloud Run entrypoint for the job-queue worker (`app/workers/runner.py`).

Cloud Run services must listen on $PORT and respond to the platform's own
health checks — a bare `asyncio.run(run_forever())` with no HTTP server
doesn't satisfy that, so this wraps the same `run_forever()` loop in a
one-route FastAPI app whose only job is to give Cloud Run something to poll
while the real work happens in a background task in the same process. This
is deploy-time plumbing only: no request ever reaches `/health` except
Cloud Run's own probe, and no application code lives here.

Deployed as a second Cloud Run service (`synkoala-worker`, see
docs/deploy-worker.md) from the exact same image as the API — the Dockerfile
is unchanged; only the container command differs at deploy time
(`python -m app.workers.service` instead of the API's `uvicorn` CMD).
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.workers.runner import run_forever

_worker_task: asyncio.Task | None = None


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _worker_task
    _worker_task = asyncio.create_task(run_forever())
    yield


app = FastAPI(lifespan=_lifespan)


@app.get("/health")
async def health() -> dict:
    alive = _worker_task is not None and not _worker_task.done()
    return {"status": "ok" if alive else "worker_stopped"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
