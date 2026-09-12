import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import LifecycleError, NotFoundError
from app.db.models import ProjectModel, StudyModel, UserModel
from app.domain.schemas.study import STUDY_STATUS_TRANSITIONS


class StudyService:
    """Owns the `studies` table (plus the `projects` join needed for ownership,
    since a StudyModel's owner is only reachable through its ProjectModel) — no other
    Service. Cross-service orchestration (ProjectModel provisioning, etc.) lives in
    app/usecases/studies.py:StudyUseCase."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        project_id: uuid.UUID,
        name: str,
        objective: str | None,
        population_size: int | None = None,
    ) -> StudyModel:
        study = StudyModel(
            project_id=project_id,
            name=name,
            objective=objective,
            status="DRAFT",
            population_size=population_size,
        )
        self._session.add(study)
        await self._session.flush()
        return study

    async def list_owned(self, user: UserModel) -> list[StudyModel]:
        result = await self._session.scalars(
            select(StudyModel)
            .join(ProjectModel)
            .where(ProjectModel.owner_id == user.id, StudyModel.deleted_at.is_(None))
            .order_by(StudyModel.created_at)
        )
        return list(result)

    async def get_owned(self, user: UserModel, study_id: uuid.UUID) -> StudyModel:
        study = await self._session.scalar(
            select(StudyModel)
            .join(ProjectModel)
            .where(
                StudyModel.id == study_id,
                ProjectModel.owner_id == user.id,
                StudyModel.deleted_at.is_(None),
            )
        )
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        return study

    async def get_by_id(self, study_id: uuid.UUID) -> StudyModel:
        """No ownership check — for job handlers (planning/11's Insight
        Engine) that already only ever see a `study_id` reached through a
        `simulation_runs` row, not a request from a specific user."""
        study = await self._session.get(StudyModel, study_id)
        if study is None:
            raise NotFoundError(f"Study {study_id} not found")
        return study

    async def update(
        self,
        study: StudyModel,
        *,
        name: str | None = None,
        objective: str | None = None,
        status: str | None = None,
        population_size: int | None = None,
    ) -> StudyModel:
        if status is not None and status != study.status:
            allowed = STUDY_STATUS_TRANSITIONS.get(study.status, ())
            if status not in allowed:
                raise LifecycleError(f"Cannot transition study from {study.status} to {status}")
            study.status = status
        if name is not None:
            study.name = name
        if objective is not None:
            study.objective = objective
        if population_size is not None:
            study.population_size = population_size
        await self._session.flush()
        # `updated_at` is server-computed (onupdate=func.now()) — flush() alone
        # leaves it stale/expired, which blows up with MissingGreenlet if this
        # object gets serialized later outside an async-safe context. Refresh
        # now, while we're still inside the session.
        await self._session.refresh(study)
        return study

    async def delete(self, study: StudyModel) -> None:
        study.deleted_at = datetime.now(UTC)
        await self._session.flush()
