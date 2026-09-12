from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobModel


class JobService:
    """Owns the `jobs` table only — the Postgres-backed queue from
    planning/03-data-model-and-infra.md. No other Service."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, job_type: str, payload: dict) -> JobModel:
        job = JobModel(job_type=job_type, payload=payload)
        self._session.add(job)
        await self._session.flush()
        return job

    async def cancel_pending(self, job_type: str, payload_key: str, payload_value: str) -> None:
        """Marks matching PENDING jobs CANCELLED — used when a simulation run is
        cancelled, so a not-yet-built worker skips them (planning/06)."""
        await self._session.execute(
            update(JobModel)
            .where(
                JobModel.job_type == job_type,
                JobModel.payload[payload_key].astext == payload_value,
                JobModel.status == "PENDING",
            )
            .values(status="CANCELLED")
        )
