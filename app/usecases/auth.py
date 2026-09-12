from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FigmaConnectionModel, UserModel
from app.services.figma_oauth_service import FigmaOAuthService


class FigmaOAuthUseCase:
    """Orchestration for the Figma account-linking flow (planning/01-auth.md).
    A single Service (FigmaOAuthService) covers this resource, but the sequencing
    — validate config, then decode state / exchange code / persist, in that order
    — is exactly the "decides what happens and in what order" a UseCase owns."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._figma = FigmaOAuthService(session)

    def get_authorize_url(self, user: UserModel) -> str:
        self._figma.require_configured()
        return self._figma.build_authorize_url(user.id)

    async def handle_callback(self, code: str, state: str) -> FigmaConnectionModel:
        self._figma.require_configured()
        user_id = self._figma.decode_state(state)
        token_payload = await self._figma.exchange_code(code)
        expires_at = datetime.now(UTC) + timedelta(seconds=token_payload["expires_in"])
        connection = await self._figma.save_tokens(
            user_id=user_id,
            access_token=token_payload["access_token"],
            refresh_token=token_payload["refresh_token"],
            expires_at=expires_at,
        )
        await self._session.commit()
        return connection
