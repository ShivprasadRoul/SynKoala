import base64
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.settings import settings
from app.db.models import FigmaConnectionModel

FIGMA_AUTHORIZE_URL = "https://www.figma.com/oauth"
# https://developers.figma.com/docs/rest-api/oauth-apps/ — both the token exchange
# and refresh endpoints require HTTP Basic auth with (client_id, client_secret),
# not those as body params (an earlier version of this file sent them as body
# params against the older www.figma.com/api/oauth/token host; verified current
# against Figma's own docs while building the Stimulus Engine's Figma import).
FIGMA_TOKEN_URL = "https://api.figma.com/v1/oauth/token"
FIGMA_REFRESH_URL = "https://api.figma.com/v1/oauth/refresh"
# The one scope the Stimulus Engine's Figma import needs (planning/05):
# GET /v1/files/:key and GET /v1/images/:key both read under file_content:read.
FIGMA_OAUTH_SCOPE = "file_content:read"
# Refresh this far ahead of actual expiry, not exactly at it — a long-running
# import job shouldn't have its token expire mid-request.
TOKEN_REFRESH_BUFFER = timedelta(minutes=5)


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
            "scope": FIGMA_OAUTH_SCOPE,
            "state": self.encode_state(user_id),
            "response_type": "code",
        }
        return f"{FIGMA_AUTHORIZE_URL}?{urlencode(params)}"

    def _basic_auth_header(self) -> dict[str, str]:
        credentials = f"{settings.figma_client_id}:{settings.figma_client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    async def exchange_code(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                FIGMA_TOKEN_URL,
                headers=self._basic_auth_header(),
                data={
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

    async def refresh_access_token(self, connection: FigmaConnectionModel) -> FigmaConnectionModel:
        """The refresh response only carries a new `access_token`/`expires_in`
        (per Figma's docs) — the original `refresh_token` stays valid and is
        reused, not replaced."""
        refresh_token = crypto.decrypt(connection.refresh_token_encrypted)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                FIGMA_REFRESH_URL,
                headers=self._basic_auth_header(),
                data={"refresh_token": refresh_token},
            )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Figma token refresh failed"
            )
        payload = response.json()
        connection.access_token_encrypted = crypto.encrypt(payload["access_token"])
        connection.expires_at = datetime.now(UTC) + timedelta(seconds=payload["expires_in"])
        await self._session.flush()
        await self._session.refresh(connection)
        return connection

    async def get_connection(self, user_id: uuid.UUID) -> FigmaConnectionModel | None:
        return await self._session.scalar(
            select(FigmaConnectionModel).where(FigmaConnectionModel.user_id == user_id)
        )

    async def get_valid_access_token(self, user_id: uuid.UUID) -> str:
        """Used by the Figma-import job (planning/05-stimulus-engine.md), which
        has no HTTP request/session cookie to fall back on — this is the only
        way it can get a usable token for that user's Figma account."""
        connection = await self.get_connection(user_id)
        if connection is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account hasn't connected Figma yet",
            )
        if datetime.now(UTC) + TOKEN_REFRESH_BUFFER >= connection.expires_at:
            connection = await self.refresh_access_token(connection)
        return crypto.decrypt(connection.access_token_encrypted)

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
