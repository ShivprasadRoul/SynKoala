import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserModel


class AuthService:
    """planning/01-auth.md "User sync" (upsert-on-first-request). Called directly
    from the `get_current_user` dependency (app/core/auth.py) — auth/context
    dependencies sit above the UseCase layer, same as the reference pattern's
    `add_user_context`, not routed through one."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_user(self, user_id: str, email: str | None) -> UserModel:
        uid = uuid.UUID(user_id)
        user = await self._session.get(UserModel, uid)
        if user is not None:
            return user
        user = UserModel(id=uid, email=email or f"{user_id}@no-email.supabase")
        self._session.add(user)
        await self._session.commit()
        return user
