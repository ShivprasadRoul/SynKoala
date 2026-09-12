from fastapi import APIRouter, Depends

from app.common.routes import UsersRoutes
from app.core.auth import get_current_user
from app.db.models import UserModel
from app.domain.schemas.user import UserRead

users_router_v1 = APIRouter(tags=UsersRoutes.TAGS)


@users_router_v1.get(UsersRoutes.ME, response_model=UserRead)
async def read_current_user(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    return current_user
