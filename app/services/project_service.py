import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProjectModel


class ProjectService:
    """Owns the `projects` table only — no other Service or ownership logic. The
    PRD's Core UserModel Flow has no "create project" step, so callers (StudyUseCase)
    get a transparent default project rather than exposing project management."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_default(self, owner_id: uuid.UUID) -> ProjectModel:
        project = await self._session.scalar(
            select(ProjectModel)
            .where(ProjectModel.owner_id == owner_id)
            .order_by(ProjectModel.created_at)
            .limit(1)
        )
        if project is not None:
            return project
        project = ProjectModel(owner_id=owner_id, name="Default")
        self._session.add(project)
        await self._session.flush()
        return project
