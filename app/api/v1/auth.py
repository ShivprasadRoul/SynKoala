from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.routes import AuthRoutes
from app.core.auth import get_current_user
from app.db.models import UserModel
from app.db.session import get_session
from app.usecases.auth import FigmaOAuthUseCase

auth_router_v1 = APIRouter(tags=AuthRoutes.TAGS)


@auth_router_v1.get(AuthRoutes.FIGMA_AUTHORIZE)
async def figma_authorize(
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Account-linking flow — the user is already signed in via Supabase Auth;
    this links a Figma account so the Stimulus Engine can import prototypes later."""
    use_case = FigmaOAuthUseCase(session)
    return RedirectResponse(use_case.get_authorize_url(current_user))


@auth_router_v1.get(AuthRoutes.FIGMA_CALLBACK)
async def figma_callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    use_case = FigmaOAuthUseCase(session)
    await use_case.handle_callback(code, state)
    return {"status": "connected"}
