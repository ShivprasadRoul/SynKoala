import uuid
from datetime import datetime
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.settings import settings
from app.db.models import FigmaConnectionModel

FIGMA_AUTHORIZE_URL = "https://www.figma.com/oauth"
FIGMA_TOKEN_URL = "https://www.figma.com/api/oauth/token"


class FigmaOAuthService:
    """Owns the `figma_connections` table and the Figma API calls (this Service's
    own external call, like Stripe/S3 in the reference pattern) — no ownership
    check (that's handled by the router's auth dependency, since authorize/
    callback don't need StudyModel-level ownership). Composed by
    app/usecases/auth.py:FigmaOAuthUseCase."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def require_configured(self) -> None:
        configured = (
            settings.figma_client_id
            and settings.figma_client_secret
            and settings.figma_redirect_uri
        )
        if not configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Figma OAuth is not configured (FIGMA_CLIENT_ID/SECRET/REDIRECT_URI)",
            )

    @staticmethod
    def encode_state(user_id: uuid.UUID) -> str:
        """Ties the Figma OAuth callback back to the user who started it."""
        return crypto.encrypt(str(user_id))

    @staticmethod
    def decode_state(state: str) -> uuid.UUID:
        try:
            return uuid.UUID(crypto.decrypt(state))
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state"
            ) from exc

    def build_authorize_url(self, user_id: uuid.UUID) -> str:
        params = {
            "client_id": settings.figma_client_id,
            "redirect_uri": settings.figma_redirect_uri,
            "scope": "file_read",
            "state": self.encode_state(user_id),
            "response_type": "code",
        }
        return f"{FIGMA_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                FIGMA_TOKEN_URL,
                data={
                    "client_id": settings.figma_client_id,
                    "client_secret": settings.figma_client_secret,
                    "redirect_uri": settings.figma_redirect_uri,
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Figma token exchange failed"
            )
        return response.json()

    async def save_tokens(
        self,
        user_id: uuid.UUID,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> FigmaConnectionModel:
        existing = await self._session.scalar(
            select(FigmaConnectionModel).where(FigmaConnectionModel.user_id == user_id)
        )
        encrypted_access = crypto.encrypt(access_token)
        encrypted_refresh = crypto.encrypt(refresh_token)
        if existing is not None:
            existing.access_token_encrypted = encrypted_access
            existing.refresh_token_encrypted = encrypted_refresh
            existing.expires_at = expires_at
        else:
            existing = FigmaConnectionModel(
                user_id=user_id,
                access_token_encrypted=encrypted_access,
                refresh_token_encrypted=encrypted_refresh,
                expires_at=expires_at,
            )
            self._session.add(existing)
        await self._session.flush()
        # Same onupdate-refresh requirement as StudyService.update — see that
        # method's comment. Only needed on the re-link path (existing row), but
        # cheap enough to always do.
        await self._session.refresh(existing)
        return existing
