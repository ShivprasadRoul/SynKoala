import uuid

import pytest

from app.workers import runner as runner_module


class _StopLoop(Exception):
    """Lets a test end `_worker_loop`'s `while True:` deliberately, from
    outside its `except Exception` (raised by `_claim_one_job`, not
    `_process_job`), instead of hanging forever."""


async def test_worker_loop_survives_an_exception_that_escapes_process_job(monkeypatch):
    """The bug this closes: a handler failure that leaves its session in a
    rolled-back state used to raise `PendingRollbackError` out of
    `_process_job`'s own `except` block (see `runner.py`'s fix alongside this
    test) — and with nothing catching that in `_worker_loop`, it propagated
    through `run_forever`'s `asyncio.gather`, killing every other worker too.
    This asserts the loop now survives *any* exception from `_process_job`,
    not just the one specific case that first surfaced it."""
    calls = {"n": 0}

    async def fake_claim_one_job():
        calls["n"] += 1
        if calls["n"] == 1:
            return uuid.uuid4()
        raise _StopLoop

    async def fake_process_job(_job_id):
        raise RuntimeError("simulates a bug that escapes _process_job's own except block")

    monkeypatch.setattr(runner_module, "_claim_one_job", fake_claim_one_job)
    monkeypatch.setattr(runner_module, "_process_job", fake_process_job)

    with pytest.raises(_StopLoop):
        await runner_module._worker_loop(0)

    assert calls["n"] == 2  # proves the loop reached a second iteration
