import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from app.workers import runner as runner_module


class _FakeJob:
    def __init__(self, job_type: str, attempts: int, payload: dict):
        self.id = uuid.uuid4()
        self.job_type = job_type
        self.attempts = attempts
        self.payload = payload
        self.status = "RUNNING"
        self.locked_at = None


class _FakeSession:
    def __init__(self, job: _FakeJob) -> None:
        self._job = job
        self.rollback_calls = 0

    async def get(self, model, job_id):
        return self._job

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        self.rollback_calls += 1


@asynccontextmanager
async def _session_cm(session):
    yield session


async def test_permanent_failure_hook_fires_only_on_the_final_attempt(monkeypatch):
    """Closes the gap a stuck-forever PENDING participant_run would otherwise
    leave (planning/06-study-orchestrator.md item 4): once a job exhausts its
    retries, its ON_PERMANENT_FAILURE hook must run exactly once."""
    job = _FakeJob(
        "simulate_participant", attempts=runner_module.MAX_ATTEMPTS - 1, payload={"x": 1}
    )
    fake_session = _FakeSession(job)
    monkeypatch.setattr(runner_module, "async_session_factory", lambda: _session_cm(fake_session))

    failing_handler = AsyncMock(side_effect=RuntimeError("boom"))
    permanent_failure_hook = AsyncMock()
    monkeypatch.setattr(runner_module, "HANDLERS", {"simulate_participant": failing_handler})
    monkeypatch.setattr(
        runner_module, "ON_PERMANENT_FAILURE", {"simulate_participant": permanent_failure_hook}
    )

    await runner_module._process_job(job.id)

    assert job.status == "FAILED"
    permanent_failure_hook.assert_awaited_once_with(fake_session, job.payload)
    assert fake_session.rollback_calls == 1


async def test_permanent_failure_hook_does_not_fire_before_the_final_attempt(monkeypatch):
    job = _FakeJob("simulate_participant", attempts=0, payload={"x": 1})
    fake_session = _FakeSession(job)
    monkeypatch.setattr(runner_module, "async_session_factory", lambda: _session_cm(fake_session))

    failing_handler = AsyncMock(side_effect=RuntimeError("boom"))
    permanent_failure_hook = AsyncMock()
    monkeypatch.setattr(runner_module, "HANDLERS", {"simulate_participant": failing_handler})
    monkeypatch.setattr(
        runner_module, "ON_PERMANENT_FAILURE", {"simulate_participant": permanent_failure_hook}
    )

    await runner_module._process_job(job.id)

    assert job.status == "PENDING"
    permanent_failure_hook.assert_not_awaited()


async def test_a_permanent_failure_hook_exception_does_not_prevent_the_job_from_being_marked_failed(
    monkeypatch,
):
    job = _FakeJob("simulate_participant", attempts=runner_module.MAX_ATTEMPTS - 1, payload={})
    fake_session = _FakeSession(job)
    monkeypatch.setattr(runner_module, "async_session_factory", lambda: _session_cm(fake_session))

    monkeypatch.setattr(
        runner_module,
        "HANDLERS",
        {"simulate_participant": AsyncMock(side_effect=RuntimeError("boom"))},
    )
    monkeypatch.setattr(
        runner_module,
        "ON_PERMANENT_FAILURE",
        {"simulate_participant": AsyncMock(side_effect=RuntimeError("cleanup also broke"))},
    )

    await runner_module._process_job(job.id)

    assert job.status == "FAILED"
