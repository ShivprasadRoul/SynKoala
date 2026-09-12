import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudyModel, UserModel
from app.services.project_service import ProjectService
from app.services.study_service import StudyService


class StudyUseCase:
    """Orchestration for the Studies resource (planning/02-api.md). Composes
    ProjectService + StudyService — neither Service calls the other."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._studies = StudyService(session)
        self._projects = ProjectService(session)

    async def create(self, user: UserModel, name: str, objective: str | None) -> StudyModel:
        project = await self._projects.get_or_create_default(user.id)
        study = await self._studies.create(project.id, name, objective)
        await self._session.commit()
        return study

    async def get(self, user: UserModel, study_id: uuid.UUID) -> StudyModel:
        return await self._studies.get_owned(user, study_id)

    async def list_studies(self, user: UserModel) -> list[StudyModel]:
        return await self._studies.list_owned(user)

    async def update(
        self,
        user: UserModel,
        study_id: uuid.UUID,
        *,
        name: str | None = None,
        objective: str | None = None,
        status: str | None = None,
    ) -> StudyModel:
        study = await self._studies.get_owned(user, study_id)
        study = await self._studies.update(study, name=name, objective=objective, status=status)
        await self._session.commit()
        return study

    async def delete(self, user: UserModel, study_id: uuid.UUID) -> None:
        study = await self._studies.get_owned(user, study_id)
        await self._studies.delete(study)
        await self._session.commit()
